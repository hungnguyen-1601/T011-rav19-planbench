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

import hashlib
import inspect
from collections.abc import Sequence
from functools import cache
from importlib import import_module
from typing import Any

from planbench_benchmark.observation import ObservationClass
from planbench_benchmark.registry import (
    AlgorithmInfo,
    UnknownAlgorithmError,
    algorithm_info,
    build_global_planner,
    build_local_planner,
    list_algorithms,
    validate_algorithm_config,
)
from planbench_decision.candidate import Candidate, StackComponent, StructuralResourceProfile
from planbench_planning.common.base import GlobalPlanner
from planbench_planning.common.local_base import LocalPlanner
from planbench_schemas.observations import ObservationToken
from planbench_schemas.task_profile import TaskProfile

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


#: Byte sizes of the *target* implementation's data structures (HĐ-1.5),
#: not of the Python objects this simulator allocates. The figures are
#: the contract's worked example for a C++/ROS2 navigation stack: a
#: search node holding (index, g, f, parent) packs into 40 bytes, a
#: costmap cell is one byte per layer, and 8 MB covers the fixed
#: allocations of the process. They are a project-wide declaration
#: because every registry stack targets the same implementation; a
#: candidate that does not can pass its own profile.
DEFAULT_STRUCTURAL_PROFILE = StructuralResourceProfile(
    kind="structural",
    target_implementation="cpp_ros2",
    bytes_per_search_node=40,
    bytes_per_tree_node=40,
    bytes_per_costmap_cell=1,
    costmap_layers=3,
    fixed_overhead_mb=8.0,
)


#: Modules whose source is hashed into a controller's ``local_version``.
#:
#: **A declared set, not a transitive closure**, and the distinction is
#: the honest part of this fingerprint. Following imports would eventually
#: reach ``math`` and the Python version; stopping somewhere is
#: unavoidable, so where it stops is written down rather than implied.
#:
#: What is in, and why each earns its place:
#:
#: * the controller's **own** modules — obviously;
#: * ``common.dwa_core`` — ``dwa`` and ``dwa_predictive`` call the same
#:   functions, so a fix there changes what **both** do. Hashing only each
#:   controller's own file would let that happen with both recorded ids
#:   unmoved, which is precisely the promise ``StackComponent.version``
#:   makes and used to break;
#: * ``schemas.feasibility`` — ``admissible_speed`` **is** the speed bound
#:   and ``hard_clearance`` **is** the refusal threshold. A change there
#:   changes what every controller may do, and leaving it out would have
#:   made P1 — which rewrote ``admissible_speed`` — invisible to the id.
#:
#: What is deliberately out: ``geometry``, ``robot``, ``episode`` and the
#: rest carry types and constants rather than control decisions. That is a
#: judgement, and a wrong one is possible — a behaviour change in an
#: excluded module would not move the id. The list is the place to fix
#: that when it happens.
_CONTROLLER_SOURCES: dict[str, tuple[str, ...]] = {
    "dwa": (
        "planbench_planning.dwa.planner",
        "planbench_planning.common.dwa_core",
        "planbench_schemas.feasibility",
    ),
    "dwa_predictive": (
        "planbench_planning.dwa_predictive.planner",
        "planbench_planning.dwa_predictive.tracking",
        "planbench_planning.dwa_predictive.tracks",
        "planbench_planning.common.dwa_core",
        "planbench_schemas.feasibility",
    ),
}


@cache
def controller_version(controller: str) -> str:
    """Short checksum over a **declared set** of the modules it depends on.

    Not "the code this controller runs" — that would be the transitive
    closure and it does not terminate anywhere useful. It is the set named
    in :data:`_CONTROLLER_SOURCES`, chosen because those modules make
    control decisions, and a behaviour change in a module left out of that
    list **will not** move the id.

    **The debt this pays.** ``candidate_from_stack`` took
    ``local_version: str = "v1"`` and **no caller ever passed one**, so
    every candidate the platform has produced was ``v1`` for ever — while
    ``StackComponent``'s own docstring promised that *the same DWA after a
    bug fix is a different candidate*. The id said two runs were the same
    candidate when the code had changed underneath them.

    Hashing source text rather than a version somebody types: a number a
    human maintains is a number a human forgets, and the failure is
    silent. Docstrings and comments count too — they cannot change
    behaviour, but a checksum that tried to ignore them would need to
    parse Python to decide what matters, and being occasionally too
    sensitive is the safe direction for an identity.

    Unknown controllers fall back to ``"v1"``: ``ppo`` carries its
    checkpoint checksum already, and ``pure_pursuit`` is not
    benchmarkable.
    """
    modules = _CONTROLLER_SOURCES.get(controller)
    if not modules:
        return "v1"
    digest = hashlib.sha256()
    for name in modules:
        digest.update(inspect.getsource(import_module(name)).encode("utf-8"))
    return digest.hexdigest()[:12]


def candidate_from_stack(
    stack_id: str,
    *,
    params: dict[str, Any] | None = None,
    global_version: str = "v1",
    local_version: str | None = None,
    resource_profile: StructuralResourceProfile | None = None,
) -> Candidate:
    """Build the candidate for a registry stack and one parameter set.

    ``params`` holds the *local controller's* configuration, matching what
    a benchmark spec configures today; it is validated against the
    registry's config model here so an unrunnable candidate cannot be
    registered and then fail 300 episodes later. Global-planner
    parameters are not configurable through the registry yet, so the
    candidate carries no block for that layer.

    ``local_version`` defaults to the **checksum of the controller's own
    source plus the shared core** rather than to a literal. It used to
    default to ``"v1"`` and no caller ever overrode it, so every candidate
    id was ``v1`` permanently and two runs of materially different code
    were recorded as the same candidate — the exact thing HĐ-1.3 says an
    id must distinguish. Passing a value explicitly is still allowed, for
    a caller reconstructing a historical candidate.

    **This changes every candidate id in existence.** Runs stored before
    it keep their old ids and no longer match the ids the same stacks
    produce now. That is accepted rather than papered over (dev decision
    15-08): the platform already refuses to edit identity in place —
    ``same_deployment`` exists for the same reason — and the alternative,
    hashing only the new controller, would leave the hole half-patched
    while the two controllers share ``dwa_core``.
    """
    info = algorithm_info(stack_id)
    if info is None:
        raise UnknownAlgorithmError(f"unknown algorithm {stack_id!r}")
    if not info.benchmarkable:
        raise NotBenchmarkableError(
            f"{stack_id!r} may not be offered as a candidate: "
            + (info.withdrawn or "registered as a reference stack only")
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
        local_controller=StackComponent(
            name=local_name,
            version=local_version or controller_version(local_name),
        ),
        params={local_name: validated.model_dump(mode="json")},
        observation_requirements=observation_requirements_for(info),
        resource_profile=resource_profile or DEFAULT_STRUCTURAL_PROFILE,
    )


def stack_id_for(candidate: Candidate) -> str:
    """The registry id that builds this candidate's planners.

    Modular only, by construction: this resolves a *stack*, and a
    monolithic candidate has none. Since H1b that is a redirect rather
    than a dead end — ``planbench_benchmark.policies.build_policy`` turns
    a declared monolithic candidate into a running policy, and
    ``run_policy`` drives it through the same loop, charged for no global
    search and handed no path.
    """
    if candidate.type != "modular":
        raise NotBenchmarkableError(
            "monolithic candidates have no registry stack; build them with "
            "planbench_benchmark.policies.build_policy and run them through "
            "run_policy — the modular path here would plan a global route the "
            "policy must never receive"
        )
    return candidate.stack_label


#: Named local-controller configurations, so a sampling choice is a
#: *candidate* rather than a constant inside whichever script ran.
#:
#: ``dwa_coarse`` samples 7×15 instead of the library's 20×40. It exists
#: because a full evaluation set at the default is hours of wall clock —
#: which is a fact about the benchmark machine, not about the warehouse.
#: Left as a bare constant in a script, that turns into a tuned candidate
#: nobody declared: the DWA *is* half of what is being compared (HĐ-1),
#: so configuring it for the clock is configuring the thing under test.
#:
#: Naming both and letting the platform score both is the only way the
#: obvious question gets an answer instead of an assumption — the first
#: easy-map run had ``astar+dwa`` stall at a convex corner with 0.30 m of
#: clearance while ``rrtstar+dwa`` slipped through 0.11 m, and whether
#: that is a property of the stack or of the coarse sampling is not
#: something anyone can reason out from the code.
#:
#: ``control_period`` is the deployment's, not a taste setting: a
#: controller slower than T_cycle misses deadlines that G4 cannot see
#: (:func:`validate_control_rate`).
#: Grouped **by controller**, because a configuration only means
#: anything for the controller it configures: ``velocity_samples`` is a
#: DWA idea and a PPO checkpoint has nothing to do with it.
#:
#: The flat table below is derived from this one rather than maintained
#: beside it. Every name here is globally unique and carries its
#: controller, which is what lets both views exist without a second
#: place to keep in sync — and what lets a stored report keep quoting
#: ``local_controller_config: dwa_coarse`` unchanged.
#:
#: Adding a controller is adding a key here. Nothing else has to move.
CONTROLLER_CONFIGS: dict[str, dict[str, dict[str, Any]]] = {
    "dwa": {
        "dwa_coarse": {
            "control_period": 0.05,
            "velocity_samples": 7,
            "omega_samples": 15,
            "horizon_seconds": 1.0,
        },
        "dwa_balanced": {
            "control_period": 0.05,
            "velocity_samples": 12,
            "omega_samples": 24,
            "horizon_seconds": 1.0,
        },
        "dwa_default": {
            "control_period": 0.05,
            "velocity_samples": 20,
            "omega_samples": 40,
            "horizon_seconds": 1.0,
        },
    },
    # **Identical sampling density to `dwa`, deliberately.** The latency
    # axis is only comparable if the two controllers sample the same
    # number of candidates; a predictive stack that also sampled more
    # coarsely would mix two changes into one G4 reading. Whatever this
    # candidate costs above `dwa` is then the tracker plus the space-time
    # broadcast, which is the number worth having.
    #
    # Names are the full `dwa_predictive_*`, not an abbreviation: item 3
    # below checks a configuration name against the controller it belongs
    # to, and these strings appear verbatim in every stored report.
    "dwa_predictive": {
        "dwa_predictive_coarse": {
            "control_period": 0.05,
            "velocity_samples": 7,
            "omega_samples": 15,
            "horizon_seconds": 1.0,
        },
        "dwa_predictive_balanced": {
            "control_period": 0.05,
            "velocity_samples": 12,
            "omega_samples": 24,
            "horizon_seconds": 1.0,
        },
        "dwa_predictive_default": {
            "control_period": 0.05,
            "velocity_samples": 20,
            "omega_samples": 40,
            "horizon_seconds": 1.0,
        },
    },
}

#: Every named configuration, flat, keyed by name.
#:
#: Derived — never edited. Eight modules and a script look configs up by
#: name and a stored report quotes that name, so the flat view has to
#: keep existing; deriving it means the grouping cannot drift from it.
LOCAL_CONTROLLER_CONFIGS: dict[str, dict[str, Any]] = {
    name: params
    for controller_configs in CONTROLLER_CONFIGS.values()
    for name, params in controller_configs.items()
}

#: Which controller each named configuration belongs to. Derived too.
CONTROLLER_OF_CONFIG: dict[str, str] = {
    name: controller
    for controller, controller_configs in CONTROLLER_CONFIGS.items()
    for name in controller_configs
}

#: ``dwa_balanced`` is a third point on a real design axis, not a knob
#: turned until something passed. The two ends were measured first and
#: they bracket the deployment's real-time budget: on ``open_hall_v2``,
#: ``dwa_coarse`` (105 samples) gave a pooled p99 of 5.26 ms for
#: ``astar+dwa`` and 6.06 ms for ``rrtstar+dwa``, while ``dwa_default``
#: (800 samples) gave 29.40 ms and **50.28 ms** — the latter failing G4
#: by 0.28 ms against a 50 ms threshold.
#:
#: So the open question is not "can we make something pass" but "where on
#: this axis does the budget actually run out", and 288 samples is the
#: midpoint by count. Predicted by linear interpolation *before* running
#: it, recorded here so the record shows which came first: **11.6 ms**
#: for ``astar+dwa`` and **17.7 ms** for ``rrtstar+dwa``.
#:
#: If it comes out over budget, that is the answer and the candidate
#: stays registered saying so. Re-picking the sampling density until a
#: number clears a gate is the move HĐ-15.3 asks about, and the four
#: reverted changes of 2026-08-11 are what it looks like.


class ConfigControllerMismatch(ValueError):
    """A configuration name that belongs to a different controller."""


def offered_controller_configs() -> dict[str, dict[str, dict]]:
    """The named configurations a candidate can actually be registered with.

    ``CONTROLLER_CONFIGS`` lists every configuration the platform knows;
    this narrows it to the ones some **usable** stack pairs with, by
    reading the registry rather than by keeping a second list beside it.

    The distinction became real when ``dwa_predictive`` was withdrawn:
    the catalogue still offered ``dwa_predictive_balanced`` while
    registration refused every stack that could take it, so a dropdown
    served a name the server would reject — the exact drift that serving
    the catalogue instead of hard-coding it in the browser was meant to
    prevent. Deriving it here means withdrawing a stack withdraws its
    configurations in the same move, with nobody having to remember.
    """
    usable = {info.local_controller for info in list_algorithms() if info.benchmarkable}
    return {
        controller: configs
        for controller, configs in CONTROLLER_CONFIGS.items()
        if controller in usable
    }


def validate_config_names(specs: Sequence[tuple[str, str]]) -> None:
    """Refuse ``astar+dwa_predictive:dwa_coarse`` and its relatives.

    **A live hole until this existed.** Configuration names are a single
    flat namespace, and nothing checked that the one a run asked for
    belonged to the controller in its stack. ``dwa_coarse`` names only
    sampling densities, and every one of its keys is also a valid
    ``DWAPredictiveConfig`` field — so the pair above **runs**, and the
    stored report says ``local_controller_config: dwa_coarse`` beside a
    candidate that is not ``dwa``. Nothing is wrong with the episodes;
    what is wrong is that the record describes a configuration nobody
    chose, and that only becomes visible once a second controller exists.

    ``CONTROLLER_OF_CONFIG`` has been derived and exported all along with
    nothing reading it. This is the reader.

    Checked here rather than at the registry: the registry knows a stack
    and a config model, and ``dwa_coarse`` validates cleanly against
    both. Only the *pairing* is wrong, and the pairing is what a run
    declares.
    """
    for stack, config_name in specs:
        info = algorithm_info(stack)
        if info is None:
            continue
        owner = CONTROLLER_OF_CONFIG.get(config_name)
        if owner is None:
            raise ConfigControllerMismatch(
                f"{stack}:{config_name} names a configuration that does not exist. "
                f"Available: {', '.join(sorted(LOCAL_CONTROLLER_CONFIGS))}"
            )
        if owner != info.local_controller:
            raise ConfigControllerMismatch(
                f"{stack}:{config_name} pairs a {info.local_controller} stack with a "
                f"{owner} configuration. It would run — every field of {config_name} is "
                f"also valid for {info.local_controller} — and the report would then "
                f"name a configuration this candidate never used. Pick one of: "
                f"{', '.join(sorted(CONTROLLER_CONFIGS.get(info.local_controller, {})))}"
            )


class ControlRateViolation(ValueError):
    """A candidate's controller runs slower than the deployment demands."""


#: Float slack for comparing two declared periods. Both sides are numbers
#: a human typed into a config, so this only has to absorb the difference
#: between ``0.05`` and ``0.05000000000000001``.
_PERIOD_EPS = 1e-9


def validate_control_rate(profile: TaskProfile, candidates: Sequence[Candidate]) -> None:
    """Refuse a candidate whose controller is slower than T_cycle.

    Two different things are both called ``control_period`` and they were
    quietly allowed to disagree:

    * ``profile.robot.control_period`` is the deployment's **requirement**
      — how fast the loop must close on the target board. G4's threshold
      is exactly this number (:attr:`RobotConfig.t_cycle_ms`).
    * a local controller's ``control_period`` is the rate the candidate
      **actually runs at**. ``nav_stack`` holds the last command between
      ticks, exactly as a real ``/cmd_vel`` stream behaves.

    Nothing compared them. G4 measures the cost of *one* controller call,
    so a candidate that closes its loop at 10 Hz on a deployment
    demanding 20 Hz passes the real-time gate while missing every second
    deadline — the gate sees a cheap call, not a late one. That is the
    loophole underneath the ``control_period: 0.1`` concession in both
    reference profiles: the deployment was relaxed to 10 Hz so the DWA
    would fit, and the gate had no way to say the robot was being asked
    for less than the warehouse needs.

    A controller reporting ``None`` runs on every simulation step, which
    is at least as fast as any period the deployment can declare, so it
    always satisfies this.

    Raises :class:`ControlRateViolation`; callers must not downgrade this
    to a warning (HĐ-1.4's "fail at startup" shape — a slow controller
    discovered after 300 episodes is 300 episodes of a run that never
    answered the question asked).
    """
    required = profile.robot.control_period
    for candidate in candidates:
        if candidate.local_controller is None:
            continue
        period = build_local_planner(
            stack_id_for(candidate),
            candidate.layer_params(candidate.local_controller.name),
        ).control_period
        if period is None or period <= required + _PERIOD_EPS:
            continue
        raise ControlRateViolation(
            f"candidate {candidate.candidate_id} ({candidate.stack_label}) closes its "
            f"control loop every {period} s, but deployment {profile.id} declares "
            f"control_period = {required} s. The stack would hold each command for "
            f"{period / required:.3g} deployment cycles, so G4 — which times a single "
            "controller call — cannot see the missed deadlines. Either run the "
            "controller at the deployment's rate or declare a deployment that only "
            "needs this one"
        )


def build_planners(
    candidate: Candidate, *, episode_seed: int
) -> tuple[GlobalPlanner, LocalPlanner]:
    """Instantiate ``(global_planner, local_controller)`` for one episode.

    ``episode_seed`` comes from the episode context, never from global
    randomness: a sampling planner must explore a different tree per
    episode while staying reproducible from the context id (HĐ-3.2).

    Since H2 the pair comes back wrapped behind an ``AlgorithmHost``:
    same ABCs outside, host mediation inside (crash → safe stop, invalid
    output refused). The wrap is byte-neutral, and that is not asserted
    here but *pinned* — ``tests/test_host_parity_golden.py`` compares
    episodes run through this exact function against a fixture generated
    before the host existed.
    """
    # Imported at build time, not module import: candidates.py serves
    # identity-only callers (API validation, id hashing) that never run
    # an episode and should not pull the simulator in to answer.
    from planbench_simulator.host import host_backed_planners

    stack_id = stack_id_for(candidate)
    assert candidate.local_controller is not None
    local_params = candidate.layer_params(candidate.local_controller.name)
    return host_backed_planners(
        build_global_planner(stack_id, episode_seed=episode_seed),
        build_local_planner(stack_id, local_params),
    )
