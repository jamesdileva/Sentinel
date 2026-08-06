"""World Simulator endpoints — /api/v1/world-sim (docs/02 §11.6).

Polling-based (no websocket): state/history for the map UI, plus god tools
(tick, reset, accelerate, disaster). All mutations run deterministically in
the API process; background advancement happens via the Celery beat task.
"""

from fastapi import APIRouter, Depends, HTTPException

from app.schemas import (
    WorldAccelerateRequest,
    WorldDisasterRequest,
    WorldDisasterResponse,
    WorldEventRead,
    WorldResetRequest,
    WorldSettlementDetailRead,
    WorldSimStateRead,
    WorldTickRequest,
    WorldTickResponse,
)
from app.services.world_sim import WorldSimulatorService

router = APIRouter(tags=["world-sim"])


def get_world_service() -> WorldSimulatorService:
    """FastAPI dependency: world service backed by its own engine/DB."""
    return WorldSimulatorService()


@router.get("/world-sim/state", response_model=WorldSimStateRead)
def world_state(
    service: WorldSimulatorService = Depends(get_world_service),
) -> dict:
    return service.get_state()


@router.get("/world-sim/history", response_model=list[WorldEventRead])
def world_history(
    limit: int = 100,
    before: int | None = None,
    service: WorldSimulatorService = Depends(get_world_service),
) -> list[dict]:
    return service.get_history(limit=min(limit, 500), before=before)


@router.get(
    "/world-sim/settlements/{settlement_id}",
    response_model=WorldSettlementDetailRead,
)
def world_settlement(
    settlement_id: str,
    service: WorldSimulatorService = Depends(get_world_service),
) -> dict:
    detail = service.get_settlement(settlement_id)
    if detail is None:
        raise HTTPException(
            status_code=404, detail=f"Unknown settlement: {settlement_id}"
        )
    return detail


@router.post("/world-sim/tick", response_model=WorldTickResponse)
def world_tick(
    payload: WorldTickRequest,
    service: WorldSimulatorService = Depends(get_world_service),
) -> WorldTickResponse:
    """God tool: advance the world by N days immediately."""
    service.advance_day(payload.days)
    day_number = service.get_state(recent=1)["day_number"]
    return WorldTickResponse(days_advanced=payload.days, day_number=day_number)


@router.post("/world-sim/reset")
def world_reset(
    payload: WorldResetRequest,
    service: WorldSimulatorService = Depends(get_world_service),
) -> dict:
    """God tool: wipe the world and start over, optionally with a new seed."""
    service.reset(payload.seed)
    return {"status": "reset", "seed": payload.seed}


@router.post("/world-sim/accelerate", response_model=WorldAccelerateRequest)
def world_accelerate(
    payload: WorldAccelerateRequest,
    service: WorldSimulatorService = Depends(get_world_service),
) -> WorldAccelerateRequest:
    """God tool: set day-per-tick ratio (each tick advances `time_scale` days)."""
    service.set_time_scale(payload.time_scale)
    return payload


@router.post("/world-sim/disaster", response_model=WorldDisasterResponse)
def world_disaster(
    payload: WorldDisasterRequest,
    service: WorldSimulatorService = Depends(get_world_service),
) -> WorldDisasterResponse:
    """God tool: force a flood/drought/plague on a settlement."""
    try:
        applied = service.trigger_disaster(payload.settlement_id, payload.disaster_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not applied:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown or inactive settlement: {payload.settlement_id}",
        )
    return WorldDisasterResponse(
        settlement_id=payload.settlement_id,
        disaster_type=payload.disaster_type,
        applied=True,
    )
