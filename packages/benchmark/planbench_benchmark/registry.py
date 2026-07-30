"""Algorithm registry: stack id -> local-planner factory.

Every benchmarkable entry is a *stack* (``astar+<controller>``) because
comparing a global planner with a local planner is meaningless
(decision D13). The pure-pursuit stack is registered but flagged
``benchmarkable=False``: it exists only as a pipeline reference (D12).
"""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel, ConfigDict, ValidationError

from planbench_planning import DWAConfig, DWAPlanner
from planbench_planning.common.local_base import LocalPlanner
from planbench_simulator.nav_stack import PurePursuitLocalPlanner
from planbench_simulator.path_follower import PurePursuitConfig


class AlgorithmInfo(BaseModel):
    """Static description of one registered stack."""

    model_config = ConfigDict(frozen=True)

    id: str
    kind: str
    description: str
    benchmarkable: bool
    config_schema: dict


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
            config_schema=DWAConfig.model_json_schema(),
        ),
        config_model=DWAConfig,
        factory=lambda config: DWAPlanner(config),  # type: ignore[arg-type]
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
