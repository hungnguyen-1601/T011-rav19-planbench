"""The two E2 endpoints, exercised over HTTP.

These exist because the first version of the exemplar endpoint chose its
pair by report order while the page drew the card's pair, and every
source-text assertion on both sides passed. Only a call that seeds a
report whose order disagrees with its ranking catches that.
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


def seed_run(
    app,
    run_id: str,
    *,
    card: dict[str, object] | None,
    candidates: list[dict[str, object]],
    pair: dict[str, str] | None = None,
) -> None:
    """One stored run, filed directly.

    A real sweep would spend minutes of simulation to produce the same
    row, and none of it is what these tests are about.
    """
    from planbench_api.decisions import StoredDecisionRun

    report = {
        "candidates": candidates,
        "decision_card": card,
        # What a real ranked run stores. Deliberately *not* taken from
        # the card: `alternative` there is a Pareto claim and is null on
        # an ordinary run, so a fixture that parked the runner-up in it
        # would be testing a card shape the platform never writes.
        "comparison_pair": pair,
        "sample": {"episode_context_ids": ["ep00", "ep01", "ep02"]},
    }
    app.state.repos.decision_runs.create(
        StoredDecisionRun(
            id=run_id,
            task_profile_id="warehouse_a_v1",
            artifact_kind="decision_card" if card else "comparison",
            experiment_scope="global_planner_selection",
            contracts_version="6.9.0",
            created_at="2026-08-19T10:00:00Z",
            created_by=None,
            report=report,
            card=card,
            manifest=None,
            recommended_candidate_id="winner" if card else None,
            status="recommended" if card else "unranked",
        )
    )


def scored(candidate_id: str, utilities: list[float], **row_overrides: object) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "episodes": [
            episode_row(f"ep{index:02d}", value, **row_overrides)
            for index, value in enumerate(utilities)
        ],
    }


#: An ordinary ranked run's card. ``alternative`` is null because HĐ-12
#: lets it name only a PARETO_FRONTIER candidate and no Pareto analysis
#: ran — which is exactly why the pair cannot be read from here.
CARD = {
    "recommended": {"candidate_id": "winner"},
    "alternative": None,
}

PAIR = {"recommended_candidate_id": "winner", "runner_up_candidate_id": "runner_up"}


class TestExemplars:
    def test_the_pair_comes_from_the_card_not_from_report_order(
        self, client: TestClient, app, alice_headers: dict[str, str]
    ) -> None:
        """Three candidates, and list order disagrees with the ranking.

        The eliminated candidate is first in the report and carries no
        utility at all; the winner is last. Choosing "the first two with
        utility" would compare the runner-up against the winner with the
        roles reversed, and label the runner-up's best episode as the
        winner's.
        """
        seed_run(
            app,
            "run_pairing",
            card=CARD,
            pair=PAIR,
            candidates=[
                {"candidate_id": "eliminated", "episodes": []},
                scored("runner_up", [0.50, 0.50, 0.50]),
                scored("winner", [0.55, 0.90, 0.40]),
            ],
        )

        body = client.get(f"{API}/decisions/run_pairing/exemplars", headers=alice_headers).json()

        assert body["candidate_a"] == "winner"
        assert body["candidate_b"] == "runner_up"
        roles = {item["role"]: item for item in body["exemplars"]}
        # ΔU is [+0.05, +0.40, −0.10]: the winner's best is ep01 and the
        # runner-up's is ep02, which is only true with the pair the right
        # way round.
        assert roles["strongest_for_winner"]["episode_context_id"] == "ep01"
        assert roles["strongest_for_runnerup"]["episode_context_id"] == "ep02"

    def test_a_run_that_ranked_nobody_has_no_exemplars(
        self, client: TestClient, app, alice_headers: dict[str, str]
    ) -> None:
        seed_run(
            app,
            "run_no_card",
            card=None,
            candidates=[scored("a", [0.6, 0.7, 0.8]), scored("b", [0.5, 0.5, 0.5])],
        )

        response = client.get(f"{API}/decisions/run_no_card/exemplars", headers=alice_headers)

        # A state, not a server fault and not a malformed request.
        assert response.status_code == 409
        assert "winner" in response.json()["error"]["message"]

    def test_a_run_scored_before_the_column_existed_says_so(
        self, client: TestClient, app, alice_headers: dict[str, str]
    ) -> None:
        """The old-run case a reader will actually hit.

        Reported as a 409 with a message naming the fix, rather than as
        a 500 that files an expected data state as an internal error.
        """
        seed_run(
            app,
            "run_old",
            card=CARD,
            pair=PAIR,
            candidates=[
                scored("winner", [None, None, None]),  # type: ignore[list-item]
                scored("runner_up", [None, None, None]),  # type: ignore[list-item]
            ],
        )

        response = client.get(f"{API}/decisions/run_old/exemplars", headers=alice_headers)

        assert response.status_code == 409
        assert "scored again" in response.json()["error"]["message"]

    def test_an_unknown_run_is_a_404(
        self, client: TestClient, alice_headers: dict[str, str]
    ) -> None:
        assert (
            client.get(f"{API}/decisions/nope/exemplars", headers=alice_headers).status_code == 404
        )


class TestReplaySync:
    def test_an_absurd_step_count_is_refused_before_any_work(
        self, client: TestClient, app, alice_headers: dict[str, str]
    ) -> None:
        """One query parameter sizes both a loop and the response body.

        Unbounded, ``?steps=1000000000`` is a request for four billion
        floats from a route that needs no login.
        """
        seed_run(app, "run_steps", card=CARD, pair=PAIR, candidates=[scored("winner", [0.6])])

        response = client.get(
            f"{API}/decisions/run_steps/replay-sync/ep00",
            params={"candidate_a": "winner", "candidate_b": "runner_up", "steps": 1_000_000_000},
            headers=alice_headers,
        )

        assert response.status_code == 422

    def test_one_step_is_refused_too(
        self, client: TestClient, app, alice_headers: dict[str, str]
    ) -> None:
        seed_run(app, "run_steps_low", card=CARD, pair=PAIR, candidates=[scored("winner", [0.6])])

        response = client.get(
            f"{API}/decisions/run_steps_low/replay-sync/ep00",
            params={"candidate_a": "winner", "candidate_b": "runner_up", "steps": 1},
            headers=alice_headers,
        )

        assert response.status_code == 422

    def test_a_candidate_outside_the_run_is_a_404_not_a_500(
        self, client: TestClient, app, alice_headers: dict[str, str]
    ) -> None:
        seed_run(app, "run_sync", card=CARD, pair=PAIR, candidates=[scored("winner", [0.6])])

        response = client.get(
            f"{API}/decisions/run_sync/replay-sync/ep00",
            params={"candidate_a": "winner", "candidate_b": "ghost"},
            headers=alice_headers,
        )

        assert response.status_code == 404


class TestTheExplanationRoute:
    """E4.1 — the case packet, served from what the scoring pass wrote."""

    def _packet_block(self) -> dict[str, object]:
        """A packet built the way the scoring pass builds one."""
        from test_explanation_e41 import report_with_components, waterfall

        from planbench_explanation.catalog import TOOL_CATALOG_VERSION
        from planbench_explanation.detectors import DETECTOR_VERSION
        from planbench_explanation.knowledge import KNOWLEDGE_BASE_VERSION
        from planbench_explanation.packet_builder import build_scoring_packet, packet_block

        return packet_block(
            build_scoring_packet(
                run_id="run_packet",
                source_manifest_ref="manifest.json",
                source_manifest_checksum="a" * 64,
                detector_version=DETECTOR_VERSION,
                knowledge_base_version=KNOWLEDGE_BASE_VERSION,
                tool_catalog_version=TOOL_CATALOG_VERSION,
                task_profile_id="warehouse_a_v1",
                robot_radius_m=0.26,
                inflation_margin_m=0.11,
                decision_status="CLEAR_RECOMMENDATION",
                waterfall=waterfall(),
                report=report_with_components(),
                traces=[],
                episodes_total=0,
                evidence_class="production",
            )
        )

    def test_a_scored_run_serves_its_packet(
        self, client: TestClient, app, alice_headers: dict[str, str]
    ) -> None:
        seed_run(app, "run_packet", card=None, candidates=[])
        stored = app.state.repos.decision_runs.get("run_packet")
        stored.report["case_packet"] = self._packet_block()

        response = client.get(f"{API}/decisions/run_packet/explanation", headers=alice_headers)

        assert response.status_code == 200
        body = response.json()
        assert body["packet"]["task"]["task_profile_id"] == "warehouse_a_v1"
        assert body["packet"]["decision"]["waterfall"]["candidate_a"] == "cand_a"

    def test_the_packet_carries_the_gaps_the_platform_declares(
        self, client: TestClient, app, alice_headers: dict[str, str]
    ) -> None:
        """Evidence with the holes named, which is the point of the packet."""
        seed_run(app, "run_packet", card=None, candidates=[])
        app.state.repos.decision_runs.get("run_packet").report["case_packet"] = self._packet_block()

        body = client.get(f"{API}/decisions/run_packet/explanation", headers=alice_headers).json()

        blocked = {
            kind for gap in body["packet"]["known_unknowns"] for kind in gap["blocks_claim_types"]
        }
        assert "perception_attribution" in blocked

    def test_a_thin_packet_says_why_it_is_thin(
        self, client: TestClient, app, alice_headers: dict[str, str]
    ) -> None:
        """Whoever asks why an explanation is thin should not have to guess."""
        seed_run(app, "run_packet", card=None, candidates=[])
        app.state.repos.decision_runs.get("run_packet").report["case_packet"] = self._packet_block()

        body = client.get(f"{API}/decisions/run_packet/explanation", headers=alice_headers).json()

        assert any("no episode traces" in note for note in body["omissions"])

    def test_a_run_scored_before_e41_answers_409_not_an_empty_packet(
        self, client: TestClient, app, alice_headers: dict[str, str]
    ) -> None:
        """ "No packet" and "nothing to explain" are different facts."""
        seed_run(app, "run_old", card=None, candidates=[])

        response = client.get(f"{API}/decisions/run_old/explanation", headers=alice_headers)

        assert response.status_code == 409
        assert "scored before E4.1" in response.json()["error"]["message"]

    def test_a_run_with_no_card_serves_evidence_without_a_comparison(
        self, client: TestClient, app, alice_headers: dict[str, str]
    ) -> None:
        """E4.2 — the runs somebody most asks "why did it fail" about.

        No pair, so no waterfall and no exemplars. Everything else is
        still a fact about this run, and the route serves it rather than
        answering 409 to the one question the run provoked.
        """
        from planbench_explanation.packet_builder import packet_block
        from test_explanation_e41 import built

        seed_run(app, "run_no_pair", card=None, candidates=[])
        app.state.repos.decision_runs.get("run_no_pair").report["case_packet"] = packet_block(
            built(waterfall=None, decision_status="NO_DECISION_CARD")
        )

        body = client.get(
            f"{API}/decisions/run_no_pair/explanation", headers=alice_headers
        ).json()

        assert body["packet"]["decision"]["waterfall"] is None
        assert body["packet"]["decision"]["status"] == "NO_DECISION_CARD"
        assert body["packet"]["lattice"]
        assert any("ranked nobody" in note for note in body["omissions"])
