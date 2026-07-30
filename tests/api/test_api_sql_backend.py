"""The whole API over SQL storage, driven through HTTP.

The repository tests prove the SQL classes behave; these prove the
application wired to them still does. That is a different claim: the
services, routers and approval machine were all written against the
in-memory backend, and a mismatch would only surface here.

The database is SQLite so the suite needs nothing installed. PostgreSQL
is the production target and is *not* exercised — see
docs/KNOWN_LIMITATIONS.md.
"""

from __future__ import annotations

import pytest
from conftest import OPERATOR, REVIEWER, SEED_USERS, auth_headers
from fastapi.testclient import TestClient
from payloads import bordered_map_payload, scenario_payload

from planbench_api.config import get_settings
from planbench_api.db.repositories import SqlRepositoryHub
from planbench_api.main import create_app


@pytest.fixture
def sql_app(tmp_path, monkeypatch):
    monkeypatch.setenv("PLANBENCH_SEED_USERS", SEED_USERS)
    monkeypatch.setenv("PLANBENCH_JWT_SECRET", "test-secret-not-used-in-production")
    monkeypatch.setenv("PLANBENCH_DATABASE_URL", f"sqlite:///{tmp_path / 'api.db'}")
    # Throwaway database: create the schema directly rather than running
    # Alembic per test. The migration is verified separately.
    monkeypatch.setenv("PLANBENCH_DB_CREATE_ALL", "true")
    get_settings.cache_clear()
    application = create_app(artifact_dir=str(tmp_path / "artifacts"))
    yield application
    if application.state.sessions is not None:
        application.state.sessions.dispose()
    get_settings.cache_clear()


@pytest.fixture
def sql_client(sql_app) -> TestClient:
    return TestClient(sql_app, raise_server_exceptions=False)


def test_the_app_actually_selected_the_sql_backend(sql_app):
    # Otherwise every test below would silently pass on the in-memory
    # backend and prove nothing.
    assert isinstance(sql_app.state.repos, SqlRepositoryHub)
    assert sql_app.state.sessions is not None


def test_map_round_trips_through_http(sql_client):
    created = sql_client.post("/api/v1/maps", json=bordered_map_payload())
    assert created.status_code == 201, created.text
    map_id = created.json()["id"]

    fetched = sql_client.get(f"/api/v1/maps/{map_id}")
    assert fetched.status_code == 200
    assert fetched.json()["map_data"]["cells"] == bordered_map_payload()["cells"]


def test_unknown_map_is_a_404(sql_client):
    assert sql_client.get("/api/v1/maps/does-not-exist").status_code == 404


def test_full_benchmark_lifecycle_on_sql(sql_client):
    """Both human gates, a real run, and the audit trail, all persisted."""
    operator = auth_headers(sql_client, OPERATOR)
    reviewer = auth_headers(sql_client, REVIEWER)

    map_id = sql_client.post("/api/v1/maps", json=bordered_map_payload()).json()["id"]
    scenario_id = sql_client.post(
        "/api/v1/scenarios", json={"map_id": map_id, "scenario": scenario_payload()}
    ).json()["id"]

    benchmark = sql_client.post(
        "/api/v1/benchmarks",
        json={
            "name": "sql lifecycle",
            "map_id": map_id,
            "scenario_id": scenario_id,
            "algorithms": [{"id": "astar+dwa", "config": {}}],
            "seeds": [1],
        },
        headers=operator,
    )
    assert benchmark.status_code == 201, benchmark.text
    benchmark_id = benchmark.json()["id"]

    # Gate 1: an unapproved benchmark must not run.
    blocked = sql_client.post(f"/api/v1/benchmarks/{benchmark_id}/run", headers=operator)
    assert blocked.status_code == 409

    sql_client.post(f"/api/v1/benchmarks/{benchmark_id}/submit", json={}, headers=operator)
    sql_client.post(f"/api/v1/benchmarks/{benchmark_id}/approve", json={}, headers=reviewer)
    run = sql_client.post(f"/api/v1/benchmarks/{benchmark_id}/run", headers=operator)
    assert run.status_code == 200, run.text

    results = sql_client.get(f"/api/v1/benchmarks/{benchmark_id}/results", headers=operator).json()
    assert results["benchmark"]["state"] == "pending_review"  # gate 2 still ahead
    assert results["report"] is not None
    assert results["report"]["fairness"]["conditions_checksum"]

    actions = [entry["action"] for entry in results["benchmark"]["approvals"]]
    assert actions == ["submit", "approve", "run", "complete"]


def test_episode_replay_reads_from_the_artifact_store(sql_client):
    """A SQL row keeps a pointer; the trajectory comes back from storage."""
    operator = auth_headers(sql_client, OPERATOR)
    reviewer = auth_headers(sql_client, REVIEWER)

    map_id = sql_client.post("/api/v1/maps", json=bordered_map_payload()).json()["id"]
    scenario_id = sql_client.post(
        "/api/v1/scenarios", json={"map_id": map_id, "scenario": scenario_payload()}
    ).json()["id"]
    benchmark_id = sql_client.post(
        "/api/v1/benchmarks",
        json={
            "name": "sql replay",
            "map_id": map_id,
            "scenario_id": scenario_id,
            "algorithms": [{"id": "astar+dwa", "config": {}}],
            "seeds": [1],
        },
        headers=operator,
    ).json()["id"]
    sql_client.post(f"/api/v1/benchmarks/{benchmark_id}/submit", json={}, headers=operator)
    sql_client.post(f"/api/v1/benchmarks/{benchmark_id}/approve", json={}, headers=reviewer)
    sql_client.post(f"/api/v1/benchmarks/{benchmark_id}/run", headers=operator)

    episodes = sql_client.get(
        f"/api/v1/benchmarks/{benchmark_id}/episodes", headers=operator
    ).json()
    assert len(episodes) == 1
    assert episodes[0]["artifact_uri"].startswith("file://")

    replay = sql_client.get(f"/api/v1/episodes/{episodes[0]['id']}/replay", headers=operator)
    assert replay.status_code == 200, replay.text
    assert len(replay.json()["trajectory"]) > 1

    # And the diagnosis path, which needs both the row and the artifact.
    failures = sql_client.get(f"/api/v1/episodes/{episodes[0]['id']}/failures", headers=operator)
    assert failures.status_code == 200
    assert failures.json()["primary"]["category"]


def test_leaderboard_groups_accepted_results_from_sql(sql_client):
    operator = auth_headers(sql_client, OPERATOR)
    reviewer = auth_headers(sql_client, REVIEWER)

    map_id = sql_client.post("/api/v1/maps", json=bordered_map_payload()).json()["id"]
    scenario_id = sql_client.post(
        "/api/v1/scenarios", json={"map_id": map_id, "scenario": scenario_payload()}
    ).json()["id"]
    benchmark_id = sql_client.post(
        "/api/v1/benchmarks",
        json={
            "name": "sql leaderboard",
            "map_id": map_id,
            "scenario_id": scenario_id,
            "algorithms": [{"id": "astar+dwa", "config": {}}],
            "seeds": [1],
        },
        headers=operator,
    ).json()["id"]
    sql_client.post(f"/api/v1/benchmarks/{benchmark_id}/submit", json={}, headers=operator)
    sql_client.post(f"/api/v1/benchmarks/{benchmark_id}/approve", json={}, headers=reviewer)
    sql_client.post(f"/api/v1/benchmarks/{benchmark_id}/run", headers=operator)

    # Before acceptance the leaderboard stays empty: results a reviewer
    # has not accepted are not conclusions.
    assert sql_client.get("/api/v1/leaderboard", headers=operator).json()["groups"] == []

    sql_client.post(f"/api/v1/benchmarks/{benchmark_id}/accept-result", json={}, headers=reviewer)
    groups = sql_client.get("/api/v1/leaderboard", headers=operator).json()["groups"]
    assert len(groups) == 1
    assert groups[0]["entries"][0]["algorithm"] == "astar+dwa"


def test_data_outlives_the_application_instance(tmp_path, monkeypatch):
    """The point of M10: a restart does not lose anything."""
    monkeypatch.setenv("PLANBENCH_SEED_USERS", SEED_USERS)
    monkeypatch.setenv("PLANBENCH_JWT_SECRET", "test-secret-not-used-in-production")
    monkeypatch.setenv("PLANBENCH_DATABASE_URL", f"sqlite:///{tmp_path / 'restart.db'}")
    monkeypatch.setenv("PLANBENCH_DB_CREATE_ALL", "true")
    get_settings.cache_clear()

    first = create_app(artifact_dir=str(tmp_path / "artifacts"))
    with TestClient(first) as client:
        map_id = client.post("/api/v1/maps", json=bordered_map_payload()).json()["id"]
    first.state.sessions.dispose()

    # A completely separate application object, same database file.
    get_settings.cache_clear()
    second = create_app(artifact_dir=str(tmp_path / "artifacts"))
    try:
        with TestClient(second) as client:
            assert client.get(f"/api/v1/maps/{map_id}").status_code == 200
    finally:
        second.state.sessions.dispose()
        get_settings.cache_clear()


def test_in_memory_backend_loses_data_on_restart(tmp_path, monkeypatch):
    """The behaviour M10 exists to remove — asserted so it stays visible."""
    monkeypatch.setenv("PLANBENCH_SEED_USERS", SEED_USERS)
    monkeypatch.setenv("PLANBENCH_JWT_SECRET", "test-secret-not-used-in-production")
    monkeypatch.delenv("PLANBENCH_DATABASE_URL", raising=False)
    get_settings.cache_clear()

    first = create_app(artifact_dir=str(tmp_path / "artifacts"))
    assert first.state.sessions is None
    with TestClient(first) as client:
        map_id = client.post("/api/v1/maps", json=bordered_map_payload()).json()["id"]

    second = create_app(artifact_dir=str(tmp_path / "artifacts"))
    with TestClient(second, raise_server_exceptions=False) as client:
        assert client.get(f"/api/v1/maps/{map_id}").status_code == 404
    get_settings.cache_clear()
