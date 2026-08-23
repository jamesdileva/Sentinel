"""Career OS tester — FastAPI backend smoke + API-surface assertions.

Verified ground truth (2026-08-22):
- launch: cd backend && .venv\\Scripts\\python -m uvicorn app.main:app
  --port 8000 (cwd=backend is required; the venv is created via
  `pip install -e ".[dev]"`)
- port 8000, no auth
- GET / -> {"status":"ok"}; GET /health -> {"status":"healthy"}
- fallback: scripts/dev.py --backend-only starts the same server

Beyond the two GET smokes this tester exercises one representative POST
per major API group against the live server: a uniquely-tokened knowledge
item is created via the API, found by /search/, ranked by /build/suggest,
assembled into a document by /build/resume, scored by /validate/, and then
DELETED again — the user's real corpus is untouched (create + cleanup,
never assert against or mutate existing data). Direct httpx calls with
ctx.checkpoint() follow the WorkFlow-Toolkit pattern (ctx.http has no
JSON-body support). Headless HTTP only, no mouse.
"""

import uuid

import httpx

from app.testers import Tester
from app.testers._helpers import (
    TesterAssertionError,
    TesterContext,
    TesterEnvError,
)

LAUNCH_CMD = "cd backend && .venv\\Scripts\\python -m uvicorn app.main:app --port 8000"
BASE_URL = "http://127.0.0.1:8000/api/v1"


def _post(ctx: TesterContext, path: str, payload: dict) -> httpx.Response:
    """POST JSON and return the response; non-2xx is an honest assertion."""
    response = httpx.post(f"{BASE_URL}{path}", json=payload, timeout=30)
    if response.status_code >= 300:
        raise TesterAssertionError(
            f"POST {path} -> {response.status_code}, expected 2xx: "
            f"{response.text[:200]}"
        )
    ctx.checkpoint(f"post {path} -> {response.status_code}")
    return response


def _assert_item_found(
    ctx: TesterContext, path: str, payload: dict, item_id: str, label: str
) -> None:
    """Assert a ranked endpoint returns the tokened item among its results."""
    response = _post(ctx, path, payload)
    body = response.json()
    items = body["items"] if isinstance(body, dict) else body
    ids = {
        entry["id"] if "id" in entry else entry["knowledge_item"]["id"]
        for entry in items
    }
    if item_id not in ids:
        raise TesterAssertionError(f"{label} did not surface the smoke item")
    ctx.checkpoint(f"{label} surfaced the smoke item")


def _cleanup(ctx: TesterContext, item_id: str) -> None:
    """Delete the smoke item and prove it is gone (204 then 404)."""
    deleted = httpx.delete(f"{BASE_URL}/knowledge-items/{item_id}", timeout=30)
    if deleted.status_code != 204:
        raise TesterEnvError(
            f"cleanup DELETE -> {deleted.status_code}, expected 204 — "
            f"smoke item {item_id} may linger in the corpus"
        )
    gone = httpx.get(f"{BASE_URL}/knowledge-items/{item_id}", timeout=30)
    if gone.status_code != 404:
        raise TesterEnvError(
            f"smoke item still readable after delete ({gone.status_code})"
        )
    ctx.checkpoint("smoke item deleted — corpus restored")


def run(ctx: TesterContext) -> None:
    ctx.launch(LAUNCH_CMD, env={"PYTHONPATH": ""})
    ctx.http("GET", f"{BASE_URL}/health", expect_body="healthy", retries=6)
    ctx.http("GET", "http://127.0.0.1:8000/", expect_body='"status":"ok"')

    # One tokened item drives every POST group; unique per run so parallel
    # sessions never collide and the corpus stays untouched after cleanup.
    token = f"SENTINELSMOKE{uuid.uuid4().hex[:8]}"
    created = _post(
        ctx,
        "/knowledge-items/",
        {
            "type": "resume_bullet",
            "title": f"Sentinel smoke item {token}",
            "content": (
                f"{token}: processed confidential records under deadline "
                "understanding customer service escalation procedures."
            ),
            "category": "General",
        },
    )
    item_id = created.json().get("id")
    if not item_id:
        raise TesterAssertionError("knowledge-item create response lacks id")

    try:
        _assert_item_found(
            ctx,
            "/search/",
            {"query": token, "sort_by": "relevance"},
            item_id,
            "/search/",
        )
        _assert_item_found(
            ctx,
            "/build/suggest",
            {"query": token, "min_score": 0.01},
            item_id,
            "/build/suggest",
        )

        built = _post(
            ctx,
            "/build/resume",
            {
                "item_ids": [item_id],
                "user_profile": {"name": "Sentinel Smoke", "contact": "s@s.local"},
            },
        )
        document_id = built.json().get("document_id")
        if not document_id:
            raise TesterAssertionError("/build/resume response lacks document_id")

        validated = _post(
            ctx,
            "/validate/",
            {"document_id": document_id, "doc_type": "resume"},
        )
        if "score" not in validated.json():
            raise TesterAssertionError("/validate/ response lacks score")
        ctx.checkpoint("search/suggest/build/validate all surfaced the smoke item")
    finally:
        _cleanup(ctx, item_id)


TESTER = Tester(
    name="Career OS API smoke",
    description=(
        "Launch the FastAPI backend from backend/ (venv uvicorn on :8000), "
        "verify GET /health and GET / body markers, then exercise one POST "
        "per major group — search, suggest, resume build, validate — using "
        "a uniquely-tokened knowledge item that is deleted afterwards so "
        "the real corpus is untouched. HTTP-only, no mouse."
    ),
    run=run,
    project_slug="Resmaker",  # must match _slug(project.name) on the dashboard
    ports=(8000,),
    auto_launch=False,
)
