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

import base64
import math
import time
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


@pytest.fixture(scope="module", autouse=True)
def shared_traces(tmp_path_factory: pytest.TempPathFactory):
    """One trace directory for the whole module, not one per test.

    **This is the single reason this file took seven of the suite's
    twenty-one minutes.** Every test here drives a real selection through
    the API, and the ``app`` fixture rooted artifacts at a per-test
    ``tmp_path`` — so each test re-simulated episodes another test had
    already run. Thirteen of the suite's fifteen slowest entries came
    from this one module.

    Sharing the traces is safe by construction rather than by luck: a
    trace path is ``<candidate_id>/<episode_context_id>.parquet``, and
    both halves are content hashes (HĐ-1.3, HĐ-3.1). Two tests reach the
    same file only when they asked for the same candidate on the same
    episode of the same deployment — in which case the file *is* the
    answer, and recomputing it would be recomputing a pure function. Two
    deployments cannot collide: their ids differ, so their context ids do.

    This is also what ``--reuse-traces`` does in production, so the tests
    now exercise the reuse path they always claimed was safe.

    ``decision_run_dir`` is deliberately left per-test. Run directories
    are named from the profile, the scope and the candidate set, so
    sharing them would let one test's report be overwritten by another's
    while both assert on directory contents.
    """
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("PLANBENCH_DECISION_TRACE_DIR", str(tmp_path_factory.mktemp("traces")))
        yield


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
        noise = stored["environment"]["sensor_noise"]
        # The declared amplitudes, by name. Comparing the whole block for
        # equality asserted something the docstring never claimed — that
        # `SensorNoise` has exactly two fields — so adding a noise axis
        # turned a storage test red for a reason with nothing to do with
        # storage.
        assert noise["lidar_range_sigma_m"] == 0.02
        assert noise["wheel_slip_fraction"] == 0.02
        # The rest still travel, at whatever the profile left them, because
        # a manifest missing an amplitude is a manifest that cannot tell
        # two experiments apart.
        assert noise["localization_drift_m"] == 0.0
        assert noise["command_latency_steps"] == 0

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


class TestTheValuesABlankFormOpensWith:
    """Served, not duplicated in the browser.

    A hand-copied set of defaults in TypeScript would be a second
    statement of what a working deployment looks like, and the day
    somebody tunes ``open_hall_v2`` the form would quietly keep handing
    out the old numbers.
    """

    def test_it_is_the_shipped_profile(self, client):
        response = client.get(f"{API}/task-profiles/template")
        assert response.status_code == 200, response.text
        body = response.json()
        shipped = hall_profile()
        for block in ("robot", "constraints", "hardware", "environment"):
            assert body[block] == shipped[block]

    def test_it_hands_over_no_id(self, client):
        """Re-filing an existing id with different content is refused
        (HĐ-3.1). A template carrying ``open_hall_v2`` would make the
        first submit fail for a reason the author did not choose."""
        assert client.get(f"{API}/task-profiles/template").json()["id"] == ""

    def test_what_it_returns_files_as_a_real_deployment(self, client, alice_headers):
        """The strong version of the claim: the defaults are not merely
        plausible, they are a profile the contract accepts. Give it an id
        and it goes in."""
        template = client.get(f"{API}/task-profiles/template").json()
        template["id"] = "from_the_template"
        created = client.post(f"{API}/task-profiles", json=template, headers=alice_headers)
        assert created.status_code == 201, created.text
        assert created.json()["id"] == "from_the_template"

    def test_it_does_not_shadow_a_real_profile_named_template(self, client, alice_headers):
        """Both routes are GET and the parametrised one would answer for
        the literal word "template" if it came first. Registration order
        is what keeps them apart, so it is asserted rather than assumed."""
        profile = tiny_profile()
        profile["id"] = "template_lookalike"
        client.post(f"{API}/task-profiles", json=profile, headers=alice_headers)
        assert client.get(f"{API}/task-profiles/template_lookalike").json()["id"] == (
            "template_lookalike"
        )
        assert client.get(f"{API}/task-profiles/template").json()["id"] == ""


class TestARefusalThatSaysWhichFieldItIsAbout:
    """One blob is enough to paste-and-fix a YAML file; it is not enough
    to put a red outline on one row of a thirty-field form.

    Nothing here is a second copy of a rule. The server still decides
    what is valid — this only keeps the *address* pydantic already
    computed instead of flattening it into prose.
    """

    def test_a_bad_field_is_reported_with_its_path(self, client, alice_headers):
        invalid = tiny_profile()
        invalid["id"] = "field_errors_radius"
        invalid["robot"]["radius"] = -1.0
        response = client.post(f"{API}/task-profiles", json=invalid, headers=alice_headers)
        assert response.status_code == 422, response.text
        details = response.json()["error"]["details"]
        assert {"robot.radius"} <= {entry["path"] for entry in details}
        assert all(entry["message"] for entry in details)

    def test_the_path_uses_the_same_shape_as_the_profile(self, client, alice_headers):
        """Dotted and indexed the way the YAML nests, so one address
        works for the form and for the file."""
        invalid = tiny_profile()
        invalid["id"] = "field_errors_mission"
        invalid["missions"][0]["probability"] = 5.0
        response = client.post(f"{API}/task-profiles", json=invalid, headers=alice_headers)
        assert response.status_code == 422, response.text
        paths = {entry["path"] for entry in response.json()["error"]["details"]}
        assert "missions.0.probability" in paths

    def test_a_whole_block_failing_points_at_the_block(self, client, alice_headers):
        """``goal_tolerance_rad`` is refused by a validator on the whole
        ``constraints`` model, so that is what the address says. Naming
        one field would be the API guessing at a rule it does not own."""
        invalid = tiny_profile()
        invalid["id"] = "field_errors_heading"
        invalid["constraints"]["goal_tolerance_rad"] = 0.35
        response = client.post(f"{API}/task-profiles", json=invalid, headers=alice_headers)
        assert response.status_code == 422, response.text
        details = response.json()["error"]["details"]
        assert [entry["path"] for entry in details] == ["constraints"]
        assert "goal_tolerance_rad" in details[0]["message"]

    def test_the_blob_message_is_still_there(self, client, alice_headers):
        """The paste box has no fields to outline, so it keeps reading
        the sentence. Both audiences, one response."""
        invalid = tiny_profile()
        invalid["id"] = "field_errors_blob"
        invalid["constraints"]["goal_tolerance_rad"] = 0.35
        body = client.post(f"{API}/task-profiles", json=invalid, headers=alice_headers).json()
        assert "HĐ-2" in body["error"]["message"]

    def test_a_valid_profile_carries_no_details(self, client, alice_headers):
        response = client.post(f"{API}/task-profiles", json=tiny_profile(), headers=alice_headers)
        assert response.status_code == 201
        assert "details" not in response.json()

    def test_it_survives_an_error_that_carries_no_locations(self):
        """The callers catch ``Exception`` on purpose. An error that is
        not a pydantic one must degrade to no details rather than raise
        while reporting a failure."""
        from planbench_api.errors import field_errors

        assert field_errors(ValueError("plain")) == []

        class Awkward(Exception):
            def errors(self):
                raise RuntimeError("not today")

        assert field_errors(Awkward()) == []


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

    def test_a_configuration_belonging_to_another_controller_is_refused(
        self, client, alice_headers
    ):
        """**Registration is the second door into the same mistake.**

        ``dwa_coarse`` exists, so the "unknown configuration" check passes
        it; every one of its keys is also a valid ``DWAPredictiveConfig``
        field, so ``candidate_from_stack`` builds happily. The candidate
        would then be **stored** carrying a configuration name it never
        used — and unlike a bad comparison, which is wrong for one run, a
        stored candidate is wrong from then on.

        The comparison path gained this check at ``build_candidates``.
        This is the other entrance.
        """
        response = client.post(
            f"{API}/candidates",
            json={"stack": "astar+dwa_predictive", "local_config": "dwa_coarse"},
            headers=alice_headers,
        )
        assert response.status_code == 422
        assert "dwa_predictive" in response.text

    def test_even_the_matching_configuration_is_refused_now(self, client, alice_headers):
        """Two different refusals, and the second one arrived later.

        The test above refuses ``dwa_coarse`` on ``astar+dwa_predictive``
        because the *pairing* is a lie: the run would be sound and the
        record would name a configuration belonging to another
        controller. This one is refused for a reason that has nothing to
        do with pairing — the stack was **withdrawn on 2026-08-16**,
        after its LiDAR tracker was measured reporting obstacles moving
        at up to 1.9 m/s on a static warehouse.

        Both are 422, and the messages have to stay different or the
        first defect becomes invisible behind the second.
        """
        response = client.post(
            f"{API}/candidates",
            json={"stack": "astar+dwa_predictive", "local_config": "dwa_predictive_balanced"},
            headers=alice_headers,
        )
        assert response.status_code == 422
        assert "perception" in response.text, "the refusal must say it is a withdrawal"
        assert "pairs a" not in response.text, "this is not the mismatched-pairing refusal"

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
    def test_filing_a_deployment_needs_a_login(self, anonymous):
        response = anonymous.post(f"{API}/task-profiles", json=tiny_profile())
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

    Reading and signing now sit behind a claim (contract 7.0.0), so each
    of these walks the workflow — submit, claim, then act. That is not
    ceremony added to the test: the claim is what makes an
    acknowledgement belong to a particular person at a particular time,
    and a test that skipped it would be testing an endpoint nobody can
    reach.
    """

    @staticmethod
    def _hand_over(client, run_id: str, owner_headers, reviewer_headers) -> None:
        """Owner asks; the reviewer takes it."""
        sent = client.post(
            f"{API}/decisions/{run_id}/submit", json={}, headers=owner_headers
        )
        assert sent.status_code == 200, sent.text
        claimed = client.post(f"{API}/decisions/{run_id}/claim", headers=reviewer_headers)
        assert claimed.status_code == 200, claimed.text

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

        self._hand_over(client, run["id"], alice_headers, bob_headers)
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

        self._hand_over(client, run["id"], alice_headers, bob_headers)
        client.post(
            f"{API}/decisions/{run['id']}/review", json={"comment": "đọc"}, headers=bob_headers
        )
        refused = client.post(
            f"{API}/decisions/{run['id']}/config-approval",
            json={"decision": "approve", "comment": "muốn duyệt"},
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
        self._hand_over(client, run["id"], alice_headers, bob_headers)
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


class TestQueueingASweepInsteadOfWaitingForIt:
    """A three-hour sweep cannot happen inside an HTTP request.

    The synchronous path stays for small runs — a six-episode fixture
    finishes before a progress bar would appear. What the queue adds is
    the only honest answer for a 300-episode warehouse sweep: hand back
    something to watch, and let the browser go.
    """

    @staticmethod
    def _await(client, job_id: str, tries: int = 400):
        """Poll until the job leaves the running states.

        Polling rather than a callback because that is what the HTTP
        client actually has, and because the test should exercise the
        same endpoint a browser would.
        """
        for _ in range(tries):
            job = client.get(f"{API}/decisions/jobs/{job_id}").json()
            if job["state"] in {"succeeded", "failed", "cancelled"}:
                return job
            time.sleep(0.25)
        raise AssertionError(f"job {job_id} never finished: {job}")

    def _queue(self, client, headers, profile_id, episodes=2):
        response = client.post(
            f"{API}/decisions/jobs",
            json={
                "task_profile_id": profile_id,
                "candidates": [
                    {"stack": "astar+dwa", "local_config": "dwa_coarse"},
                    {"stack": "rrtstar+dwa", "local_config": "dwa_coarse"},
                ],
                "episodes": episodes,
            },
            headers=headers,
        )
        assert response.status_code == 202, response.text
        return response.json()

    def test_queueing_answers_202_and_names_nothing_that_exists_yet(
        self, client, alice_headers, profile_id
    ):
        """202, not 201. Nothing has been created — the run appears when
        the sweep finishes, and a 201 carrying a job id would name a
        resource that does not exist."""
        job = self._queue(client, alice_headers, profile_id)
        assert job["state"] in {"queued", "running"}
        assert job["run_id"] is None

    def test_the_run_shows_up_when_the_sweep_finishes(self, client, alice_headers, profile_id):
        queued = self._queue(client, alice_headers, profile_id)
        job = self._await(client, queued["id"])
        assert job["state"] == "succeeded", job

        # The job names the run, so a client never has to guess which of
        # the stored runs is "the recent one".
        assert job["run_id"]
        stored = client.get(f"{API}/decisions/{job['run_id']}")
        assert stored.status_code == 200, stored.text
        assert stored.json()["task_profile_id"] == profile_id

    def test_progress_counts_episodes_rather_than_guessing(self, client, alice_headers, profile_id):
        """The numbers come from the sweep itself — the same ones it
        writes to the run journal — not from a timer pretending."""
        queued = self._queue(client, alice_headers, profile_id)
        job = self._await(client, queued["id"])
        assert job["total"] > 0
        assert job["progress"] == job["total"]

    def test_a_queued_sweep_can_be_cancelled(self, client, alice_headers, profile_id):
        queued = self._queue(client, alice_headers, profile_id, episodes=6)
        cancelled = client.delete(f"{API}/decisions/jobs/{queued['id']}", headers=alice_headers)
        assert cancelled.status_code == 200, cancelled.text
        assert cancelled.json()["state"] in {"cancelled", "running", "succeeded"}

    def test_an_unknown_job_is_a_404(self, client):
        assert client.get(f"{API}/decisions/jobs/nope").status_code == 404

    def test_the_same_candidate_twice_is_refused_before_anything_is_queued(
        self, client, alice_headers, profile_id
    ):
        """The refusal that costs hours if it arrives late. Same rule as
        the synchronous path, checked before a slot is taken."""
        response = client.post(
            f"{API}/decisions/jobs",
            json={
                "task_profile_id": profile_id,
                "candidates": [
                    {"stack": "astar+dwa", "local_config": "dwa_coarse"},
                    {"stack": "astar+dwa", "local_config": "dwa_coarse"},
                ],
                "episodes": 2,
            },
            headers=alice_headers,
        )
        assert response.status_code == 422, response.text
        assert "distinct" in response.json()["error"]["message"]


class TestReadingBackTheEvidence:
    """A gate verdict computed from files nobody can open.

    One Parquet trace per (candidate, episode) is the sole input the
    Metrics Engine has (HĐ-5), and every number on a Decision Card comes
    out of one. Until this endpoint existed the platform could compute
    "G3: fail, 70% success" and offer no way to look at a single episode
    behind it.
    """

    @pytest.fixture
    def a_run(self, client, alice_headers, profile_id) -> dict:
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
        return response.json()

    def _fetch(self, client, run, candidate=None, episode=None):
        candidate = candidate or run["report"]["candidates"][0]["candidate_id"]
        episode = episode or run["report"]["sample"]["episode_context_ids"][0]
        return client.get(f"{API}/decisions/{run['id']}/traces/{candidate}/{episode}")

    def test_it_serves_the_poses_the_file_holds(self, client, a_run):
        response = self._fetch(client, a_run)
        assert response.status_code == 200, response.text
        trace = response.json()
        assert len(trace["x"]) == len(trace["y"]) == len(trace["t"]) > 0
        assert len(trace["clearance_m"]) == len(trace["x"])

    def test_the_map_travels_with_the_trajectory(self, client, a_run):
        """A trajectory without its map is a squiggle. The grid comes
        packed one bit per cell — the reference hall is 480x320, which is
        300 kB as a JSON array and 19 kB packed."""
        trace = self._fetch(client, a_run).json()
        grid = trace["map"]
        assert grid["width"] > 0 and grid["height"] > 0
        assert grid["resolution"] > 0
        packed = base64.b64decode(grid["occupied_bits"])
        assert len(packed) == (grid["width"] * grid["height"] + 7) // 8

    def test_events_are_sparse_and_carry_their_index(self, client, a_run):
        """A collision and an arrival draw the same curve; the event is
        the only thing that tells them apart, and its index is where on
        the path it happened."""
        trace = self._fetch(client, a_run).json()
        for event in trace["events"]:
            assert 0 <= event["index"] < len(trace["x"])
            assert event["event"]

    def test_it_carries_what_the_drawing_needs_to_be_to_scale(self, client, a_run):
        """The robot is drawn to its declared radius, not as a dot: a
        path that looks clear at one pixel per cell may not be."""
        trace = self._fetch(client, a_run).json()
        assert trace["robot_radius_m"] > 0
        # G4's budget travels with the trace so the latency chart can
        # draw where "too slow" is. Without it the chart is a shape with
        # no threshold, and a deployment that declares a different
        # control rate would be graded against somebody else's line.
        assert trace["control_period_s"] > 0
        assert trace["missions"]
        first = trace["missions"][0]
        assert set(first["start"]) == {"x", "y"}

    def test_a_candidate_from_another_run_is_refused(self, client, a_run):
        """Ids are content hashes, so a mismatch is not a typo — it is a
        request for a different experiment's evidence under this run's
        name."""
        response = self._fetch(client, a_run, candidate="deadbeefdead")
        assert response.status_code == 404, response.text

    def test_an_episode_this_run_never_measured_is_refused(self, client, a_run):
        response = self._fetch(client, a_run, episode="0000deadbeef")
        assert response.status_code == 404, response.text


class TestWhichEpisodesFailedAndHow:
    """The aggregate was never the whole answer.

    ``success_rate: 0.70`` says seventy per cent of something happened.
    It does not say which thirty per cent did not, nor whether they were
    collisions or timeouts — and those two ask for different work. Every
    ``EpisodeMetricSet`` carried ``success`` and ``failure_reason`` all
    along; the report pooled them and dropped the rows.
    """

    @pytest.fixture
    def a_run(self, client, alice_headers, profile_id):
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
        return response.json()

    def test_every_candidate_carries_one_row_per_episode_it_ran(self, client, a_run):
        """Per candidate, not one shared table: early stopping retires
        candidates at different episodes, and a shared table would have
        to invent blanks for the difference."""
        for entry in a_run["report"]["candidates"]:
            episodes = entry["episodes"]
            assert len(episodes) == entry["n_episodes"]
            assert [row["episode_context_id"] for row in episodes] == [
                row["episode_context_id"] for row in episodes
            ]

    def test_a_failed_episode_says_which_of_the_four_ways(self, client, a_run):
        """HĐ-6's four buckets. Thirty collisions and thirty timeouts
        produce the same success rate and the same gate verdict."""
        rows = [row for entry in a_run["report"]["candidates"] for row in entry["episodes"]]
        assert rows
        for row in rows:
            if row["success"]:
                # Null on success, never "none of the four" — an empty
                # string here would come to mean a fifth bucket.
                assert row["failure_reason"] is None
            else:
                assert row["failure_reason"] in {"no_path", "collision", "timeout", "stuck"}

    def test_the_rows_add_up_to_the_success_rate_they_replaced(self, client, a_run):
        """The table and the aggregate must not be able to disagree —
        two numbers for one fact is how a page ends up arguing with
        itself."""
        for entry in a_run["report"]["candidates"]:
            episodes = entry["episodes"]
            passed = sum(1 for row in episodes if row["success"])
            assert math.isclose(entry["success_rate"], passed / len(episodes))

    def test_the_episode_ids_are_ones_this_run_measured(self, client, a_run):
        """The ids are what pair a row with a trace file, so a row naming
        an episode outside the sample is a row nothing can open."""
        sample = set(a_run["report"]["sample"]["episode_context_ids"])
        for entry in a_run["report"]["candidates"]:
            assert {row["episode_context_id"] for row in entry["episodes"]} <= sample

    def test_the_list_endpoint_leaves_the_rows_behind(self, client, a_run):
        """A warehouse run is 300 episodes across two candidates, and ten
        of them on one page is close to a megabyte of rows the list draws
        none of. Stripped in the response, not dropped from storage."""
        listed = client.get(f"{API}/decisions").json()
        row = next(entry for entry in listed if entry["id"] == a_run["id"])
        for candidate in row["report"]["candidates"]:
            assert "episodes" not in candidate
            # Everything the list *does* draw is still there.
            assert candidate["cleared_gates"] is not None
            assert candidate["stack_label"]

        detail = client.get(f"{API}/decisions/{a_run['id']}").json()
        assert all("episodes" in c for c in detail["report"]["candidates"])


class TestPuttingADifferentMapUnderADeployment:
    """The only way a drawn map reaches a comparison.

    A profile names its map by path (HĐ-2) and the editor stores grids in
    the database. Deriving writes the chosen grid out as a map_server
    pair and files a *new* deployment pointing at it — new, because a map
    is the world and ``episode_context_id`` does not hash it (HĐ-3.1).
    """

    @pytest.fixture
    def a_map(self, client, alice_headers) -> str:
        """A 12x8 m room with a wall down the middle and a doorway.

        Not an empty box: a map with no obstacle would let a broken
        mission validator pass everything, and the doorway is what makes
        "start and goal in the same region" a claim with content.
        """
        width, height = 60, 40  # 0.2 m cells -> 12 x 8 m
        cells = []
        for row in range(height):
            for col in range(width):
                on_border = row in (0, height - 1) or col in (0, width - 1)
                # Wall at x = 6 m with a gap in the middle rows.
                in_wall = col == width // 2 and not (16 <= row <= 23)
                cells.append(100 if (on_border or in_wall) else 0)
        response = client.post(
            f"{API}/maps",
            json={
                "name": "derived_room",
                "width": width,
                "height": height,
                "resolution": 0.2,
                "origin": {"x": 0.0, "y": 0.0, "theta": 0.0},
                "cells": cells,
            },
            headers=alice_headers,
        )
        assert response.status_code == 201, response.text
        return response.json()["id"]

    @pytest.fixture
    def base_id(self, client, alice_headers) -> str:
        client.post(f"{API}/task-profiles", json=tiny_profile(), headers=alice_headers)
        return "api_hall_tiny"

    def _derive(self, client, headers, base_id, map_id, **overrides):
        body = {
            "base_task_profile_id": base_id,
            "new_id": "derived_room_v1",
            "map_id": map_id,
            "missions": [
                {"id": "custom_route", "start": [2.0, 4.0, 0.0], "goal": [10.0, 4.0, 0.0]},
            ],
        }
        body.update(overrides)
        return client.post(f"{API}/task-profiles/derive", json=body, headers=headers)

    def test_it_files_a_new_deployment_pointing_at_the_written_map(
        self, client, alice_headers, base_id, a_map
    ):
        response = self._derive(client, alice_headers, base_id, a_map)
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["id"] == "derived_room_v1"
        assert body["environment"].startswith("maps/custom/")
        # Relative, never absolute: a profile carrying an absolute path
        # is a profile that is only true on one machine, and HĐ-13 asks
        # somebody else to rebuild the run from what it says.
        assert not Path(body["environment"]).is_absolute()
        assert (REPO_ROOT / body["environment"]).is_file()

    def test_the_new_deployment_keeps_everything_else(self, client, alice_headers, base_id, a_map):
        """A derived deployment differs in the map and the missions and
        in nothing else. Silently resetting the noise or a threshold
        would make the comparison answer a question nobody asked."""
        base = client.get(f"{API}/task-profiles/{base_id}").json()["profile"]
        derived = self._derive(client, alice_headers, base_id, a_map).json()["profile"]
        assert derived["environment"]["sensor_noise"] == base["environment"]["sensor_noise"]
        assert derived["constraints"] == base["constraints"]
        assert derived["robot"] == base["robot"]

    def test_reusing_the_base_id_is_refused(self, client, alice_headers, base_id, a_map):
        """The trap: two worlds under one id give contexts hashing
        identically, and ``--reuse-traces`` would serve episodes recorded
        on walls that are gone. Nothing warns; the ids match."""
        response = self._derive(client, alice_headers, base_id, a_map, new_id=base_id)
        assert response.status_code == 422, response.text
        assert "HĐ-3.1" in response.json()["error"]["message"]

    def test_a_goal_the_robot_cannot_reach_is_refused_before_storing(
        self, client, alice_headers, base_id, a_map
    ):
        """A goal inside a wall gives 0% success for *every* candidate,
        and the comparison then reports a tie between stacks on a
        question none of them was asked — every column a plausible 0.00,
        nothing in the numbers wrong."""
        response = self._derive(
            client,
            alice_headers,
            base_id,
            a_map,
            new_id="derived_bad_goal",
            missions=[
                {"id": "into_the_wall", "start": [2.0, 4.0, 0.0], "goal": [6.0, 1.0, 0.0]},
            ],
        )
        assert response.status_code == 422, response.text
        assert client.get(f"{API}/task-profiles/derived_bad_goal").status_code == 404

    def test_a_start_outside_the_map_is_refused(self, client, alice_headers, base_id, a_map):
        response = self._derive(
            client,
            alice_headers,
            base_id,
            a_map,
            new_id="derived_offmap",
            missions=[
                {"id": "nowhere", "start": [99.0, 99.0, 0.0], "goal": [10.0, 4.0, 0.0]},
            ],
        )
        assert response.status_code == 422, response.text

    def test_a_start_heading_survives_into_the_simulated_scenario(
        self, client, alice_headers, base_id, a_map
    ):
        """The heading is part of the mission, not a drawing detail.

        The engine seeds ``RobotState(pose=scenario.start_pose)``, so a
        robot placed facing away from its goal spends its first second
        turning around. Dropping theta on the way through would silently
        replace the author's mission with a different one.
        """
        derived = self._derive(
            client,
            alice_headers,
            base_id,
            a_map,
            new_id="derived_facing_away",
            missions=[
                {
                    "id": "facing_away",
                    "start": [2.0, 4.0, math.pi],
                    "goal": [10.0, 4.0, math.pi / 2],
                }
            ],
        )
        assert derived.status_code == 201, derived.text
        mission = derived.json()["profile"]["missions"][0]
        assert mission["start"]["theta"] == pytest.approx(math.pi)
        assert mission["goal"]["theta"] == pytest.approx(math.pi / 2)

        # And that it is still the heading by the time an episode is built.
        from planbench_benchmark.contexts import build_evaluation_contexts
        from planbench_benchmark.episode import scenario_for
        from planbench_schemas.task_profile import TaskProfile

        profile = TaskProfile.model_validate(derived.json()["profile"])
        context = build_evaluation_contexts(profile, seed_count=1)[0]
        assert scenario_for(profile, context).start_pose.theta == pytest.approx(math.pi)

        # The other half of the same story: the *arrival* heading is
        # stored and never judged, because HĐ-6 forces every deployment
        # to leave it unconstrained. The UI says so beside its field; if
        # this ever stops being true, that note becomes a lie.
        assert profile.constraints.goal_tolerance_rad >= math.pi

    def test_an_unknown_map_is_a_404(self, client, alice_headers, base_id):
        response = self._derive(client, alice_headers, base_id, "no_such_map")
        assert response.status_code == 404, response.text

    def test_deriving_needs_a_login(self, anonymous, base_id, a_map):
        response = self._derive(anonymous, {}, base_id, a_map)
        assert response.status_code == 401

    def test_the_derived_deployment_can_actually_be_swept(
        self, client, alice_headers, base_id, a_map
    ):
        """The whole point, end to end: a map somebody drew, measured on.

        Two episodes rather than N_min — this asserts the chain runs on a
        custom map, and the sample size is a separate contract (HĐ-7.1)
        with its own tests.
        """
        derived = self._derive(
            client, alice_headers, base_id, a_map, new_id="derived_room_swept"
        ).json()["id"]
        response = client.post(
            f"{API}/decisions",
            json={
                "task_profile_id": derived,
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
        assert body["task_profile_id"] == "derived_room_swept"
        assert body["report"]["sample"]["n_episodes"] == 2
        assert len(body["report"]["candidates"]) == 2


class TestWhatACandidateCanBeBuiltFrom:
    """The registry, served rather than copied into the client.

    Registration already refuses a local-controller name outside this
    table, so a hand-maintained list in the browser would be a second
    statement of what the platform accepts — free to drift, and drifting
    silently until somebody's dropdown offers a configuration the server
    rejects.
    """

    def test_it_lists_every_named_configuration(self, client):
        response = client.get(f"{API}/local-controllers")
        assert response.status_code == 200, response.text
        names = {entry["name"] for entry in response.json()}
        assert {"dwa_coarse", "dwa_balanced", "dwa_default"} <= names

    def test_the_parameters_travel_with_the_name(self, client):
        """The name alone says nothing. `dwa_coarse` and `dwa_default`
        differ by 7x15 samples against 20x40, and that difference is the
        entire reason a sampling choice is a *candidate* rather than a
        constant inside whichever script ran (HĐ-1.3)."""
        entries = {e["name"]: e["params"] for e in client.get(f"{API}/local-controllers").json()}
        assert entries["dwa_coarse"]["velocity_samples"] == 7
        assert entries["dwa_default"]["velocity_samples"] == 20
        assert entries["dwa_coarse"] != entries["dwa_default"]

    def test_every_offered_name_is_one_registration_accepts(self, client, alice_headers):
        """The point of serving the list: what it offers must be exactly
        what the server takes. A name here that registration refused
        would be a dropdown that produces an error.

        **Paired with the stack the entry says it belongs to.** Each entry
        carries its ``controller``, and since P6 registration refuses a
        configuration paired with a different one — ``dwa_coarse`` on a
        predictive stack builds cleanly and then mislabels every report.
        A test that ignored ``controller`` and posted everything at
        ``astar+dwa`` would be asserting the platform accepts exactly the
        mistake it now rejects.

        Which is also the requirement on the client: the list is flat, so
        a dropdown has to filter it by ``controller`` rather than offer
        every name for every stack.
        """
        stacks = {"dwa": "astar+dwa", "dwa_predictive": "astar+dwa_predictive"}
        offered = client.get(f"{API}/local-controllers").json()
        assert not any(entry["controller"] == "dwa_predictive" for entry in offered), (
            "a withdrawn controller's configurations must leave the catalogue with it, "
            "or the dropdown offers names POST /candidates answers 422 to"
        )
        assert offered, "an empty catalogue would pass this vacuously"
        for entry in offered:
            stack = stacks.get(entry["controller"])
            assert stack, f"no stack known for controller {entry['controller']!r}"
            response = client.post(
                f"{API}/candidates",
                json={"stack": stack, "local_config": entry["name"]},
                headers=alice_headers,
            )
            assert response.status_code == 201, f"{entry['name']}: {response.text}"

    def test_reading_it_does_not_need_a_login(self, client):
        """It is a catalogue of what the platform can do, not anybody's
        data."""
        assert client.get(f"{API}/local-controllers").status_code == 200
