"""Settings endpoints — /api/v1/settings (v1.17.18.0, read-only).

Renders the effective configuration (every SENTINEL_* setting with value /
default / source) plus deterministic validation warnings. Purely a status
read (docs/01 Rule 2): there are no write endpoints — editing config means
editing `.env` and restarting, by design.
"""

from fastapi import APIRouter

from app.services.settings_service import settings_report

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
def get_settings() -> dict:
    """Full configuration report: grouped settings, sources, validation warnings."""
    return settings_report()
