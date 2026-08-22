"""System page response schemas (v1.17.18.5, audit2 C5).

The /api/v1/system/* endpoints previously returned ad-hoc dicts, leaving the
OpenAPI contract empty for the dashboard's home page. These models mirror
the exact JSON shapes `system_service` and `activity_bus` already produce —
documentation only, no behavior change.
"""

from pydantic import BaseModel


class ComponentStatusRead(BaseModel):
    name: str
    ok: bool
    detail: str = ""


class OllamaRecentQuery(BaseModel):
    model: str
    purpose: str
    prompt_chars: int
    response_chars: int
    eval_count: int
    eval_duration_ns: int
    total_duration_ns: int
    tokens_per_second: float | None = None
    latency_ms: float = 0
    created_at: str


class OllamaStatusRead(BaseModel):
    available: bool
    host: str = ""
    model_default: str = ""
    models: list[str] = []
    recent: list[OllamaRecentQuery] = []


class SystemOverview(BaseModel):
    generated_at: str
    startup: dict  # {"states": [{name, ok, detail}]}
    ollama: OllamaStatusRead


class SyncLastRun(BaseModel):
    status: str
    ran_at: str | None = None
    cloned: list = []
    pulled: list = []
    failed: dict = {}
    indexed: int = 0
    knowledge_queued: int = 0
    detail: str | None = None


class SyncStatusRead(BaseModel):
    configured: bool
    last_run: SyncLastRun | None = None
    interval_minutes: int


class ActivityEventRead(BaseModel):
    id: str
    kind: str
    message: str
    detail: str | None = None
    data: dict | None = None
    created_at: str


class ActivityResponse(BaseModel):
    events: list[ActivityEventRead]
