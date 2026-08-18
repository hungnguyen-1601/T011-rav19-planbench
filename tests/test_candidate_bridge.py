"""Registry stack <-> candidate bridge (HĐ-1, P02 reuse)."""

from __future__ import annotations

import pytest
from task_profile_fakes import make_profile

from planbench_benchmark.candidates import (
    LOCAL_CONTROLLER_CONFIGS,
    ControlRateViolation,
    NotBenchmarkableError,
    UnknownParameterError,
    build_planners,
    candidate_from_stack,
    observation_requirements_for,
    stack_id_for,
    validate_control_rate,
)
from planbench_benchmark.registry import (
    AlgorithmConfigError,
    UnknownAlgorithmError,
    algorithm_info,
)
from planbench_decision.candidate import Candidate, validate_experiment_scope


class TestRequirementsMapping:
    def test_lidar_only_controller_needs_lidar(self) -> None:
        info = algorithm_info("astar+dwa")
        assert info is not None
        assert observation_requirements_for(info) == ("lidar_2d",)

    def test_static_map_is_not_a_requirement(self) -> None:
        """The deployment ships the map in its task profile; requiring it
        would fail every modular candidate at G6."""
        info = algorithm_info("astar+dwa")
        assert info is not None
        assert info.global_observation_class == "full_static_map"
        assert "static_map" not in observation_requirements_for(info)


class TestCandidateFromStack:
    def test_astar_dwa_maps_to_modular(self) -> None:
        candidate = candidate_from_stack("astar+dwa")
        assert candidate.type == "modular"
        assert candidate.stack_label == "astar+dwa"
        assert candidate.observation_requirements == ("lidar_2d",)

    def test_ppo_stack_is_modular_not_monolithic(self) -> None:
        """astar+ppo is A* planning with a PPO controller following the
        path (requires_global_path), which is the modular shape."""
        candidate = candidate_from_stack("astar+ppo", params={"model_id": "m1"})
        assert candidate.type == "modular"
        assert candidate.local_controller is not None
        assert candidate.local_controller.name == "ppo"

    def test_params_are_validated_against_the_registry(self) -> None:
        with pytest.raises(AlgorithmConfigError):
            candidate_from_stack("astar+dwa", params={"horizon_seconds": -1.0})

    def test_unknown_parameter_refused(self) -> None:
        """Pydantic ignores unknown keys, which here would mint a
        candidate identical to the default one — see UnknownParameterError."""
        with pytest.raises(UnknownParameterError, match="no parameter"):
            candidate_from_stack("astar+dwa", params={"sim_time": 2.5})

    def test_defaults_are_materialised_into_params(self) -> None:
        """The id must cover what actually ran, so defaults cannot stay
        implicit — otherwise a default change silently reuses an old id."""
        candidate = candidate_from_stack("astar+dwa")
        assert candidate.layer_params("dwa")["horizon_seconds"] > 0

    def test_differing_params_give_differing_ids(self) -> None:
        a = candidate_from_stack("astar+dwa")
        b = candidate_from_stack("astar+dwa", params={"horizon_seconds": 2.5})
        assert a.candidate_id != b.candidate_id
        assert a.stack_label == b.stack_label

    def test_version_reaches_the_id(self) -> None:
        a = candidate_from_stack("astar+dwa")
        b = candidate_from_stack("astar+dwa", local_version="v2")
        assert a.candidate_id != b.candidate_id

    def test_reference_stack_refused(self) -> None:
        with pytest.raises(NotBenchmarkableError, match="reference stack"):
            candidate_from_stack("astar+pure_pursuit")

    def test_unknown_stack_refused(self) -> None:
        with pytest.raises(UnknownAlgorithmError):
            candidate_from_stack("astar+nope")

    def test_round_trip_through_registry_id(self) -> None:
        candidate = candidate_from_stack("rrtstar+dwa")
        assert stack_id_for(candidate) == "rrtstar+dwa"


class TestBuildPlanners:
    def test_builds_both_layers(self) -> None:
        global_planner, local_planner = build_planners(
            candidate_from_stack("astar+dwa"), episode_seed=7
        )
        assert global_planner.name == "astar"
        assert local_planner.name == "dwa"

    def test_seed_reaches_a_sampling_planner(self) -> None:
        candidate = candidate_from_stack("rrtstar+dwa")
        first, _ = build_planners(candidate, episode_seed=1)
        second, _ = build_planners(candidate, episode_seed=2)
        assert first.name == second.name == "rrtstar"

    def test_monolithic_has_no_registry_stack(self) -> None:
        mono = Candidate(
            type="monolithic",
            policy={"name": "ppo_navigation", "checkpoint": "c1"},  # type: ignore[arg-type]
            observation_requirements=("lidar_2d",),
            resource_profile={  # type: ignore[arg-type]
                "kind": "artifact",
                "model_artifact_mb": 340.0,
                "runtime_footprint_mb": 2100.0,
            },
        )
        with pytest.raises(NotBenchmarkableError, match="build_policy"):
            build_planners(mono, episode_seed=0)


class TestScopeWithRealStacks:
    def test_astar_vs_rrtstar_is_a_valid_global_selection(self) -> None:
        """The vertical slice's comparison: same controller config, two
        global planners."""
        validate_experiment_scope(
            "global_planner_selection",
            [candidate_from_stack("astar+dwa"), candidate_from_stack("rrtstar+dwa")],
        )

    def test_retuned_controller_breaks_the_global_claim(self) -> None:
        with pytest.raises(Exception, match="identical local layer"):
            validate_experiment_scope(
                "global_planner_selection",
                [
                    candidate_from_stack("astar+dwa"),
                    candidate_from_stack("rrtstar+dwa", params={"horizon_seconds": 2.5}),
                ],
            )


class TestNamedLocalConfigurations:
    """A sampling choice made for the wall clock is a candidate, not a
    constant in whichever script happened to run it."""

    def test_both_configurations_run_at_the_reference_control_period(self) -> None:
        """Neither named config may quietly ask for a slower loop than
        the reference deployments declare."""
        for name, params in LOCAL_CONTROLLER_CONFIGS.items():
            assert params["control_period"] == 0.05, name

    def test_coarse_and_default_are_different_candidates(self) -> None:
        """Same stack, two sampling densities, two ids — which is what
        makes "is the convex-corner stall a property of the stack or of
        the coarse sampling?" a question the platform can answer."""
        coarse = candidate_from_stack(
            "astar+dwa", params=dict(LOCAL_CONTROLLER_CONFIGS["dwa_coarse"])
        )
        default = candidate_from_stack(
            "astar+dwa", params=dict(LOCAL_CONTROLLER_CONFIGS["dwa_default"])
        )
        assert coarse.candidate_id != default.candidate_id

    def test_comparing_the_two_is_not_a_global_planner_claim(self) -> None:
        """Holding the global planner fixed and changing the controller
        is a *local* selection; declaring it as a global one is refused
        rather than mislabelled."""
        with pytest.raises(Exception, match="identical local layer"):
            validate_experiment_scope(
                "global_planner_selection",
                [
                    candidate_from_stack(
                        "astar+dwa", params=dict(LOCAL_CONTROLLER_CONFIGS["dwa_coarse"])
                    ),
                    candidate_from_stack(
                        "astar+dwa", params=dict(LOCAL_CONTROLLER_CONFIGS["dwa_default"])
                    ),
                ],
            )


class TestControlRateAgainstTheDeployment:
    """G4 times one controller call and never asks how often the call
    happens. Without this check a candidate closing its loop at half the
    declared rate passes the real-time gate while missing every second
    deadline — the loophole under the old ``control_period: 0.1``
    profiles.
    """

    def test_a_controller_at_the_declared_rate_is_accepted(self) -> None:
        profile = make_profile()
        assert profile.robot.control_period == 0.05
        validate_control_rate(
            profile,
            [
                candidate_from_stack(stack, params=dict(LOCAL_CONTROLLER_CONFIGS["dwa_coarse"]))
                for stack in ("astar+dwa", "rrtstar+dwa")
            ],
        )

    def test_a_slower_controller_is_refused_before_any_episode_runs(self) -> None:
        slow = candidate_from_stack(
            "astar+dwa",
            params={**LOCAL_CONTROLLER_CONFIGS["dwa_coarse"], "control_period": 0.1},
        )
        with pytest.raises(ControlRateViolation, match="closes its control loop"):
            validate_control_rate(make_profile(), [slow])

    def test_the_message_names_both_numbers(self) -> None:
        """Whoever hits this needs to know which two declarations
        disagree; "invalid configuration" would send them reading code."""
        slow = candidate_from_stack(
            "astar+dwa",
            params={**LOCAL_CONTROLLER_CONFIGS["dwa_coarse"], "control_period": 0.2},
        )
        with pytest.raises(ControlRateViolation) as excinfo:
            validate_control_rate(make_profile(), [slow])
        assert "0.2" in str(excinfo.value)
        assert "0.05" in str(excinfo.value)

    def test_a_faster_controller_is_fine(self) -> None:
        """The deployment states a *minimum* rate. Running the loop more
        often than required is a candidate spending its own budget."""
        fast = candidate_from_stack(
            "astar+dwa",
            params={**LOCAL_CONTROLLER_CONFIGS["dwa_coarse"], "control_period": 0.02},
        )
        validate_control_rate(make_profile(), [fast])
