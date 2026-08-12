"""Is the *simulator* fair? (CONTRACTS HĐ-3, HĐ-4, HĐ-7.4)

``test_fairness.py`` asks whether the scoring layer is blind to who it is
scoring. This asks the question one layer down, where it is easier to get
wrong and much harder to notice: **did the two candidates run in the same
world?**

Six things have to be identical between two candidates sharing an episode
context. They are not independent nice-to-haves — each one is a distinct
way for a comparison to be meaningless while every number in it looks
reasonable:

1. **Ground-truth world.** Same map, same static obstacles, same moving
   obstacles at the same instants.
2. **Robot embodiment.** Same radius, same velocity and acceleration
   limits, same sensor.
3. **External randomness.** The same seed drives the world, and a
   candidate's own random draws cannot disturb it.
4. **Physics and time.** Same integration step, same timeout, same clock.
5. **Success / failure semantics.** One definition of arrived, collided,
   timed out and stuck, applied by the same code to both.
6. **Scenario distribution.** The episodes exist before the candidates
   and do not depend on them.

The structural guarantee behind most of this is one line in
``episode.py``: ``scenario_for(profile, context)`` takes no candidate, so
the world is a pure function of the deployment and the episode. These
tests hold that line, because it is the kind of parameter somebody adds
later for a good-sounding reason.

HĐ-4 names the failure these guard against: *"a planner reaching into
SimBackend internals for obstacle positions instead of going through
Observation — both an architecture violation and a cheat on the
observation layer."*
"""

from __future__ import annotations

import inspect
import random
from pathlib import Path

import numpy as np
import pytest
import yaml

from planbench_benchmark import episode as episode_module
from planbench_benchmark.candidates import (
    LOCAL_CONTROLLER_CONFIGS,
    candidate_from_stack,
    validate_control_rate,
)
from planbench_benchmark.contexts import build_evaluation_contexts, iter_run_plan
from planbench_benchmark.episode import scenario_for
from planbench_benchmark.task_map import load_task_map
from planbench_schemas.dynamic import position_at
from planbench_schemas.episode_context import EpisodeContext
from planbench_schemas.sensor import SensorNoise
from planbench_schemas.task_profile import TaskProfile
from planbench_simulator.noise import NoiseModel

REPO_ROOT = Path(__file__).resolve().parents[1]
HALL = REPO_ROOT / "profiles" / "open_hall_v1.yaml"
NOISY_HALL = REPO_ROOT / "profiles" / "open_hall_v2.yaml"
WAREHOUSE = REPO_ROOT / "profiles" / "warehouse_a_v2.yaml"

#: The slice's local-controller configuration, shared by both candidates.
LOCAL: dict[str, object] = dict(LOCAL_CONTROLLER_CONFIGS["dwa_coarse"])


def load(path: Path) -> TaskProfile:
    return TaskProfile.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


@pytest.fixture(scope="module")
def warehouse() -> TaskProfile:
    """The profile with traffic — a world with something to get wrong."""
    return load(WAREHOUSE)


@pytest.fixture(scope="module")
def contexts(warehouse: TaskProfile) -> tuple[EpisodeContext, ...]:
    return build_evaluation_contexts(warehouse, seed_count=4)


def both_candidates() -> tuple[object, object]:
    """Two stacks differing only in the global planner (HĐ-1.4 scope)."""
    return (
        candidate_from_stack("astar+dwa", params=dict(LOCAL)),
        candidate_from_stack("rrtstar+dwa", params=dict(LOCAL)),
    )


class TestTheWorldIsBuiltWithoutKnowingTheCandidate:
    """Invariant 1, 2, 4, 5 and 6 all rest on this one property."""

    def test_scenario_for_takes_no_candidate(self) -> None:
        """The structural guarantee, asserted so it survives refactoring.

        A ``candidate`` parameter here would let any of the other five
        invariants be broken later without anything else changing — and
        it is exactly the parameter somebody adds when a planner needs
        "just one" hint from the world.
        """
        parameters = set(inspect.signature(scenario_for).parameters)
        assert parameters == {"profile", "context"}
        for banned in ("candidate", "planner", "stack", "controller"):
            assert banned not in parameters

    def test_the_candidate_reaches_only_the_planners(self) -> None:
        """In ``run_contract_episode`` the candidate is allowed to choose
        the planners and to declare its own resource counters. It must
        not appear in the call that builds the world."""
        source = inspect.getsource(episode_module.run_contract_episode)
        assert "scenario_for(profile, context)" in source
        assert "scenario_for(candidate" not in source

    def test_two_candidates_get_an_identical_scenario(
        self, warehouse: TaskProfile, contexts: tuple[EpisodeContext, ...]
    ) -> None:
        """The behavioural form of the same claim."""
        for context in contexts:
            first = scenario_for(warehouse, context)
            second = scenario_for(warehouse, context)
            assert first == second

    def test_the_scenario_is_reproducible_from_the_contract_alone(
        self, warehouse: TaskProfile, contexts: tuple[EpisodeContext, ...]
    ) -> None:
        """Nothing about the world comes from ambient state — no clock,
        no global RNG, no filesystem. Two processes handed the same
        profile and context must build the same episode."""
        random.seed(1234)
        np.random.seed(1234)
        first = scenario_for(warehouse, contexts[0])
        random.seed(9999)
        np.random.seed(9999)
        np.random.random(1000)
        assert scenario_for(warehouse, contexts[0]) == first


class TestSameGroundTruthWorld:
    """Invariant 1."""

    def test_the_moving_obstacles_are_the_deployments_not_the_candidates(
        self, warehouse: TaskProfile, contexts: tuple[EpisodeContext, ...]
    ) -> None:
        scenario = scenario_for(warehouse, contexts[0])
        assert scenario.dynamic_obstacles == warehouse.environment.dynamic_obstacles

    def test_obstacle_positions_depend_only_on_time_and_the_episode_seed(
        self, warehouse: TaskProfile
    ) -> None:
        """``position_at`` is a pure function. If it ever consulted the
        candidate — or anything else — two stacks would be dodging
        different traffic while sharing an episode id."""
        obstacle = warehouse.environment.dynamic_obstacles[0]
        parameters = list(inspect.signature(position_at).parameters)
        assert parameters == ["obstacle", "time", "seed"]
        for time in (0.0, 7.5, 31.25):
            for seed in (0, 3, 17):
                assert position_at(obstacle, time, seed) == position_at(obstacle, time, seed)

    def test_the_map_is_loaded_from_the_deployment(self, warehouse: TaskProfile) -> None:
        first = load_task_map(warehouse, base_dir=REPO_ROOT)
        second = load_task_map(warehouse, base_dir=REPO_ROOT)
        assert first.checksum() == second.checksum()
        parameters = set(inspect.signature(load_task_map).parameters)
        assert "candidate" not in parameters


class TestSameRobotEmbodiment:
    """Invariant 2."""

    def test_the_robot_comes_from_the_profile(
        self, warehouse: TaskProfile, contexts: tuple[EpisodeContext, ...]
    ) -> None:
        robot = scenario_for(warehouse, contexts[0]).robot
        assert robot.radius == warehouse.robot.radius
        assert robot.max_linear_velocity == warehouse.robot.max_linear_velocity
        assert robot.max_angular_velocity == warehouse.robot.max_angular_velocity
        assert robot.max_linear_acceleration == warehouse.robot.max_linear_acceleration

    def test_a_candidate_cannot_declare_its_own_vehicle(self) -> None:
        """``_robot_config`` narrows the deployment's robot spec and takes
        nothing else. A stack that could widen its own turning circle
        would be competing in a different vehicle."""
        parameters = set(inspect.signature(episode_module._robot_config).parameters)
        assert parameters == {"profile"}

    def test_the_simulators_robot_has_no_control_period_field(
        self, warehouse: TaskProfile, contexts: tuple[EpisodeContext, ...]
    ) -> None:
        """``control_period`` is a *requirement* (G4's threshold), not a
        property of the vehicle. Keeping it off the simulator's robot is
        what stops a candidate's declared loop rate from changing how the
        world is stepped."""
        robot = scenario_for(warehouse, contexts[0]).robot
        assert not hasattr(robot, "control_period")


class TestSameExternalRandomness:
    """Invariant 3 — and the noise it was written in advance of.

    It used to hold trivially: the world drew no random numbers at all,
    obstacle motion being a closed-form function of time and the episode
    seed. The guard was written then anyway, against the day per-step
    randomness arrived. It has now arrived
    (:mod:`planbench_simulator.noise`), and the invariant survives for a
    specific reason: every draw is a pure function of ``(seed, stream,
    step)`` rather than the next value off a shared stream, so a
    candidate that steps or replans differently cannot shift anybody
    else's noise.
    """

    def test_noise_is_the_episodes_not_the_candidates(
        self, warehouse: TaskProfile, contexts: tuple[EpisodeContext, ...]
    ) -> None:
        """The amplitudes come from the deployment. A candidate able to
        declare its own would be choosing its own exam."""
        for context in contexts:
            built = scenario_for(warehouse, context)
            assert built.sensor_noise == warehouse.environment.sensor_noise

    def test_two_candidates_meet_the_same_noise_at_every_step(self) -> None:
        """The property the whole indexed-not-consumed design exists for.

        Two candidates in one episode context run different numbers of
        steps and replan at different moments. Drawing sequentially would
        make the noise a function of that behaviour, so the two would
        face different worlds under one ``episode_context_id`` — this
        invariant broken by the very fix meant to preserve it.
        """
        spec = SensorNoise(lidar_range_sigma_m=0.02, wheel_slip_fraction=0.02)
        one = NoiseModel(spec=spec, seed=11)
        other = NoiseModel(spec=spec, seed=11)
        # "Other candidate" = the same episode queried in a different
        # order, after a different number of prior draws.
        _ = [one.slip_factors(step) for step in range(50)]
        for step in (0, 7, 40):
            assert one.slip_factors(step) == other.slip_factors(step)

    def test_planning_draws_cannot_move_the_noise_either(self, warehouse: TaskProfile) -> None:
        """The same guard as for obstacle motion, one layer over: a
        planner exhausting a global generator must not shift the world's
        draws."""
        spec = SensorNoise(lidar_range_sigma_m=0.05, wheel_slip_fraction=0.05)
        before = NoiseModel(spec=spec, seed=3).slip_factors(9)

        rng = np.random.default_rng(999)
        rng.random(2048)
        np.random.random(64)
        random.random()

        assert NoiseModel(spec=spec, seed=3).slip_factors(9) == before

    def test_a_deployment_that_declares_nothing_stays_deterministic(
        self, warehouse: TaskProfile
    ) -> None:
        """Default off, and off is exact. Every result stored before the
        noise model existed was produced under a world that drew nothing,
        so a profile that says nothing must still draw nothing."""
        assert warehouse.environment.sensor_noise.active is False
        model = NoiseModel(spec=warehouse.environment.sensor_noise, seed=1)
        assert model.slip_factors(5) == (1.0, 1.0)
        assert model.lidar_offsets(5, 16) is None

    def test_the_world_seed_is_the_episodes_not_the_candidates(
        self, warehouse: TaskProfile, contexts: tuple[EpisodeContext, ...]
    ) -> None:
        for context in contexts:
            assert scenario_for(warehouse, context).random_seed == context.seed

    def test_a_planners_draws_cannot_move_the_world(self, warehouse: TaskProfile) -> None:
        """RRT* is randomised; the traffic must not be. If the planner
        drew from the same stream as the world, then swapping A* for
        RRT* would move the obstacles — and the paired comparison would
        be over two different episodes wearing one id.
        """
        obstacle = warehouse.environment.dynamic_obstacles[0]
        before = [position_at(obstacle, t, 5) for t in (1.0, 9.0, 23.0)]

        rng = np.random.default_rng(12345)
        rng.random(10_000)
        np.random.seed(777)
        np.random.random(10_000)
        random.seed(777)
        [random.random() for _ in range(10_000)]

        assert [position_at(obstacle, t, 5) for t in (1.0, 9.0, 23.0)] == before

    def test_the_randomised_planner_owns_its_generator(self) -> None:
        """RRT* must not consume the global streams. If it did, every
        candidate evaluated after it in the same process would see a
        different world — and the order of the run would decide the
        result."""
        from planbench_planning.rrtstar.planner import RRTStarPlanner

        source = inspect.getsource(RRTStarPlanner)
        assert "default_rng" in source or "Generator" in source
        assert "np.random.seed" not in source
        assert "random.seed" not in source

    def test_planning_leaves_the_global_streams_untouched(
        self, warehouse: TaskProfile, contexts: tuple[EpisodeContext, ...]
    ) -> None:
        """The behavioural form: plan with the randomised stack, then
        check the ambient random state is where it was."""
        from planbench_simulator.grid import OccupancyGrid
        from planbench_simulator.nav_stack import plan_global_path

        np.random.seed(4242)
        random.seed(4242)
        numpy_before = np.random.get_state()
        python_before = random.getstate()

        _, rrtstar = both_candidates()
        planner, _ = episode_module.build_planners(rrtstar, episode_seed=3)
        scenario = scenario_for(warehouse, contexts[0])
        map_data = load_task_map(warehouse, base_dir=REPO_ROOT)
        plan_global_path(map_data, scenario, planner)
        assert isinstance(OccupancyGrid(map_data), OccupancyGrid)

        assert np.random.get_state()[1].tolist() == numpy_before[1].tolist()
        assert random.getstate() == python_before


class TestSamePhysicsAndTime:
    """Invariant 4."""

    def test_the_step_comes_from_the_deployment_not_the_controller(
        self, warehouse: TaskProfile, contexts: tuple[EpisodeContext, ...]
    ) -> None:
        """``simulation_dt`` is capped by ``profile.robot.control_period``.
        Both candidates here declare a DWA ``control_period`` of their own
        in ``params``; it must not reach the physics, or a stack could buy
        a finer-integrated world by asking for a faster loop."""
        scenario = scenario_for(warehouse, contexts[0])
        assert scenario.simulation_dt == min(
            episode_module.MAX_SIMULATION_DT, warehouse.robot.control_period
        )
        astar, rrtstar = both_candidates()
        assert astar.params["dwa"]["control_period"] == LOCAL["control_period"]
        assert rrtstar.params["dwa"]["control_period"] == LOCAL["control_period"]
        # ...and the scenario would be the same whatever they declared,
        # because it was built without consulting them at all.
        assert scenario == scenario_for(warehouse, contexts[0])

    def test_a_slower_deployment_loop_does_not_coarsen_the_physics(self) -> None:
        """The cap exists in one direction only. A deployment declaring a
        relaxed real-time budget must not also get a robot simulated in
        half-second jumps — that is a different experiment, not a more
        lenient one."""
        relaxed = load(WAREHOUSE).model_copy(
            update={"robot": load(WAREHOUSE).robot.model_copy(update={"control_period": 0.5})}
        )
        context = build_evaluation_contexts(relaxed, seed_count=1)[0]
        assert scenario_for(relaxed, context).simulation_dt == episode_module.MAX_SIMULATION_DT

    def test_the_timeout_is_the_deployments(
        self, warehouse: TaskProfile, contexts: tuple[EpisodeContext, ...]
    ) -> None:
        scenario = scenario_for(warehouse, contexts[0])
        assert scenario.timeout_seconds == warehouse.constraints.episode_timeout_s


class TestSameSuccessAndFailureSemantics:
    """Invariant 5."""

    def test_goal_tolerance_and_stuck_window_come_from_the_deployment(
        self, warehouse: TaskProfile, contexts: tuple[EpisodeContext, ...]
    ) -> None:
        scenario = scenario_for(warehouse, contexts[0])
        assert scenario.goal_tolerance == warehouse.constraints.goal_tolerance_m
        assert scenario.stuck_time_window == warehouse.constraints.stuck_threshold_s

    def test_the_verdict_is_computed_from_the_trace_not_from_the_stack(self) -> None:
        """HĐ-6 puts every metric — including ``success`` — in one module
        whose only inputs are the trace, the profile, the context and the
        map. A per-candidate success rule would let one stack be graded
        gently."""
        from planbench_metrics.definitions import compute_metrics

        parameters = set(inspect.signature(compute_metrics).parameters)
        assert parameters == {"trace", "profile", "context", "map_data", "resource_profile"}
        assert "candidate" not in parameters

    def test_the_resource_profile_only_reaches_the_memory_estimate(self) -> None:
        """``resource_profile`` is the one candidate-derived input to the
        metrics, and HĐ-7.3 confines it to G5's estimate. If it touched
        success or clearance, a candidate's own declaration would move
        its verdict."""
        from planbench_metrics import definitions

        source = inspect.getsource(definitions.compute_metrics)
        assert "resource_profile" in source
        assert "memory_estimate" in source


class TestSameScenarioDistribution:
    """Invariant 6."""

    def test_contexts_are_generated_without_the_candidates(self) -> None:
        parameters = set(inspect.signature(build_evaluation_contexts).parameters)
        assert "candidate" not in parameters
        assert "candidates" not in parameters

    def test_every_candidate_runs_exactly_the_same_episodes(
        self, warehouse: TaskProfile, contexts: tuple[EpisodeContext, ...]
    ) -> None:
        candidates = list(both_candidates())
        seen: dict[str, list[str]] = {c.candidate_id: [] for c in candidates}
        for context, candidate in iter_run_plan(contexts, candidates):
            seen[candidate.candidate_id].append(context.episode_context_id)
        sets = [tuple(v) for v in seen.values()]
        assert len(set(sets)) == 1, "candidates were given different episode sets"
        assert len(sets[0]) == len(contexts)

    def test_the_episode_count_is_the_deployments_decision(self, warehouse: TaskProfile) -> None:
        """HĐ-7.1: N comes from the accepted collision risk, not from
        whoever is being evaluated.

        Asserted against the declared risk rather than by reimplementing
        the formula — the first draft of this test wrote
        ``-(-3.0 // 0.03)`` and got 101, because ``3.0 / 0.03`` is
        100.00000000000001. ``n_min_evaluation_episodes`` rounds before
        it ceilings for exactly that reason, and a test that repeats the
        arithmetic tests the copy instead of the original.
        """
        assert warehouse.constraints.collision_probability_max == 0.01
        assert warehouse.constraints.n_min_evaluation_episodes == 300

    @pytest.mark.parametrize(("risk", "expected"), [(0.1, 30), (0.03, 100), (0.01, 300), (0.5, 6)])
    def test_the_count_moves_with_the_declared_risk(self, risk: float, expected: int) -> None:
        """A stricter deployment buys more episodes; nothing a candidate
        declares can shorten the run."""
        profile = load(WAREHOUSE)
        stricter = profile.model_copy(
            update={
                "constraints": profile.constraints.model_copy(
                    update={"collision_probability_max": risk}
                )
            }
        )
        assert stricter.constraints.n_min_evaluation_episodes == expected


class TestGatesAreNotWidenedToFitTheImplementation:
    """A seventh axis, and the one that got past the other six.

    Nothing here is about two candidates being treated differently — they
    were not. It is about the *world* being relaxed until the code fit
    inside it, which every symmetry test passes with flying colours
    because it relaxes both sides equally.

    The concrete case: G4's threshold is ``robot.control_period``, both
    reference profiles declared 10 Hz instead of the deployment's 20 Hz,
    and the reason written in the file was that the Python DWA cannot
    close a loop in 50 ms. The real-time gate was widened from 50 ms to
    100 ms because the candidate could not clear it. Two later fixes —
    pooled p99 (contract 3.0.0) and core pinning (Phase 5.1) — had
    already removed the need: measured p99 is 10.81 ms and 16.10 ms.
    """

    def test_both_reference_deployments_declare_the_real_control_period(self) -> None:
        """20 Hz, as §6.2 of the topic document states. Relaxing this
        field is relaxing G4, so it may not drift without someone
        noticing here."""
        for path in (HALL, WAREHOUSE):
            assert load(path).robot.control_period == 0.05, path.name

    def test_the_gate_threshold_is_that_declaration(self) -> None:
        assert load(WAREHOUSE).robot.t_cycle_ms == 50.0

    def test_relaxing_the_gate_does_not_buy_a_cheaper_simulation(self) -> None:
        """The incentive that made the concession attractive must not
        exist. If a slower declared loop also coarsened the physics, then
        widening G4 would pay for itself in wall clock and the pressure
        to widen it would never go away.

        It does not: ``simulation_dt`` is ``min(MAX_SIMULATION_DT,
        control_period)`` and MAX is 0.05, so 10 Hz and 20 Hz integrate
        the world identically.
        """
        strict = load(WAREHOUSE)
        relaxed = strict.model_copy(
            update={"robot": strict.robot.model_copy(update={"control_period": 0.1})}
        )
        context = build_evaluation_contexts(strict, seed_count=1)[0]
        assert (
            scenario_for(strict, context).simulation_dt
            == scenario_for(relaxed, context).simulation_dt
        )

    def test_a_candidate_may_not_run_slower_than_the_deployment_asks(self) -> None:
        """The loophole underneath the concession. G4 times a single
        controller call, so a 10 Hz controller on a 20 Hz deployment
        looks *cheap* to the gate rather than late — it holds each
        command for two deployment cycles and nothing measures that."""
        warehouse = load(WAREHOUSE)
        slow = candidate_from_stack("astar+dwa", params={**LOCAL, "control_period": 0.1})
        with pytest.raises(Exception, match="closes its control loop"):
            validate_control_rate(warehouse, [slow])

    def test_the_slice_candidates_satisfy_it(self) -> None:
        validate_control_rate(load(WAREHOUSE), list(both_candidates()))
        validate_control_rate(load(HALL), list(both_candidates()))

    def test_the_declared_risk_is_not_a_runtime_budget(self) -> None:
        """``collision_probability_max`` is the site's safety
        requirement, and HĐ-7.1 runs `risk -> N_min -> hours`, never
        back. An earlier revision declared 3% with "because the run has
        to share a working machine" written in the profile — a machine
        being busy is not a fact about the warehouse.

        Running fewer episodes than N_min stays possible and needs no
        edit to the deployment: G2 reports the shortfall instead.
        """
        assert load(WAREHOUSE).constraints.collision_probability_max == 0.01

    def test_no_deployment_may_require_a_heading(self) -> None:
        """The same shape one layer over: HĐ-6 judges arrival on position
        and heading, the simulator has no final-orientation controller,
        so a heading requirement fails every candidate for a property of
        the platform. Refused at load, and the reservation lives in the
        contract rather than in a comment inside one profile."""
        for path in (HALL, WAREHOUSE):
            assert load(path).constraints.goal_tolerance_rad >= 3.14159, path.name


class TestTheTwoHallsStayInStep:
    """``open_hall_v1`` and ``open_hall_v2`` are one hall doing two jobs.

    v1 is a measuring instrument: fully deterministic, which is what lets
    the symmetry tests compare two runs step by step instead of comparing
    distributions. v2 is a deployment to measure on, with the vehicle's
    real noise declared so a deterministic stack stops replaying one
    episode per seed.

    They must therefore differ in exactly two things and never in a
    third. A mission or a map that drifted between them would make every
    fairness property asserted on v1 a statement about a hall that is not
    the one being measured — and nothing would say so.
    """

    def test_they_differ_only_in_id_and_noise(self) -> None:
        quiet = load(HALL).model_dump()
        noisy = load(NOISY_HALL).model_dump()
        quiet_env = quiet.pop("environment")
        noisy_env = noisy.pop("environment")
        assert quiet.pop("id") == "open_hall_v1"
        assert noisy.pop("id") == "open_hall_v2"
        assert quiet == noisy
        assert quiet_env.pop("sensor_noise") != noisy_env.pop("sensor_noise")
        assert quiet_env == noisy_env

    def test_the_instrument_stays_silent(self) -> None:
        """v1's determinism is load-bearing for the symmetry suite, so it
        is asserted rather than assumed."""
        assert load(HALL).environment.sensor_noise.active is False

    def test_the_hall_declares_itself_an_acceptance_deployment(self) -> None:
        """``success_rate_min = 1.00``, and the number is the claim.

        The hall is easy, mirror-symmetric and run under declared noise:
        nothing here defeats a stack by geometry. So a failure is not a
        statistic to average — it is a **diagnostic signal**, and one is
        enough to say something is wrong with the stack or its
        configuration.

        This is emphatically **not** an operating requirement for a real
        site; ``warehouse_a_v2`` declares its own. Reading a red G3 here
        as "unfit to ship" is reading an instrument as a customer.

        Until 2026-08-11 both halls said 0.95, copied from the warehouse
        and never declared for the hall — the only constant in either
        file without a reason beside it. Answering it needed the
        deployment's *role*, not any candidate's result (HĐ-15.3).
        """
        for path in (HALL, NOISY_HALL):
            assert load(path).constraints.success_rate_min == 1.00, path.name

    def test_the_deployment_declares_the_noise_axes_of_the_topic_document(self) -> None:
        noise = load(NOISY_HALL).environment.sensor_noise
        assert noise.lidar_range_sigma_m == 0.02
        assert noise.wheel_slip_fraction == 0.02

    def test_a_new_world_gets_a_new_id_so_traces_cannot_be_reused(self) -> None:
        """The trap this split exists to avoid. ``episode_context_id``
        hashes (task_profile_id, mission_id, environment_variant, seed)
        and HĐ-3.1 freezes that payload — the noise amplitude is not in
        it. Editing sigma in place would leave every context id
        unchanged, and ``--reuse-traces`` would serve episodes recorded
        in a world that no longer exists, with nothing to warn anyone.
        """
        quiet = build_evaluation_contexts(load(HALL), seed_count=4)
        noisy = build_evaluation_contexts(load(NOISY_HALL), seed_count=4)
        assert [c.seed for c in quiet] == [c.seed for c in noisy]
        assert not (
            {c.episode_context_id for c in quiet} & {c.episode_context_id for c in noisy}
        )


class TestTheReplanGridIsAKnownInformationAsymmetry:
    """A fairness defect that is latent today and must not go live quietly.

    On a replan the *global planner* is handed a grid with the dynamic
    obstacles' **ground-truth** positions burned into it
    (``nav_stack._replan``). The reasoning is sound and written down: a
    planner given only the static map would replan the identical route it
    was just blocked on, because none of its inputs changed.

    Among the candidates that can run today this is symmetric — every
    modular stack gets the same grid, so no comparison is distorted.

    It stops being symmetric the moment a ``monolithic`` candidate can
    run. HĐ-4's ``MonolithicPolicy`` sees only ``Observation``; a modular
    stack's global planner sees where the obstacles actually are. That is
    the information-privilege P02 and G6 exist to price, and it would
    favour modular stacks for a reason that has nothing to do with
    navigation quality.

    The test below fails the day the adapter lands. That is deliberate:
    it is the cheapest way to make whoever adds it read this.
    """

    def test_only_modular_stacks_can_run_today(self) -> None:
        from planbench_benchmark import candidates as candidates_module

        source = inspect.getsource(candidates_module)
        assert "MonolithicPolicy" in source
        assert "does not exist yet" in source, (
            "A monolithic candidate can now be run. Before comparing one against a modular "
            "stack, settle the replan asymmetry documented on this test: the modular stack's "
            "global planner sees ground-truth obstacle positions on a replan and the policy "
            "does not (HĐ-4, P02, G6)."
        )

    def test_the_ground_truth_hatch_is_used_by_the_stack_not_by_a_planner(self) -> None:
        """``dynamic_obstacles_now`` is the engine's ground truth. It may
        be read *between* control steps to rebuild a planning grid; it
        must never be reachable through ``get_observation``, which is
        what every candidate type sees.

        Asserted over the whole observation path rather than one method:
        adding the noise model put a helper between the two, and a check
        that only read ``get_observation`` would have gone quiet at
        exactly the moment a new layer appeared.
        """
        from planbench_simulator import engine as engine_module

        path = "".join(
            inspect.getsource(getattr(engine_module.SimulationEngine, name))
            for name in ("get_observation", "_measured_ranges")
        )
        assert "dynamic_obstacles_now" not in path
        assert "_sensor_grid_now" in path

    def test_measurement_noise_does_not_reach_the_collision_test(self) -> None:
        """LiDAR noise is an error in what the robot *reads*. A collision
        judged on a noisy pose would be a different world, not a robot
        that measures poorly — so the termination check must not consult
        the noise model at all."""
        from planbench_simulator import engine as engine_module

        source = inspect.getsource(engine_module.SimulationEngine._check_termination)
        assert "_noise" not in source
        assert "lidar" not in source.lower()


class TestTheSimulatorIsDeterministic:
    """The precondition for all six. Without it, "same world" is not a
    property anyone can check, and a re-run is not a re-run."""

    def test_one_context_gives_one_world_every_time(
        self, warehouse: TaskProfile, contexts: tuple[EpisodeContext, ...]
    ) -> None:
        obstacle = warehouse.environment.dynamic_obstacles[0]
        for context in contexts:
            trajectory = [position_at(obstacle, t / 4, context.seed) for t in range(200)]
            again = [position_at(obstacle, t / 4, context.seed) for t in range(200)]
            assert trajectory == again

    def test_different_seeds_give_different_worlds(self, warehouse: TaskProfile) -> None:
        """The other half: if every seed gave the same world, the
        evaluation set would have one member however many rows it had
        (HĐ-7.1's effective sample size)."""
        obstacle = warehouse.environment.dynamic_obstacles[0]
        snapshots = {position_at(obstacle, 30.0, seed) for seed in range(20)}
        assert len(snapshots) > 1
