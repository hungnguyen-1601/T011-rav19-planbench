"""Navigation stacks: a global planner + a local planner (controller).

A benchmark always compares *stacks* — ``astar+dwa`` versus
``astar+ppo`` versus Nav2 — never a global planner against a local one
(decision D13).

Planning-safety margin: the planning grid is inflated by
``hard_clearance(robot, envelope) + sqrt(2) * resolution``. The first
term is the hard feasible set, shared with the local controller so the
two layers cannot disagree about where the robot may be; the second is
the half-diagonal of a cell, so a line-of-sight-sampled path cannot
graze obstacle corners (see the proof in the docstring of
``episode_runner``). They are different kinds of quantity and
``_inflation_radius`` keeps them separable — only the first belongs in a
feasibility judgement. The engine still checks collisions with the exact
robot radius.
"""

from __future__ import annotations

import inspect
import math
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from planbench_metrics import EpisodeMetrics, compute_episode_metrics
from planbench_planning import AStarPlanner, GlobalPlanner, PlanResult
from planbench_planning.common.local_base import LocalPlanner, LocalPlanResult
from planbench_schemas.episode import EpisodeEvent, EpisodeResult, EpisodeStatus, Observation
from planbench_schemas.feasibility import SafetyEnvelope, hard_clearance
from planbench_schemas.geometry import EPS, Point2D
from planbench_schemas.map import CellState, MapData
from planbench_schemas.replanning import NO_REPLANNING, ReplanningConfig
from planbench_schemas.robot import RobotConfig, RobotState
from planbench_schemas.scenario import CircleObstacle, Scenario
from planbench_schemas.sensor import LidarConfig
from planbench_simulator.engine import SimulationEngine
from planbench_simulator.grid import OccupancyGrid, rasterize_obstacles
from planbench_simulator.path_follower import PurePursuitConfig, PurePursuitFollower
from planbench_simulator.trace import (
    EpisodeTraceRecorder,
    clearance_probe,
    event_for_status,
)


class PurePursuitLocalPlanner(LocalPlanner):
    """LocalPlanner adapter around the pure-pursuit follower.

    TEMPORARY reference controller (decision D12) — it ignores sensing
    and therefore must never appear in algorithm comparisons.
    """

    def __init__(self, config: PurePursuitConfig | None = None) -> None:
        self._config = config
        self._follower: PurePursuitFollower | None = None

    @property
    def name(self) -> str:
        return "pure_pursuit"

    def reset(self, global_path: Sequence[Point2D], robot: RobotConfig) -> None:
        self._follower = PurePursuitFollower(global_path, robot, self._config)

    def compute(self, state: RobotState, observation) -> LocalPlanResult:  # noqa: ANN001
        if self._follower is None:
            raise RuntimeError("reset() must be called before compute()")
        return LocalPlanResult(action=self._follower.compute_action(state))


class StackRun(BaseModel):
    """Everything one stack episode produced.

    ``metrics`` is the *previous* topic's in-memory metric set. It is
    ``None`` when the caller asked for it to be skipped — which the
    contract pipeline does, because HĐ-5 makes the trace file the single
    input of the Metrics Engine and a second set computed during the
    simulation is exactly the parallel source that rule forbids.
    """

    model_config = ConfigDict(frozen=True)

    algorithm: str
    plan: PlanResult
    result: EpisodeResult
    metrics: EpisodeMetrics | None
    plans: tuple[PlanResult, ...] = ()
    """Every path the global planner returned, first plan included.

    ``plan`` is ``plans[0]`` and stays because most callers want the
    route the episode set out on. This carries the rest so contract L1 —
    *global may only return paths inside the hard set local can drive* —
    is checkable at all: the replans are where a path outside that set
    would come from, since they are planned from a **believed** pose over
    a grid whose inflation was relaxed around the robot.

    Refused replans are not here. A plan that found nothing has no path
    to check, and its refusal is already an episode event.

    Empty means **not recorded**, not "no plans" — episodes stored before
    this field existed come back that way, and reconstructing ``(plan,)``
    for them would claim they never replanned.
    """


def _planning_grid(
    map_data: MapData,
    scenario: Scenario,
    extra_obstacles: Sequence[CircleObstacle] = (),
) -> OccupancyGrid:
    """Inflated grid the global planner plans on.

    ``extra_obstacles`` are burned in alongside the static ones. Empty
    for the initial plan — a global planner reasons about the map, not
    about where a pedestrian happened to be at t=0 — and populated on a
    replan, where the whole point is that something is in the way.
    """
    planning_map = rasterize_obstacles(map_data, scenario.static_obstacles)
    if extra_obstacles:
        planning_map = rasterize_obstacles(planning_map, extra_obstacles)
    return OccupancyGrid(planning_map).inflate(_inflation_radius(map_data, scenario))


def _inflation_radius(map_data: MapData, scenario: Scenario) -> float:
    """How far the planner keeps off, and where each part comes from.

    Two parts, and they are **different kinds of quantity**:

    * :func:`~planbench_schemas.feasibility.hard_clearance` — the hard
      feasible set, shared with the local controller. Footprint plus the
      deployment's safety envelope, both deployment-owned. This is the
      part neither layer may go inside.
    * ``√2 × resolution`` — the half-diagonal of a cell, so a diagonal
      step between two free cells cannot clip the corner of an occupied
      one. **Not a safety property at all**: it is an artifact of drawing
      a continuous set on a grid, and it shrinks when somebody halves the
      cell size with nothing about the world having changed.

    Keeping them separable matters because only the first belongs in a
    feasibility judgement. Anything validating L1 or L4 must ask
    ``hard_clearance`` directly rather than this, or it will call a
    coarsely rasterised path infeasible. The quantisation term moves out
    of prohibition and into cost in the graded-inflation phase; until
    then it stays here and `_with_room_to_leave` is what stops it
    trapping the robot.
    """
    envelope = SafetyEnvelope.for_noise(scenario.sensor_noise)
    return hard_clearance(scenario.robot, envelope) + math.sqrt(2.0) * map_data.resolution


def plan_global_path(
    map_data: MapData, scenario: Scenario, global_planner: GlobalPlanner | None = None
) -> tuple[PlanResult, OccupancyGrid]:
    """Run the global planner on the inflated grid; also return the raw grid.

    Defaults to A* so callers that do not care which global planner runs
    (the RL environment, most tests) keep the historical behaviour.
    """
    planner = global_planner or AStarPlanner()
    plan = planner.plan(
        _planning_grid(map_data, scenario),
        scenario.start_pose.position,
        scenario.goal_pose.position,
    )
    return plan, OccupancyGrid(map_data)


def _with_room_to_leave(
    inflated: OccupancyGrid, solid: OccupancyGrid, position: Point2D, radius: float
) -> OccupancyGrid:
    r"""Undo the *inflation* around the robot — never the obstacles.

    **Why this exists, measured rather than assumed.** A robot that has
    just been blocked is standing closer to the thing blocking it than
    the planner's inflation margin, because the two layers do not use the
    same margin. When this was written they disagreed twice over: the
    controller rejected a trajectory at ``robot.radius + safety_margin``
    — a *candidate* parameter — while the planner inflated by
    ``robot.radius + √2 × resolution`` on cells, giving 0.31 m against
    0.61 m on the shipped `sudden_stop`.

    Half of that is now gone: both layers share
    :func:`~planbench_schemas.feasibility.hard_clearance`, and
    ``safety_margin`` is a soft cost. What remains is the grid term, and
    it remains **on purpose** — a diagonal step between two free cells
    must not clip an occupied corner. But it is a property of the *map's
    resolution* rather than of the world, so it must not decide whether a
    robot may stand somewhere, and this is what stops it doing so until
    the graded-inflation phase moves it into cost.

    So the robot parks at a spot that is legal by its own test and 0.30 m
    inside the planner's no-go ring. Freeing only the cell it stands in —
    which is what this did before — left it with **0 of 8 free
    neighbours**: A\* entered the start cell and could not take a single
    step, reporting "no path exists between start and goal" while a
    point-robot flood fill of the same scene reached the goal easily. The
    robot never moved, so all 55 replans of a 120-second episode met the
    identical grid and returned the identical refusal.

    **What is safe to assert here.** The engine ends an episode the
    instant the robot overlaps an obstacle, so a robot that is still
    driving is provably not inside one — and neither is the ground it
    could reach before the inflation was applied. This frees exactly the
    cells that are blocked on ``inflated`` but free on ``solid``: the
    ones blocked *because of the buffer*, never one holding a real
    return. A path out may therefore pass closer to the cart than the
    planner would normally allow, and the local controller still refuses
    to drive into it — the continuous collision test runs every control
    step and is not relaxed by anything here.

    Bounded to ``radius`` around the robot so the relaxation is local:
    beyond the bubble the map is inflated exactly as before, and any
    route that leaves has to cross genuinely clear space to get anywhere.
    """
    centre = inflated.world_to_grid(position.x, position.y)
    if centre is None:
        return inflated
    resolution = inflated.resolution
    reach = max(1, int(math.ceil(radius / resolution)))
    row0, col0 = centre
    cells = list(inflated.map_data.cells)
    solid_cells = solid.map_data.cells
    changed = False
    for row in range(max(0, row0 - reach), min(inflated.height, row0 + reach + 1)):
        for col in range(max(0, col0 - reach), min(inflated.width, col0 + reach + 1)):
            index = row * inflated.width + col
            if cells[index] == CellState.FREE.value:
                continue
            # The whole rule, in one line: blocked by the buffer, not by
            # anything the robot can see.
            if solid_cells[index] != CellState.OCCUPIED.value:
                cells[index] = CellState.FREE.value
                changed = True
    if not changed:
        return inflated
    return OccupancyGrid(
        inflated.map_data.model_copy(update={"cells": tuple(cells)}),
        inflated.unknown_as_occupied,
    )


def _map_as_the_robot_sees_it(
    map_data: MapData, observation: Observation, lidar: LidarConfig
) -> MapData:
    """The static map plus **one occupied cell per LiDAR return**.

    A range reading says *something is at this bearing and this distance*
    and nothing more. So each return marks exactly the cell that contains
    the point it stopped at — no circle around it, no assumed extent.

    **The first draft did use a circle, of half a cell diagonal, and it
    broke the premise the replanning tests exist for.** At a half-metre
    resolution that circle is wider than a cell, so every one of the
    seventy-two returns painted a two-by-two block; the walls thickened
    by a third of a metre before the planner's own inflation, both
    doorways closed, and A* — which is complete, so this was not sampler
    luck — reported no path where a metre and a half of clearance was
    actually free. A measurement rendered wider than the measurement is
    an obstacle the robot invented.

    **Returns at maximum range are dropped, and that line is load
    bearing.** A ray reaching its limit means "nothing within range";
    burning it in would build a wall out of empty floor at exactly the
    distance the sensor stops seeing, ringing the robot in.

    Noise reaches the planner here, on purpose. A robot that measures
    badly plans on bad measurements — that is what measuring badly *is*.
    It still never reaches the collision test, which stays on the true
    geometry (see :mod:`planbench_simulator.noise`).
    """
    increment = lidar.angle_span / lidar.num_rays
    start = observation.pose.theta - lidar.angle_span / 2.0
    cells = list(map_data.cells)
    for index, distance in enumerate(observation.lidar_ranges):
        if distance >= lidar.max_range - EPS:
            continue
        angle = start + index * increment
        column = math.floor(
            (observation.pose.x + distance * math.cos(angle) - map_data.origin.x)
            / map_data.resolution
        )
        row = math.floor(
            (observation.pose.y + distance * math.sin(angle) - map_data.origin.y)
            / map_data.resolution
        )
        if 0 <= row < map_data.height and 0 <= column < map_data.width:
            cells[row * map_data.width + column] = CellState.OCCUPIED.value
    return map_data.model_copy(update={"cells": tuple(cells)})


def _reset_local(
    local_planner: LocalPlanner,
    path: Sequence[Point2D],
    robot: RobotConfig,
    envelope: SafetyEnvelope,
) -> None:
    """Hand a path to the controller, with the envelope if it takes one.

    Not every local planner has been taught about the envelope — a
    monolithic policy has no notion of a keep-out to respect — so this
    passes it only where it is accepted rather than forcing the argument
    into an interface some implementations cannot use. Detected once per
    reset, from the signature, so a controller that gains the parameter
    later starts receiving it without anything here changing.
    """
    if "envelope" in inspect.signature(local_planner.reset).parameters:
        local_planner.reset(path, robot, envelope)  # type: ignore[call-arg]
    else:
        local_planner.reset(path, robot)


def _replan(
    map_data: MapData,
    scenario: Scenario,
    global_planner: GlobalPlanner,
    engine: SimulationEngine,
) -> PlanResult:
    """Plan again from where the robot is, around what the robot can see.

    Both halves matter. Replanning from the original start would hand
    back a path the robot has already half-driven; replanning on the
    static-only grid would hand back the identical path, because none of
    the planner's inputs would have changed since it was blocked.

    **The obstacles come from ``get_observation`` and not from the
    engine's ground truth, and that is a fairness requirement rather than
    a style choice** (HĐ-4.1). This used to read
    ``engine.dynamic_obstacles_now()`` — where the obstacles *actually*
    were. Among modular stacks that was symmetric, so no comparison was
    distorted; it stops being symmetric the moment a ``monolithic``
    candidate runs, because an end-to-end policy sees only
    ``Observation`` while a modular stack's global planner would be
    seeing through walls. That is the information privilege G6 exists to
    price, and it would favour modular stacks for a reason with nothing
    to do with navigation quality.

    The contract names the fix and rules out the alternative: replan from
    ``Observation``, **not** ground truth for both. Handing it to both
    sides would turn one skewed comparison into two wrong measurements.
    """
    position = engine.get_state().pose.position
    believed = _map_as_the_robot_sees_it(map_data, engine.get_observation(), scenario.lidar)
    grid = _planning_grid(believed, scenario)
    # The un-inflated view, so the relaxation below can tell a cell held
    # by the safety buffer from a cell holding an actual LiDAR return.
    solid = OccupancyGrid(rasterize_obstacles(believed, scenario.static_obstacles))
    return global_planner.plan(
        _with_room_to_leave(grid, solid, position, _inflation_radius(believed, scenario)),
        position,
        scenario.goal_pose.position,
    )


#: Engine verdicts a replan is allowed to overturn. Both mean "the path
#: this robot is following has stopped working", which is the one thing
#: a new path can fix. A collision or a timeout is not on the list.
_REPLANNABLE = (EpisodeStatus.STUCK, EpisodeStatus.NO_PROGRESS)


class _NoGlobalPlanning(GlobalPlanner):
    """The global planner of a candidate that has none (HĐ-1.2).

    A monolithic policy is one layer. It still goes through the shared
    driving loop — same clock, same ``Observation``, same termination
    rules — because a comparison between two harnesses is not a
    comparison between two navigators. This stands in the one slot the
    loop insists on and reports the truth: **nothing was planned, and
    that is not a failure.**

    ``success=True`` with an empty path, deliberately. ``success=False``
    is how the loop records *no route exists*, which G1 counts; a policy
    that was never asked to find a route must not be counted there.

    Zero planning time and zero expanded nodes are facts, not
    placeholders: a candidate that runs no global search spends nothing
    on one, and charging it a number would price work it did not do.
    """

    @property
    def name(self) -> str:
        return "none"

    def plan(self, grid: OccupancyGrid, start: Point2D, goal: Point2D) -> PlanResult:  # noqa: ARG002
        return PlanResult(success=True, path=(), path_length=0.0, cost=0.0)


#: Passed as ``global_planner`` to run a candidate that plans nothing.
NO_GLOBAL_PLANNING = _NoGlobalPlanning()


def run_policy(
    map_data: MapData,
    scenario: Scenario,
    policy: LocalPlanner,
    recorder: EpisodeTraceRecorder | None = None,
    legacy_metrics: bool = True,
) -> StackRun:
    """Run one episode of a monolithic candidate (HĐ-4's second shape).

    The same engine, the same loop and the same recorder as
    :func:`run_stack` — which is the point. What differs is that no
    global planner runs, so the policy is handed no path and is charged
    for no search.

    **Replanning is not offered and cannot be.** Replanning replaces a
    global path; a policy has none, so a budget here would be a control
    with nothing behind it. A monolithic candidate that drives into a
    dead end recovers with its own next command or it does not, and that
    is the thing being measured.
    """
    return run_stack(
        map_data,
        scenario,
        policy,
        global_planner=NO_GLOBAL_PLANNING,
        replanning=NO_REPLANNING,
        recorder=recorder,
        legacy_metrics=legacy_metrics,
    )


def run_stack(
    map_data: MapData,
    scenario: Scenario,
    local_planner: LocalPlanner,
    global_planner: GlobalPlanner | None = None,
    replanning: ReplanningConfig | None = None,
    recorder: EpisodeTraceRecorder | None = None,
    legacy_metrics: bool = True,
) -> StackRun:
    """Run one episode of ``<global_planner>+<local_planner>`` on a scenario.

    Deterministic for identical inputs (given deterministic planners; a
    sampling planner counts as deterministic once its seed is fixed —
    see ``RRTStarPlanner``). Local-planner failures are recorded as
    episode events, not swallowed.

    ``replanning`` is a property of the evaluation conditions, not of the
    stack: it is applied here, on the path every stack goes through, with
    one trigger and one budget for all of them. It defaults to disabled,
    and a disabled run is byte-identical to the behaviour before
    replanning existed.

    ``recorder`` writes the HĐ-5 trace as the episode happens. It has to
    happen here, inside the one loop, rather than afterwards from
    ``result.trajectory``: ``clearance_m`` is a distance to obstacles that
    have since moved, and no amount of post-processing recovers it. The
    caller owns the recorder's lifetime, so a run that raises still leaves
    the samples it collected on disk.

    Note what one recorded row means: **one control step**, not one
    simulation tick. HĐ-6 defines ``p99_latency_ms`` as the compute time
    of a control step, and a controller running slower than the simulator
    holds its last command for several ticks. Emitting those held ticks
    with a latency of zero would drag the 99th percentile down and make
    G4 pass on steps where nothing was computed — optimistic in exactly
    the direction a real-time gate must not be.

    The one exception is the final row, which carries the terminal event
    at the moment the episode ended and reports a latency of zero because
    nothing was computed there. It is a single sample among the hundreds a
    normal episode records, so its effect on the 99th percentile is
    bounded by one rank; the alternative — dating ``goal_reached`` to the
    last control tick — would move the final pose that HĐ-6 checks against
    the goal tolerance, which is not bounded at all.

    ``legacy_metrics=False`` skips the previous topic's ``EpisodeMetrics``
    entirely. Two reasons, and the first is the one that matters: HĐ-5
    makes the trace the single input of the Metrics Engine, so computing
    a second metric set inside the simulation is the parallel source the
    contract exists to prevent. The second is cost — that computation
    calls the exhaustive whole-map clearance scan once per trajectory
    sample, and on a 40×25 m map it was three quarters of the wall-clock
    time of a contract episode.
    """
    global_planner = global_planner or AStarPlanner()
    replanning = replanning or NO_REPLANNING
    # A monolithic candidate is one layer, so it is named by one name.
    # "none+policy" would read as a stack whose global planner happened
    # to be missing, which is a different candidate from one that has no
    # global planner by construction (HĐ-1.2).
    algorithm = (
        local_planner.name
        if isinstance(global_planner, _NoGlobalPlanning)
        else f"{global_planner.name}+{local_planner.name}"
    )
    plan, raw_grid = plan_global_path(map_data, scenario, global_planner)

    if not plan.success:
        # One row, so the episode exists in the paired comparison. A
        # candidate that found no route still ran this context, and a
        # missing file would silently shrink its N and unbalance the
        # pairing (HĐ-3.2) — while also hiding the failure from G1,
        # whose whole job is to count exactly this.
        if recorder is not None:
            # Static-only clearance: there is no engine to ask where the
            # moving obstacles are, and building one to measure a robot
            # that never moved would be theatre. The number is the start
            # pose's distance to the fixed world, and that is what the
            # episode is.
            recorder.bind_clearance(
                clearance_probe(raw_grid, scenario.static_obstacles, scenario.robot.radius)
            )
            recorder.record(
                0.0,
                RobotState(pose=scenario.start_pose),
                event="no_path",
                planner_latency_ms=plan.planning_time_seconds * 1000.0,
            )
        result = EpisodeResult(
            status=EpisodeStatus.NO_GLOBAL_PATH,
            reason=plan.failure_reason,
            elapsed_time=0.0,
            steps=0,
            trajectory=(),
            events=(EpisodeEvent(time=0.0, type="no_global_path", message=plan.failure_reason),),
        )
        metrics = (
            compute_episode_metrics(
                result,
                global_planning_time=plan.planning_time_seconds,
                expanded_nodes=plan.expanded_nodes,
                grid=raw_grid,
                obstacles=scenario.static_obstacles,
                robot_radius=scenario.robot.radius,
                replan_count=0,
            )
            if legacy_metrics
            else None
        )
        return StackRun(
            algorithm=algorithm, plan=plan, result=result, metrics=metrics, plans=(plan,)
        )

    engine = SimulationEngine()
    engine.load_map(map_data)
    engine.load_scenario(scenario)
    engine.reset()
    # The hard feasible set travels with the path. It comes from the
    # deployment, not from the controller's own configuration, which is
    # what stops a candidate narrowing the set the planner used (L2).
    envelope = SafetyEnvelope.for_noise(scenario.sensor_noise)
    _reset_local(local_planner, plan.path, scenario.robot, envelope)
    if recorder is not None:
        recorder.bind_clearance(
            clearance_probe(
                raw_grid,
                scenario.static_obstacles,
                scenario.robot.radius,
                engine.dynamic_obstacles_now,
            )
        )

    latencies: list[float] = []
    failures: list[EpisodeEvent] = []
    # Every plan this episode used, initial one first. Planning cost is
    # reported as the total the stack spent, so a stack that recovers by
    # replanning three times is not shown as cheap as one that planned
    # once; the path metrics use the last entry, which is the path the
    # robot was actually following when the episode ended.
    plans: list[PlanResult] = [plan]
    # Controllers run at their own rate; the last command is held between
    # control ticks, exactly as a real /cmd_vel stream behaves.
    control_period = local_planner.control_period
    held_action = None
    next_control_time = 0.0
    #: Global-planner time owed by the next recorded control step. See the
    #: replan branch below for why it is carried rather than recorded on
    #: the spot.
    pending_replan_ms = 0.0
    #: Every attempt, not only the ones that produced a path. The two
    #: differ exactly when a reader most needs them to.
    replan_attempts = 0
    while not engine.is_done():
        recompute = (
            held_action is None or control_period is None or engine.time >= next_control_time - EPS
        )
        if recompute:
            decision = local_planner.compute(engine.get_state(), engine.get_observation())
            step_latency_ms = decision.latency_seconds * 1000.0 + pending_replan_ms
            latencies.append(step_latency_ms / 1000.0)
            if recorder is not None:
                # Recorded before the step, so the row says "at time t the
                # robot was here and deciding cost this much" — pairing the
                # latency with the state it was computed from rather than
                # with the state it produced.
                recorder.record(
                    engine.time,
                    engine.get_state(),
                    # `replan` marks the step that paid for one, which is
                    # what `replan_count` counts.
                    event="replan" if pending_replan_ms > 0.0 else None,
                    planner_latency_ms=step_latency_ms,
                )
            if decision.failure_reason:
                failures.append(
                    EpisodeEvent(
                        time=engine.time,
                        type="local_planner_failure",
                        message=decision.failure_reason,
                    )
                )
            pending_replan_ms = 0.0
            held_action = decision.action
            if control_period is not None:
                next_control_time = engine.time + control_period
        engine.step(held_action)

        if (
            engine.is_done()
            and replanning.allows(len(plans))
            and engine.episode_status in _REPLANNABLE
        ):
            blocked_as = engine.episode_status.value
            new_plan = _replan(map_data, scenario, global_planner, engine)
            # **A replan is compute the next control step had to wait
            # for**, and until it was charged it cost nothing the platform
            # could see: `recorder.record` runs only in the `recompute`
            # branch above, which times the *local* controller, so G4
            # pooled its p99 over a set containing no replan at all. A
            # stack could plan the whole map fifty times and still pass a
            # latency gate measuring 12 ms DWA steps.
            #
            # It is charged onto the **next** step rather than as a row of
            # its own, and the first attempt at a row of its own is what
            # showed why: a replan happens at the same *simulation*
            # instant as the step before it — it costs compute, not
            # sim-time — so the row arrived with a duplicate timestamp and
            # the recorder refused it, exactly as it should ("out-of-order
            # samples silently corrupt every rate and percentile computed
            # from this file"). Delaying the next decision is also the
            # true story: the robot's next command was late by however
            # long the global planner took.
            #
            # This is the whole cost model for unlimited replanning. There
            # is no `max_replans` any more, deliberately: a shared budget
            # is a number somebody chose, and it scores a stack that would
            # have escaped on its fourth try as a failure of the budget
            # rather than of the planner. p99 cuts at the 99th percentile,
            # so one or two replans in four hundred steps sit above the
            # cut and cost nothing, while habitual replanning walks into
            # G4 on its own — the ceiling grows out of the physics instead
            # of being declared.
            pending_replan_ms += new_plan.planning_time_seconds * 1000.0
            replan_attempts += 1
            if not new_plan.success:
                # **A replan that found nothing used to be invisible**, and
                # that is how a robot could sit in front of a cart with
                # replanning switched on, `Replans: 0` on screen, and no
                # way to tell "it never tried" from "it tried and the
                # planner refused". They are opposite diagnoses: the first
                # points at the setting, the second at the world.
                #
                # It happens for an ordinary reason. `_replan` plans from
                # the robot's *believed* pose over a grid built from its
                # own LiDAR returns, so localisation drift and dropout can
                # put the start inside the marked cells or close the only
                # gap — in a 2 m corridor with a 0.4 m cart and a 0.26 m
                # robot there is not much width to lose.
                failures.append(
                    EpisodeEvent(
                        time=engine.time,
                        type="replan_failed",
                        message=(
                            f"replan {replan_attempts} found no path from where the robot "
                            f"believes it is: {new_plan.failure_reason}"
                        ),
                    )
                )
                # **And it no longer ends the episode.** The budget is the
                # timeout, not the first refusal: "no route right now" is
                # not "no route", and traffic moves. Resuming lets the
                # stuck detector fire again later and the stack try again
                # — bounded, because each attempt costs its own A* time and
                # the detector needs another full stuck window before it
                # re-triggers, so the retries are seconds apart in
                # simulation time rather than a tight loop.
                engine.resume_after_replan(
                    f"replan {replan_attempts} found no path ({new_plan.failure_reason}); "
                    "carrying on until the timeout"
                )
                held_action = None
                continue
            if new_plan.success:
                plans.append(new_plan)
                _reset_local(local_planner, new_plan.path, scenario.robot, envelope)
                # Numbered by *attempt*, the same counter the failures
                # use. Numbering successes separately produced an event
                # stream reading "replan 6 found no path" then "replan 1
                # after stuck", which is two clocks in one log and no way
                # to order them.
                engine.resume_after_replan(
                    f"replan {replan_attempts}"
                    f"{'' if replanning.max_replans is None else f'/{replanning.max_replans}'}"
                    f" after {blocked_as}: "
                    f"new path of {len(new_plan.path)} waypoints, "
                    f"{new_plan.path_length:.2f} m"
                )
                # Force a control decision on the next iteration: the
                # held command was computed for the path that just failed.
                held_action = None

    if recorder is not None:
        # The verdict is a row of its own, at the time the episode
        # actually ended. Attaching it to the last control tick instead
        # would date `goal_reached` to whenever the controller last
        # thought, which can be several ticks early — and HĐ-6 reads the
        # final pose of the trace against the profile's goal tolerance.
        recorder.record(
            engine.time,
            engine.get_state(),
            event=event_for_status(engine.episode_status),
            # A replan that the episode ended before anybody could act on
            # still cost the time it cost. Dropping it here would make the
            # last replan of every failed recovery free — which is the one
            # a reader most wants priced.
            planner_latency_ms=pending_replan_ms,
        )

    result = engine.get_result()
    if failures:
        result = result.model_copy(update={"events": tuple(failures) + result.events})
    final_plan = plans[-1]
    metrics = (
        compute_episode_metrics(
            result,
            planned_path_length=final_plan.path_length,
            global_planning_time=sum(entry.planning_time_seconds for entry in plans),
            expanded_nodes=sum(entry.expanded_nodes for entry in plans),
            grid=raw_grid,
            obstacles=scenario.static_obstacles,
            robot_radius=scenario.robot.radius,
            local_planner_latencies=latencies,
            # **Attempts, not successes.** `len(plans) - 1` counted only
            # the replans that produced a path, so an episode that tried
            # eleven times and found a route three times reported 3 — and
            # the eight refusals, which are the expensive half and the
            # interesting half, vanished. Attempts is also what a reader
            # comparing two stacks wants: the one that asked the global
            # planner eleven times did more work than the one that asked
            # three times, whatever came back.
            replan_count=replan_attempts,
        )
        if legacy_metrics
        else None
    )
    return StackRun(
        algorithm=algorithm, plan=plan, result=result, metrics=metrics, plans=tuple(plans)
    )
