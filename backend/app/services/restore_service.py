"""RestoreService — bring a backup zip back to life (audit A6).

The backup side makes one instant; this side is explicit about what that
instant is worth. `restore_backup()` installs the SQLite, screenshots and
logs halves directly, and for Chroma it *verifies the pairing first* and
rebuilds rather than trusts when it cannot:

1. the zip carries no `chroma/` (a pre-A6 backup) — there is nothing to
   restore, so the next knowledge pass re-embeds everything;
2. the restored vector counts do not match the manifest written at backup
   time — the copy is torn, not merely old;
3. `verify_pairing()` finds a row whose embedding flag promises a vector the
   store does not have — the exact state that makes an index look healthy
   and absorb no re-embedding.

Ruling: a rebuild is the honest outcome. It costs Ollama time; the
alternative is a knowledge index that answers from a subset and never
notices.

Run with Sentinel stopped — restoring under a live server would replace the
SQLite file beneath it. `_assert_not_running()` refuses rather than hoping.
"""

import datetime
import json
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger
from app.services.backup_service import MANIFEST_NAME, data_dir
from app.services.knowledge_integrity import PairingReport, verify_pairing

logger = get_logger(__name__)

# Vector outcomes. `restored` = the pairing verified, so the restored store
# is used as-is. `rebuilt` = it was not installed; the index stays empty
# until a knowledge pass re-embeds it.
RESTORED = "restored"
REBUILT = "rebuilt"


class RestoreError(Exception):
    """A restore that refused to run. Nothing was installed."""


@dataclass
class RestoreReport:
    """What a restore did, and why the vectors ended up the way they did."""

    path: str
    files: int = 0
    vectors: str = REBUILT
    vector_reason: str | None = None
    restored: list[str] = field(default_factory=list)
    moved_aside: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [f"Restored {self.path} ({self.files} files)"]
        lines.append(
            "vectors: "
            + (
                "restored from the backup"
                if self.vectors == RESTORED
                else f"will be rebuilt — {self.vector_reason}"
            )
        )
        if self.moved_aside:
            lines.append("previous state kept at: " + ", ".join(self.moved_aside))
        return "\n".join(lines)


def _assert_not_running() -> None:
    """Refuse while a Sentinel server is up.

    Restore replaces the SQLite file, not the connection: a live server keeps
    writing through a handle whose file has been swapped underneath it, and
    the next checkpoint corrupts the very state being restored. SQLite alone
    cannot tell us this — an idle WAL reader holds no lock — so the probe
    asks the loopback API directly, which is exactly the population that has
    no business being restored over.

    The probe is deliberately narrow: something listening on the configured
    port is enough to refuse. Proceeding would be the riskier guess.
    """
    import httpx

    url = f"http://127.0.0.1:{settings.port}/api/v1/system/health"
    try:
        response = httpx.get(url, timeout=2.0)
    except Exception:  # noqa: BLE001 — nothing listening; safe to restore
        return
    if response.status_code < 600:
        raise RestoreError(
            f"Sentinel appears to be running at {url} (HTTP "
            f"{response.status_code}). Stop the server before restoring."
        )


def _manifest_of(zf: zipfile.ZipFile) -> dict | None:
    if MANIFEST_NAME not in zf.namelist():
        return None
    try:
        return json.loads(zf.read(MANIFEST_NAME).decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        logger.warning("Backup manifest unreadable (%s)", exc)
        return None


def _move_aside(target: Path, stamp: str) -> str | None:
    """Rename a live directory out of the way instead of deleting it — the
    user may still want what was there before the restore.

    A failure here is not cosmetic: the install that follows would write into
    a directory something else still holds open, so it raises `RestoreError`
    and nothing is installed at all.
    """
    if not target.exists():
        return None
    aside = target.with_name(f"{target.name}.pre-restore-{stamp}")
    try:
        shutil.move(str(target), str(aside))
    except OSError as exc:
        raise RestoreError(
            f"Could not set aside {target} ({exc}) — another process is "
            "holding it. Stop Sentinel, then restore."
        ) from exc
    return str(aside)


def restore_backup(path: str | Path) -> RestoreReport:
    """Install a backup zip into `data/`, rebuilding vectors if they cannot
    be verified. Raises `RestoreError` before touching anything it cannot
    finish."""
    source = Path(path)
    if not source.is_file():
        raise RestoreError(f"No such backup: {source}")
    if not zipfile.is_zipfile(source):
        raise RestoreError(f"Not a backup zip: {source}")

    with zipfile.ZipFile(source) as zf:
        names = set(zf.namelist())
        if "sqlite/sentinel.db" not in names:
            raise RestoreError(f"{source.name} holds no database to restore")
        manifest = _manifest_of(zf)
        has_chroma = any(name.startswith("chroma/") for name in names)

        _assert_not_running()

        # Stage in the system temp rather than under data/: verifying the
        # Chroma half opens it with a Chroma manager, and on Windows a
        # directory a client has touched can be copied but never renamed or
        # deleted for the life of the process. Keeping it out of data/ means
        # a cleanup that cannot run leaves nothing behind next to the state.
        staging = Path(tempfile.mkdtemp(prefix="sentinel-restore-"))
        try:
            zf.extractall(str(staging))
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise

    try:
        report = _install(staging, manifest, has_chroma, str(source))
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return report


def _install(
    staging: Path, manifest: dict | None, has_chroma: bool, source: str
) -> RestoreReport:
    root = data_dir()
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
    report = RestoreReport(path=source)

    staged_db = staging / "sqlite" / "sentinel.db"
    pairing: PairingReport | None = None
    if has_chroma:
        pairing = verify_pairing(staged_db, staging / "chroma")

    trusted = _vector_decision(manifest, has_chroma, pairing)
    report.vectors, report.vector_reason = trusted

    # SQLite is exact state: the live file is set aside, the backup's file
    # copied in. (The server-stopped guard above is what makes the rename
    # safe against a live connection.)
    staged_db_file = staging / "sqlite" / "sentinel.db"
    target_db = root / "sqlite" / "sentinel.db"
    target_db.parent.mkdir(parents=True, exist_ok=True)
    aside = _move_aside(target_db, stamp)
    if aside:
        report.moved_aside.append(aside)
    shutil.copy2(str(staged_db_file), str(target_db))
    report.restored.append(str(target_db))
    report.files += 1

    # Screenshots and logs are evidence, not state: the backup's files are
    # copied over the live tree rather than replacing it. The restore's own
    # log handle is inside `logs/`, so renaming that directory would refuse
    # against itself.
    for relative in ("screenshots", "logs"):
        staged = staging / relative
        if not staged.is_dir():
            continue
        target = root / relative
        target.mkdir(parents=True, exist_ok=True)
        copied = 0
        for path in sorted(staged.rglob("*")):
            if not path.is_file():
                continue
            dest = target / path.relative_to(staged)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(path), str(dest))
            copied += 1
        report.restored.append(str(target))
        report.files += copied

    # Chroma is installed only when the pairing verified. Otherwise the
    # staged vectors are dropped with the staging dir and the knowledge index
    # starts empty, which is the state a rebuild turns into a correct index.
    # Copied, not moved: the verification above has this store open.
    chroma_target = root / "chroma"
    if trusted[0] == RESTORED:
        aside = _move_aside(chroma_target, stamp)
        if aside:
            report.moved_aside.append(aside)
        shutil.copytree(str(staging / "chroma"), str(chroma_target))
        report.restored.append(str(chroma_target))
        report.files += sum(1 for p in chroma_target.rglob("*") if p.is_file())
    else:
        aside = _move_aside(chroma_target, stamp)
        if aside:
            report.moved_aside.append(aside)
        logger.info("Chroma not installed from %s: %s", source, trusted[1])

    logger.info(
        "Restore finished from %s: %d files, vectors=%s (%s)",
        source,
        report.files,
        report.vectors,
        report.vector_reason,
    )
    return report


def _vector_decision(
    manifest: dict | None, has_chroma: bool, pairing: PairingReport | None
) -> tuple[str, str]:
    """Return `(state, reason)` for the Chroma half.

    Every branch is deterministic: a manifest comparison and a row/id
    comparison, no timing, no heuristic.
    """
    if not has_chroma:
        return REBUILT, "the backup predates A6 and carries no vectors"
    if manifest is None:
        return REBUILT, "the backup has no manifest to verify against"
    if pairing is None:  # unreachable while has_chroma, kept explicit
        return REBUILT, "no pairing check ran"

    expected = manifest.get("chroma_counts") or {}
    if not expected:
        return REBUILT, "the manifest records no vector counts"
    mismatched = {
        name: (expected.get(name), count)
        for name, count in pairing.collection_counts.items()
        if expected.get(name) != count
    }
    if mismatched:
        return (
            REBUILT,
            "vector counts differ from the manifest: "
            + ", ".join(
                f"{name} backup={wanted} got={seen}"
                for name, (wanted, seen) in sorted(mismatched.items())
            ),
        )
    if pairing.unreadable:
        return REBUILT, "unreadable collections: " + ", ".join(pairing.unreadable)
    if pairing.missing:
        return REBUILT, f"{len(pairing.missing)} file(s) have no vectors"
    if pairing.orphans:
        return REBUILT, f"{len(pairing.orphans)} vector(s) have no file row"
    return RESTORED, ""
