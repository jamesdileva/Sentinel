"""Demake Engine tester — full pipeline E2E over the FastAPI backend.

Verified ground truth (2026-08-15):
- Backend: `cd backend && uvicorn main:app` on :8000; repo venv at
  `venv` (uvicorn + deps present). GET / serves the Phaser frontend.
- GET /health -> {"status": "ok", "service": "demake-engine", ...}.
- POST /api/v1/demake/upload (multipart MP4) -> {demake_id, status,
  message}; the in-process worker runs ingestion (ffmpeg on PATH) -> VLM
  analysis (falls back to safe defaults with no Ollama) -> procedural
  sprites/audio -> WFC tilemap -> manifest -> "ready".
- Determinism caveat: tilemap/audio use unseeded random — asserts are
  structural (status codes, keys, non-empty bodies), never byte-exact.
- `backend/test_game_trailer.mp4` ships in the repo (upload fixture).
"""

import time
from pathlib import Path

import httpx

from app.testers import Tester
from app.testers._helpers import (
    TesterAssertionError,
    TesterContext,
    TesterEnvError,
    TesterTimeoutError,
)

BACKEND_CMD = "cd backend && uvicorn main:app"
PORT = "http://127.0.0.1:8000"
POLL_STEP_S = 5
MAX_WAIT_S = 420


def run(ctx: TesterContext) -> None:
    root = Path(ctx.project.path)
    trailer = root / "backend" / "test_game_trailer.mp4"
    if not trailer.exists():
        raise TesterEnvError(f"Upload fixture missing: {trailer}")

    ctx.launch(BACKEND_CMD)
    ctx.wait_log("[sentinel] App launched", 30)
    ctx.wait(6)
    ctx.http("GET", f"{PORT}/health", expect_body="demake-engine")
    ctx.http("GET", f"{PORT}/", expect=200)
    ctx.checkpoint("backend up, frontend served")

    with open(trailer, "rb") as fh:
        response = httpx.post(
            f"{PORT}/api/v1/demake/upload",
            files={"file": ("test_game_trailer.mp4", fh, "video/mp4")},
            timeout=60,
        )
    if response.status_code != 200:
        raise TesterAssertionError(f"upload -> {response.status_code}, expected 200")
    demake_id = response.json().get("demake_id")
    if not demake_id:
        raise TesterAssertionError("upload response lacks demake_id")
    ctx.checkpoint(f"uploaded trailer -> {demake_id}")

    status = None
    deadline = time.time() + MAX_WAIT_S
    while time.time() < deadline:
        status_resp = httpx.get(f"{PORT}/api/v1/demake/{demake_id}/status", timeout=20)
        if status_resp.status_code != 200:
            raise TesterAssertionError(
                f"status poll -> {status_resp.status_code}, expected 200"
            )
        status = status_resp.json().get("status")
        if status in ("ready", "failed"):
            break
        time.sleep(POLL_STEP_S)
    if status == "failed":
        raise TesterAssertionError(
            f"pipeline failed: {status_resp.json().get('error', 'see log')}"
        )
    if status != "ready":
        raise TesterTimeoutError(
            f"pipeline not ready after {MAX_WAIT_S}s (status={status!r})"
        )
    ctx.checkpoint("pipeline reached ready")

    manifest = httpx.get(f"{PORT}/api/v1/demake/{demake_id}/manifest", timeout=20)
    if manifest.status_code != 200:
        raise TesterAssertionError(f"manifest -> {manifest.status_code}, expected 200")
    body = manifest.json()
    if not body.get("title"):
        raise TesterAssertionError("manifest lacks title")
    ctx.checkpoint(f"manifest ready: {body['title']}")

    sprites = body.get("assets", {}).get("sprites", {})
    if not sprites:
        raise TesterAssertionError("manifest has no sprite assets")
    sprite_path = next(iter(sprites.values()))
    if not isinstance(sprite_path, str):
        raise TesterAssertionError(f"unexpected sprite value: {sprite_path!r}")
    # The manifest's sprite values are already absolute asset URLs
    # (`/api/v1/demake/<id>/asset/<name>.png`) — use them as-is.
    asset_url = (
        f"{PORT}{sprite_path}"
        if sprite_path.startswith("/api/")
        else f"{PORT}/api/v1/demake/{demake_id}/asset/{sprite_path}"
    )
    asset = httpx.get(asset_url, timeout=20)
    if asset.status_code != 200:
        raise TesterAssertionError(
            f"asset {sprite_path!r} -> {asset.status_code}, expected 200"
        )
    ctx.checkpoint(f"asset served: {sprite_path}")


TESTER = Tester(
    name="Demake pipeline E2E",
    description=(
        "Launch the FastAPI backend, upload the repo's test_game_trailer.mp4, "
        "poll the pipeline to ready (max 7 min — sprite generation can use the "
        "slow SD/ONNX path), then verify the manifest and serve a generated "
        "sprite asset. Structural asserts only — tilemap and audio use unseeded "
        "random, so nothing byte-exact is compared."
    ),
    run=run,
    project_slug="Demake-Engine",
)
