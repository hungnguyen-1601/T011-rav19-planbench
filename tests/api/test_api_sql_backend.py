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
from conftest import ALICE, BOB, auth_headers, isolate_environment
from fastapi.testclient import TestClient
from payloads import bordered_map_payload, scenario_payload

from planbench_api.config import get_settings
from planbench_api.db.repositories import SqlRepositoryHub
from planbench_api.main import create_app


@pytest.fixture
def sql_app(tmp_path, monkeypatch):
    isolate_environment(monkeypatch)
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
    """Signed in as alice, matching the in-memory ``client`` fixture.

    Reading a stored map or a run needs an account now, so an anonymous
    client would test the door rather than the storage these cases are
    about.
    """
    signed_in = TestClient(sql_app, raise_server_exceptions=False)
    signed_in.headers.update(auth_headers(signed_in, ALICE))
    return signed_in


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
    """The reviewed path end to end, over SQL.

    Deliberately the two-person flow: it is the only one that writes
    review-request rows, so it proves accounts, requests and the audit
    trail all survive the database round trip together.
    """
    operator = auth_headers(sql_client, ALICE)
    reviewer = auth_headers(sql_client, BOB)

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

    # Sent for review by nickname, and stored.
    request = sql_client.post(
        f"/api/v1/benchmarks/{benchmark_id}/review-requests",
        json={"reviewer_nickname": "bob", "stage": "spec", "comment": "fair?"},
        headers=operator,
    )
    assert request.status_code == 201, request.text
    request_id = request.json()["id"]

    # Gate 1: while it is pending, not even the owner may run it.
    blocked = sql_client.post(f"/api/v1/benchmarks/{benchmark_id}/run", headers=operator)
    assert blocked.status_code == 403

    inbox = sql_client.get("/api/v1/reviews/inbox", headers=reviewer).json()
    assert inbox["pending"] == 1
    assert inbox["requests"][0]["requested_by"]["nickname"] == "alice"

    approved = sql_client.post(
        f"/api/v1/reviews/{request_id}/approve", json={"comment": "ok"}, headers=reviewer
    )
    assert approved.status_code == 200, approved.text

    run = sql_client.post(f"/api/v1/benchmarks/{benchmark_id}/run", headers=operator)
    assert run.status_code == 200, run.text

    results = sql_client.get(f"/api/v1/benchmarks/{benchmark_id}/results", headers=operator).json()
    assert results["benchmark"]["state"] == "pending_review"  # gate 2 still ahead
    assert results["report"] is not None
    assert results["report"]["fairness"]["conditions_checksum"]

    actions = [entry["action"] for entry in results["benchmark"]["approvals"]]
    assert actions == ["submit", "request_review", "approve", "run", "complete"]
    # The reviewer's approval is traceable to the request that asked for it.
    approval = next(e for e in results["benchmark"]["approvals"] if e["action"] == "approve")
    assert approval["review_request_id"] == request_id
    assert approval["user"] == "bob"
    assert approval["user_id"]


def test_episode_replay_reads_from_the_artifact_store(sql_client):
    """A SQL row keeps a pointer; the trajectory comes back from storage."""
    operator = auth_headers(sql_client, ALICE)

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
    operator = auth_headers(sql_client, ALICE)

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
    sql_client.post(f"/api/v1/benchmarks/{benchmark_id}/run", headers=operator)

    # Before acceptance the leaderboard stays empty: results nobody has
    # accepted are not conclusions.
    assert sql_client.get("/api/v1/leaderboard", headers=operator).json()["groups"] == []

    sql_client.post(f"/api/v1/benchmarks/{benchmark_id}/accept-result", json={}, headers=operator)
    groups = sql_client.get("/api/v1/leaderboard", headers=operator).json()["groups"]
    assert len(groups) == 1
    assert groups[0]["entries"][0]["algorithm"] == "astar+dwa"


def test_data_outlives_the_application_instance(tmp_path, monkeypatch):
    """The point of M10: a restart does not lose anything."""
    isolate_environment(monkeypatch)
    monkeypatch.setenv("PLANBENCH_DATABASE_URL", f"sqlite:///{tmp_path / 'restart.db'}")
    monkeypatch.setenv("PLANBENCH_DB_CREATE_ALL", "true")
    get_settings.cache_clear()

    first = create_app(artifact_dir=str(tmp_path / "artifacts"))
    with TestClient(first) as client:
        client.headers.update(auth_headers(client, ALICE))
        map_id = client.post("/api/v1/maps", json=bordered_map_payload()).json()["id"]
    first.state.sessions.dispose()

    # A completely separate application object, same database file.
    get_settings.cache_clear()
    second = create_app(artifact_dir=str(tmp_path / "artifacts"))
    try:
        with TestClient(second) as client:
            client.headers.update(auth_headers(client, ALICE))
            assert client.get(f"/api/v1/maps/{map_id}").status_code == 200
    finally:
        second.state.sessions.dispose()
        get_settings.cache_clear()


def test_in_memory_backend_loses_data_on_restart(tmp_path, monkeypatch):
    """The behaviour M10 exists to remove — asserted so it stays visible."""
    isolate_environment(monkeypatch)
    monkeypatch.delenv("PLANBENCH_DATABASE_URL", raising=False)
    get_settings.cache_clear()

    first = create_app(artifact_dir=str(tmp_path / "artifacts"))
    assert first.state.sessions is None
    with TestClient(first) as client:
        client.headers.update(auth_headers(client, ALICE))
        map_id = client.post("/api/v1/maps", json=bordered_map_payload()).json()["id"]

    second = create_app(artifact_dir=str(tmp_path / "artifacts"))
    with TestClient(second, raise_server_exceptions=False) as client:
        client.headers.update(auth_headers(client, ALICE))
        assert client.get(f"/api/v1/maps/{map_id}").status_code == 404
    get_settings.cache_clear()


def test_a_benchmark_from_before_accounts_is_still_owned_by_its_creator(sql_client, sql_app):
    """Rows written before this refactor have no owner id.

    They must not be stranded: the fallback compares the stored creator
    *name* against the caller's nickname. It is a weaker check, which is
    why it applies only where the strong one is absent — a member who
    later takes that nickname must not inherit the benchmark, and that
    is what the second half asserts.
    """
    from sqlalchemy import text

    alice = auth_headers(sql_client, ALICE)
    bob = auth_headers(sql_client, BOB)

    map_id = sql_client.post("/api/v1/maps", json=bordered_map_payload()).json()["id"]
    scenario_id = sql_client.post(
        "/api/v1/scenarios", json={"map_id": map_id, "scenario": scenario_payload()}
    ).json()["id"]
    benchmark_id = sql_client.post(
        "/api/v1/benchmarks",
        json={
            "name": "legacy",
            "map_id": map_id,
            "scenario_id": scenario_id,
            "algorithms": [{"id": "astar+dwa"}],
            "seeds": [1],
        },
        headers=alice,
    ).json()["id"]

    # Make it look like a row written before owner_user_id existed.
    with sql_app.state.sessions.begin() as session:
        session.execute(
            text("UPDATE benchmarks SET owner_user_id = NULL WHERE id = :id"),
            {"id": benchmark_id},
        )

    assert sql_client.get(f"/api/v1/benchmarks/{benchmark_id}", headers=alice).json()["is_owner"]
    assert not sql_client.get(f"/api/v1/benchmarks/{benchmark_id}", headers=bob).json()["is_owner"]
    # And she can still run it.
    assert (
        sql_client.post(f"/api/v1/benchmarks/{benchmark_id}/run", headers=alice).status_code == 200
    )
    assert sql_client.post(f"/api/v1/benchmarks/{benchmark_id}/run", headers=bob).status_code in (
        403,
        409,
    )


def test_a_schema_one_migration_behind_does_not_take_the_api_down(tmp_path, monkeypatch):
    """A database without `plugin_bundles` must cost imported algorithms,
    not the whole process.

    This is a regression test for an outage, not a hypothetical. The
    startup catalogue sync queried the table unguarded, so a checkout
    that had taken the update without running `alembic upgrade head`
    died inside `create_app` — before a single route was served, with a
    SQL traceback naming nothing an operator could act on. Everything
    unrelated to imported algorithms was working perfectly.

    Built by creating the whole schema and then dropping the one table,
    which is exactly the shape a pending migration leaves behind.
    """
    isolate_environment(monkeypatch)
    database = tmp_path / "stale.db"
    monkeypatch.setenv("PLANBENCH_DATABASE_URL", f"sqlite:///{database}")
    monkeypatch.setenv("PLANBENCH_DB_CREATE_ALL", "true")
    get_settings.cache_clear()
    try:
        warmed = create_app(artifact_dir=str(tmp_path / "artifacts"))
        warmed.state.sessions.dispose()

        import sqlite3

        with sqlite3.connect(database) as connection:
            connection.execute("DROP TABLE plugin_bundles")

        # The assertion is that this line returns at all.
        monkeypatch.setenv("PLANBENCH_DB_CREATE_ALL", "false")
        get_settings.cache_clear()
        application = create_app(artifact_dir=str(tmp_path / "artifacts"))
        client = TestClient(application, raise_server_exceptions=False)
        # Built-in algorithms are still offered; only imported ones are not.
        listed = client.get("/api/v1/algorithms", headers=auth_headers(client, ALICE)).json()
        assert any(row["id"] == "astar+dwa" for row in listed)
        application.state.sessions.dispose()
    finally:
        get_settings.cache_clear()
