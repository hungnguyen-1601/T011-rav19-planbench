"""Algorithm registry: stack id -> global planner + local-planner factory.

Every benchmarkable entry is a *stack* (``<global>+<controller>``)
because comparing a global planner with a local planner is meaningless
(decision D13). The pure-pursuit stacks are registered but flagged
``benchmarkable=False``: they exist only as a pipeline reference (D12).
"""

from __future__ import annotations

from collections.abc import Callable
from importlib.util import find_spec

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from planbench_benchmark.observation import ObservationClass
from planbench_planning import (
    AStarPlanner,
    DWAConfig,
    DWAPlanner,
    GlobalPlanner,
    RRTStarConfig,
    RRTStarPlanner,
)
from planbench_planning.common.local_base import LocalPlanner
from planbench_simulator.nav_stack import PurePursuitLocalPlanner
from planbench_simulator.path_follower import PurePursuitConfig


class UnknownAlgorithmError(ValueError):
    """Raised when a benchmark references an algorithm that is not registered."""


class AlgorithmConfigError(ValueError):
    """Raised when an algorithm config fails its schema."""


class PPOStackConfig(BaseModel):
    """Which trained policy to run.

    There is no default checkpoint: a benchmark must state exactly which
    model produced its numbers, or the numbers mean nothing.

    Two ways to say which, and the difference matters.

    ``model_id`` is the way. It names a record in the model registry;
    the API resolves it to bytes at launch, records the checksum that
    actually ran, and can tell the user *before* the run whether the
    model fits the robot. Nobody has to know where files live.

    ``model_path`` is the old way, kept because benchmarks created
    before the registry existed still carry one and must remain
    readable. New benchmarks do not set it — the API does not offer it
    and the UI has no field for it — but a stored spec that has one
    still runs, provided the file is still there.

    Exactly one of the two is required, and this is enforced here rather
    than at the API edge so a spec loaded straight from the database
    cannot be half-valid.
    """

    model_config = ConfigDict(frozen=True)

    model_id: str = Field(
        default="", description="Registry model id. The supported way to choose a model."
    )
    model_version: str = Field(default="", description="Recorded for reproducibility.")
    model_checksum: str = Field(
        default="", description="SHA-256 of the file that ran, recorded at launch."
    )
    robot_profile_id: str = Field(default="", description="Robot the model was checked against.")
    compatibility_snapshot: dict = Field(
        default_factory=dict,
        description="The compatibility verdict at the time the benchmark was created.",
    )
    #: Legacy. Present only on benchmarks that predate the registry.
    model_path: str = Field(default="", description="Deprecated: filesystem path to a .zip.")
    metadata_path: str = Field(
        default="", description="Deprecated: sidecar JSON beside model_path."
    )
    deterministic: bool = Field(
        default=True,
        description="Evaluation uses the mean action, never sampled noise.",
    )
    control_period: float = Field(default=0.1, gt=0)

    @model_validator(mode="after")
    def _require_a_model(self) -> PPOStackConfig:
        if not self.model_id and not self.model_path:
            # Phrased for the person choosing, not for a stack trace.
            # The API turns this into the same sentence the UI shows.
            raise ValueError(
                "no PPO model was chosen. Pick one from the model registry, or upload "
                "a trained Stable-Baselines3 .zip if you have not yet."
            )
        return self


def _build_ppo(config: BaseModel) -> LocalPlanner:
    """Import the RL package lazily: torch is optional infrastructure.

    By the time this runs the caller has already resolved a registry
    ``model_id`` into ``model_path`` (see ``BenchmarkService._resolve_ppo``).
    This layer therefore still only knows about files — which keeps the
    benchmark package free of any dependency on the API's storage.
    """
    # PPO is an optional install (torch is gigabytes). Ask before
    # importing rather than catching ModuleNotFoundError around the call:
    # deserialising a checkpoint can legitimately raise that same error
    # when the policy references a module the server does not have, and
    # reporting *that* as "SB3 is not installed" would send the operator
    # to fix something that is not broken.
    if find_spec("stable_baselines3") is None:
        raise AlgorithmConfigError(
            "this server cannot run PPO models: the reinforcement-learning "
            "dependencies are not installed. Install them from "
            "requirements-optional.txt, or benchmark A* + DWA instead."
        )
    from planbench_rl.policy import load_ppo_planner

    path = config.model_path  # type: ignore[attr-defined]
    if not path:
        raise AlgorithmConfigError(
            "this PPO benchmark refers to a registry model that was not resolved to a "
            "file before launch; this is a wiring bug, not a configuration mistake"
        )
    return load_ppo_planner(
        path,
        config.metadata_path or None,  # type: ignore[attr-defined]
        deterministic=config.deterministic,  # type: ignore[attr-defined]
    )


class AlgorithmInfo(BaseModel):
    """Static description of one registered stack."""

    model_config = ConfigDict(frozen=True)

    id: str
    kind: str
    description: str
    benchmarkable: bool
    config_schema: dict
    #: Which global planner the stack runs. Stated rather than parsed
    #: out of ``id``: the id is a display convention, this is the fact
    #: a report has to be able to quote.
    global_planner: str = "astar"
    #: Which local controller the stack runs, and stated for the same
    #: reason as ``global_planner``.
    #:
    #: Added when the UI stopped offering whole stacks in one dropdown.
    #: Choosing a global planner and a controller separately needs to
    #: know which pairs the registry actually has — ``rrtstar+ppo`` is
    #: not one of them — and deriving that by splitting the id would put
    #: a parser between a picker and the fact it is picking.
    local_controller: str = "dwa"
    #: True when the global planner draws random samples. Such a stack
    #: needs more seeds to say anything, and a report that hides this
    #: invites the reader to compare one lucky tree against A*.
    stochastic_global_planner: bool = False
    #: This stack cannot run without a trained model chosen by a person.
    #:
    #: It used to be inferred from the config schema's ``required`` list,
    #: which broke silently the moment every field gained a default: the
    #: conversational agent started offering PPO, and it has no way to
    #: know which model is the right one. Inventing one is the
    #: fabrication the spec forbids, so the property is now stated
    #: outright instead of being a side effect of field defaults.
    requires_model: bool = False
    #: What each half of the stack is allowed to see (P02).
    #:
    #: Deliberately without a default. A default would be a guess made
    #: on behalf of whoever adds the next planner, and the one thing
    #: worse than an unlabelled stack on the leaderboard is a wrongly
    #: labelled one: the ranking would then look fair while comparing a
    #: sensing planner against one reading ground truth. Registering a
    #: stack must fail loudly until someone states both classes.
    global_observation_class: ObservationClass
    local_observation_class: ObservationClass
    #: True when the controller is steered by a global path. A stack
    #: that ignores it (end-to-end policies, in principle) solves a
    #: different problem and a report should be able to say so.
    requires_global_path: bool


class _Entry(BaseModel):
    """One registered stack.

    ``config_model``/``factory`` describe the *local* planner: that is
    the half a benchmark spec configures today. ``global_factory`` takes
    the episode seed and returns the global planner, because a sampling
    planner must draw a different tree per episode (see
    ``RRTStarPlanner``); deterministic planners simply ignore it. When
    tuning arrives (P01) it replaces the config baked into these
    closures — the seed plumbing does not have to change again.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    info: AlgorithmInfo
    config_model: type[BaseModel]
    factory: Callable[[BaseModel], LocalPlanner]
    global_factory: Callable[[int], GlobalPlanner]


def _astar(episode_seed: int) -> GlobalPlanner:  # noqa: ARG001 - A* ignores the seed
    return AStarPlanner()


def _rrtstar(episode_seed: int) -> GlobalPlanner:
    return RRTStarPlanner(RRTStarConfig(), episode_seed=episode_seed)


#: Read on `/candidates` rather than left in a comment, on purpose: the
#: cost-aware variant is a real departure from the published algorithm,
#: and anybody comparing this against a paper's RRT* numbers has to know
#: before they draw the conclusion, not after.
_RRT_STAR_DESCRIPTION = (
    "RRT* global planner: samples the free space, rewires the tree towards "
    "cheaper paths, and keeps improving for its whole iteration budget. "
    "Randomised — the tree is seeded from the episode seed, so results "
    "must be read across many seeds, not from one run. "
    "Cost-aware variant: edge cost integrates the deployment's clearance "
    "field rather than being pure length, so hugging an obstacle is "
    "expensive rather than free. RRT*'s asymptotic-optimality guarantee "
    "is proved for cost functionals this field may not satisfy, and "
    "whether it survives has not been verified — see KNOWN_LIMITATIONS."
)


ALGORITHMS: dict[str, _Entry] = {
    "astar+dwa": _Entry(
        info=AlgorithmInfo(
            id="astar+dwa",
            local_controller="dwa",
            kind="stack",
            description=(
                "A* global planner with a Dynamic Window Approach controller. "
                "Classic baseline: samples reachable velocities, rejects colliding "
                "rollouts and minimises a weighted cost."
            ),
            benchmarkable=True,
            config_schema=DWAConfig.model_json_schema(),
            global_observation_class="full_static_map",
            local_observation_class="lidar_only",
            requires_global_path=True,
        ),
        config_model=DWAConfig,
        factory=lambda config: DWAPlanner(config),  # type: ignore[arg-type]
        global_factory=_astar,
    ),
    "astar+ppo": _Entry(
        info=AlgorithmInfo(
            id="astar+ppo",
            local_controller="ppo",
            kind="stack",
            description=(
                "A* global planner with a PPO-trained controller. Choose a model "
                "from the registry; the platform resolves it to a checkpoint, "
                "verifies the observation and reward versions on load, and records "
                "the checksum of what actually ran."
            ),
            benchmarkable=True,
            requires_model=True,
            config_schema=PPOStackConfig.model_json_schema(),
            global_observation_class="full_static_map",
            local_observation_class="lidar_only",
            requires_global_path=True,
        ),
        config_model=PPOStackConfig,
        factory=_build_ppo,
        global_factory=_astar,
    ),
    "astar+pure_pursuit": _Entry(
        info=AlgorithmInfo(
            id="astar+pure_pursuit",
            local_controller="pure_pursuit",
            kind="reference_stack",
            description=(
                "A* global planner with a pure-pursuit follower. Temporary "
                "pipeline reference only — it ignores sensing, so it must not "
                "be used to draw benchmark conclusions."
            ),
            benchmarkable=False,
            config_schema=PurePursuitConfig.model_json_schema(),
            global_observation_class="full_static_map",
            local_observation_class="lidar_only",
            requires_global_path=True,
        ),
        config_model=PurePursuitConfig,
        factory=lambda config: PurePursuitLocalPlanner(config),  # type: ignore[arg-type]
        global_factory=_astar,
    ),
    "rrtstar+dwa": _Entry(
        info=AlgorithmInfo(
            id="rrtstar+dwa",
            local_controller="dwa",
            kind="stack",
            description=(
                _RRT_STAR_DESCRIPTION + " Paired here with the Dynamic Window "
                "Approach controller, so it differs from astar+dwa in the "
                "global planner alone."
            ),
            benchmarkable=True,
            config_schema=DWAConfig.model_json_schema(),
            global_planner="rrtstar",
            stochastic_global_planner=True,
            global_observation_class="full_static_map",
            local_observation_class="lidar_only",
            requires_global_path=True,
        ),
        config_model=DWAConfig,
        factory=lambda config: DWAPlanner(config),  # type: ignore[arg-type]
        global_factory=_rrtstar,
    ),
    "rrtstar+pure_pursuit": _Entry(
        info=AlgorithmInfo(
            id="rrtstar+pure_pursuit",
            local_controller="pure_pursuit",
            kind="reference_stack",
            description=(
                "RRT* global planner with a pure-pursuit follower. Temporary "
                "pipeline reference only — it ignores sensing, so it must not "
                "be used to draw benchmark conclusions."
            ),
            benchmarkable=False,
            config_schema=PurePursuitConfig.model_json_schema(),
            global_planner="rrtstar",
            stochastic_global_planner=True,
            global_observation_class="full_static_map",
            local_observation_class="lidar_only",
            requires_global_path=True,
        ),
        config_model=PurePursuitConfig,
        factory=lambda config: PurePursuitLocalPlanner(config),  # type: ignore[arg-type]
        global_factory=_rrtstar,
    ),
}


def algorithm_info(algorithm_id: str) -> AlgorithmInfo | None:
    """The registry entry for ``algorithm_id``, or None if unregistered.

    Returns None rather than raising because callers are usually reading
    an old stored report: a benchmark run before a stack was renamed (or
    removed) must still be displayable, just without its metadata.
    """
    entry = ALGORITHMS.get(algorithm_id)
    return entry.info if entry is not None else None


def list_algorithms() -> list[AlgorithmInfo]:
    return [entry.info for entry in sorted(ALGORITHMS.values(), key=lambda e: e.info.id)]


def _entry(algorithm_id: str) -> _Entry:
    try:
        return ALGORITHMS[algorithm_id]
    except KeyError:
        raise UnknownAlgorithmError(
            f"unknown algorithm {algorithm_id!r}; registered: {sorted(ALGORITHMS)}"
        ) from None


def validate_algorithm_config(algorithm_id: str, config: dict | None) -> BaseModel:
    """Parse ``config`` with the algorithm's model; raise on mismatch."""
    entry = _entry(algorithm_id)
    try:
        return entry.config_model.model_validate(config or {})
    except ValidationError as exc:
        raise AlgorithmConfigError(f"invalid config for {algorithm_id!r}: {exc}") from exc


def build_local_planner(algorithm_id: str, config: dict | None = None) -> LocalPlanner:
    """Instantiate the controller for a registered stack."""
    entry = _entry(algorithm_id)
    return entry.factory(validate_algorithm_config(algorithm_id, config))


def build_global_planner(algorithm_id: str, *, episode_seed: int = 0) -> GlobalPlanner:
    """Instantiate the global planner for a registered stack.

    ``episode_seed`` is the seed of the episode about to run. Passing it
    is what makes a sampling planner explore a different tree per
    episode; a deterministic planner ignores it.
    """
    return _entry(algorithm_id).global_factory(episode_seed)
