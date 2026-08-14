"""Sprint 9: World Simulator tests.

Covers determinism (same seed = same world), the core rules (food/growth,
construction, expansion+roads, collapse, skill tiers), god tools, catch-up
timing, and the HTTP API. All tests are fast and deterministic — no AI, no
broker, no network.
"""

import datetime
import random

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlmodel import Session

import app.api.v1.world_sim as ws_api
import app.db.world_sim_models as wdb
from app.core.config import settings
from app.db.world_sim_models import world_sim_metadata
from app.main import app
from app.services.world_sim import names
from app.services.world_sim.rules_engine import (
    EXPAND_LEVEL,
    EXPAND_POPULATION,
    TERRAIN_TYPES,
    terrain_at,
)
from app.services.world_sim.skill_system import (
    grant_survival_experience,
    production_bonus,
    rebuild_speed,
    skill_level,
)
from app.services.world_sim.world_simulator import WorldSimulatorService


def make_service(tmp_path, seed=42, starting=2):
    """Fresh world service over an isolated temp SQLite file."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{tmp_path}/world.db", connect_args={"check_same_thread": False}
    )
    world_sim_metadata.create_all(engine)
    return WorldSimulatorService(
        engine=engine,
        seed=seed,
        starting_settlements=starting,
        tick_seconds=60,
        max_catchup_days=48,
        time_scale=1,
    )


def deterministic_state(svc):
    """State minus volatile bookkeeping (timestamps, event ids)."""
    state = svc.get_state()
    state["updated_at"] = None
    for event in state["recent_events"]:
        event["id"] = None
    return state


def update_row(svc, row_id: str, **kwargs) -> None:
    with Session(svc.engine) as session:
        row = session.get(wdb.WorldSettlement, row_id)
        for key, value in kwargs.items():
            setattr(row, key, value)
        session.commit()


# ── determinism ──────────────────────────────────────────────────────


def test_same_seed_produces_identical_worlds(tmp_path):
    a = make_service(tmp_path / "a")
    b = make_service(tmp_path / "b")
    a.advance_day(200)
    b.advance_day(200)
    assert deterministic_state(a) == deterministic_state(b)


def test_same_seed_same_names(tmp_path):
    a = make_service(tmp_path / "a")
    b = make_service(tmp_path / "b")
    a.ensure_world()
    b.ensure_world()
    assert [s["name"] for s in a.get_state()["settlements"]] == [
        s["name"] for s in b.get_state()["settlements"]
    ]


def test_different_seed_diverges(tmp_path):
    a = make_service(tmp_path / "a", seed=1)
    b = make_service(tmp_path / "b", seed=2)
    a.advance_day(50)
    b.advance_day(50)
    assert a.get_state() != b.get_state()


def test_terrain_is_stable_per_seed():
    for x in range(-5, 6):
        for y in range(-5, 6):
            assert terrain_at(x, y, 42) in TERRAIN_TYPES
    assert terrain_at(2, 3, 42) == terrain_at(2, 3, 42)


def test_names_deterministic():
    a = names.settlement_name(random.Random(9))
    b = names.settlement_name(random.Random(9))
    assert a == b
    assert len(a.split()) >= 1


# ── skill system ─────────────────────────────────────────────────────


def test_skill_levels_follow_tier_table():
    assert skill_level(0) == 1
    assert skill_level(49) == 1
    assert skill_level(50) == 2
    assert skill_level(149) == 2
    assert skill_level(150) == 3
    assert skill_level(500) == 5
    assert skill_level(10_000) == 5


def test_production_and_rebuild_scaling():
    assert production_bonus(1) == 1.0
    assert production_bonus(5) == 1.2
    assert rebuild_speed(1) == 1.0
    assert rebuild_speed(5) == 1.4


def test_survival_experience_scales_with_severity():
    flood = grant_survival_experience(6)
    plague = grant_survival_experience(8)
    assert flood == 20 + 5 * (6 - 1)
    assert plague > flood


# ── core rules via the service ───────────────────────────────────────


def test_food_growth_on_surplus(tmp_path):
    svc = make_service(tmp_path)
    svc.ensure_world()
    first = svc.get_state()["settlements"][0]
    with Session(svc.engine) as session:
        row = session.get(wdb.WorldSettlement, first["id"])
        row.population = 50
        row.food = 1000
        session.commit()
    svc.advance_day(1)
    after = svc.get_settlement(first["id"])
    assert after["food"] > 1000


def test_expansion_creates_child_and_road(tmp_path):
    svc = make_service(tmp_path)
    svc.ensure_world()
    starter = svc.get_state()["settlements"][0]
    update_row(
        svc,
        starter["id"],
        population=EXPAND_POPULATION + 50,
        level=EXPAND_LEVEL,
        farmers=200,
        food=1_000_000,
    )
    expanded = False
    for _ in range(60):
        svc.advance_day(1)
        state = svc.get_state()
        if len(state["settlements"]) > 1 and state["roads"]:
            expanded = True
            break
    assert expanded, "expected expansion + road within 60 days"
    road = svc.get_state()["roads"][0]
    assert road["from_id"] == starter["id"] or road["to_id"] == starter["id"]


def test_roads_appear_from_natural_growth(tmp_path):
    """Sprint 12.2 regression: from the bootstrap alone (no manual role
    injection) a settlement must grow, level up, and found a child linked
    by a road within the cap. Pre-fix, farmers stayed fixed at ~20 so
    population plateaued at ~130 and EXPAND_POPULATION (600) was never
    reached — the natural world could not produce roads at all."""
    svc = make_service(tmp_path)
    svc.ensure_world()
    assert svc.get_state()["roads"] == []
    while svc.get_state()["day_number"] < 1000:
        svc.advance_day(1)
        if svc.get_state()["roads"]:
            break
    state = svc.get_state()
    assert state["roads"], "natural growth must produce roads within 1000 days"
    assert state["day_number"] < 1000


def test_famine_collapses_settlement(tmp_path):
    svc = make_service(tmp_path)
    svc.ensure_world()
    target = svc.get_state()["settlements"][0]
    update_row(svc, target["id"], farmers=0, food=10, population=200)
    collapsed = False
    for _ in range(120):
        svc.advance_day(1)
        state = svc.get_state()
        s = [x for x in state["settlements"] if x["id"] == target["id"]][0]
        if s["status"] == "abandoned":
            collapsed = True
            break
    assert collapsed, "famine should eventually abandon the settlement"


def test_level_up_event_and_construction_progress(tmp_path):
    svc = make_service(tmp_path)
    svc.ensure_world()
    target = svc.get_state()["settlements"][0]
    update_row(
        svc,
        target["id"],
        farmers=100,
        builders=100,
        food=1_000_000,
        population=1_000,
    )
    svc.advance_day(2)
    events = svc.get_history()
    assert any("reached level" in e["title"] for e in events)


# ── disasters & god tools ────────────────────────────────────────────


def test_disaster_grants_experience_and_reduces_resources(tmp_path):
    svc = make_service(tmp_path)
    svc.ensure_world()
    target = svc.get_state()["settlements"][0]
    update_row(svc, target["id"], population=400, food=2000, experience=0)
    assert svc.trigger_disaster(target["id"], "flood")
    detail = svc.get_settlement(target["id"])
    assert detail["status"] == "active"
    assert detail["population"] < 400
    assert detail["food"] < 2000
    assert detail["experience"] > 0
    assert detail["skill_level"] == skill_level(detail["experience"])


def test_disaster_collapses_tiny_settlement(tmp_path):
    svc = make_service(tmp_path)
    svc.ensure_world()
    target = svc.get_state()["settlements"][0]
    update_row(svc, target["id"], population=1, food=5000)
    assert svc.trigger_disaster(target["id"], "plague")
    detail = svc.get_settlement(target["id"])
    assert detail["status"] == "abandoned"
    assert detail["population"] == 0
    assert detail["destroyed_day"] is not None


def test_disaster_rejects_unknown_type(tmp_path):
    svc = make_service(tmp_path)
    svc.ensure_world()
    with pytest.raises(ValueError):
        svc.trigger_disaster("s0", "meteor")


def test_disaster_unknown_settlement(tmp_path):
    svc = make_service(tmp_path)
    svc.ensure_world()
    assert not svc.trigger_disaster("no-such-id", "flood")


def test_reset_binds_new_seed(tmp_path):
    svc = make_service(tmp_path, seed=7)
    svc.ensure_world()
    assert svc.get_state()["seed"] == 7
    svc.reset(seed=13)
    assert svc.get_state()["seed"] == 13
    assert svc.get_state()["day_number"] == 0


def test_time_scale_clamped(tmp_path):
    svc = make_service(tmp_path)
    svc.ensure_world()
    svc.set_time_scale(99)
    assert svc.get_state()["time_scale"] == 10
    svc.set_time_scale(0)
    assert svc.get_state()["time_scale"] == 1


# ── catch-up timing ──────────────────────────────────────────────────


def _set_world_updated_at(svc, dt: datetime.datetime) -> None:
    with Session(svc.engine) as session:
        world = session.get(wdb.WorldSimStateRow, "world")
        world.updated_at = dt
        session.commit()


def test_catch_up_advances_bounded_days(tmp_path):
    svc = make_service(tmp_path)
    svc.ensure_world()
    past = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=24)
    _set_world_updated_at(svc, past)
    days = svc.catch_up()
    assert days == 48  # bounded by max_catchup_days
    assert svc.get_state()["day_number"] == 48


def test_catch_up_noop_with_fresh_world(tmp_path):
    svc = make_service(tmp_path)
    svc.ensure_world()
    assert svc.catch_up() == 0
    assert svc.get_state()["day_number"] == 0


# ── HTTP API ─────────────────────────────────────────────────────────


@pytest.fixture()
def world_client(tmp_db, tmp_path):
    # v1.17.7.3: the world-sim router is opt-in (world_sim_enabled=False by
    # default); tests mount it explicitly so they pass either way.
    if settings.world_sim_enabled is False:
        _mount_world_sim_router()
    svc = make_service(tmp_path / "api")
    svc.ensure_world()
    app.dependency_overrides[ws_api.get_world_service] = lambda: svc
    yield TestClient(app), svc
    app.dependency_overrides.pop(ws_api.get_world_service, None)


def _mount_world_sim_router() -> None:
    """Mount the world-sim router ahead of the SPA fallback route.

    main.py registers `/{full_path:path}` at import time (it must stay the
    last route); a router included afterwards would be shadowed by it for
    GET requests, so the fallback is re-appended after the include."""
    if any(getattr(r, "path", "").startswith("/api/v1/world-sim") for r in app.routes):
        return
    app.include_router(ws_api.router, prefix="/api/v1")
    fallbacks = [
        r for r in app.routes if getattr(r, "path", None) == "/{full_path:path}"
    ]
    for route in fallbacks:
        app.routes.remove(route)
        app.routes.append(route)


def test_state_endpoint(world_client):
    client, _ = world_client
    resp = client.get("/api/v1/world-sim/state")
    assert resp.status_code == 200
    body = resp.json()
    assert body["day_number"] == 0
    assert body["stats"]["active"] >= 1
    assert "seed" in body


def test_tick_endpoint(world_client):
    client, svc = world_client
    resp = client.post("/api/v1/world-sim/tick", json={"days": 3})
    assert resp.status_code == 200
    body = resp.json()
    assert body["days_advanced"] == 3
    assert body["day_number"] == 3
    assert svc.get_state()["day_number"] == 3


def test_history_endpoint(world_client):
    client, _ = world_client
    client.post("/api/v1/world-sim/tick", json={"days": 1})
    events = client.get("/api/v1/world-sim/history").json()
    assert isinstance(events, list)
    assert all({"day", "title", "event_type"} <= set(e) for e in events)


def test_settlement_endpoint_and_404(world_client):
    client, svc = world_client
    sid = svc.get_state()["settlements"][0]["id"]
    resp = client.get(f"/api/v1/world-sim/settlements/{sid}")
    assert resp.status_code == 200
    assert resp.json()["id"] == sid
    assert client.get("/api/v1/world-sim/settlements/nope").status_code == 404


def test_disaster_endpoint(world_client):
    client, svc = world_client
    sid = svc.get_state()["settlements"][0]["id"]
    ok = client.post(
        "/api/v1/world-sim/disaster",
        json={"settlement_id": sid, "disaster_type": "flood"},
    )
    assert ok.status_code == 200
    assert ok.json()["applied"] is True
    badtype = client.post(
        "/api/v1/world-sim/disaster",
        json={"settlement_id": sid, "disaster_type": "meteor"},
    )
    assert badtype.status_code == 400
    missing = client.post(
        "/api/v1/world-sim/disaster",
        json={"settlement_id": "nope", "disaster_type": "flood"},
    )
    assert missing.status_code == 404


def test_reset_and_accelerate_endpoints(world_client):
    client, svc = world_client
    resp = client.post("/api/v1/world-sim/reset", json={"seed": 9})
    assert resp.status_code == 200
    assert svc.get_state()["seed"] == 9
    resp = client.post("/api/v1/world-sim/accelerate", json={"time_scale": 5})
    assert resp.status_code == 200
    assert svc.get_state()["time_scale"] == 5
