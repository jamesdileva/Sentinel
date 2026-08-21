"""Startup validation — structured checks reported when the server boots.

Sprint 12. Every component Sentinel depends on is probed at startup: the
validators are deterministic (connectivity + filesystem existence only, no
side effects). Results are logged and also returned by `/api/v1/system/overview`
so the dashboard can show the same state (docs/02 §7.3).
"""

from dataclasses import asdict, dataclass
from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger
from app.db.connection import check_db
from app.services.ollama_service import OllamaService

logger = get_logger(__name__)


@dataclass
class ComponentStatus:
    name: str
    ok: bool
    detail: str = ""


def _check_watch_dirs() -> ComponentStatus:
    missing = [p for p in settings.watch_dirs if not Path(p).exists()]
    if not settings.watch_dirs:
        return ComponentStatus("watch_dirs", False, "No watch directories configured")
    if missing:
        return ComponentStatus("watch_dirs", False, f"Missing: {', '.join(missing)}")
    return ComponentStatus("watch_dirs", True, ", ".join(settings.watch_dirs))


def _check_ollama() -> ComponentStatus:
    if not settings.ollama_host:
        return ComponentStatus("ollama", False, "AI host not configured")
    ollama = OllamaService()
    try:
        models = ollama.list_models()
    except Exception as exc:  # noqa: BLE001  (probe; failures are expected)
        return ComponentStatus("ollama", False, str(exc).splitlines()[0])
    finally:
        ollama.close()  # v1.17.18.3 (audit2 S1)
    detail = ", ".join(models) if models else "reachable, no models"
    return ComponentStatus("ollama", True, detail)


def _check_schema() -> ComponentStatus:
    """Model-vs-DB drift (v1.17.18.3, audit2 Q5): create_all cannot ALTER
    existing tables, so a new model field without a migration would leave
    old deployments silently missing it. Surface any gap on the System page
    instead of failing to boot."""
    from sqlmodel import Session

    from app.db.connection import check_schema_drift, get_engine

    try:
        with Session(get_engine()) as session:
            drifted = check_schema_drift(session.get_bind())
    except Exception as exc:  # noqa: BLE001 — never crash the check pass
        return ComponentStatus("schema", False, f"drift probe failed: {exc}")
    if drifted:
        return ComponentStatus(
            "schema",
            False,
            f"missing column(s): {', '.join(drifted)} — add a migration in "
            "app/db/connection.py",
        )
    return ComponentStatus("schema", True, "models match database")


def _check_chroma(chroma_path: Path) -> ComponentStatus:
    if chroma_path.exists() and not chroma_path.is_dir():
        return ComponentStatus("chroma", False, "path exists but is not a directory")
    try:
        chroma_path.mkdir(parents=True, exist_ok=True)
        return ComponentStatus("chroma", True, str(chroma_path))
    except OSError as exc:
        return ComponentStatus("chroma", False, str(exc))


def run_startup_checks() -> list[ComponentStatus]:
    """Run all startup checks in dependency order. Never raises."""
    checks = [
        ComponentStatus("database", check_db(), str(settings.db_path)),
        _check_schema(),
        _check_chroma(settings.chroma_path),
        _check_watch_dirs(),
        _check_ollama(),
    ]
    for status in checks:
        (logger.info if status.ok else logger.warning)(
            "Startup check %s=%s (%s)",
            status.name,
            "ok" if status.ok else "FAILED",
            status.detail,
        )
    return checks


def startup_report() -> dict:
    return {"states": [asdict(s) for s in run_startup_checks()]}
