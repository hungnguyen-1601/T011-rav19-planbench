"""Advice about a comparison nobody has run yet.

Two properties carry the module, and both are about restraint. It must
not cry wolf — a clean draft returning advice teaches a reader to skip
the panel, and the panel is worthless from then on. And every citation
must resolve against the draft it was computed from, because a rule that
points at a field this particular draft does not carry is making the
same unverifiable claim a hallucinating model would.

The second one is tested exhaustively rather than by sampling: an
unresolvable citation is dropped in silence by `keep_resolvable`, so a
rule with a typo in its path would look like a rule that simply chose not
to fire.
"""

from __future__ import annotations

from typing import Any

import pytest

from planbench_benchmark.preflight import (
    PREFLIGHT_CODES,
    STOCHASTIC_SEED_FLOOR,
    build_draft,
    preflight,
)
from planbench_decision.self_check import exists

PROFILE: dict[str, Any] = {
    "id": "warehouse_01",
    "environment": {"map": "warehouse", "dynamic_obstacles": [], "sensor_noise": {}},
    "robot": {"control_period": 0.2, "radius": 0.3},
    "available_observations": ["lidar_2d"],
    "constraints": {"collision_probability_max": 0.001, "success_rate_min": 0.85},
    "replanning": {"enabled": False},
    "missions": [{"id": "m1"}],
}

#: Two different benchmarkable stacks, enough episodes for the declared
#: risk. Everything a clean draft needs.
CLEAN = [
    {"stack": "astar+dwa", "local_config": "dwa_coarse"},
    {"stack": "rrtstar+dwa", "local_config": "dwa_balanced"},
]


def draft(specs: list[dict[str, Any]] | None = None, /, **overrides: Any) -> dict[str, Any]:
    profile = {**PROFILE, **overrides.pop("profile", {})}
    return build_draft(profile, specs if specs is not None else CLEAN, **overrides)


def codes(specs: list[dict[str, Any]] | None = None, /, **overrides: Any) -> set[str]:
    return {a.code for a in preflight(draft(specs, **overrides))}


class TestItCatchesWhatAGateWouldCatchTooLate:
    def test_too_few_episodes_for_the_declared_risk(self) -> None:
        """G2 fails on the count however the runs go, and only says so
        after every one of them has run."""
        assert "PF_EPISODES_BELOW_N_MIN" in codes(episodes=20)

    def test_the_advice_names_the_number_the_reader_must_reach(self) -> None:
        found = [a for a in preflight(draft(episodes=20)) if a.code == "PF_EPISODES_BELOW_N_MIN"]
        assert "3000" in found[0].do

    def test_enough_episodes_draws_nothing(self) -> None:
        assert "PF_EPISODES_BELOW_N_MIN" not in codes(episodes=3000)

    def test_an_observation_the_deployment_does_not_offer(self) -> None:
        """This is G6, computed from two lists that both exist before a
        single episode runs."""
        bare = {**PROFILE, "available_observations": ["odometry"]}
        assert "PF_OBSERVATION_NOT_AVAILABLE" in codes(profile=bare, episodes=3000)

    def test_a_controller_slower_than_the_deployment_requires(self) -> None:
        """G4's deadline is the deployment's control period, and the
        controller's own period is declared in its config."""
        strict = {**PROFILE, "robot": {"control_period": 0.01, "radius": 0.3}}
        assert "PF_CONTROL_RATE_SLOWER_THAN_DEPLOYMENT" in codes(profile=strict, episodes=3000)


class TestItCatchesWhatNoGateCatches:
    def test_a_reference_stack_entered_as_a_competitor(self) -> None:
        specs = [{"stack": "astar+pure_pursuit"}, *CLEAN[:1]]
        assert "PF_REFERENCE_STACK_IN_COMPARISON" in codes(specs, episodes=3000)

    def test_two_entries_that_are_the_same_configuration(self) -> None:
        """`candidate_id` is a hash of the configuration, so these two
        would share every trace, pairing and ΔU."""
        same = [dict(CLEAN[0]), dict(CLEAN[0])]
        assert "PF_DUPLICATE_CANDIDATE_ID" in codes(same, episodes=3000)

    def test_a_policy_stack_with_no_policy_named(self) -> None:
        specs = [{"stack": "astar+ppo"}, *CLEAN[:1]]
        assert "PF_MODEL_NOT_CHOSEN" in codes(specs, episodes=3000)

    def test_a_world_where_every_seed_replays_one_episode(self) -> None:
        """No traffic, no noise, no randomised planner: N runs carry the
        information of one, and a confidence interval over them is a
        confidence interval over nothing."""
        deterministic = [{"stack": "astar+dwa", "local_config": "dwa_coarse"}] * 1 + [
            {"stack": "astar+dwa", "local_config": "dwa_balanced"}
        ]
        assert "PF_QUIET_WORLD_REPEATS_ONE_EPISODE" in codes(deterministic, episodes=3000)

    def test_a_randomised_planner_says_so(self) -> None:
        assert "PF_STOCHASTIC_PLANNER_SEEDS" in codes(episodes=3000)

    def test_too_few_seeds_for_a_randomised_planner_is_louder(self) -> None:
        thin = [a for a in preflight(draft(seed_count=5, episodes=3000)) if "STOCHASTIC" in a.code]
        wide = [
            a
            for a in preflight(draft(seed_count=STOCHASTIC_SEED_FLOOR + 1, episodes=3000))
            if "STOCHASTIC" in a.code
        ]
        assert thin[0].severity == "material"
        assert wide[0].severity == "disclosure"

    def test_traffic_with_replanning_off_is_disclosed_not_condemned(self) -> None:
        """Both settings are valid experiments. The advice is to decide
        it rather than inherit it."""
        busy = {
            **PROFILE,
            "environment": {**PROFILE["environment"], "dynamic_obstacles": [{"id": "cart"}]},
        }
        found = [
            a
            for a in preflight(draft(profile=busy, episodes=3000))
            if a.code == "PF_REPLANNING_OFF_WITH_TRAFFIC"
        ]
        assert found and found[0].severity == "disclosure"


class TestTheSpecificDiagnosisBeatsTheGeneralOne:
    """A build failure is the least useful true thing this module can
    say. Emitting it over a rule that explains the failure would send a
    reader fishing for a parameter when the answer was "this stack is
    not a competitor"."""

    def test_a_reference_stack_is_not_reported_as_a_build_failure(self) -> None:
        found = codes([{"stack": "astar+pure_pursuit"}, *CLEAN[:1]], episodes=3000)
        assert "PF_REFERENCE_STACK_IN_COMPARISON" in found
        assert "PF_BUILD_FAILED" not in found

    def test_a_missing_policy_is_not_reported_as_a_build_failure(self) -> None:
        found = codes([{"stack": "astar+ppo"}, *CLEAN[:1]], episodes=3000)
        assert "PF_MODEL_NOT_CHOSEN" in found
        assert "PF_BUILD_FAILED" not in found

    def test_an_unexplained_failure_still_surfaces(self) -> None:
        """The net has to stay under everything else, or a stack that
        breaks for a reason no rule anticipated fails silently."""
        found = codes([{"stack": "no_such_stack"}, *CLEAN[:1]], episodes=3000)
        assert "PF_BUILD_FAILED" in found


class TestEveryCitationResolves:
    """Exhaustive rather than sampled. `keep_resolvable` drops an
    unresolvable citation without a word, so a typo in a rule's path is
    indistinguishable from a rule that chose not to fire."""

    @pytest.mark.parametrize(
        ("specs", "kwargs"),
        [
            (CLEAN, {"episodes": 20}),
            (CLEAN, {"episodes": 3000}),
            (CLEAN, {"episodes": 3000, "seed_count": 5}),
            ([{"stack": "astar+pure_pursuit"}, *CLEAN[:1]], {"episodes": 3000}),
            ([{"stack": "astar+ppo"}, *CLEAN[:1]], {"episodes": 3000}),
            ([{"stack": "no_such_stack"}, *CLEAN[:1]], {"episodes": 3000}),
            ([dict(CLEAN[0]), dict(CLEAN[0])], {"episodes": 3000}),
        ],
    )
    def test_every_advice_points_at_a_field_the_draft_carries(
        self, specs: list[dict[str, Any]], kwargs: dict[str, Any]
    ) -> None:
        built = draft(specs, **kwargs)
        for item in preflight(built):
            assert exists(built, item.field_path), f"{item.code} cites {item.field_path}"

    def test_an_observation_citation_resolves_too(self) -> None:
        bare = {**PROFILE, "available_observations": ["odometry"]}
        built = draft(profile=bare, episodes=3000)
        for item in preflight(built):
            assert exists(built, item.field_path), item.code


class TestItNeverGetsInTheWay:
    def test_a_clean_draft_draws_no_blocking_advice(self) -> None:
        """A pre-flight that objects to a correct plan teaches the reader
        to skip the panel, and then it is worth nothing when it is
        right."""
        blocking = [a for a in preflight(draft(episodes=3000)) if a.severity == "blocking"]
        assert blocking == []

    def test_it_returns_advice_rather_than_raising_on_a_broken_draft(self) -> None:
        assert preflight({}) == ()
        assert preflight({"candidates": "not a list"}) == ()

    def test_a_missing_map_directory_does_not_take_the_check_down(self) -> None:
        """Eleven rules have nothing to do with the map; losing them to
        an unreadable file would be the check punishing the reader for
        the thing it was trying to warn about."""
        from pathlib import Path

        built = build_draft(PROFILE, CLEAN, episodes=20, map_base_dir=Path("/no/such/place"))
        assert "PF_EPISODES_BELOW_N_MIN" in {a.code for a in preflight(built)}

    def test_the_order_is_stable_across_runs(self) -> None:
        first = [a.code for a in preflight(draft(episodes=20))]
        second = [a.code for a in preflight(draft(episodes=20))]
        assert first == second

    def test_blocking_advice_sorts_above_disclosure(self) -> None:
        found = preflight(draft(episodes=20))
        severities = [a.severity for a in found]
        assert severities == sorted(severities, key=["blocking", "material", "disclosure"].index)


class TestWhatIsPublished:
    def test_every_code_a_rule_can_emit_is_declared(self) -> None:
        """`PREFLIGHT_CODES` is what a caller renders as "12 rules ran".
        A code missing from it makes that count a lie."""
        emitted: set[str] = set()
        for specs, kwargs in [
            (CLEAN, {"episodes": 20}),
            (CLEAN, {"episodes": 3000, "seed_count": 5}),
            ([{"stack": "astar+pure_pursuit"}, *CLEAN[:1]], {"episodes": 3000}),
            ([{"stack": "astar+ppo"}, *CLEAN[:1]], {"episodes": 3000}),
            ([{"stack": "no_such_stack"}, *CLEAN[:1]], {"episodes": 3000}),
            ([dict(CLEAN[0]), dict(CLEAN[0])], {"episodes": 3000}),
        ]:
            emitted |= {a.code for a in preflight(draft(specs, **kwargs))}
        assert emitted <= set(PREFLIGHT_CODES), emitted - set(PREFLIGHT_CODES)

    def test_the_codes_are_unique(self) -> None:
        assert len(PREFLIGHT_CODES) == len(set(PREFLIGHT_CODES))

    def test_every_advice_is_tagged_as_preflight(self) -> None:
        """The kind is what lets a caller render "before you spend the
        compute" separately from the post-hoc critique."""
        assert all(a.kind == "preflight" for a in preflight(draft(episodes=20)))

    def test_every_blocking_advice_names_a_forbidden_move(self) -> None:
        """Every gate here has a remedy that makes the symptom vanish
        without making the conclusion true, and a reader told only "this
        failed" is being invited to find it."""
        for item in preflight(draft(episodes=20)):
            if item.severity == "blocking":
                assert item.do_not, item.code

    def test_the_plan_block_says_what_the_run_would_cost(self) -> None:
        plan = draft(episodes=3000)["plan"]
        assert plan["episode_runs_total"] == 3000 * len(CLEAN)
        assert plan["n_min_required"] == 3000
