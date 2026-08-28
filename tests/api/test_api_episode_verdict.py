"""The episode verdict endpoint, over HTTP.

Seeded runs rather than real sweeps: a sweep would spend minutes of
simulation to produce the same rows, and what these tests are about is
the four ways an episode can be decided and the two ways the route can
be asked wrongly.

The traces are absent throughout. That is deliberate and it is the
common case for a stored run in a test database — the endpoint still
has to answer with the verdict and say, in the omissions, that the
detectors never ran.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

API = "/api/v1"


def episode_row(context: str, utility: float | None, **overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "episode_context_id": context,
        "success": True,
        "failure_reason": None,
        "collision_count": 0,
        "min_clearance": 0.45,
        "travel_time_s": 60.0,
        "p99_latency_ms": 25.0,
        "replan_count": 0,
        "episode_decision_utility": utility,
    }
    row.update(overrides)
    return row


def candidate(
    candidate_id: str,
    rows: list[dict[str, object]],
    *,
    global_planner: str = "astar",
) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "stack_label": f"{global_planner}+dwa",
        "components": {
            "global_planner": global_planner,
            "local_controller": "dwa",
            "local_controller_config": "dwa_coarse",
        },
        "episodes": rows,
    }


PAIR = {"recommended_candidate_id": "winner", "runner_up_candidate_id": "runner_up"}


def seed(
    app,
    run_id: str,
    *,
    candidates: list[dict[str, object]],
    pair: dict[str, str] | None = PAIR,
) -> None:
    from planbench_api.decisions import StoredDecisionRun

    app.state.repos.decision_runs.create(
        StoredDecisionRun(
            id=run_id,
            task_profile_id="warehouse_a_v1",
            artifact_kind="comparison",
            experiment_scope="global_planner_selection",
            contracts_version="6.9.0",
            created_at="2026-08-27T10:00:00Z",
            created_by=None,
            report={
                "candidates": candidates,
                "comparison_pair": pair,
                "sample": {"episode_context_ids": ["ep00", "ep01"]},
            },
            card=None,
            manifest=None,
            recommended_candidate_id=None,
            status="unranked",
        )
    )


def verdict_of(client: TestClient, run_id: str, episode: str, headers, **params):  # type: ignore[no-untyped-def]
    return client.get(
        f"{API}/decisions/{run_id}/episodes/{episode}/verdict",
        headers=headers,
        params=params,
    )


class TestWhichSideTheEpisodeWentTo:
    def test_utility_decides_and_the_margin_says_it_is_one_episode(
        self, client: TestClient, app, alice_headers: dict[str, str]
    ) -> None:
        seed(
            app,
            "run_ep_utility",
            candidates=[
                candidate("winner", [episode_row("ep00", 0.88)]),
                candidate("runner_up", [episode_row("ep00", 0.71)], global_planner="rrtstar"),
            ],
        )
        response = verdict_of(client, "run_ep_utility", "ep00", alice_headers)
        assert response.status_code == 200, response.json()
        body = response.json()
        assert body["verdict"]["basis"] == "episode_decision_utility"
        assert body["verdict"]["winner"] == "winner"
        assert body["verdict"]["delta_utility"]["denominator"] == 1

    def test_a_missing_row_is_not_a_defeat(
        self, client: TestClient, app, alice_headers: dict[str, str]
    ) -> None:
        """The candidate may never have run this episode, or a gate may have
        eliminated it first. Neither is losing."""
        seed(
            app,
            "run_ep_missing",
            candidates=[
                candidate("winner", [episode_row("ep00", 0.88)]),
                candidate("runner_up", [], global_planner="rrtstar"),
            ],
        )
        body = verdict_of(client, "run_ep_missing", "ep00", alice_headers).json()
        assert body["verdict"]["basis"] == "not_comparable"
        assert body["verdict"]["winner"] is None

    def test_two_unlike_failures_decline_to_rank(
        self, client: TestClient, app, alice_headers: dict[str, str]
    ) -> None:
        seed(
            app,
            "run_ep_failures",
            candidates=[
                candidate(
                    "winner",
                    [episode_row("ep00", None, success=False, failure_reason="collision")],
                ),
                candidate(
                    "runner_up",
                    [episode_row("ep00", None, success=False, failure_reason="timeout")],
                    global_planner="rrtstar",
                ),
            ],
        )
        body = verdict_of(client, "run_ep_failures", "ep00", alice_headers).json()
        assert body["verdict"]["basis"] == "undecidable"
        assert body["verdict"]["winner"] is None

    def test_success_against_failure_ranks_without_utility(
        self, client: TestClient, app, alice_headers: dict[str, str]
    ) -> None:
        seed(
            app,
            "run_ep_outcome",
            candidates=[
                candidate("winner", [episode_row("ep00", None)]),
                candidate(
                    "runner_up",
                    [episode_row("ep00", None, success=False, failure_reason="timeout")],
                    global_planner="rrtstar",
                ),
            ],
        )
        body = verdict_of(client, "run_ep_outcome", "ep00", alice_headers).json()
        assert body["verdict"]["basis"] == "outcome_only"
        assert body["verdict"]["winner"] == "winner"


class TestWhichTwoAreCompared:
    def test_the_pair_comes_from_the_run_and_not_from_list_order(
        self, client: TestClient, app, alice_headers: dict[str, str]
    ) -> None:
        """The eliminated candidate is listed first and carries no utility.
        Taking "the first two" would compare the wrong pair and label the
        runner-up's episode as the winner's."""
        seed(
            app,
            "run_ep_order",
            candidates=[
                candidate("eliminated", [episode_row("ep00", None)]),
                candidate("runner_up", [episode_row("ep00", 0.71)], global_planner="rrtstar"),
                candidate("winner", [episode_row("ep00", 0.88)]),
            ],
        )
        body = verdict_of(client, "run_ep_order", "ep00", alice_headers).json()
        assert {body["candidate_a"], body["candidate_b"]} == {"winner", "runner_up"}

    def test_a_run_that_ranked_nobody_refuses_rather_than_picking(
        self, client: TestClient, app, alice_headers: dict[str, str]
    ) -> None:
        seed(
            app,
            "run_ep_unranked",
            candidates=[
                candidate("one", [episode_row("ep00", 0.88)]),
                candidate("two", [episode_row("ep00", 0.71)], global_planner="rrtstar"),
            ],
            pair=None,
        )
        response = verdict_of(client, "run_ep_unranked", "ep00", alice_headers)
        assert response.status_code == 409

    def test_an_explicit_pair_overrides_the_default(
        self, client: TestClient, app, alice_headers: dict[str, str]
    ) -> None:
        seed(
            app,
            "run_ep_explicit",
            candidates=[
                candidate("one", [episode_row("ep00", 0.88)]),
                candidate("two", [episode_row("ep00", 0.71)], global_planner="rrtstar"),
            ],
            pair=None,
        )
        body = verdict_of(
            client,
            "run_ep_explicit",
            "ep00",
            alice_headers,
            candidate_a="one",
            candidate_b="two",
        ).json()
        assert body["verdict"]["winner"] == "one"

    def test_an_unknown_run_is_a_404(
        self, client: TestClient, alice_headers: dict[str, str]
    ) -> None:
        assert verdict_of(client, "no_such_run", "ep00", alice_headers).status_code == 404


class TestWhatComesBackBesideTheVerdict:
    def _body(self, client: TestClient, app, headers: dict[str, str]) -> dict[str, object]:
        seed(
            app,
            "run_ep_shape",
            candidates=[
                candidate("winner", [episode_row("ep00", 0.88)]),
                candidate("runner_up", [episode_row("ep00", 0.71)], global_planner="rrtstar"),
            ],
        )
        return verdict_of(client, "run_ep_shape", "ep00", headers).json()

    def test_both_sides_get_a_diagnosis(
        self, client: TestClient, app, alice_headers: dict[str, str]
    ) -> None:
        body = self._body(client, app, alice_headers)
        assert [item["candidate_id"] for item in body["diagnoses"]] == ["winner", "runner_up"]

    def test_a_missing_trace_is_written_down_rather_than_hidden(
        self, client: TestClient, app, alice_headers: dict[str, str]
    ) -> None:
        """No trace means the detectors never ran, which is not the same as
        having looked and found nothing."""
        body = self._body(client, app, alice_headers)
        assert any("no trace was served" in note for note in body["omissions"])

    def test_the_caveat_travels_with_the_verdict(
        self, client: TestClient, app, alice_headers: dict[str, str]
    ) -> None:
        body = self._body(client, app, alice_headers)
        assert "not the run's verdict" in body["verdict"]["caveat"]

    def test_the_floor_answers_too_and_says_so_when_it_abstains(
        self, client: TestClient, app, alice_headers: dict[str, str]
    ) -> None:
        """With no traces there is nothing detected, so the model-free floor
        has nothing to say — and saying nothing is the right answer, not an
        empty section."""
        body = self._body(client, app, alice_headers)
        assert body["floor"]["abstained"] is True
        assert body["floor"]["proposals"] == []

    def test_nothing_here_needs_a_model(
        self, client: TestClient, app, alice_headers: dict[str, str]
    ) -> None:
        """The route is the deterministic half of the feature and ships
        without any model being configured."""
        body = self._body(client, app, alice_headers)
        assert "model" not in body
        assert "audit" not in body


class TestWhatTheAnswerSurvivesWithout:
    def test_a_run_whose_deployment_is_gone_still_gets_its_verdict(
        self, client: TestClient, app, alice_headers: dict[str, str]
    ) -> None:
        """A run outlives the profile it was run under, and the verdict needs
        none of it: the rows were scored while the profile still existed.
        What a missing deployment costs is the timeline and the geometry,
        and the answer says so rather than refusing."""
        seed(
            app,
            "run_ep_no_profile",
            candidates=[
                candidate("winner", [episode_row("ep00", 0.88)]),
                candidate("runner_up", [episode_row("ep00", 0.71)], global_planner="rrtstar"),
            ],
        )
        response = verdict_of(client, "run_ep_no_profile", "ep00", alice_headers)
        assert response.status_code == 200, response.json()
        body = response.json()
        assert body["verdict"]["winner"] == "winner"
        assert body["packet"]["timelines"] == []
