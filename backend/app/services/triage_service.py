"""Deterministic error triage for failed sessions (later.md Tier 3).

The triage packet is built with zero AI: error lines are quoted verbatim
from the session's own log slice, traceback frames are resolved against the
project repo, and the responsible source lines are read straight from disk
(Rule 3). The optional AI summary is a single local-LLM paragraph DESCRIBING
that evidence — no causes, no fixes, no decisions (Rules 2+3); model and
timestamp are stored with it for provenance (Rule 7).
"""

import datetime
import json
import re
from pathlib import Path

from sqlmodel import Session

from app.core.logging import get_logger
from app.db.models import AppSession, Project, TriageAnalysis
from app.repositories import TriageAnalysisRepository
from app.services.ollama_service import OllamaService
from app.services.system_service import OllamaStatus

logger = get_logger(__name__)

MAX_ERROR_LINES = 40
MAX_FRAMES = 8
SOURCE_CONTEXT_BEFORE = 3
SOURCE_CONTEXT_AFTER = 2

ERROR_HINT_RE = re.compile(
    r"(Traceback|ERROR|CRITICAL|FAILED|Exception|error:|failed to|"
    r"Unhandled error|OperationalError)"
)

TRACEBACK_FRAME_RE = re.compile(r'^\s*File "([^"]+)", line (\d+)(?:, in (.+))?$')

KNOWN_PATTERNS = (
    "ModuleNotFoundError",
    "ImportError",
    "NameError",
    "AttributeError",
    "TypeError",
    "ValueError",
    "KeyError",
    "IndexError",
    "UnicodeDecodeError",
    "ConnectionRefusedError",
    "ConnectionError",
    "TimeoutError",
    "FileNotFoundError",
    "PermissionError",
    "OSError",
    "SyntaxError",
    "AssertionError",
    "HttpError",
    "OperationalError",
)


def error_lines(log_slice: str) -> list[str]:
    """Error-hinting lines, quoted verbatim, capped."""
    return [line for line in log_slice.splitlines() if ERROR_HINT_RE.search(line)][
        :MAX_ERROR_LINES
    ]


def traceback_frames(log_slice: str) -> list[tuple[str, int, str | None]]:
    """`File "path", line N, in func` frames in order (uncapped scan).

    Capping here would cut real project frames: uvicorn tracebacks lead with
    many site-packages frames (sqlalchemy, starlette, fastapi middleware),
    so a pre-resolution cap of 8 grabs only dependency frames. The cap is
    applied to the *resolved* list instead (see build_evidence).
    """
    return [
        (match.group(1), int(match.group(2)), match.group(3))
        for line in log_slice.splitlines()
        if (match := TRACEBACK_FRAME_RE.match(line))
    ]


def _source_preview(file_path: Path, line: int) -> list[dict]:
    try:
        lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    start = max(1, line - SOURCE_CONTEXT_BEFORE)
    end = min(len(lines), line + SOURCE_CONTEXT_AFTER)
    return [{"line_number": n, "text": lines[n - 1]} for n in range(start, end + 1)]


def resolve_frames(
    frames: list[tuple[str, int, str | None]], project_path: str
) -> list[dict]:
    """Resolve traceback frames to files inside the project; capture source.

    Frames pointing outside the project (venv, site-packages) are dropped
    from source capture — they are not the project's own code.
    """
    root = Path(project_path).resolve()
    root_norm = str(root).casefold()
    resolved = []
    seen = set()
    for file_path, line, function in frames:
        if file_path.startswith("<") and file_path.endswith(">"):
            continue  # pseudo frames: <string>, <frozen importlib...>
        candidate = Path(file_path)
        if not candidate.is_absolute():
            candidate = root / candidate
        candidate = candidate.resolve()
        if str(candidate).casefold() not in root_norm and root not in candidate.parents:
            continue
        try:
            relative_path = candidate.relative_to(root)
        except ValueError:
            relative_path = candidate
        key = (str(relative_path), line)
        if key in seen:
            continue
        seen.add(key)
        resolved.append(
            {
                "file": str(candidate),
                "relative_path": str(relative_path),
                "line": line,
                "function": function,
                "source": _source_preview(candidate, line),
            }
        )
    return resolved


def detect_patterns(log_slice: str) -> list[str]:
    return [p for p in KNOWN_PATTERNS if p in log_slice]


def build_evidence(project: Project, app_session: AppSession) -> dict:
    """The deterministic packet — no AI anywhere in this path."""
    log_slice = app_session.log_slice or ""
    frames = traceback_frames(log_slice)
    resolved = resolve_frames(frames, project.path)[:MAX_FRAMES]
    evidence = {
        "status": getattr(app_session.status, "value", app_session.status),
        "actual_outcome": app_session.actual_outcome,
        "error_lines": error_lines(log_slice),
        "patterns": detect_patterns(log_slice),
        "frames": resolved,
        "traceback_available": bool(frames),
        "note": None,
    }
    if not frames:
        evidence["note"] = (
            "No traceback found — source mapping unavailable. The console error "
            "lines above are the evidence."
        )
    elif frames and not resolved:
        evidence["note"] = (
            "Traceback frames found but none resolved inside the project path — "
            "the failure is in dependencies or the environment."
        )
    return evidence


class TriageService:
    """One responsibility (Rule 4): triage failed sessions deterministically."""

    def __init__(self, session: Session):
        self.session = session
        self.repo = TriageAnalysisRepository(session)

    def triage(self, app_session: AppSession) -> TriageAnalysis:
        project = app_session.project
        analysis = TriageAnalysis(
            session_id=app_session.id, evidence=build_evidence(project, app_session)
        )
        self.repo.add(analysis)
        self.session.commit()
        self.session.refresh(analysis)
        return analysis

    def summarize(self, app_session: AppSession) -> TriageAnalysis:
        """Attach a local-LLM description to the latest triage row.

        Creates the evidence row first when the session was never triaged.
        """
        latest = self.repo.by_session(app_session.id)
        analysis = latest[0] if latest else self.triage(app_session)
        project = app_session.project
        evidence = build_evidence(project, app_session)
        prompt = _summary_prompt(evidence)
        ollama = OllamaService()
        try:
            result = ollama.generate_with_metrics(
                prompt,
                max_tokens=150,
                temperature=0.2,
                purpose="triage-summary",
                num_ctx=4096,
            )
        finally:
            # v1.17.18.3 (audit2 S1): per-call client must not leak its pool.
            ollama.close()
        analysis.evidence = evidence
        analysis.summary = result["response"]
        analysis.model = result["model"]
        analysis.created_at = datetime.datetime.now(datetime.timezone.utc)
        self.session.add(analysis)
        self.session.commit()
        self.session.refresh(analysis)
        OllamaStatus(self.session).record_query(
            model=result["model"],
            prompt=prompt,
            response=result["response"],
            eval_count=result["eval_count"],
            eval_duration_ns=result["eval_duration_ns"],
            total_duration_ns=result["total_duration_ns"],
            purpose="triage-summary",
        )
        return analysis


def _summary_prompt(evidence: dict) -> str:
    return (
        "You are a session triage assistant. The JSON below is deterministic "
        "evidence from a failed app-testing session: error lines verbatim from "
        "the app's own log, and traceback frames resolved to source lines in "
        "the project.\n"
        "Describe in one short paragraph (at most 120 words) what the evidence "
        "shows: which step failed and where (cite file:line references).\n"
        "Do NOT propose fixes, root causes, or next steps — describe the "
        "evidence only.\n\n"
        f"Evidence:\n{json.dumps(evidence, indent=2)}"
    )
