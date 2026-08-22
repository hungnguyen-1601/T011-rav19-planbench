"""H2: the host's guardrail semantics, and the facades' fidelity.

Byte-level parity of real episodes through the host is pinned by
``test_host_parity_golden.py`` (the H0 fixture now runs through
``build_planners``, which wraps). This file pins everything parity
cannot: what happens when a plugin crashes, lies about its output shape,
or misses its deadline — the cases no legacy planner exercises.
"""

from __future__ import annotations

import inspect

import pytest
from planbench_plugin_sdk import LocalResetRequest, LocalStepRequest

from planbench_benchmark.candidates import LOCAL_CONTROLLER_CONFIGS
from planbench_benchmark.policies import BUILTIN_CHECKPOINT, build_policy
from planbench_benchmark.registry import build_local_planner
from planbench_benchmark.scenarios import build_scenario
from planbench_decision.candidate import Candidate
from planbench_planning.common.base import PlanResult
from planbench_planning.common.local_base import LocalPlanResult
from planbench_schemas.robot import RobotConfig, SimAction
from planbench_simulator.host import (
    AlgorithmHost,
    HostBackedLocalPlanner,
    HostPluginError,
    LegacyLocalPlugin,
    host_backed_planners,
    host_backed_policy,
)
from planbench_simulator.nav_stack import _reset_local, run_policy, run_stack


class _CrashingLocal:
    name = "crasher"
    control_period = None

    def reset(self, request: LocalResetRequest) -> None:
        del request

    def step(self, request: LocalStepRequest) -> LocalPlanResult:
        raise RuntimeError("segfault in disguise")


class _LyingLocal(_CrashingLocal):
    name = "liar"

    def step(self, request):  # returns the wrong shape on purpose
        return {"linear_velocity": 99.0}


class _ResetCrasher(_CrashingLocal):
    name = "reset_crasher"

    def reset(self, request: LocalResetRequest) -> None:
        raise RuntimeError("bad config deep inside")


class _CrashingGlobal:
    name = "crashing_global"

    def plan(self, request):
        raise RuntimeError("planner exploded")


def _step_request() -> LocalStepRequest:
    return LocalStepRequest(state={"robot_state": None}, channels=())


class TestStepGuardrails:
    def test_a_crash_becomes_a_safe_stop(self) -> None:
        host = AlgorithmHost(local_plugin=_CrashingLocal())
        result = host.step_local(_step_request())
        assert result.action == SimAction(linear_velocity=0.0, angular_velocity=0.0)
        assert "crashed" in result.failure_reason
        assert host.stats.crashes == 1

    def test_a_wrong_shape_becomes_a_safe_stop(self) -> None:
        """The loop records failure_reason as an episode event, so a lie
        about the contract surfaces in the trace instead of propagating a
        dict into the kinematics."""
        host = AlgorithmHost(local_plugin=_LyingLocal())
        result = host.step_local(_step_request())
        assert result.action.linear_velocity == 0.0
        assert "not a LocalPlanResult" in result.failure_reason
        assert host.stats.invalid_outputs == 1

    def test_a_reset_crash_is_loud(self) -> None:
        """An episode whose controller cannot initialise is misconfigured;
        driving on with a safe-stop controller would manufacture data."""
        host = AlgorithmHost(local_plugin=_ResetCrasher())
        with pytest.raises(HostPluginError, match="during reset"):
            host.reset_local(LocalResetRequest(robot={"robot_config": None}, declared={}))

    def test_a_global_crash_is_a_failed_plan_not_an_exception(self) -> None:
        """No-route is a verdict the loop already understands (G1 counts
        it, replanning retries it); a crash maps onto it rather than onto
        a new failure mode."""
        host = AlgorithmHost(global_plugin=_CrashingGlobal())
        from planbench_plugin_sdk import GlobalPlanRequest

        result = host.plan_global(GlobalPlanRequest(start=(0.0, 0.0), goal=(1.0, 1.0)))
        assert isinstance(result, PlanResult)
        assert not result.success
        assert "crashed" in result.failure_reason

    def test_deadline_misses_are_observed_never_enforced(self) -> None:
        """deadline 0 ⇒ every step misses; the result still comes back
        intact. Preemption is the subprocess lane's job (H7)."""

        class _FineLocal(_CrashingLocal):
            name = "fine"

            def step(self, request):
                return LocalPlanResult(action=SimAction(linear_velocity=0.5, angular_velocity=0.0))

        host = AlgorithmHost(local_plugin=_FineLocal(), control_deadline_s=0.0)
        result = host.step_local(_step_request())
        assert result.action.linear_velocity == 0.5
        assert host.stats.deadline_misses == 1


class TestTheProbeIsQuarantinedInTheAdapter:
    """§7.2: the facade always ships all three declarations; which ones a
    legacy controller receives is decided per its own signature, in one
    place, on the far side of the host."""

    def test_a_controller_that_accepts_nothing_extra_gets_nothing(self) -> None:
        received = {}

        class _Bare:
            name = "bare"
            control_period = None

            def reset(self, global_path, robot):
                received["kwargs"] = "none"

            def compute(self, state, observation):
                raise NotImplementedError

        plugin = LegacyLocalPlugin(_Bare())
        plugin.reset(
            LocalResetRequest(
                robot={"robot_config": None},
                declared={"envelope": "E", "obstacle_speed": 1.0, "sensor_noise": "N"},
            )
        )
        assert received["kwargs"] == "none"

    def test_a_controller_that_accepts_them_receives_the_declared_values(self) -> None:
        received = {}

        class _Full:
            name = "full"
            control_period = None

            def reset(self, global_path, robot, envelope=None, obstacle_speed=None):
                received.update(envelope=envelope, obstacle_speed=obstacle_speed)

            def compute(self, state, observation):
                raise NotImplementedError

        plugin = LegacyLocalPlugin(_Full())
        plugin.reset(
            LocalResetRequest(
                robot={"robot_config": None},
                declared={"envelope": "E", "obstacle_speed": 0.8, "sensor_noise": "N"},
            )
        )
        assert received == {"envelope": "E", "obstacle_speed": 0.8}

    def test_the_facade_signature_carries_all_three_names(self) -> None:
        """``_reset_local`` probes *its callee* — now the facade — so the
        facade must declare every name the loop may pass, or a
        deployment declaration goes missing exactly the way
        ``sensor_noise`` once did."""
        parameters = set(inspect.signature(HostBackedLocalPlanner.reset).parameters)
        assert {"envelope", "obstacle_speed", "sensor_noise"} <= parameters


class TestFacadesPreserveTheContractSurface:
    def test_names_and_control_period_pass_through(self) -> None:
        dwa = build_local_planner("astar+dwa", dict(LOCAL_CONTROLLER_CONFIGS["dwa_balanced"]))
        from planbench_benchmark.registry import build_global_planner

        astar = build_global_planner("astar+dwa", episode_seed=0)
        hosted_global, hosted_local = host_backed_planners(astar, dwa)
        assert hosted_global.name == "astar"
        assert hosted_local.name == "dwa"
        assert hosted_local.control_period == dwa.control_period

    def test_diagnostics_are_forwarded_not_invented(self) -> None:
        dwa = build_local_planner("astar+dwa", dict(LOCAL_CONTROLLER_CONFIGS["dwa_balanced"]))
        _, hosted_local = host_backed_planners(_StubGlobal(), dwa)
        assert hosted_local.diagnostics == getattr(dwa, "diagnostics", None)

    def test_reset_local_drives_the_facade_like_any_controller(self) -> None:
        """The loop's own probing helper against the facade: all three
        declarations must arrive at a controller that accepts them."""
        received = {}

        class _Probe:
            name = "probe"
            control_period = None

            def reset(self, global_path, robot, envelope=None, sensor_noise=None):
                received.update(envelope=envelope, sensor_noise=sensor_noise)

            def compute(self, state, observation):
                raise NotImplementedError

        _, hosted = host_backed_planners(_StubGlobal(), _Probe())
        robot = RobotConfig(
            radius=0.3,
            max_linear_velocity=1.0,
            max_angular_velocity=1.5,
            max_linear_acceleration=1.0,
            max_angular_acceleration=2.0,
        )
        _reset_local(hosted, (), robot, envelope="ENV", sensor_noise="NOISE")
        assert received == {"envelope": "ENV", "sensor_noise": "NOISE"}


class _StubGlobal:
    name = "stub"

    def plan(self, grid, start, goal):  # pragma: no cover - never called here
        raise NotImplementedError


class TestSharedLoopStillRuns:
    def test_a_host_backed_stack_survives_an_episode(self) -> None:
        """Smoke, not parity — parity is the golden file's job. This pins
        that the wrap plugs into ``run_stack`` itself, replans included,
        without touching the loop."""
        map_data, scenario = build_scenario("doorway")
        scenario = scenario.model_copy(update={"timeout_seconds": 5.0})
        from planbench_benchmark.registry import build_global_planner

        hosted_global, hosted_local = host_backed_planners(
            build_global_planner("astar+dwa", episode_seed=0),
            build_local_planner("astar+dwa", dict(LOCAL_CONTROLLER_CONFIGS["dwa_balanced"])),
        )
        run = run_stack(map_data, scenario, hosted_local, hosted_global)
        assert run.algorithm == "astar+dwa"
        assert run.result.steps > 0

    def test_a_host_backed_policy_keeps_the_one_layer_name(self) -> None:
        candidate = Candidate(
            type="monolithic",
            policy={"name": "greedy_reference_policy", "checkpoint": BUILTIN_CHECKPOINT},  # type: ignore[arg-type]
            observation_requirements=("lidar_2d",),
            resource_profile={  # type: ignore[arg-type]
                "kind": "artifact",
                "model_artifact_mb": 0.1,
                "runtime_footprint_mb": 1.0,
            },
        )
        map_data, scenario = build_scenario("doorway")
        scenario = scenario.model_copy(update={"timeout_seconds": 3.0})
        run = run_policy(map_data, scenario, host_backed_policy(build_policy(candidate)))
        assert run.algorithm == "greedy_reference_policy"
        assert run.plan.success and run.plan.path == ()
