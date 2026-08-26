"""Say what is wrong with a comparison before it costs anything to find out.

Gates G1–G6 evaluate a run that has already happened. That is the right
place for them — a gate's job is to decide, and deciding on a plan rather
than on evidence is how a benchmark stops meaning anything. But it leaves
a gap that costs real time: a deployment whose declared collision risk
needs three thousand episodes, a candidate whose stack this platform will
not benchmark, two entries that hash to the same identity — all knowable
from the request body, all currently discovered after the simulation.

This module reads the draft and says so first. It is the mirror image of
:mod:`planbench_decision.self_check`: that one argues with a run after
the fact, this one argues with a plan before it. Both produce text, both
cite a field, neither decides anything.

**It never blocks and never raises.** A pre-flight that could refuse a
launch would be a seventh gate with none of a gate's guarantees, written
against the plan instead of the evidence. Every rule here is advice a
person may read and overrule, and the launch path is untouched — a
comparison that pre-flight hates still runs if somebody asks for it.

**It never runs an episode.** Every answer comes from the stored task
profile, the algorithm registry and, for the mission rules, the map file
the profile already names. Nothing is simulated, so the whole check
returns in the time it takes to load one map.

Where this lives, and why not beside ``self_check``: most rules need the
registry (``benchmarkable``, ``requires_model``, the controller configs),
which lives here in :mod:`planbench_benchmark`. ``planbench_decision``
does not import this package and must not start — ``gates.py`` already
dodges the same cycle with a ``TYPE_CHECKING`` import. This package is
plain Python either way, so the core-first rule holds.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from planbench_benchmark.candidates import LOCAL_CONTROLLER_CONFIGS, candidate_from_stack
from planbench_benchmark.registry import algorithm_info
from planbench_decision.advice import Advice, keep_resolvable, order

__all__ = [
    "PREFLIGHT_CODES",
    "build_draft",
    "preflight",
]

#: Published so a caller can say how many rules ran, the way
#: ``RULE_CODES`` does for the post-hoc critique. A reader who sees "12
#: rules, no advice" has learned something; "no advice" alone has not
#: told them whether anything was checked.
PREFLIGHT_CODES: tuple[str, ...] = (
    "PF_BUILD_FAILED",
    "PF_CONTROL_RATE_SLOWER_THAN_DEPLOYMENT",
    "PF_DUPLICATE_CANDIDATE_ID",
    "PF_EPISODES_BELOW_N_MIN",
    "PF_GOAL_UNREACHABLE_FOR_RADIUS",
    "PF_MAP_UNREADABLE",
    "PF_MODEL_NOT_CHOSEN",
    "PF_OBSERVATION_NOT_AVAILABLE",
    "PF_QUIET_WORLD_REPEATS_ONE_EPISODE",
    "PF_REFERENCE_STACK_IN_COMPARISON",
    "PF_REPLANNING_OFF_WITH_TRAFFIC",
    "PF_STOCHASTIC_PLANNER_SEEDS",
)

#: Below this many seeds a randomised global planner's spread is mostly
#: its own sampling rather than anything about the deployment. Not a
#: threshold anything is decided on — it only decides whether to speak.
STOCHASTIC_SEED_FLOOR = 20


def _n_min(collision_probability_max: float) -> int:
    """Episodes needed to support a zero-collision claim (rule of three).

    Re-derived here rather than read from
    ``TaskConstraints.n_min_evaluation_episodes``, which is a
    ``@property``: properties are invisible to ``model_dump()``, so a
    rule citing that path would be dropped by ``keep_resolvable`` without
    a word. The arithmetic is one line and the citation points at the
    declared risk instead, which is the number a reader would change.
    """
    if collision_probability_max <= 0.0:
        return 0
    return math.ceil(round(3.0 / collision_probability_max, 6))


def _candidate_record(spec: Mapping[str, Any]) -> dict[str, Any]:
    """One merged view of a candidate: what was asked for, and what it is.

    Deliberately one flat shape rather than a ``Candidate.model_dump()``.
    Half the rules need what the *request* said (``stack``,
    ``local_config``), half need what the registry knows
    (``benchmarkable``, ``requires_model``), and half need what the built
    candidate became (``candidate_id``, ``observation_requirements``).
    A record missing any of those forces rules to cite a path that does
    not exist in this particular draft, which is the silent-drop failure
    this whole layer is built to avoid.

    Every key is always present. When a stack is unknown or a build
    fails, the unknown halves are ``None`` — present and null, which
    ``keep_resolvable`` accepts and a rule can cite.
    """
    stack = str(spec.get("stack", ""))
    local_config = str(spec.get("local_config", ""))
    params = dict(LOCAL_CONTROLLER_CONFIGS.get(local_config, {}))
    params.update(dict(spec.get("params") or {}))

    info = algorithm_info(stack)
    record: dict[str, Any] = {
        "stack": stack,
        "local_config": local_config,
        "params": params,
        "benchmarkable": getattr(info, "benchmarkable", None),
        "requires_model": getattr(info, "requires_model", None),
        "stochastic_global_planner": getattr(info, "stochastic_global_planner", None),
        "local_controller": getattr(info, "local_controller", None),
        "candidate_id": None,
        "observation_requirements": None,
        "control_period": params.get("control_period"),
        "build_error": None,
    }

    try:
        built = candidate_from_stack(stack, params=params)
    except Exception as exc:  # every registry refusal, kept as text
        record["build_error"] = f"{type(exc).__name__}: {exc}"
        return record

    record["candidate_id"] = built.candidate_id
    record["observation_requirements"] = list(built.observation_requirements)
    return record


def build_draft(
    profile: Mapping[str, Any],
    specs: Sequence[Mapping[str, Any]],
    *,
    scope: str = "",
    episodes: int | None = None,
    seed_count: int | None = None,
    map_base_dir: Path | None = None,
) -> dict[str, Any]:
    """Assemble the dict the rules read. The only part that touches disk.

    ``profile`` is a ``TaskProfile.model_dump(mode="json")`` and ``specs``
    are the candidate entries from the launch request, so a caller can
    pre-flight exactly the body it is about to POST.

    Separated from :func:`preflight` for the same reason
    :func:`~planbench_decision.self_check.critique` takes a report dict:
    the rules stay pure, take one argument, and are testable without a
    filesystem.
    """
    constraints = dict(profile.get("constraints") or {})
    risk = float(constraints.get("collision_probability_max") or 0.0)
    required = _n_min(risk)
    per_candidate = int(episodes) if episodes else required

    draft: dict[str, Any] = {
        "task_profile": dict(profile),
        "candidates": [_candidate_record(spec) for spec in specs],
        "scope": scope,
        "plan": {
            "episodes_requested": episodes,
            "episodes_per_candidate": per_candidate,
            "seed_count": seed_count if seed_count is not None else per_candidate,
            "n_min_required": required,
            "episode_runs_total": per_candidate * len(specs),
        },
        "map": {"loaded": False, "error": None, "mission_error": None, "resolution": None},
    }
    _attach_map(draft, profile, map_base_dir)
    return draft


def _attach_map(draft: dict[str, Any], profile: Mapping[str, Any], base: Path | None) -> None:
    """Load the map this deployment names, and check the missions fit it.

    Two failures, kept apart on purpose. A map that will not load is a
    file problem and names no mission; a goal the robot cannot reach is a
    deployment problem and names exactly one. Folding them into one
    message would hand a reader a filename when their real problem is a
    dock parked 18 cm from a shelf.

    Neither raises. Eleven other rules have nothing to do with the map,
    and losing them to an unreadable file would be the check punishing
    the reader for the thing it was trying to warn about.
    """
    if base is None:
        return
    try:
        from planbench_benchmark.task_map import load_environment_map, validate_missions_on_map
        from planbench_schemas.task_profile import TaskProfile

        parsed = TaskProfile(**dict(profile))
    except Exception as exc:
        draft["map"]["error"] = f"{type(exc).__name__}: {exc}"
        return

    try:
        data = load_environment_map(parsed.environment, base_dir=base)
    except Exception as exc:
        draft["map"]["error"] = f"{type(exc).__name__}: {exc}"
        return

    draft["map"].update(
        {
            "loaded": True,
            "resolution": getattr(data, "resolution", None),
            "width": getattr(data, "width", None),
            "height": getattr(data, "height", None),
        }
    )

    # Separate call rather than `load_task_map(validate=True)`: that one
    # raises the two failures as one exception type, and the whole point
    # here is to tell them apart.
    try:
        validate_missions_on_map(parsed, data)
    except Exception as exc:
        draft["map"]["mission_error"] = f"{type(exc).__name__}: {exc}"


def preflight(draft: Mapping[str, Any]) -> tuple[Advice, ...]:
    """Advice about a comparison that has not run. Never raises.

    Returns an empty tuple for a clean draft. That is a result rather
    than a silence: paired with ``len(PREFLIGHT_CODES)``, it says twelve
    rules looked and none objected, which is the measurement that makes a
    false-alarm rate computable.
    """
    try:
        found = tuple(_rules(draft))
    except Exception:  # noqa: BLE001 — advice must never take a caller down
        return ()
    return order(keep_resolvable(found, dict(draft)))


def _rules(draft: Mapping[str, Any]) -> Any:
    profile = dict(draft.get("task_profile") or {})
    candidates = list(draft.get("candidates") or [])
    plan = dict(draft.get("plan") or {})
    environment = dict(profile.get("environment") or {})
    constraints = dict(profile.get("constraints") or {})
    robot = dict(profile.get("robot") or {})

    yield from _candidate_rules(candidates, profile, robot)
    yield from _stochastic_rules(candidates, plan)
    yield from _plan_rules(candidates, plan, constraints)
    yield from _world_rules(candidates, draft, environment, profile)


def _candidate_rules(
    candidates: list[dict[str, Any]], profile: Mapping[str, Any], robot: Mapping[str, Any]
) -> Any:
    """Advice about each entry, most specific first.

    Order is the point. A candidate that cannot be built is the most
    general thing this module can say about it, and it is nearly always
    the *least* useful: "astar+pure_pursuit cannot be built" tells a
    reader to go fishing, where "this is a pipeline reference and ranking
    against it measures its blindness" tells them what they did wrong and
    what not to conclude. So the specific rules run first, and
    ``PF_BUILD_FAILED`` is emitted only for a failure none of them
    explained.
    """
    available = set(profile.get("available_observations") or ())
    seen: dict[str, int] = {}

    for index, entry in enumerate(candidates):
        stack = entry.get("stack") or "(unnamed)"
        subject = entry.get("candidate_id") or stack
        explained = False

        if entry.get("benchmarkable") is False:
            explained = True
            yield Advice(
                code="PF_REFERENCE_STACK_IN_COMPARISON",
                kind="preflight",
                severity="blocking",
                subject=subject,
                claim=f"{stack} is a pipeline reference, not a benchmark entry",
                ground=(
                    "the registry marks it `benchmarkable=False` because it ignores sensing; "
                    "any ranking against it measures the reference's blindness"
                ),
                field_path=f"candidates[{index}].benchmarkable",
                do=(
                    "compare two benchmarkable stacks, and use the reference only to "
                    "check the pipeline"
                ),
                do_not="report a win over a reference stack as a result about navigation",
            )

        if entry.get("requires_model") and not str(entry.get("params", {}).get("model_id") or ""):
            explained = True
            yield Advice(
                code="PF_MODEL_NOT_CHOSEN",
                kind="preflight",
                severity="blocking",
                subject=subject,
                claim=f"{stack} needs a trained policy and none was named",
                ground=(
                    "the registry marks it `requires_model=True`; there is no default checkpoint"
                ),
                field_path=f"candidates[{index}].requires_model",
                do="name a `model_id` from the model registry",
                do_not="assume a default policy exists — a benchmark must say which one ran",
            )

        required = entry.get("observation_requirements")
        if required is not None and available:
            missing = sorted(set(required) - available)
            if missing:
                explained = True
                yield Advice(
                    code="PF_OBSERVATION_NOT_AVAILABLE",
                    kind="preflight",
                    severity="blocking",
                    subject=subject,
                    claim=(
                        f"{stack} needs {', '.join(missing)}, which this deployment does not offer"
                    ),
                    ground=(
                        "G6 compares the same two lists and will fail this candidate — "
                        "after every episode has run"
                    ),
                    field_path=f"candidates[{index}].observation_requirements",
                    do=(
                        "declare the observation on the deployment, or choose a stack that fits it"
                    ),
                    do_not=(
                        "add the token to the deployment just to pass G6 — the deployment is a "
                        "claim about what the robot really has"
                    ),
                )

        period = entry.get("control_period")
        deadline = robot.get("control_period")
        both_numeric = isinstance(period, (int, float)) and isinstance(deadline, (int, float))
        if both_numeric and period > deadline:
            yield Advice(
                code="PF_CONTROL_RATE_SLOWER_THAN_DEPLOYMENT",
                kind="preflight",
                severity="material",
                subject=subject,
                claim=(
                    f"{stack} is configured to think every {period}s, but the deployment "
                    f"requires a decision every {deadline}s"
                ),
                ground="G4 reads the deployment's control period as its deadline",
                field_path=f"candidates[{index}].control_period",
                do="lower the controller's control_period, or declare a deployment that can wait",
                do_not="relax the deployment's control period to make the gate pass",
            )

        if entry.get("build_error") and not explained:
            yield Advice(
                code="PF_BUILD_FAILED",
                kind="preflight",
                severity="blocking",
                subject=subject,
                claim=f"{stack} cannot be built from the configuration given",
                ground=str(entry["build_error"]),
                field_path=f"candidates[{index}].build_error",
                do="fix the parameter the registry named, or pick a configuration that exists",
                do_not="launch and read the failure as a result about the algorithm",
            )

        cid = entry.get("candidate_id")
        if isinstance(cid, str) and cid:
            if cid in seen:
                yield Advice(
                    code="PF_DUPLICATE_CANDIDATE_ID",
                    kind="preflight",
                    severity="blocking",
                    subject=cid,
                    claim=f"entries {seen[cid]} and {index} are the same configuration",
                    ground=(
                        "`candidate_id` is a hash of the configuration (HĐ-1.3), so these two "
                        "would share every trace, pairing and ΔU"
                    ),
                    field_path=f"candidates[{index}].candidate_id",
                    do="change one of them, or drop it and compare against something different",
                    do_not="read the resulting tie as evidence that two approaches are equivalent",
                )
            else:
                seen[cid] = index


def _stochastic_rules(candidates: list[dict[str, Any]], plan: Mapping[str, Any]) -> Any:
    """A randomised planner is worth saying, and worth saying louder when
    there are too few seeds to average its own sampling out.

    Two severities from one condition rather than two rules: the fact is
    the same, and only how much it should worry the reader changes with
    the seed count.
    """
    seeds = plan.get("seed_count")
    thin = isinstance(seeds, int) and seeds < STOCHASTIC_SEED_FLOOR

    for index, entry in enumerate(candidates):
        if not entry.get("stochastic_global_planner"):
            continue
        stack = entry.get("stack") or "(unnamed)"
        yield Advice(
            code="PF_STOCHASTIC_PLANNER_SEEDS",
            kind="preflight",
            severity="material" if thin else "disclosure",
            subject=entry.get("candidate_id") or stack,
            claim=(
                f"{stack} plans randomly, and {seeds} seeds is too few to average that out"
                if thin
                else f"{stack} plans randomly, so one seed is one sample of the planner"
            ),
            ground=(
                "the registry marks it `stochastic_global_planner=True`; its spread "
                "across seeds is partly its own sampling, not only the deployment"
            ),
            field_path=f"candidates[{index}].stochastic_global_planner",
            do=(
                f"run at least {STOCHASTIC_SEED_FLOOR} seeds"
                if thin
                else "read its numbers across seeds, and say in the report that it is randomised"
            ),
            do_not="quote a single seed's path length as the planner's path length",
        )


def _plan_rules(
    candidates: list[dict[str, Any]], plan: Mapping[str, Any], constraints: Mapping[str, Any]
) -> Any:
    planned = plan.get("episodes_per_candidate")
    needed = plan.get("n_min_required")
    if isinstance(planned, int) and isinstance(needed, int) and needed > 0 and planned < needed:
        risk = constraints.get("collision_probability_max")
        yield Advice(
            code="PF_EPISODES_BELOW_N_MIN",
            kind="preflight",
            severity="blocking",
            claim=f"{planned} episodes cannot support the declared collision risk",
            ground=(
                f"a claim of at most {risk} needs {needed} clean episodes by the rule of three; "
                "G2 will fail on the count no matter how the runs go"
            ),
            field_path="plan.episodes_per_candidate",
            do=(
                f"run {needed} episodes per candidate, or declare a risk this many "
                "episodes can support"
            ),
            do_not=(
                "raise collision_probability_max to shrink the requirement — the deployment's "
                "risk is a statement about the world, not a budget"
            ),
        )


def _world_rules(
    candidates: list[dict[str, Any]],
    draft: Mapping[str, Any],
    environment: Mapping[str, Any],
    profile: Mapping[str, Any],
) -> Any:
    traffic = list(environment.get("dynamic_obstacles") or ())
    noise = dict(environment.get("sensor_noise") or {})
    replanning = dict(profile.get("replanning") or {})
    noisy = any(bool(value) for value in noise.values())
    random_planner = any(entry.get("stochastic_global_planner") for entry in candidates)

    if not traffic and not noisy and not random_planner:
        yield Advice(
            code="PF_QUIET_WORLD_REPEATS_ONE_EPISODE",
            kind="preflight",
            severity="material",
            claim="every seed will produce the same episode",
            ground=(
                "no dynamic obstacles, no sensor noise, and no randomised planner — a "
                "deterministic stack replays one trajectory, so N runs carry the information of one"
            ),
            field_path="task_profile.environment.sensor_noise",
            do="add traffic or sensor noise, or state that this measures one trajectory",
            do_not="report a confidence interval over N identical episodes as N samples",
        )

    if traffic and not replanning.get("enabled"):
        yield Advice(
            code="PF_REPLANNING_OFF_WITH_TRAFFIC",
            kind="preflight",
            severity="disclosure",
            claim=f"{len(traffic)} moving obstacles, and a blocked candidate may not replan",
            ground=(
                "replanning is off, so a candidate whose global path is blocked has only its "
                "local controller to escape with"
            ),
            field_path="task_profile.replanning.enabled",
            do="decide this deliberately — both settings are valid experiments",
            do_not=(
                "switch it on midway and compare against earlier runs; it is a different "
                "deployment and needs its own id"
            ),
        )

    map_state = dict(draft.get("map") or {})
    if map_state.get("mission_error"):
        yield Advice(
            code="PF_GOAL_UNREACHABLE_FOR_RADIUS",
            kind="preflight",
            severity="blocking",
            claim="a mission does not fit the map this deployment names",
            ground=str(map_state["mission_error"]),
            field_path="map.mission_error",
            do="move the pose, or declare a deployment whose map has room for this robot",
            do_not=(
                "shrink the robot radius to make the pose fit — the radius is a fact about "
                "the vehicle, and every clearance number downstream is computed from it"
            ),
        )

    if map_state.get("error"):
        yield Advice(
            code="PF_MAP_UNREADABLE",
            kind="preflight",
            severity="blocking",
            claim="the map this deployment names cannot be read",
            ground=str(map_state["error"]),
            field_path="map.error",
            do="fix the map file or the name the deployment gives it",
            do_not="launch — every candidate would fail for a property of the file",
        )
