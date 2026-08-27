"""The recommendation route over real HTTP.

The seam assertions, in the tradition of ``test_api_advice.py``: that the
route reads what is actually stored, that an empty history is the honest
tier-3 answer rather than a guess, that a missing profile is a 404 rather
than a plausible reply, and that nothing here can act — the route that
says "adopt rrtstar+dwa" must be structurally unable to adopt it.
"""

from __future__ import annotations

from typing import Any

import pytest
import yaml


@pytest.fixture
def deployment(client, alice_headers, app, tmp_path) -> str:
    """A real deployment through the real endpoint (see test_api_advice)."""
    from test_vertical_slice import write_profile

    profile_path = write_profile(tmp_path)
    app.state.decision_map_root = tmp_path
    payload = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    created = client.post("/api/v1/task-profiles", json=payload, headers=alice_headers)
    assert created.status_code == 201, created.text
    return str(created.json()["id"])


def _seed_ranked_run(app, deployment: str, *, run_id: str = "seededrun001") -> None:
    """Plant one ranked run in the store, keyed to the profile's real
    mission ids, so the endpoint has first-tier evidence to read."""
    from planbench_api.decisions import StoredDecisionRun
    from planbench_schemas.episode_context import NOMINAL_VARIANT, EpisodeContext

    a_id, b_id = "aaa111aaa111", "bbb222bbb222"
    a_eps, b_eps = [], []
    for seed in range(6):
        context = EpisodeContext(
            task_profile_id=deployment,
            mission_id="m1",
            seed=seed,
            environment_variant=NOMINAL_VARIANT,
            sample_set="evaluation",
        ).episode_context_id
        a_eps.append({"episode_context_id": context, "episode_decision_utility": 0.55})
        b_eps.append({"episode_context_id": context, "episode_decision_utility": 0.50})
    report: dict[str, Any] = {
        "comparison_pair": {
            "recommended_candidate_id": a_id,
            "runner_up_candidate_id": b_id,
        },
        "candidates": [
            {"candidate_id": a_id, "stack_label": "rrtstar+dwa", "episodes": a_eps},
            {"candidate_id": b_id, "stack_label": "astar+dwa", "episodes": b_eps},
        ],
    }
    app.state.repos.decision_runs.create(
        StoredDecisionRun(
            id=run_id,
            task_profile_id=deployment,
            artifact_kind="decision_card",
            contracts_version="6.6.0",
            created_at="2026-08-21T00:00:00Z",
            created_by=None,
            report=report,
            card={"recommended": {"stack": "rrtstar+dwa", "candidate_id": a_id}},
            recommended_candidate_id=a_id,
            status="CLEAR_RECOMMENDATION",
        )
    )


class TestTheRouteIsClosed:
    def test_authentication_is_required(self, anonymous):
        assert anonymous.get("/api/v1/task-profiles/x/recommendation").status_code == 401

    def test_an_unknown_profile_is_a_404_not_a_plausible_answer(self, client, alice_headers):
        response = client.get(
            "/api/v1/task-profiles/never_declared/recommendation", headers=alice_headers
        )
        assert response.status_code == 404

    def test_the_route_publishes_only_get(self, client):
        paths = client.get("/openapi.json").json()["paths"]
        path = "/api/v1/task-profiles/{profile_id}/recommendation"
        assert path in paths
        assert set(paths[path]) == {"get"}


class TestEmptyHistoryIsTierThree:
    def test_no_runs_yields_the_honest_answer(self, client, alice_headers, deployment):
        response = client.get(
            f"/api/v1/task-profiles/{deployment}/recommendation", headers=alice_headers
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["evidence_tier"] == 3
        assert body["runs_considered"] == []
        assert body["cases"] == []
        codes = {item["code"] for item in body["advice"]}
        assert "RC_NO_COMPARABLE_HISTORY" in codes
        # Twelve rules looked; the count is what distinguishes "none
        # objected" from "nothing ran".
        from planbench_benchmark.recommendation import RECOMMENDATION_CODES

        assert body["rules_applied"] == len(RECOMMENDATION_CODES)

    def test_asking_creates_nothing(self, client, alice_headers, deployment):
        before = client.get("/api/v1/decisions", headers=alice_headers).json()
        client.get(f"/api/v1/task-profiles/{deployment}/recommendation", headers=alice_headers)
        assert client.get("/api/v1/decisions", headers=alice_headers).json() == before


class TestStoredEvidenceIsTierOne:
    def test_a_ranked_run_is_read_and_split_per_mission(
        self, client, alice_headers, app, deployment
    ):
        _seed_ranked_run(app, deployment)
        response = client.get(
            f"/api/v1/task-profiles/{deployment}/recommendation", headers=alice_headers
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["evidence_tier"] == 1
        assert body["runs_considered"] == ["seededrun001"]
        (case,) = body["cases"]
        assert case["mission_id"] == "m1"
        assert case["status"] == "CLEAR"
        assert case["winner_stack"] == "rrtstar+dwa"
        codes = {item["code"] for item in body["advice"]}
        assert "RC_CARD_ON_THIS_PROFILE" in codes
        assert "RC_CASE_WINNER" in codes
        # One mission ⇒ the per-case question is honestly unanswerable.
        assert "RC_SINGLE_CASE_ONLY" in codes

    def test_the_model_layer_keeps_the_floor(self, client, alice_headers, app, deployment):
        """use_model with the deterministic mock: the rules survive
        whatever the provider does, because the floor is not its to
        remove."""
        _seed_ranked_run(app, deployment)
        plain = client.get(
            f"/api/v1/task-profiles/{deployment}/recommendation", headers=alice_headers
        ).json()
        modelled = client.get(
            f"/api/v1/task-profiles/{deployment}/recommendation?use_model=true",
            headers=alice_headers,
        )
        assert modelled.status_code == 200, modelled.text
        floor = {item["code"] for item in plain["advice"]}
        kept = {item["code"] for item in modelled.json()["advice"]}
        assert floor <= kept
