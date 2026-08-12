"""Deployments, candidates and selection runs over HTTP (Phase 6.2).

The endpoints are thin — every rule they rely on is enforced one layer
down, and these tests check that the thinness is real rather than that
the rules exist (the contract layer has its own suite for that).

Two properties get most of the attention because they are the ones an
API can quietly get wrong:

1. **A run that could not be ranked is still a result.** Fewer than two
   candidates through the gates means no ΔU and no Decision Card, and
   the gate table is then the whole deliverable. ``POST /decisions``
   answers 201 for that case; a 4xx would tell the caller their request
   was wrong when the platform in fact answered the question they asked.
2. **A deployment id cannot be redefined.** ``episode_context_id`` does
   not hash the environment (HĐ-3.1), so re-filing a changed profile
   under an old id would make every stored run describe a world that no
   longer exists, with nothing to warn anyone.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
API = "/api/v1"


def hall_profile() -> dict:
    """The shipped fairness deployment, read from the repository.

    A hand-written fixture would drift from the real profile and would
    stop exercising the validators that matter (heading reservation,
    full-period traffic offset, RAM budget arithmetic).
    """
    path = REPO_ROOT / "profiles" / "open_hall_v2.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def tiny_profile() -> dict:
    """The hall, cut down to something a test can run to completion.

    Only the episode budget changes: a 50% accepted collision risk makes
    ``N_min`` 6 (HĐ-7.1) and a 25 s timeout keeps a stalled episode
    short. The map, the mission and the noise are the shipped ones, so
    what runs here is the real chain on the real deployment.
    """
    profile = hall_profile()
    profile["id"] = "api_hall_tiny"
    profile["constraints"]["collision_probability_max"] = 0.5
    profile["constraints"]["episode_timeout_s"] = 25
    profile["constraints"]["stuck_threshold_s"] = 4
    return profile


@pytest.fixture
def profile_id(client: TestClient, alice_headers: dict[str, str]) -> str:
    response = client.post(f"{API}/task-profiles", json=tiny_profile(), headers=alice_headers)
    assert response.status_code == 201, response.text
    return response.json()["id"]


class TestDeployments:
    def test_a_profile_round_trips(self, client, alice_headers):
        created = client.post(f"{API}/task-profiles", json=tiny_profile(), headers=alice_headers)
        assert created.status_code == 201, created.text
        body = created.json()
        assert body["id"] == "api_hall_tiny"
        assert body["environment"] == "maps/open_hall.pgm"

        fetched = client.get(f"{API}/task-profiles/{body['id']}")
        assert fetched.status_code == 200
        assert fetched.json()["profile"] == body["profile"]

    def test_the_noise_amplitudes_survive_storage(self, client, alice_headers):
        """HĐ-13: two runs at the same seeds under different sigma are
        two experiments, and ``episode_context_id`` does not tell them
        apart. If the amplitudes were dropped on the way into storage,
        nothing downstream could."""
        client.post(f"{API}/task-profiles", json=tiny_profile(), headers=alice_headers)
        stored = client.get(f"{API}/task-profiles/api_hall_tiny").json()["profile"]
        assert stored["environment"]["sensor_noise"] == {
            "lidar_range_sigma_m": 0.02,
            "wheel_slip_fraction": 0.02,
        }

    def test_refiling_the_same_content_is_idempotent(self, client, alice_headers):
        first = client.post(f"{API}/task-profiles", json=tiny_profile(), headers=alice_headers)
        second = client.post(f"{API}/task-profiles", json=tiny_profile(), headers=alice_headers)
        assert second.status_code == 201
        assert second.json()["created_at"] == first.json()["created_at"]

    def test_redefining_an_id_is_refused(self, client, alice_headers):
        """The trap this closes: ``episode_context_id`` hashes
        ``(task_profile_id, mission_id, environment_variant, seed)`` and
        HĐ-3.1 freezes that payload, so a changed deployment under an old
        id produces contexts hashing identically to the old ones — and
        every stored run pointing there silently describes a world that
        no longer exists."""
        client.post(f"{API}/task-profiles", json=tiny_profile(), headers=alice_headers)
        changed = tiny_profile()
        changed["environment"]["sensor_noise"]["lidar_range_sigma_m"] = 0.05
        response = client.post(f"{API}/task-profiles", json=changed, headers=alice_headers)
        assert response.status_code == 409, response.text
        assert "new id" in response.json()["error"]["message"]

    def test_a_profile_that_breaks_the_contract_is_refused(self, client, alice_headers):
        """Validation belongs to ``TaskProfile``, not to the router. A
        heading requirement is the case the platform cannot evaluate at
        all (HĐ-6 reservation)."""
        invalid = tiny_profile()
        invalid["constraints"]["goal_tolerance_rad"] = 0.35
        response = client.post(f"{API}/task-profiles", json=invalid, headers=alice_headers)
        assert response.status_code == 422
        assert "HĐ-6" in response.json()["error"]["message"]


class TestCandidates:
    def test_the_server_computes_the_id(self, client, alice_headers):
        """HĐ-1.3. A caller-supplied id would let two configurations
        share an identity that every trace, pairing and ΔU keys on — so
        the request body has no id field at all."""
        response = client.post(
            f"{API}/candidates",
            json={"stack": "astar+dwa", "local_config": "dwa_coarse"},
            headers=alice_headers,
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["candidate_id"] and body["stack_label"] == "astar+dwa"
        assert "id" not in {*body["spec"]}

    def test_two_controllers_are_two_candidates(self, client, alice_headers):
        coarse = client.post(
            f"{API}/candidates",
            json={"stack": "astar+dwa", "local_config": "dwa_coarse"},
            headers=alice_headers,
        ).json()
        default = client.post(
            f"{API}/candidates",
            json={"stack": "astar+dwa", "local_config": "dwa_default"},
            headers=alice_headers,
        ).json()
        assert coarse["candidate_id"] != default["candidate_id"]

    def test_registering_the_same_thing_twice_is_idempotent(self, client, alice_headers):
        """The id *is* the content hash, so a second registration carries
        no new information."""
        payload = {"stack": "rrtstar+dwa", "local_config": "dwa_coarse"}
        first = client.post(f"{API}/candidates", json=payload, headers=alice_headers).json()
        second = client.post(f"{API}/candidates", json=payload, headers=alice_headers).json()
        assert first["candidate_id"] == second["candidate_id"]
        assert first["created_at"] == second["created_at"]

    def test_a_reference_only_stack_is_refused(self, client, alice_headers):
        """``*+pure_pursuit`` ignores sensing and exists to check the
        pipeline; registering it as a candidate would let a conclusion
        rest on it."""
        response = client.post(
            f"{API}/candidates",
            json={"stack": "astar+pure_pursuit", "local_config": "dwa_coarse"},
            headers=alice_headers,
        )
        assert response.status_code == 422

    def test_an_unknown_controller_is_refused_by_name(self, client, alice_headers):
        response = client.post(
            f"{API}/candidates",
            json={"stack": "astar+dwa", "local_config": "dwa_nope"},
            headers=alice_headers,
        )
        assert response.status_code == 422
        assert "unknown local controller" in response.json()["error"]["message"]


class TestRunningASelection:
    def test_the_same_candidate_twice_is_refused(self, client, alice_headers, profile_id):
        """A candidate cannot be its own rival: the same configuration
        twice is the same ``candidate_id`` (HĐ-1.3)."""
        response = client.post(
            f"{API}/decisions",
            json={
                "task_profile_id": profile_id,
                "candidates": [
                    {"stack": "astar+dwa", "local_config": "dwa_coarse"},
                    {"stack": "astar+dwa", "local_config": "dwa_coarse"},
                ],
            },
            headers=alice_headers,
        )
        assert response.status_code == 422
        assert "its own rival" in response.json()["error"]["message"]

    def test_a_scope_the_candidate_set_cannot_support_is_refused(
        self, client, alice_headers, profile_id
    ):
        """HĐ-1.4, refused before a single episode runs. Two controllers
        under one global planner is a *local* selection, and calling it a
        global one would be a rename rather than a claim."""
        response = client.post(
            f"{API}/decisions",
            json={
                "task_profile_id": profile_id,
                "candidates": [
                    {"stack": "astar+dwa", "local_config": "dwa_coarse"},
                    {"stack": "astar+dwa", "local_config": "dwa_default"},
                ],
                "scope": "global_planner_selection",
                "episodes": 2,
            },
            headers=alice_headers,
        )
        assert response.status_code >= 400

    def test_an_unranked_run_is_stored_and_returned_as_a_result(
        self, client, alice_headers, profile_id
    ):
        """The property this whole phase turned the schema around for.

        On the reference hall ``astar+dwa`` fails G3 and only one of the
        pair clears every gate, so there is no ΔU and no card. That is
        the answer, not a failure — 201, ``ranked: false``, and a gate
        table saying who was eliminated where.
        """
        response = client.post(
            f"{API}/decisions",
            json={
                "task_profile_id": profile_id,
                "candidates": [
                    {"stack": "astar+dwa", "local_config": "dwa_coarse"},
                    {"stack": "rrtstar+dwa", "local_config": "dwa_coarse"},
                ],
                "episodes": 2,
            },
            headers=alice_headers,
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["ranked"] is False
        assert body["card"] is None
        assert body["recommended_candidate_id"] is None
        assert body["artifact_kind"] == "comparison"

        # The evidence is all there, which is the point.
        assert body["report"]["why_no_card"]
        # And *why* there is no card, because two different situations
        # end here and they ask for opposite responses. This one is
        # "nobody survived", which invites a better candidate. The other
        # is a deployment that cannot rank at all (HĐ-8.4), where no
        # candidate would ever change the outcome — the hall is not one
        # while it declares `success_rate_min: 0.95`, and this asserts
        # that the two never get confused for each other.
        assert body["report"]["gate_only_deployment"] is None
        for entry in body["report"]["candidates"]:
            assert entry["gates"]["G1"] is not None
            assert entry["n_distinct_episodes"] >= 1
        assert math.isclose(body["report"]["identity"]["sensor_noise"]["lidar_range_sigma_m"], 0.02)

    def test_a_stored_run_can_be_fetched_and_filtered(self, client, alice_headers, profile_id):
        created = client.post(
            f"{API}/decisions",
            json={
                "task_profile_id": profile_id,
                "candidates": [
                    {"stack": "astar+dwa", "local_config": "dwa_coarse"},
                    {"stack": "rrtstar+dwa", "local_config": "dwa_coarse"},
                ],
                "episodes": 2,
            },
            headers=alice_headers,
        ).json()

        fetched = client.get(f"{API}/decisions/{created['id']}")
        assert fetched.status_code == 200
        assert fetched.json()["id"] == created["id"]

        # "Which runs could not be ranked" is the day-one question.
        unranked = client.get(f"{API}/decisions", params={"ranked": False})
        assert created["id"] in {run["id"] for run in unranked.json()}
        ranked = client.get(f"{API}/decisions", params={"ranked": True})
        assert created["id"] not in {run["id"] for run in ranked.json()}

    def test_a_missing_deployment_is_a_404(self, client, alice_headers):
        response = client.post(
            f"{API}/decisions",
            json={
                "task_profile_id": "no_such_profile",
                "candidates": [
                    {"stack": "astar+dwa", "local_config": "dwa_coarse"},
                    {"stack": "rrtstar+dwa", "local_config": "dwa_coarse"},
                ],
                "episodes": 2,
            },
            headers=alice_headers,
        )
        assert response.status_code == 404


class TestWhoMayDoWhat:
    def test_filing_a_deployment_needs_a_login(self, client):
        response = client.post(f"{API}/task-profiles", json=tiny_profile())
        assert response.status_code == 401

    def test_reading_does_not(self, client, alice_headers):
        client.post(f"{API}/task-profiles", json=tiny_profile(), headers=alice_headers)
        assert client.get(f"{API}/task-profiles/api_hall_tiny").status_code == 200


class TestARankedRunCarriesItsManifest:
    """The branch that had never executed through the API.

    Every selection run so far produced no card, because on the reference
    hall only one candidate of the pair clears all six gates. So the
    ranked path — card *and* manifest — was stored by code nobody had
    exercised, and it was storing ``manifest: None``: the column existed,
    its nullability was tested, and it was null for the wrong reason.

    HĐ-13's acceptance criterion is that somebody else rebuilds the same
    Decision Card **from the manifest**. A card served without one is a
    claim that cannot be reproduced, which is the single property the
    manifest exists to provide.

    The fixture deployment is the vertical slice's: a small room whose
    declared risk of 50% puts ``N_min`` at 6 (HĐ-7.1), and on which both
    candidates clear every gate — which is what makes a card possible at
    all.
    """

    @pytest.fixture
    def ranked_run(self, client, alice_headers, app, tmp_path) -> dict:
        from test_vertical_slice import write_profile

        profile_path = write_profile(tmp_path)
        # The profile names its map relatively, and storing the profile in
        # a database did not move the .pgm. Point the resolver at the
        # directory the fixture just wrote it into.
        app.state.decision_map_root = tmp_path

        payload = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
        created = client.post(f"{API}/task-profiles", json=payload, headers=alice_headers)
        assert created.status_code == 201, created.text

        response = client.post(
            f"{API}/decisions",
            json={
                "task_profile_id": created.json()["id"],
                "candidates": [
                    {"stack": "astar+dwa", "local_config": "dwa_coarse"},
                    {"stack": "rrtstar+dwa", "local_config": "dwa_coarse"},
                ],
                "episodes": 6,
            },
            headers=alice_headers,
        )
        assert response.status_code == 201, response.text
        return response.json()

    def test_the_run_is_ranked(self, ranked_run):
        assert ranked_run["ranked"] is True
        assert ranked_run["artifact_kind"] == "decision_card"
        assert ranked_run["recommended_candidate_id"]
        assert ranked_run["status"] in {"CLEAR_RECOMMENDATION", "NEAR_EQUIVALENT"}

    def test_the_manifest_is_stored_beside_the_card(self, client, ranked_run):
        """The bug this class was written for. ``run_comparison`` wrote
        the manifest to disk and did not return it, so the API stored a
        card with nothing to rebuild it from."""
        fetched = client.get(f"{API}/decisions/{ranked_run['id']}").json()
        assert fetched["card"] is not None
        stored = fetched["report"]["manifest"]
        assert stored, "a ranked run must carry the manifest that rebuilds its card (HĐ-13)"

    def test_the_manifest_carries_what_a_rebuild_needs(self, ranked_run):
        """Not merely present — sufficient. Each of these was added to
        HĐ-13 because a rebuild failed without it: the contexts because
        an id is a hash and does not invert, the bootstrap seed because
        the interval is a random draw, the host because G4 reads
        wall-clock latency, the noise because two runs at the same seeds
        under different sigma are two experiments.
        """
        manifest = ranked_run["report"]["manifest"]
        assert manifest["episode_contexts"]["evaluation"]
        assert manifest["bootstrap"]["seed"] is not None
        assert manifest["benchmark_host"]["cpu"]
        assert "sensor_noise" in manifest
        assert manifest["contracts_version"] == ranked_run["contracts_version"]

    def test_the_run_points_at_its_own_directory_and_its_traces(self, client, ranked_run):
        """D15. ``run_uri`` used to be the root every run shares, and
        ``run_checksum`` was always null — which left the reference
        decorative: a URI alone cannot say the files behind it are still
        the ones this result came from.
        """
        fetched = client.get(f"{API}/decisions/{ranked_run['id']}").json()
        assert fetched["report"]["run_uri"].startswith("file://")
        assert fetched["report"]["run_checksum"]
        # The directory is this run's, not the shared parent.
        assert fetched["report"]["identity"]["experiment_scope"] in fetched["report"]["run_uri"]

    def test_the_manifest_describes_the_run_that_was_scored(self, ranked_run):
        """A manifest naming a different context set would rebuild a
        different card while looking entirely valid."""
        manifest_ids = {
            context["episode_context_id"]
            for context in ranked_run["report"]["manifest"]["episode_contexts"]["evaluation"]
        }
        assert manifest_ids == set(ranked_run["report"]["sample"]["episode_context_ids"])

    def test_an_unranked_run_says_so_in_the_same_field(self, client, alice_headers, profile_id):
        """Shape is uniform across both branches: a caller reading
        ``report["manifest"]`` should not need to know which branch ran."""
        response = client.post(
            f"{API}/decisions",
            json={
                "task_profile_id": profile_id,
                "candidates": [
                    {"stack": "astar+dwa", "local_config": "dwa_coarse"},
                    {"stack": "rrtstar+dwa", "local_config": "dwa_coarse"},
                ],
                "episodes": 2,
            },
            headers=alice_headers,
        ).json()
        assert response["ranked"] is False
        assert response["report"]["manifest"] is None

    def test_a_ranked_run_is_filed_under_ranked(self, client, ranked_run):
        """The unranked side of this filter is covered by
        ``test_a_stored_run_can_be_fetched_and_filtered``; here the point
        is that a ranked run lands on the other side of it and not on
        both. Deliberately does not mix in the hall deployment: the two
        fixtures resolve their maps against different roots, and a test
        that needed both would be testing its own plumbing.
        """
        ranked = {
            run["id"] for run in client.get(f"{API}/decisions", params={"ranked": True}).json()
        }
        unranked = {
            run["id"] for run in client.get(f"{API}/decisions", params={"ranked": False}).json()
        }
        assert ranked_run["id"] in ranked
        assert ranked_run["id"] not in unranked


class TestTheTwoHumanActsOverHttp:
    """Phase 6.3 wiring. The rules live in
    ``tests/test_decision_review.py``; these check that the endpoints
    reach them, and that the split survives the HTTP surface.
    """

    def test_an_unranked_run_can_be_reviewed(self, client, alice_headers, bob_headers, profile_id):
        """The point of the split. This run recommends nobody, and
        somebody still has to be able to say they read it."""
        run = client.post(
            f"{API}/decisions",
            json={
                "task_profile_id": profile_id,
                "candidates": [
                    {"stack": "astar+dwa", "local_config": "dwa_coarse"},
                    {"stack": "rrtstar+dwa", "local_config": "dwa_coarse"},
                ],
                "episodes": 2,
            },
            headers=alice_headers,
        ).json()
        assert run["ranked"] is False
        assert run["review_state"] == "unreviewed"
        assert run["config_state"] == "not_applicable"

        reviewed = client.post(
            f"{API}/decisions/{run['id']}/review",
            json={"comment": "cả hai trượt G3, đã đọc bảng cổng"},
            headers=bob_headers,
        )
        assert reviewed.status_code == 200, reviewed.text
        body = reviewed.json()
        assert body["review_state"] == "reviewed"
        assert body["reviewed_by"]
        # Reading it did not deploy it.
        assert body["config_state"] == "not_applicable"

    def test_an_unranked_run_cannot_be_approved_as_a_configuration(
        self, client, alice_headers, bob_headers, profile_id
    ):
        """409, and the message has to say what the caller *can* do —
        a refusal nobody can act on is one people work around."""
        run = client.post(
            f"{API}/decisions",
            json={
                "task_profile_id": profile_id,
                "candidates": [
                    {"stack": "astar+dwa", "local_config": "dwa_coarse"},
                    {"stack": "rrtstar+dwa", "local_config": "dwa_coarse"},
                ],
                "episodes": 2,
            },
            headers=alice_headers,
        ).json()

        refused = client.post(
            f"{API}/decisions/{run['id']}/config-approval",
            json={"decision": "approve"},
            headers=bob_headers,
        )
        assert refused.status_code == 409, refused.text
        message = refused.json()["error"]["message"]
        assert "no Decision Card" in message
        assert "review" in message

    def test_the_audit_trail_is_served_in_order(
        self, client, alice_headers, bob_headers, profile_id
    ):
        run = client.post(
            f"{API}/decisions",
            json={
                "task_profile_id": profile_id,
                "candidates": [
                    {"stack": "astar+dwa", "local_config": "dwa_coarse"},
                    {"stack": "rrtstar+dwa", "local_config": "dwa_coarse"},
                ],
                "episodes": 2,
            },
            headers=alice_headers,
        ).json()
        client.post(
            f"{API}/decisions/{run['id']}/review",
            json={"comment": "đọc"},
            headers=bob_headers,
        )

        trail = client.get(f"{API}/decisions/{run['id']}/audit")
        assert trail.status_code == 200, trail.text
        events = trail.json()
        assert [event["action"] for event in events] == ["review"]
        assert events[0]["previous_state"] == "unreviewed"
        assert events[0]["new_state"] == "reviewed"

    def test_a_run_with_no_approval_exports_no_configuration(
        self, client, alice_headers, profile_id
    ):
        """HĐ-14: only an approved recommendation exports a config."""
        run = client.post(
            f"{API}/decisions",
            json={
                "task_profile_id": profile_id,
                "candidates": [
                    {"stack": "astar+dwa", "local_config": "dwa_coarse"},
                    {"stack": "rrtstar+dwa", "local_config": "dwa_coarse"},
                ],
                "episodes": 2,
            },
            headers=alice_headers,
        ).json()

        exported = client.get(f"{API}/decisions/{run['id']}/approved_config.yaml")
        assert exported.status_code == 409, exported.text
        assert "not approved" in exported.json()["error"]["message"]
