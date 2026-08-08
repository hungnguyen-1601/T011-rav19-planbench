"""Bridge: registry stacks <-> contract candidates (HĐ-1).

The registry (:mod:`planbench_benchmark.registry`) knows how to *build*
planners and is keyed by a display id like ``astar+dwa``. The contract
identifies a candidate by a hash over its full configuration. This module
is the only place the two identity schemes meet, so neither has to know
about the other:

- :func:`candidate_from_stack` turns a registry stack plus its parameters
  into a :class:`~planbench_decision.candidate.Candidate`, deriving the
  observation requirements from the P02 declarations the registry already
  carries.
- :func:`build_planners` goes the other way, so a runner holding a
  candidate can instantiate the actual planners.

**Every registry stack maps to a modular candidate**, including
``astar+ppo``: that stack is A\\* planning a global path with a PPO
controller following it (``requires_global_path=True``), which is the
modular shape. A monolithic candidate is an end-to-end policy with no
global planner at all; none exists in the registry yet, and the runner
would need the ``MonolithicPolicy`` adapter of HĐ-4 to run one.
"""

from __future__ import annotations

from typing import Any

from planbench_benchmark.observation import ObservationClass
from planbench_benchmark.registry import (
    AlgorithmInfo,
    UnknownAlgorithmError,
    algorithm_info,
    build_global_planner,
    build_local_planner,
    validate_algorithm_config,
)
from planbench_decision.candidate import Candidate, StackComponent
from planbench_planning.common.base import GlobalPlanner
from planbench_planning.common.local_base import LocalPlanner
from planbench_schemas.observations import ObservationToken

#: Which runtime perception each P02 observation class implies for G6.
#:
#: ``full_static_map`` maps to nothing: the deployment ships the map in
#: its task profile, so requiring it would fail every modular candidate
#: on a profile whose author did not restate the obvious. See
#: :mod:`planbench_schemas.observations` for the full argument.
_REQUIREMENTS: dict[ObservationClass, tuple[ObservationToken, ...]] = {
    "full_static_map": (),
    "lidar_only": ("lidar_2d",),
    "human_states": ("human_state_estimates",),
    "lidar+human_states": ("lidar_2d", "human_state_estimates"),
    "full_static_map+human_states": ("human_state_estimates",),
}


class NotBenchmarkableError(ValueError):
    """A reference-only stack cannot become a candidate.

    ``*+pure_pursuit`` ignores sensing and exists as a pipeline reference
    (decision D12). Under the new topic that matters more, not less: a
    candidate is something the system may *recommend*, and recommending a
    controller that drives without looking is the failure mode the
    feasibility gates exist to prevent.
    """


def observation_requirements_for(info: AlgorithmInfo) -> tuple[ObservationToken, ...]:
    """G6 requirements implied by a stack's P02 declarations.

    Both halves are considered and the results unioned: the deployment
    has to own every subsystem any layer reads.
    """
    tokens = set(_REQUIREMENTS[info.global_observation_class])
    tokens |= set(_REQUIREMENTS[info.local_observation_class])
    return tuple(sorted(tokens))


class UnknownParameterError(ValueError):
    """A parameter the stack's config model does not declare.

    The config models ignore unknown keys (Pydantic's default), which is
    the right behaviour for reading an old stored spec but the wrong one
    for registering a candidate. Dropped silently, ``{"sim_time": 2.5}``
    on a controller that calls the field ``horizon_seconds`` produces a
    candidate identical to the default one — same id, same numbers — while
    the person who wrote it believes a retuned controller is being
    evaluated. They would then read a real result as an answer to a
    question nobody asked.
    """


def _reject_unknown_params(
    stack_id: str, params: dict[str, Any] | None, info: AlgorithmInfo
) -> None:
    known = set(info.config_schema.get("properties", {}))
    unknown = sorted(set(params or {}) - known)
    if unknown:
        raise UnknownParameterError(
            f"{stack_id!r} has no parameter(s) {unknown}; declared parameters are "
            f"{sorted(known)}. An ignored parameter would produce a candidate "
            "indistinguishable from the default one"
        )


def candidate_from_stack(
    stack_id: str,
    *,
    params: dict[str, Any] | None = None,
    global_version: str = "v1",
    local_version: str = "v1",
) -> Candidate:
    """Build the candidate for a registry stack and one parameter set.

    ``params`` holds the *local controller's* configuration, matching what
    a benchmark spec configures today; it is validated against the
    registry's config model here so an unrunnable candidate cannot be
    registered and then fail 300 episodes later. Global-planner
    parameters are not configurable through the registry yet, so the
    candidate carries no block for that layer.

    The versions are arguments rather than registry facts because the
    registry does not track code versions. Passing the real one is what
    makes a candidate id distinguish the same stack before and after a
    bug fix (HĐ-1.3).
    """
    info = algorithm_info(stack_id)
    if info is None:
        raise UnknownAlgorithmError(f"unknown algorithm {stack_id!r}")
    if not info.benchmarkable:
        raise NotBenchmarkableError(
            f"{stack_id!r} is registered as a reference stack only and must not be "
            "offered as a candidate"
        )
    if not info.requires_global_path:
        raise NotBenchmarkableError(
            f"{stack_id!r} does not follow a global path, so it is not a modular "
            "stack; run it as a monolithic candidate once the policy adapter exists"
        )

    global_name, _, local_name = stack_id.partition("+")
    if global_name != info.global_planner:
        # The id is a display convention and the field is the fact
        # (see AlgorithmInfo.global_planner). Disagreement means the
        # registry entry is inconsistent, and hashing either choice would
        # bake the inconsistency into recorded data.
        raise NotBenchmarkableError(
            f"registry entry {stack_id!r} declares global planner "
            f"{info.global_planner!r}; refusing to guess which is right"
        )

    _reject_unknown_params(stack_id, params, info)
    validated = validate_algorithm_config(stack_id, params)
    return Candidate(
        type="modular",
        global_planner=StackComponent(name=global_name, version=global_version),
        local_controller=StackComponent(name=local_name, version=local_version),
        params={local_name: validated.model_dump(mode="json")},
        observation_requirements=observation_requirements_for(info),
    )


def stack_id_for(candidate: Candidate) -> str:
    """The registry id that builds this candidate's planners."""
    if candidate.type != "modular":
        raise NotBenchmarkableError(
            "monolithic candidates have no registry stack; they need the "
            "MonolithicPolicy adapter (HĐ-4), which does not exist yet"
        )
    return candidate.stack_label


def build_planners(
    candidate: Candidate, *, episode_seed: int
) -> tuple[GlobalPlanner, LocalPlanner]:
    """Instantiate ``(global_planner, local_controller)`` for one episode.

    ``episode_seed`` comes from the episode context, never from global
    randomness: a sampling planner must explore a different tree per
    episode while staying reproducible from the context id (HĐ-3.2).
    """
    stack_id = stack_id_for(candidate)
    assert candidate.local_controller is not None
    local_params = candidate.layer_params(candidate.local_controller.name)
    return (
        build_global_planner(stack_id, episode_seed=episode_seed),
        build_local_planner(stack_id, local_params),
    )
