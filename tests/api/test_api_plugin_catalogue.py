"""An imported plugin becomes an algorithm the platform can run (P3).

P1 registered a bundle and P2 proved the object inside it behaves. This
is the step where it stops being a row in its own tab and becomes
something `/algorithms` lists and a simulation can name — which is the
whole point of the import path, and the part that would be easiest to
declare done while the plugin remained unreachable.

The end-to-end case drives a real episode: the API builds the stack, the
lane starts a worker process, the loop binds the channel seam and steps
the plugin every tick. Nothing here is stubbed, because a stub would
prove the catalogue entry exists rather than that it runs.
"""

from __future__ import annotations

import pytest
from conftest import ADMIN, auth_headers
from test_api_plugin_conformance import WORKING_PLANNER, import_probe, probe_manifest

STACK_ID = "astar+org.vinai.vfh-plus"


@pytest.fixture
def admin(client):
    return auth_headers(client, ADMIN)


@pytest.fixture(autouse=True)
def _clean_catalogue():
    """The runtime catalogue is process-global, so a test that registers
    a plugin would otherwise leak it into the next one."""
    from planbench_benchmark.registry import clear_external

    clear_external()
    yield
    clear_external()


def algorithms(client, headers) -> dict[str, dict]:
    return {row["id"]: row for row in client.get("/api/v1/algorithms", headers=headers).json()}


class TestARunnablePluginJoinsTheCatalogue:
    def test_it_is_listed_beside_the_built_ins(self, client, admin):
        import_probe(client, admin, WORKING_PLANNER)
        catalogue = algorithms(client, admin)
        assert STACK_ID in catalogue
        assert "astar+dwa" in catalogue, "built-ins must not be displaced by the second source"

    def test_what_it_declares_is_what_is_published(self, client, admin):
        """Nothing inferred from the plugin id: the observation class
        comes from the declared requirements, the schema from the
        manifest, the global-path flag from the manifest."""
        import_probe(client, admin, WORKING_PLANNER)
        entry = algorithms(client, admin)[STACK_ID]
        assert entry["local_controller"] == "org.vinai.vfh-plus"
        assert entry["global_planner"] == "astar"
        assert entry["local_observation_class"] == "lidar_only"
        assert entry["requires_global_path"] is True
        assert entry["requires_model"] is False
        assert entry["benchmarkable"] is True

    def test_it_can_be_fetched_by_id_like_any_other(self, client, admin):
        import_probe(client, admin, WORKING_PLANNER)
        response = client.get(f"/api/v1/algorithms/{STACK_ID}", headers=admin)
        assert response.status_code == 200
        assert response.json()["id"] == STACK_ID


class TestOnlyWhatEarnedItIsOffered:
    def test_a_plugin_that_failed_conformance_is_not_in_the_catalogue(self, client, admin):
        crashing = "class Planner:\n    def reset(self, r): pass\n"
        body = import_probe(client, admin, crashing).json()
        assert body["validation_status"] == "failed"
        assert STACK_ID not in algorithms(client, admin)

    def test_a_plugin_that_could_not_be_run_is_not_offered_either(self, client, admin):
        """`structural` means unverified, not verified-good. Offering it
        would put a candidate on the leaderboard on the strength of
        having been readable."""
        manifest = probe_manifest(requirements={"all_of": ["planbench://channel/static-costmap@1"]})
        body = import_probe(client, admin, WORKING_PLANNER, manifest=manifest).json()
        assert body["validation_status"] == "structural"
        assert STACK_ID not in algorithms(client, admin)

    def test_disabling_one_withdraws_it_from_the_catalogue(self, client, admin):
        bundle_id = import_probe(client, admin, WORKING_PLANNER).json()["id"]
        assert STACK_ID in algorithms(client, admin)
        client.patch(
            f"/api/v1/algorithms/plugins/{bundle_id}", json={"status": "disabled"}, headers=admin
        )
        assert STACK_ID not in algorithms(client, admin)

    def test_re_enabling_it_puts_it_back(self, client, admin):
        bundle_id = import_probe(client, admin, WORKING_PLANNER).json()["id"]
        client.patch(
            f"/api/v1/algorithms/plugins/{bundle_id}", json={"status": "disabled"}, headers=admin
        )
        client.patch(
            f"/api/v1/algorithms/plugins/{bundle_id}", json={"status": "active"}, headers=admin
        )
        assert STACK_ID in algorithms(client, admin)


class TestItActuallyDrivesAnEpisode:
    def test_a_simulation_runs_the_imported_controller(
        self, client, admin, created_map, created_scenario
    ):
        """The end of the path An asked for: somebody who is not a
        developer uploads a bundle and the platform simulates with it.

        A worker process starts, the loop binds the channel seam it found
        on the controller, and the plugin answers every tick.
        """
        import_probe(client, admin, WORKING_PLANNER)
        created = client.post(
            "/api/v1/simulations",
            json={
                "map_id": created_map["id"],
                "scenario_id": created_scenario["id"],
                "algorithm": STACK_ID,
            },
            headers=admin,
        )
        assert created.status_code == 201, created.text

        run = client.post(f"/api/v1/simulations/{created.json()['id']}/run", headers=admin)
        assert run.status_code == 200, run.text
        body = run.json()
        assert body["state"] == "finished"
        # The probe drives forward at a constant speed and never turns,
        # so it is not expected to reach the goal — only to have been
        # asked, tick after tick, and to have answered.
        assert body["result"]["steps"] > 5
        assert len(body["result"]["trajectory"]) > 5

    def test_an_unimported_plugin_id_is_still_refused(
        self, client, admin, created_map, created_scenario
    ):
        response = client.post(
            "/api/v1/simulations",
            json={
                "map_id": created_map["id"],
                "scenario_id": created_scenario["id"],
                "algorithm": "astar+org.nobody.never-imported",
            },
            headers=admin,
        )
        assert response.status_code == 422


class TestFixingAPluginMakesADifferentCandidate:
    """The loop this platform exists for: run it, see it is not good
    enough, change it, import it again, run it again.

    Each turn of that loop has to produce a **different** candidate id.
    Otherwise the second run's numbers land on the first run's row and
    the report says one controller changed its mind, when what happened
    is that two controllers shared a name.
    """

    def candidate_for(self, client, headers):
        from planbench_benchmark.candidates import candidate_from_stack

        return candidate_from_stack(STACK_ID, params={})

    def test_a_re_import_of_the_same_version_is_refused(self, client, admin):
        """The first line of defence: you cannot silently replace what a
        benchmark may already have run."""
        assert import_probe(client, admin, WORKING_PLANNER).status_code == 201
        again = import_probe(client, admin, WORKING_PLANNER, name="Same thing again")
        assert again.status_code == 422
        assert "already imported" in again.json()["error"]["message"]

    def test_a_changed_plugin_at_a_new_version_is_a_new_candidate(self, client, admin):
        """The second: bumping the version and changing the code moves
        the candidate id, because the id follows the uploaded bytes."""
        import_probe(client, admin, WORKING_PLANNER)
        first = self.candidate_for(client, admin)

        faster = WORKING_PLANNER.replace("cruise_speed: float = 0.4", "cruise_speed: float = 0.9")
        assert faster != WORKING_PLANNER
        # Retire the old one first: both would otherwise be runnable and
        # the catalogue would hold two entries for one plugin id, which
        # is the ambiguity `external_controller_version` cannot resolve.
        old = client.get("/api/v1/algorithms/plugins", headers=admin).json()[0]["id"]
        client.patch(
            f"/api/v1/algorithms/plugins/{old}", json={"status": "disabled"}, headers=admin
        )
        manifest = probe_manifest(version="0.2.0")
        assert import_probe(client, admin, faster, manifest=manifest).status_code == 201
        second = self.candidate_for(client, admin)

        assert first.candidate_id != second.candidate_id
        assert first.local_controller.version != second.local_controller.version

    def test_a_fix_imported_beside_the_version_it_fixes_is_the_one_that_runs(self, client, admin):
        """Two runnable versions share one stack id, so one of them has
        to win. It must be the newer: importing a fix and then finding
        the platform still running the code you replaced is a wrong
        answer arriving quietly, which is the failure this repo keeps
        writing down.
        """
        first = import_probe(client, admin, WORKING_PLANNER).json()
        faster = WORKING_PLANNER.replace("cruise_speed: float = 0.4", "cruise_speed: float = 0.9")
        second = import_probe(
            client, admin, faster, manifest=probe_manifest(version="0.2.0")
        ).json()

        # Both left enabled on purpose: this is what somebody iterating
        # actually does, and nothing asks them to retire the old row.
        assert first["checksum"] != second["checksum"]
        assert (
            self.candidate_for(client, admin).local_controller.version == (second["checksum"][:12])
        )

    def test_the_version_is_the_checksum_of_what_was_uploaded(self, client, admin):
        """Not the manifest's version number. A number a person
        maintains is a number a person forgets, and the failure would be
        silent: two different bundles both labelled 0.1.0 would share an
        identity."""
        body = import_probe(client, admin, WORKING_PLANNER).json()
        candidate = self.candidate_for(client, admin)
        assert candidate.local_controller.version == body["checksum"][:12]

    def test_it_no_longer_falls_back_to_v1(self, client, admin):
        """The bug this test was written for. `controller_version` knows
        the built-in controllers by name and returns `"v1"` for anything
        else — so before the entry carried its own version, every
        imported plugin was `v1` for ever."""
        import_probe(client, admin, WORKING_PLANNER)
        assert self.candidate_for(client, admin).local_controller.version != "v1"

    def test_built_in_identities_are_untouched(self, client, admin):
        """The change adds a lookup that returns nothing for a built-in,
        so DWA's id must be exactly what it was — every stored result
        depends on that."""
        from planbench_benchmark.candidates import candidate_from_stack, controller_version

        import_probe(client, admin, WORKING_PLANNER)
        dwa = candidate_from_stack("astar+dwa", params={})
        assert dwa.local_controller.version == controller_version("dwa")


class TestAControllerIsNotTiedToOneGlobalPlanner:
    """An imported controller pairs with every planner, not just A*.

    It was registered against `astar` alone because this module picked a
    default, and the effect was visible on the Decisions screen: choose
    RRT* for one candidate and the imported controller vanished from the
    picker, with nothing on screen to say why. The manifest never claimed
    a planner — `requires_global_path` says "I follow a path somebody
    else planned", not who planned it.
    """

    def test_it_is_offered_behind_every_offerable_planner(self, client, admin):
        from planbench_benchmark.plugin_stacks import offerable_global_planners

        import_probe(client, admin, WORKING_PLANNER)
        catalogue = algorithms(client, admin)
        for planner in offerable_global_planners():
            assert f"{planner}+org.vinai.vfh-plus" in catalogue
        assert "rrtstar+org.vinai.vfh-plus" in catalogue, "the pairing An could not select"

    def test_a_withdrawn_planner_is_not_borrowed(self, client, admin):
        """Only planners some offerable built-in stack still uses. A
        pairing built on a withdrawn or reference-only stack would offer
        a candidate the gates refuse."""
        from planbench_benchmark.plugin_stacks import offerable_global_planners

        assert set(offerable_global_planners()) == {"astar", "rrtstar"}

    def test_each_pairing_is_its_own_candidate(self, client, admin):
        """The same controller behind two planners is two experiments,
        and the platform has always modelled that by making
        `astar+dwa` and `rrtstar+dwa` separate entries."""
        from planbench_benchmark.candidates import candidate_from_stack

        import_probe(client, admin, WORKING_PLANNER)
        behind_astar = candidate_from_stack("astar+org.vinai.vfh-plus", params={})
        behind_rrt = candidate_from_stack("rrtstar+org.vinai.vfh-plus", params={})
        assert behind_astar.candidate_id != behind_rrt.candidate_id
        # Same code on both sides, so the controller half must match.
        assert behind_astar.local_controller.version == behind_rrt.local_controller.version

    def test_the_planner_half_is_the_built_in_one(self, client, admin):
        """Borrowed unchanged: pairing an imported controller with RRT*
        must measure the same RRT* every other candidate ran, or the
        comparison is between two things at once."""
        import_probe(client, admin, WORKING_PLANNER)
        entry = algorithms(client, admin)["rrtstar+org.vinai.vfh-plus"]
        builtin = algorithms(client, admin)["rrtstar+dwa"]
        assert entry["global_planner"] == "rrtstar"
        assert entry["stochastic_global_planner"] == builtin["stochastic_global_planner"]
        assert entry["global_observation_class"] == builtin["global_observation_class"]


class TestAnImportedControllerCanActuallyBeSelected:
    """Appearing in a dropdown is not the same as being runnable.

    The Test Bench asks for three things — global planner, local
    controller, configuration — and refuses to start without all three.
    An imported plugin reached the second dropdown and stopped there: the
    named configurations came from a table written in this repository,
    which an imported controller cannot be in, so its configuration list
    was empty and the run button stayed disabled with nothing to pick.

    Found by using the feature, which is where this class of gap gets
    found: every layer reported success and the screen still could not
    run anything.
    """

    def test_it_is_offered_a_configuration(self, client, admin):
        from planbench_benchmark.candidates import offered_controller_configs

        import_probe(client, admin, WORKING_PLANNER)
        offered = offered_controller_configs()
        assert "org.vinai.vfh-plus" in offered
        assert offered["org.vinai.vfh-plus"], "a controller with no configuration cannot be run"

    def test_the_endpoint_the_picker_reads_lists_it(self, client, admin):
        import_probe(client, admin, WORKING_PLANNER)
        rows = client.get("/api/v1/local-controllers", headers=admin).json()
        mine = [row for row in rows if row["controller"] == "org.vinai.vfh-plus"]
        assert mine, "the configuration picker is served from here, so it has to appear"
        assert mine[0]["name"].startswith("org.vinai.vfh-plus")

    def test_the_configuration_is_accepted_where_it_is_spent(self, client, admin):
        """Offering a name that registration would refuse is the drift
        the served catalogue exists to prevent."""
        from planbench_benchmark.candidates import (
            offered_controller_configs,
            validate_config_names,
        )

        import_probe(client, admin, WORKING_PLANNER)
        name = next(iter(offered_controller_configs()["org.vinai.vfh-plus"]))
        validate_config_names([(STACK_ID, name)])

    def test_disabling_the_plugin_withdraws_its_configuration(self, client, admin):
        from planbench_benchmark.candidates import offered_controller_configs

        bundle_id = import_probe(client, admin, WORKING_PLANNER).json()["id"]
        client.patch(
            f"/api/v1/algorithms/plugins/{bundle_id}", json={"status": "disabled"}, headers=admin
        )
        assert "org.vinai.vfh-plus" not in offered_controller_configs()

    def test_built_in_configurations_are_untouched(self, client, admin):
        from planbench_benchmark.candidates import LOCAL_CONTROLLER_CONFIGS

        import_probe(client, admin, WORKING_PLANNER)
        assert "dwa_balanced" in LOCAL_CONTROLLER_CONFIGS
        assert LOCAL_CONTROLLER_CONFIGS["dwa_balanced"]["control_period"] == 0.05


class TestStoredParametersSurviveTheRoundTrip:
    """A candidate stores its parameters and replays them later, and that
    is where an imported controller died.

    `candidate_from_stack` dumps the validated config with
    `model_dump(mode="json")`, so every optional field is written out as
    `null`. Replaying those makes the fields *set* — to `None` — and a
    filter written as `exclude_unset` passes them straight through to the
    plugin's constructor.

    The Test Bench never noticed because it builds a planner directly
    from an empty config and never stores anything. The Decisions page
    does store, and it failed with
    `TypeError: unsupported operand type(s) for +: 'NoneType' and
    'NoneType'` inside the plugin, one layer past anything the platform
    could explain.
    """

    def test_nulls_are_read_as_unspecified(self):
        from planbench_benchmark.plugin_stacks import config_model_for, constructor_kwargs

        schema = {
            "type": "object",
            "properties": {"mu_target": {"type": "number"}, "loud": {"type": "boolean"}},
        }
        model = config_model_for("org.test.p", schema)
        replayed = model.model_validate({"mu_target": None, "loud": None, "control_period": 0.05})
        assert constructor_kwargs(replayed) == {"control_period": 0.05}

    def test_a_real_value_still_reaches_the_plugin(self):
        from planbench_benchmark.plugin_stacks import config_model_for, constructor_kwargs

        schema = {"type": "object", "properties": {"mu_target": {"type": "number"}}}
        model = config_model_for("org.test.p", schema)
        assert constructor_kwargs(model.model_validate({"mu_target": 7.0}))["mu_target"] == 7.0

    def test_the_dump_a_candidate_stores_is_full_of_nulls(self):
        """The condition that makes the filter necessary, asserted rather
        than assumed: if `candidate_from_stack` ever stops writing nulls,
        this fails and the filter can be reconsidered."""
        from planbench_benchmark.plugin_stacks import config_model_for

        model = config_model_for("org.test.p", {"properties": {"mu_target": {"type": "number"}}})
        stored = model.model_validate({}).model_dump(mode="json")
        assert stored["mu_target"] is None

    def test_the_whole_path_from_a_stored_candidate(self, client, admin):
        """End to end: register the candidate the way the Decisions page
        does, then build the controller from what was stored.

        The manifest has to declare a parameter for this to mean
        anything. The first version of this test used the default probe,
        whose `config_schema` declares no properties — so there were no
        nulls to survive, it passed, and it was checking nothing. It now
        asserts the trap exists before asserting the filter clears it.
        """
        from planbench_benchmark.candidates import candidate_from_stack
        from planbench_benchmark.plugin_stacks import config_model_for, constructor_kwargs

        schema = {"type": "object", "properties": {"cruise_speed": {"type": "number"}}}
        import_probe(client, admin, WORKING_PLANNER, manifest=probe_manifest(config_schema=schema))
        candidate = candidate_from_stack(STACK_ID, params={})
        stored = candidate.params["org.vinai.vfh-plus"]
        assert stored["cruise_speed"] is None, "the trap this filter exists for"

        model = config_model_for("org.vinai.vfh-plus", schema)
        kwargs = constructor_kwargs(model.model_validate(stored))
        assert "cruise_speed" not in kwargs
        assert all(value is not None for value in kwargs.values())


class TestTheTwoObservationTablesAgree:
    def test_the_inverse_mapping_matches_the_forward_one(self):
        """`plugin_stacks` states the requirements-to-class mapping in
        the opposite direction from `legacy_plugins`. Deriving one from
        the other at import time would make a typo in either look like
        agreement, so they are written twice and compared here.

        The forward mapping is **not injective**, and that is the fact
        this test exists to hold still. `human_states` and
        `full_static_map+human_states` declare the same requirement —
        what separates them is the map, which no requirement token
        carries. So an inverse cannot recover both, and the one it names
        has to be the sensing case: reading a plugin's declaration as
        "it also gets the full static map" would credit it with sight
        nobody granted it.
        """
        from collections import defaultdict

        from planbench_benchmark.legacy_plugins import _CLASS_REQUIREMENTS
        from planbench_benchmark.plugin_stacks import CLASS_FOR_REQUIREMENTS

        forward = defaultdict(set)
        for observation_class, requirements in _CLASS_REQUIREMENTS.items():
            forward[frozenset(requirements)].add(observation_class)

        assert set(CLASS_FOR_REQUIREMENTS) == set(forward), (
            "every requirement set the platform knows must have an inverse, and the "
            "inverse must not invent one it does not"
        )
        for key, classes in forward.items():
            assert CLASS_FOR_REQUIREMENTS[key] in classes

        ambiguous = {key: names for key, names in forward.items() if len(names) > 1}
        assert list(ambiguous) == [frozenset({"human_state_estimates"})]
        assert CLASS_FOR_REQUIREMENTS[frozenset({"human_state_estimates"})] == "human_states"
