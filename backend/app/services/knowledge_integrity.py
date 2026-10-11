"""Knowledge integrity — does the embedding flag match the vectors?

Both halves of Sentinel's knowledge are derived from project files on disk,
so the pairing is checkable rather than assumed: a `projectfile` row whose
`embedding_id` is set promises at least one vector in `file_summaries`, and
every vector in there belongs to a row that still exists.

Audit A6 is the reason this exists. A backup whose SQLite and Chroma halves
describe different instants restores fine and then quietly under-serves:
rows that promise vectors the store does not have, so `ingest_files` skips
them and the index absorbs no re-embedding. That invariant — flag set means
vector present — is the one thing that turns a torn snapshot from a
performance problem into a permanently wrong index, so it is what restore
checks before deciding it can trust the Chroma half.

Deterministic by construction (Rule 3): read the rows, read the ids, compare.
No embedding, no Ollama, no heuristics. Also usable at startup to report on
a store someone restored by hand — the same call, different caller.
"""

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

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

    flagged: dict[str, str] = {}  # file row id -> path (for the message)
    conn = sqlite3.connect(str(db_path))
    try:
        try:
            rows = conn.execute(
                "SELECT id, path FROM projectfile WHERE embedding_id IS NOT NULL"
            ).fetchall()
        except sqlite3.OperationalError:
            # No such table: a snapshot of a database that was never
            # initialised. Nothing is claimed, and nothing is checkable.
            report.missing.append("<projectfile table absent>")
            return report
        for row_id, path in rows:
            flagged[row_id] = path
    finally:
        conn.close()
    report.checked_files = len(flagged)

    try:
        from app.services.chroma_manager import COLLECTIONS, ChromaManager

        manager = ChromaManager(chroma_path)
    except Exception:  # noqa: BLE001 — an unopenable store is not a pairing
        logger.warning("Chroma store at %s could not be opened", chroma_path)
        report.missing.append("<vector store unreadable>")
        return report

    try:
        for name in COLLECTIONS:
            probe = manager.health().get("broken") or []
            if name in probe:
                report.unreadable.append(name)
            else:
                report.collection_counts[name] = manager.count(name)
    except Exception:  # noqa: BLE001 — same: not a pairing, a broken store
        report.unreadable.append("<health probe failed>")
        return report

    try:
        vectors = manager.all_rows("file_summaries")
    except Exception:  # noqa: BLE001
        report.unreadable.append("file_summaries")
        return report

    present: set[str] = set()
    for row in vectors:
        vector_id = row["id"]
        report.checked_vectors += 1
        # Chunked docs are `{row_id}#{n}`; code files `{row_id}#0`.
        owner = vector_id.split("#", 1)[0]
        present.add(owner)
        if owner not in flagged:
            report.orphans.append(vector_id)

    for row_id, path in flagged.items():
        if row_id not in present:
            report.missing.append(f"{path} ({row_id})")
    return report
