"""Navigation stacks: a global planner + a local planner (controller).

A benchmark always compares *stacks* — ``astar+dwa`` versus
``astar+ppo`` versus Nav2 — never a global planner against a local one
(decision D13).

Planning-safety margin: the planning grid is inflated by
``robot.radius + sqrt(2) * resolution`` so a line-of-sight-sampled path
cannot graze obstacle corners (see the proof in the docstring of
``episode_runner``). The engine still checks collisions with the exact
robot radius.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from planbench_metrics import EpisodeMetrics, compute_episode_metrics
from planbench_planning import AStarPlanner, GlobalPlanner, PlanResult
from planbench_planning.common.local_base import LocalPlanner, LocalPlanResult
from planbench_schemas.episode import EpisodeEvent, EpisodeResult, EpisodeStatus, Observation
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
    inflation_radius = scenario.robot.radius + math.sqrt(2.0) * map_data.resolution
    return OccupancyGrid(planning_map).inflate(inflation_radius)


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


def _with_free_start_cell(grid: OccupancyGrid, position: Point2D) -> OccupancyGrid:
    """Mark the single cell the robot occupies as free, if it is not.

    A robot that has just been blocked is standing close to the thing
    blocking it — closer than the inflation margin, which is a planning
    safety buffer rather than geometry. So its own cell is very often
    occupied on the inflated grid, and a global planner asked to start
    from an occupied cell reports "no path" and the replan never
    happens. That would make the feature fail exactly in the situation
    it exists for.

    Freeing one cell is safe to assert, not merely convenient: the
    engine terminates an episode the instant the robot overlaps an
    obstacle, so a robot that is still driving is provably not in one.
    Only the cell containing the robot is touched. Its neighbours keep
    their inflation, so the path that comes back still has to leave via
    genuinely clear space.
    """
    cell = grid.world_to_grid(position.x, position.y)
    if cell is None:
        return grid
    row, col = cell
    index = row * grid.width + col
    cells = grid.map_data.cells
    if cells[index] == CellState.FREE.value:
        return grid
    patched = list(cells)
    patched[index] = CellState.FREE.value
    return OccupancyGrid(
        grid.map_data.model_copy(update={"cells": tuple(patched)}),
        grid.unknown_as_occupied,
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
    return global_planner.plan(
        _with_free_start_cell(grid, position),
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
        return StackRun(algorithm=algorithm, plan=plan, result=result, metrics=metrics)

    engine = SimulationEngine()
    engine.load_map(map_data)
    engine.load_scenario(scenario)
    engine.reset()
    local_planner.reset(plan.path, scenario.robot)
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
    while not engine.is_done():
        recompute = (
            held_action is None or control_period is None or engine.time >= next_control_time - EPS
        )
        if recompute:
            decision = local_planner.compute(engine.get_state(), engine.get_observation())
            latencies.append(decision.latency_seconds)
            if recorder is not None:
                # Recorded before the step, so the row says "at time t the
                # robot was here and deciding cost this much" — pairing the
                # latency with the state it was computed from rather than
                # with the state it produced.
                recorder.record(
                    engine.time,
                    engine.get_state(),
                    planner_latency_ms=decision.latency_seconds * 1000.0,
                )
            if decision.failure_reason:
                failures.append(
                    EpisodeEvent(
                        time=engine.time,
                        type="local_planner_failure",
                        message=decision.failure_reason,
                    )
                )
            held_action = decision.action
            if control_period is not None:
                next_control_time = engine.time + control_period
        engine.step(held_action)

        if (
            engine.is_done()
            and replanning.enabled
            and len(plans) <= replanning.max_replans
            and engine.episode_status in _REPLANNABLE
        ):
            blocked_as = engine.episode_status.value
            new_plan = _replan(map_data, scenario, global_planner, engine)
            if new_plan.success:
                plans.append(new_plan)
                local_planner.reset(new_plan.path, scenario.robot)
                engine.resume_after_replan(
                    f"replan {len(plans) - 1}/{replanning.max_replans} after {blocked_as}: "
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
            planner_latency_ms=0.0,
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
            replan_count=len(plans) - 1,
        )
        if legacy_metrics
        else None
    )
    return StackRun(algorithm=algorithm, plan=plan, result=result, metrics=metrics)
