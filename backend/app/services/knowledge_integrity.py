"""Knowledge integrity — does the embedding flag match the vectors?

Both halves of Sentinel's knowledge are derived from project files on disk,
so the pairing is checkable rather than assumed: a `projectfile` row whose
`embedding_id` is set promises at least one vector in `file_summaries`, and
every vector in there belongs to a row that still exists.

Deterministic by construction (Rule 3): read the rows, read the ids, compare.
No embedding, no Ollama, no heuristics. Three callers, one rule:

* `verify_pairing(paths)` — restore checks a *staged* store before installing
  it (audit A6),
* `verify_store()` — startup and `/rag/index/status` report on the live
  store, so a hand-restored or a half-finished rebuild is visible instead of
  surfacing later as a 503 (this batch's rebuild verification),
* `reconcile_store()` — the deterministic repair: a flag with no vector is
  cleared so the next index pass re-embeds it, and a vector with no row is
  deleted. Both halves are what a rebuild would produce anyway, so the
  cheaper path is the same outcome.
"""

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PairingReport:
    """Result of checking one database against one vector store."""

    checked_files: int = 0
    checked_vectors: int = 0
    # Rows that promise a vector the store does not have.
    missing: list[str] = field(default_factory=list)
    # Vectors whose file row no longer exists — they would keep answering
    # questions from files that are gone.
    orphans: list[str] = field(default_factory=list)
    # Collections that cannot execute a query at all (A6's torn copy).
    unreadable: list[str] = field(default_factory=list)
    # Vector count per collection at the moment of the check — what a backup
    # manifest is compared against.
    collection_counts: dict[str, int] = field(default_factory=dict)

    @property
    def consistent(self) -> bool:
        return not self.missing and not self.orphans and not self.unreadable

    @property
    def diverged(self) -> bool:
        """True when a repair would change something (a half-finished
        rebuild is not a problem — nothing is claimed that is not there)."""
        return bool(self.missing or self.orphans or self.unreadable)

    def summary(self) -> str:
        if self.consistent:
            return (
                f"knowledge pairing consistent "
                f"({self.checked_files} files, {self.checked_vectors} vectors)"
            )
        parts = []
        if self.missing:
            parts.append(f"{len(self.missing)} file(s) missing vectors")
        if self.orphans:
            parts.append(f"{len(self.orphans)} orphaned vector(s)")
        if self.unreadable:
            parts.append("unreadable collection(s): " + ", ".join(self.unreadable))
        return "; ".join(parts)


@dataclass
class ReconcileReport:
    """What a repair actually changed."""

    cleared_flags: int = 0
    removed_vectors: int = 0
    after: PairingReport | None = None

    def summary(self) -> str:
        if not self.cleared_flags and not self.removed_vectors:
            return "knowledge pairing already consistent — nothing to repair"
        return (
            f"cleared {self.cleared_flags} embedding flag(s) for "
            f"re-embedding; removed {self.removed_vectors} orphaned vector(s)"
        )


def _flagged_rows(
    db_path: Path,
) -> tuple[dict[str, tuple[str, str]], PairingReport | None]:
    """File rows that claim to be embedded: {row id: (path, absolute_path)}.

    The second value is a report describing why the rows could not be read
    at all.
    """
    flagged: dict[str, tuple[str, str]] = {}
    conn = sqlite3.connect(str(db_path))
    try:
        try:
            rows = conn.execute(
                "SELECT id, path, absolute_path FROM projectfile "
                "WHERE embedding_id IS NOT NULL"
            ).fetchall()
        except sqlite3.DatabaseError:
            # Not a readable database (absent table, corrupt header, or a
            # snapshot of something else). Nothing is claimed, and nothing
            # is checkable — say so instead of raising.
            failed = PairingReport(missing=["<projectfile table unreadable>"])
            return {}, failed
        for row_id, path, absolute in rows:
            flagged[row_id] = (path, absolute or "")
    finally:
        conn.close()
    return flagged, None


def _embeddable(absolute_path: str) -> bool:
    """True when there is something to embed.

    `ingest_files` marks a file whose content reads empty (a zero-byte file,
    or one that vanished from disk) as embedded *without* upserting a vector —
    that is deliberate, so the pending-knowledge query does not re-queue the
    project forever. The invariant therefore has to allow a flag with no
    vector for exactly those rows: otherwise every install reports a
    divergence on its empty `__init__.py` files and the warning means
    nothing.
    """
    if not absolute_path:
        return False
    try:
        return Path(absolute_path).stat().st_size > 0
    except OSError:
        return False  # gone or unreadable — nothing was embedded either


def _compare(
    flagged: dict[str, tuple[str, str]],
    project_ids: set[str],
    report: PairingReport,
    manager,
) -> None:
    """The invariant itself: a flag promises a vector, a vector has a row."""
    try:
        vectors = manager.all_rows("file_summaries")
    except Exception:  # noqa: BLE001
        report.unreadable.append("file_summaries")
        return
    vector_projects = {
        str((row.get("metadata") or {}).get("project_id"))
        for row in vectors
        if (row.get("metadata") or {}).get("project_id")
    }
    if vectors and (not project_ids or not (vector_projects & project_ids)):
        # The halves do not belong to each other: the store's vectors all
        # name projects this database has never heard of (or the database
        # knows no projects at all). Seen live when a hermetic test pointed
        # a fresh database at the real store — it reported thousands of
        # orphans. Nothing here is checkable, and a repair that believed it
        # would delete the whole store.
        report.unreadable.append("<database and vector store are not paired>")
        return
    present: set[str] = set()
    for row in vectors:
        vector_id = row["id"]
        report.checked_vectors += 1
        # Chunked docs are `{row_id}#{n}`; code files `{row_id}#0`.
        owner = vector_id.split("#", 1)[0]
        present.add(owner)
        if owner not in flagged:
            report.orphans.append(vector_id)
    for row_id, (path, absolute) in flagged.items():
        if row_id in present:
            continue
        if not _embeddable(absolute):
            continue  # legitimate: nothing was ever embedded for this row
        report.missing.append(f"{path} ({row_id})")


def _project_ids(db_path: Path) -> set[str]:
    """Ids of the projects this database knows about."""
    conn = sqlite3.connect(str(db_path))
    try:
        try:
            return {str(row[0]) for row in conn.execute("SELECT id FROM project")}
        except sqlite3.DatabaseError:
            return set()
    finally:
        conn.close()


def verify_pairing(db_path: Path, chroma_path: Path) -> PairingReport:
    """Compare the `projectfile` embedding flags against `file_summaries`.

    Takes explicit paths so it can be pointed at a *staged* restore before
    anything is installed — the decision to trust or rebuild has to happen
    before the old store is gone.
    """
    report = PairingReport()
    if not Path(db_path).exists():
        # No relational half means nothing is claimed; a rebuild decides.
        report.missing.append("<database absent>")
        return report

    flagged, failure = _flagged_rows(db_path)
    if failure is not None:
        return failure
    report.checked_files = len(flagged)

    try:
        from app.services.chroma_manager import ChromaManager

        manager = ChromaManager(chroma_path)
    except Exception:  # noqa: BLE001 — an unopenable store is not a pairing
        logger.warning("Chroma store at %s could not be opened", chroma_path)
        report.missing.append("<vector store unreadable>")
        return report

    _probe_collections(report, manager)
    _compare(flagged, _project_ids(db_path), report, manager)
    return report


def _probe_collections(report: PairingReport, manager) -> None:
    """Per-collection counts plus a real query, which is what catches a store
    whose segment files vanished while its metadata still counts them."""
    try:
        from app.services.chroma_manager import COLLECTIONS

        broken = manager.health().get("broken") or []
        for name in COLLECTIONS:
            if name in broken:
                report.unreadable.append(name)
            else:
                report.collection_counts[name] = manager.count(name)
    except Exception:  # noqa: BLE001 — same: not a pairing, a broken store
        report.unreadable.append("<health probe failed>")


def verify_store(db_path: Path | None = None, chroma=None) -> PairingReport:
    """Check the live store. Read-only, and safe to call at boot.

    `chroma` is injectable so the API route can pass the same manager its
    service uses rather than reaching for the shared singleton — the v1.17.7.3
    lesson about `Depends` being the only honest way to get one.
    """
    report = PairingReport()
    target = Path(db_path or settings.db_path)
    if not target.exists():
        report.missing.append("<database absent>")
        return report
    flagged, failure = _flagged_rows(target)
    if failure is not None:
        return failure
    report.checked_files = len(flagged)

    if chroma is None:
        try:
            from app.services.chroma_manager import get_chroma_manager

            chroma = get_chroma_manager()
        except Exception:  # noqa: BLE001 — an unopenable store is not a pairing
            report.missing.append("<vector store unreadable>")
            return report

    _probe_collections(report, chroma)
    _compare(flagged, _project_ids(target), report, chroma)
    return report


def reconcile_store() -> ReconcileReport:
    """Make the live store agree with the database, deterministically.

    A flag with no vector is cleared, so the next index pass re-embeds that
    file — a rebuild's outcome, reached without re-embedding everything. A
    vector with no row is deleted, so it stops answering from files that are
    gone. Both halves of one span: a backup cannot snapshot the repair
    half-done (audit A6's barrier).

    Never automatic — a caller asks for it (CLI
    `sentinel knowledge reconcile`). Sentinel does not decide on its own to
    rewrite the index (Rule 2).
    """
    from app.services.chroma_manager import get_chroma_manager
    from app.services.ingest_barrier import ingest_transaction

    report = ReconcileReport()
    chroma = get_chroma_manager()
    with ingest_transaction():
        before = verify_store(chroma=chroma)
        if before.unreadable:
            # A store that cannot be read is a rebuild, not a repair: the
            # reset route is the honest path and this must not half-handle it.
            logger.warning(
                "Knowledge reconcile refused; store unreadable: %s",
                "; ".join(before.unreadable),
            )
            report.after = before
            return report
        if before.orphans:
            report.removed_vectors = _delete_vectors(chroma, before.orphans)
        if before.missing:
            report.cleared_flags = _clear_flags(before.missing)
        report.after = verify_store(chroma=chroma)
    if report.cleared_flags or report.removed_vectors:
        logger.info("Knowledge reconcile: %s", report.summary())
    return report


def _clear_flags(missing: list[str]) -> int:
    """Clear `embedding_id` on the rows whose vectors are gone."""
    from sqlmodel import Session, update

    from app.db.connection import get_engine
    from app.db.models import ProjectFile

    row_ids = []
    for entry in missing:
        # Entries read `{path} ({row id})`; a path may itself contain
        # parentheses, so the id is taken from the tail.
        row_ids.append(entry.rpartition("(")[2].rstrip(")"))
    if not row_ids:
        return 0
    with Session(get_engine()) as session:
        result = session.exec(
            update(ProjectFile)
            .where(ProjectFile.id.in_(row_ids))
            .values(embedding_id=None)
        )
        session.commit()
        return int(result.rowcount or 0)


def _delete_vectors(chroma, orphans: list[str]) -> int:
    """Delete vectors whose file row is gone (A1's mirror)."""
    try:
        chroma.delete_ids("file_summaries", orphans)
    except Exception:  # noqa: BLE001 — report, never crash the repair
        logger.warning("Could not delete %d orphaned vector(s)", len(orphans))
        return 0
    return len(orphans)
