"""Algorithm registry: stack id -> local-planner factory.

Every benchmarkable entry is a *stack* (``astar+<controller>``) because
comparing a global planner with a local planner is meaningless
(decision D13). The pure-pursuit stack is registered but flagged
``benchmarkable=False``: it exists only as a pipeline reference (D12).
"""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from planbench_planning import DWAConfig, DWAPlanner
from planbench_planning.common.local_base import LocalPlanner
from planbench_simulator.nav_stack import PurePursuitLocalPlanner
from planbench_simulator.path_follower import PurePursuitConfig


class ObservationClass(StrEnum):
    """What a stack is allowed to see (spec section 7.0/8.6b, P02).

    Comparing a stack with privileged access to the map or to other
    agents' true positions against one that only has LiDAR is comparing
    a sighted player to a blindfolded one — the result may still be
    real, but it does not mean what a flat leaderboard implies. None of
    the three stacks currently registered claim ``FULL_MAP`` or
    ``HUMAN_STATES``: DWA and PPO both plan from LiDAR plus the robot's
    own state, and pure-pursuit ignores sensing entirely (hence
    ``benchmarkable=False`` on that entry, independent of this field).
    The enum's other values exist for the privileged planner this
    project does not have yet, so adding one later is a one-line
    declaration rather than a silent leaderboard mismatch.
    """

    FULL_MAP = "full_map"
    HUMAN_STATES = "human_states"
    LIDAR_ONLY = "lidar_only"
    LIDAR_AND_HUMAN_STATES = "lidar+human_states"


class PPOStackConfig(BaseModel):
    """Which trained policy to run. There is no default checkpoint:
    a benchmark must state exactly which model produced its numbers."""

    model_config = ConfigDict(frozen=True)

    model_path: str = Field(description="Path to the .zip checkpoint.")
    metadata_path: str = Field(
        default="", description="Sidecar JSON; defaults to <model_path>.json."
    )
    deterministic: bool = Field(
        default=True,
        description="Evaluation uses the mean action, never sampled noise.",
    )
    control_period: float = Field(default=0.1, gt=0)


def _build_ppo(config: BaseModel) -> LocalPlanner:
    """Import the RL package lazily: torch is optional infrastructure."""
    from planbench_rl.policy import load_ppo_planner

    return load_ppo_planner(
        config.model_path,  # type: ignore[attr-defined]
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
    observation_class: ObservationClass


class _Entry(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    info: AlgorithmInfo
    config_model: type[BaseModel]
    factory: Callable[[BaseModel], LocalPlanner]


ALGORITHMS: dict[str, _Entry] = {
    "astar+dwa": _Entry(
        info=AlgorithmInfo(
            id="astar+dwa",
            kind="stack",
            description=(
                "A* global planner with a Dynamic Window Approach controller. "
                "Classic baseline: samples reachable velocities, rejects colliding "
                "rollouts and minimises a weighted cost."
            ),
            benchmarkable=True,
            observation_class=ObservationClass.LIDAR_ONLY,
            config_schema=DWAConfig.model_json_schema(),
        ),
        config_model=DWAConfig,
        factory=lambda config: DWAPlanner(config),  # type: ignore[arg-type]
    ),
    "astar+ppo": _Entry(
        info=AlgorithmInfo(
            id="astar+ppo",
            kind="stack",
            description=(
                "A* global planner with a PPO-trained controller. Requires a "
                "checkpoint path; the model's observation and reward versions "
                "are verified on load, and its metadata records whether it is "
                "only a smoke-test model."
            ),
            benchmarkable=True,
            observation_class=ObservationClass.LIDAR_ONLY,
            config_schema=PPOStackConfig.model_json_schema(),
        ),
        config_model=PPOStackConfig,
        factory=_build_ppo,
    ),
    "astar+pure_pursuit": _Entry(
        info=AlgorithmInfo(
            id="astar+pure_pursuit",
            kind="reference_stack",
            description=(
                "A* global planner with a pure-pursuit follower. Temporary "
                "pipeline reference only — it ignores sensing, so it must not "
                "be used to draw benchmark conclusions."
            ),
            benchmarkable=False,
            observation_class=ObservationClass.LIDAR_ONLY,
            config_schema=PurePursuitConfig.model_json_schema(),
        ),
        config_model=PurePursuitConfig,
        factory=lambda config: PurePursuitLocalPlanner(config),  # type: ignore[arg-type]
    ),
}


class UnknownAlgorithmError(ValueError):
    """Raised when a benchmark references an algorithm that is not registered."""


class AlgorithmConfigError(ValueError):
    """Raised when an algorithm config fails its schema."""


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
