"""Running one contract episode and writing its trace (HĐ-3, HĐ-4, HĐ-5).

Everything above this module works on recorded data; everything below it
works on a `Scenario`, the simulator's own episode schema. This is the
join: given a deployment (`TaskProfile`), a set of conditions
(`EpisodeContext`) and a candidate, run exactly one episode and leave one
Parquet file behind.

**The context decides the conditions, the candidate decides nothing about
them.** Map, mission, robot, timeouts, tolerances and traffic all come
from the profile; the seed comes from the context. A candidate that could
influence any of these would be evaluated on an environment of its own
choosing, which is the failure HĐ-3.1 exists to prevent — so the scenario
is built before the planners are, from inputs the candidate never sees.

**One row per control step, and the trace is the only output that
matters.** Nothing here computes a metric: the return value is a path on
disk (HĐ-5, HĐ-6). Anything the Metrics Engine needs and the file does
not carry is a missing column, not a reason to pass a number sideways.
"""

from __future__ import annotations

from pathlib import Path

from planbench_benchmark.candidates import build_planners
from planbench_decision.candidate import Candidate
from planbench_planning.common.base import PlanResult
from planbench_schemas.episode_context import EpisodeContext
from planbench_schemas.map import MapData
from planbench_schemas.robot import RobotConfig
from planbench_schemas.scenario import Scenario
from planbench_schemas.task_profile import Mission, TaskProfile
from planbench_simulator.nav_stack import StackRun, run_stack
from planbench_simulator.trace import DEFAULT_TRACE_ROOT, EpisodeTraceRecorder

#: Coarsest physics step the bridge will use, in seconds. 20 Hz is the
#: simulator's own default and the fidelity the engine's collision and
#: kinematics tests were written against; a deployment that declares a
#: slower control loop gets a slower *controller*, not a coarser world.
MAX_SIMULATION_DT = 0.05

__all__ = [
    "MAX_SIMULATION_DT",
    "EpisodeSetupError",
    "mission_for",
    "run_contract_episode",
    "scenario_for",
]


class EpisodeSetupError(ValueError):
    """The profile and the context do not describe a runnable episode."""


def mission_for(profile: TaskProfile, context: EpisodeContext) -> Mission:
    """The mission this context names, or a refusal.

    A context whose mission is not in the profile is not a runnable
    episode: it names conditions from a different deployment, and running
    it would put two deployments' episodes under one paired comparison.
    """
    for mission in profile.missions:
        if mission.id == context.mission_id:
            return mission
    raise EpisodeSetupError(
        f"task profile {profile.id!r} has no mission {context.mission_id!r}; this context "
        "was generated for a different profile"
    )


def scenario_for(profile: TaskProfile, context: EpisodeContext) -> Scenario:
    """The simulator's episode schema, filled entirely from the contract.

    Two choices here are worth stating rather than reading off the code.

    ``simulation_dt`` is capped at the deployment's ``control_period``
    but never coarser than :data:`MAX_SIMULATION_DT`. The two are
    different things and were briefly conflated here: the control period
    is a *requirement* — G4's threshold, how fast the loop must be on the
    target board — while the simulation step is a fidelity choice about
    how finely the physics is integrated. Tying them together meant a
    deployment could not declare a relaxed real-time budget without also
    asking for a robot simulated in half-second jumps, which is not the
    same experiment.

    The cap in the other direction is real, though: stepping the world
    more coarsely than the controller acts would let the robot issue
    commands it never gets to apply.

    ``stuck_time_window`` is the profile's ``stuck_threshold_s``. It is a
    threshold the deployment declared, so leaving the simulator's default
    in place would judge every deployment by one number nobody agreed to
    (HĐ-7's rule, applied one layer earlier).
    """
    mission = mission_for(profile, context)
    return Scenario(
        name=context.episode_context_id,
        description=f"{profile.id} · {mission.id} · seed {context.seed}",
        robot=_robot_config(profile),
        start_pose=mission.start,
        goal_pose=mission.goal,
        goal_tolerance=profile.constraints.goal_tolerance_m,
        timeout_seconds=profile.constraints.episode_timeout_s,
        simulation_dt=min(MAX_SIMULATION_DT, profile.robot.control_period),
        dynamic_obstacles=profile.environment.dynamic_obstacles,
        # From the deployment, like everything else here. A candidate
        # that could declare its own noise amplitude would be choosing
        # its own exam.
        sensor_noise=profile.environment.sensor_noise,
        random_seed=context.seed,
        stuck_time_window=profile.constraints.stuck_threshold_s,
    )


def run_contract_episode(
    candidate: Candidate,
    profile: TaskProfile,
    context: EpisodeContext,
    map_data: MapData,
    *,
    root: Path | str = DEFAULT_TRACE_ROOT,
) -> tuple[Path, StackRun]:
    """Run one episode and write its HĐ-5 trace; return where it landed.

    The ``StackRun`` comes back alongside the path for callers that want
    to log progress, **not** as a source of metrics: HĐ-5 makes the file
    the single input of the Metrics Engine, and a caller that reads
    numbers off this object instead has quietly created a second one.

    The recorder is a context manager, so an episode that raises halfway
    still leaves the samples it collected. A partial trace is evidence; a
    missing one is a hole in a paired comparison.
    """
    global_planner, local_planner = build_planners(candidate, episode_seed=context.seed)
    scenario = scenario_for(profile, context)

    with EpisodeTraceRecorder(
        context,
        candidate.candidate_id,
        root=root,
        costmap_cells=map_data.width * map_data.height,
    ) as recorder:
        run = run_stack(
            map_data,
            scenario,
            local_planner,
            global_planner,
            recorder=recorder,
            legacy_metrics=False,
        )
        recorder.close(
            peak_search_nodes=_search_nodes(candidate, run.plan),
            peak_tree_nodes=_tree_nodes(candidate, run.plan),
            global_plan_length_m=run.plan.path_length if run.plan.success else None,
            global_plan_time_ms=run.plan.planning_time_seconds * 1000.0,
        )
    return recorder.path, run


def _robot_config(profile: TaskProfile) -> RobotConfig:
    """``TaskRobotSpec`` narrowed to what the simulator's schema takes.

    ``control_period`` is deliberately dropped: it is a deployment
    requirement (G4's threshold), not a property of the robot's physics,
    and it reaches the simulator as ``simulation_dt`` instead. Copying it
    into ``Scenario`` as well would give two fields one meaning.
    """
    fields = {name: getattr(profile.robot, name) for name in RobotConfig.model_fields}
    return RobotConfig.model_validate(fields)


def _search_nodes(candidate: Candidate, plan: PlanResult) -> int:
    """``peak_search_nodes`` — graph-search nodes only (HĐ-7.3).

    Both planner families report their node count in
    ``PlanResult.expanded_nodes``, but they are counting different
    structures: A\\* holds an open and a closed set, RRT\\* holds a tree.
    G5 multiplies each by its own declared byte size, so routing both
    into one field would price a tree node as a search node — and the
    two are only equal by coincidence.
    """
    return 0 if _is_sampling_planner(candidate) else plan.expanded_nodes


def _tree_nodes(candidate: Candidate, plan: PlanResult) -> int:
    """``peak_tree_nodes`` — the RRT\\*/tree side of the same split."""
    return plan.expanded_nodes if _is_sampling_planner(candidate) else 0


#: Global planners whose ``expanded_nodes`` counts a tree rather than a
#: search frontier. Listed explicitly, so adding a planner forces the
#: question "which structure does yours count?" rather than defaulting to
#: the wrong byte size.
_SAMPLING_PLANNERS = frozenset({"rrtstar", "rrt"})


def _is_sampling_planner(candidate: Candidate) -> bool:
    planner = candidate.global_planner
    return planner is not None and planner.name in _SAMPLING_PLANNERS
