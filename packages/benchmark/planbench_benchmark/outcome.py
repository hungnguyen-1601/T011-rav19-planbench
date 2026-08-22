"""Why one candidate won and the other lost, in checkable sentences.

A finished run says *who*: the card names a winner, the gate table names
who was eliminated where. Nobody currently says *why* — whether the gap
is what the algorithms' own natures predict, or a surprise worth
investigating. That question has two halves, and both live here.

**The numbers half** comes from the stored report: which metric actually
separated the candidates (success rate, tail latency, ΔU), by how much,
and whether the margin licenses a conclusion at all.

**The nature half** comes from :data:`TRAITS` — what each algorithm
family is known to be good and bad at. Every trait is anchored where it
can be checked: the registry's own flags first
(``stochastic_global_planner``, ``requires_model``), textbook properties
of the algorithm second, and each entry names its anchor. A trait table
with no anchors would be the model's folklore in a constant's clothing.

The two halves meet in the rules: "the sampling planner lost on tail
latency" is a number; "and that is the textbook price of sampling, not a
configuration bug" is the nature; the advice is the join, with the field
path of the number so a reader can check the half that is checkable.

Same constitution as every advisory module: read-only, never raises,
every citation resolves, and the LLM layer above may rank and extend but
never overrule.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from planbench_benchmark.registry import algorithm_info
from planbench_decision.advice import Advice, keep_resolvable, order

__all__ = [
    "OUTCOME_CODES",
    "TRAITS",
    "build_outcome",
    "outcome_advice",
]

OUTCOME_CODES: tuple[str, ...] = (
    "OC_ELIMINATED_BY_GATE",
    "OC_LATENCY_PRICE_OF_SAMPLING",
    "OC_MARGIN_IS_NOISE",
    "OC_METRIC_DRIVER",
    "OC_SAME_CONTROLLER_ISOLATES_PLANNER",
    "OC_TRAIT_SURPRISE",
    "OC_WINNER_ON_MARGIN",
)

#: What each algorithm family is known for. ``anchor`` says where the
#: claim can be checked: a registry flag, or the algorithm's defining
#: mechanics. Nothing here is a measurement — measurements come from the
#: report, and the rules only pair the two.
TRAITS: dict[str, dict[str, Any]] = {
    "astar": {
        "kind": "global",
        "strengths": (
            "complete and optimal on the grid it searches — the same map in, the same path out",
            "cost is bounded by the grid, so latency is predictable episode to episode",
        ),
        "weaknesses": (
            "paths are grid-constrained: never shorter than the 8-connected lattice allows",
            "search cost grows with map size and inflation, all of it paid before the robot moves",
        ),
        "anchor": "deterministic by construction; registry marks stochastic_global_planner=False",
    },
    "rrtstar": {
        "kind": "global",
        "strengths": (
            "any-angle paths — sampling is not bound to a lattice, so converged paths run shorter",
            "anytime: more iterations buy a better tree without a new algorithm",
        ),
        "weaknesses": (
            "stochastic: one seed is one draw, and its spread across seeds is its "
            "own sampling noise",
            "tail latency is the price of sampling — the slowest episodes are "
            "where the tree grew wrong",
        ),
        "anchor": (
            "registry marks stochastic_global_planner=True; results must be read across seeds"
        ),
    },
    "dwa": {
        "kind": "local",
        "strengths": (
            "reactive and cheap per tick: samples reachable velocities against the live costmap",
            "degrades gracefully — a blocked rollout costs a bad score, not a crash",
        ),
        "weaknesses": (
            "local: it optimises one horizon, so doorways and dead ends it cannot "
            "see past become stalls",
            "oscillation-prone in tight spaces — competing rollouts flip the turn direction",
        ),
        "anchor": "velocity-sampling controller; horizon and weights are its whole world",
    },
    "ppo": {
        "kind": "local",
        "strengths": (
            "learned reactions can beat hand-tuned costs inside the training distribution",
        ),
        "weaknesses": (
            "behaviour is bound to the training distribution; a new map is an "
            "out-of-distribution question",
            "needs a named checkpoint — the number means nothing without which policy produced it",
        ),
        "anchor": "registry marks requires_model=True",
    },
    "dwa_predictive": {
        "kind": "local",
        "strengths": (
            "scores rollouts against where obstacles are going, not a photograph of "
            "them at t=0 — with perfect perception, 11 of 11 paired disagreements "
            "favoured it (p = 0.0005, intersection, 2026-08-15)",
        ),
        "weaknesses": (
            "withdrawn 2026-08-16: the LiDAR tracker feeding it reports up to "
            "1.9 m/s of motion on a static warehouse, and none of the perfect-"
            "perception gain survives the real estimator (KNOWN_LIMITATIONS L16/L19)",
            "constant-velocity motion model — wrong the moment anything turns or "
            "stops; sudden_stop is the counter-example, not a corner case",
        ),
        "anchor": (
            "registry marks benchmarkable=False and its description records the "
            "withdrawal with the measurements behind it"
        ),
    },
    "pure_pursuit": {
        "kind": "local",
        "strengths": ("a pipeline reference: follows the path and nothing else",),
        "weaknesses": (
            "ignores sensing entirely, so any ranking against it measures its blindness",
        ),
        "anchor": "registry marks benchmarkable=False",
    },
}


def _components(stack_label: str) -> tuple[str, str]:
    """``astar+dwa`` → its two component names, from the registry when it
    knows the stack, from the label's own shape when it does not."""
    info = algorithm_info(stack_label)
    if info is not None:
        return str(info.global_planner), str(info.local_controller)
    left, _, right = str(stack_label).partition("+")
    return left, right


def build_outcome(
    report: Mapping[str, Any], profile: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """One dict: the report, each candidate's traits, and the deployment.

    The traits ride inside the source rather than being looked up by the
    rules, for the same reason every module in this family pre-computes
    its diff: each rule cites a path into the structure the caller can
    render, and a citation into a table the reader cannot see would be
    advice they cannot check.
    """
    candidates = []
    for entry in report.get("candidates") or []:
        stack = str(entry.get("stack_label") or "")
        global_name, local_name = _components(stack)
        candidates.append(
            {
                **dict(entry),
                "global_planner": global_name,
                "local_controller": local_name,
                "traits": {
                    "global": TRAITS.get(global_name, {}),
                    "local": TRAITS.get(local_name, {}),
                },
            }
        )
    return {
        "report": {**dict(report), "candidates": candidates},
        "task_profile": dict(profile or {}),
    }


def outcome_advice(source: Mapping[str, Any]) -> tuple[Advice, ...]:
    """Why the run ended the way it did. Never raises."""
    try:
        found = tuple(_rules(source))
    except Exception:  # noqa: BLE001 — advice must never take a caller down
        return ()
    return order(keep_resolvable(found, dict(source)))


def _rules(source: Mapping[str, Any]) -> Any:
    report = dict(source.get("report") or {})
    candidates = list(report.get("candidates") or [])
    card = report.get("decision_card")

    yield from _gate_eliminations(candidates)
    yield from _scope_isolation(report, candidates)
    if isinstance(card, dict):
        yield from _card_rules(card, candidates)
    yield from _metric_rules(candidates)


def _gate_eliminations(candidates: list[dict[str, Any]]) -> Any:
    """A loss at the gates is a different kind of loss, and the trait
    that predicts it is worth naming next to the number."""
    for index, entry in enumerate(candidates):
        blocking = list(entry.get("blocking_gates") or [])
        if not blocking:
            continue
        label = entry.get("stack_label") or entry.get("candidate_id") or f"entry {index}"
        weaknesses = tuple((entry.get("traits") or {}).get("local", {}).get("weaknesses") or ())
        nature = (
            f" {label.split('+')[-1]}'s known weakness — {weaknesses[0]} — is "
            "the first place to look."
            if weaknesses
            else ""
        )
        yield Advice(
            code="OC_ELIMINATED_BY_GATE",
            kind="diagnosis",
            severity="material",
            subject=str(entry.get("candidate_id") or label),
            claim=f"{label} did not lose the ranking — it was eliminated at {', '.join(blocking)}",
            ground=(
                "an eliminated candidate never entered the ΔU comparison, so the outcome is "
                f"a gate story, not a margin story.{nature}"
            ),
            field_path=f"report.candidates[{index}].blocking_gates",
            do=(
                "read the failed gate's advice and the failing episodes' traces before "
                "concluding anything about the algorithm itself"
            ),
            do_not=(
                "describe this as the other stack 'winning' — nobody was compared; one "
                "entry did not qualify"
            ),
        )


def _scope_isolation(report: Mapping[str, Any], candidates: list[dict[str, Any]]) -> Any:
    """When both candidates share a local controller, the outcome is
    about the global planners — a fact the scope declares and readers
    routinely miss."""
    if len(candidates) < 2:
        return
    locals_ = {entry.get("local_controller") for entry in candidates}
    scope = (report.get("identity") or {}).get("experiment_scope")
    if len(locals_) == 1 and scope == "global_planner_selection":
        globals_ = " vs ".join(str(entry.get("global_planner")) for entry in candidates[:2])
        yield Advice(
            code="OC_SAME_CONTROLLER_ISOLATES_PLANNER",
            kind="diagnosis",
            severity="disclosure",
            claim=(
                f"both candidates drive with the same controller, so this outcome is {globals_}"
            ),
            ground=(
                "the experiment scope holds the local layer fixed; every difference in the "
                "numbers is attributable to the global planners and their interaction with it"
            ),
            field_path="report.identity.experiment_scope",
            do=(
                "read the result as a planner comparison, which is what the scope "
                "was built to isolate"
            ),
            do_not="credit the controller for a gap the scope deliberately kept it out of",
        )


def _card_rules(card: dict[str, Any], candidates: list[dict[str, Any]]) -> Any:
    status = str(card.get("status") or "")
    evidence = dict(card.get("evidence") or {})
    recommended = dict(card.get("recommended") or {})
    winner_stack = str(recommended.get("stack") or "")
    ci = evidence.get("ci95")
    delta = evidence.get("delta_u_vs_second")

    if status == "NEAR_EQUIVALENT" or (
        isinstance(ci, (list, tuple)) and len(ci) == 2 and ci[0] <= 0.0 <= ci[1]
    ):
        yield Advice(
            code="OC_MARGIN_IS_NOISE",
            kind="diagnosis",
            severity="material",
            subject=str(recommended.get("candidate_id") or ""),
            claim="the margin between these candidates does not clear the noise",
            ground=(
                f"ΔU {delta} with CI95 {ci}: an interval that touches zero means the sign of "
                "the difference is not established, whatever the point estimate says"
            ),
            field_path="report.decision_card.evidence.ci95",
            do=(
                "say 'no established difference on this deployment' — that is a result, and "
                "often the useful one"
            ),
            do_not="name a winner from a point estimate whose interval contains zero",
        )
        return

    if winner_stack:
        global_name, _, _rest = winner_stack.partition("+")
        trait = TRAITS.get(global_name, {})
        strengths = tuple(trait.get("strengths") or ())
        nature = f" That is what {global_name} is built for: {strengths[0]}." if strengths else ""
        yield Advice(
            code="OC_WINNER_ON_MARGIN",
            kind="diagnosis",
            severity="disclosure",
            subject=str(recommended.get("candidate_id") or ""),
            claim=f"{winner_stack} won on a margin the interval supports",
            ground=(
                f"ΔU {delta}, CI95 {ci}, over {evidence.get('n_episodes')} paired episodes.{nature}"
            ),
            field_path="report.decision_card.evidence.delta_u_vs_second",
            do="quote the margin with its interval and episode count, never the point alone",
            do_not=(
                "generalise past this deployment — the margin was measured on one map, one "
                "robot, one mission set"
            ),
        )


def _metric_rules(candidates: list[dict[str, Any]]) -> Any:
    """Which observable metric actually separated the field, tied to the
    trait that predicts it — or flagged when the trait predicts the
    opposite."""
    measured = [
        (index, entry)
        for index, entry in enumerate(candidates)
        if isinstance(entry.get("success_rate"), (int, float))
    ]
    if len(measured) < 2:
        return
    (index_a, a), (index_b, b) = measured[0], measured[1]

    gap = float(a["success_rate"]) - float(b["success_rate"])
    if abs(gap) >= 0.1:
        lead, trail = (a, b) if gap > 0 else (b, a)
        lead_index = index_a if gap > 0 else index_b
        yield Advice(
            code="OC_METRIC_DRIVER",
            kind="diagnosis",
            severity="disclosure",
            subject=str(lead.get("candidate_id") or ""),
            claim=(
                f"success rate is the separator: {lead.get('stack_label')} "
                f"{lead.get('success_rate'):.0%} against {trail.get('stack_label')} "
                f"{trail.get('success_rate'):.0%}"
            ),
            ground=(
                "a gap this wide is about episodes one stack finishes and the other does "
                "not — read the failing episodes' termination reasons before crediting speed "
                "or path quality"
            ),
            field_path=f"report.candidates[{lead_index}].success_rate",
            do=(
                "open the trailing stack's failed traces; the reason (stall, timeout, "
                "no-path) names the fix"
            ),
            do_not=(
                "attribute a success-rate gap to path optimality — finishing is upstream of quality"
            ),
        )

    lat_a, lat_b = a.get("pooled_p99_latency_ms"), b.get("pooled_p99_latency_ms")
    if (
        isinstance(lat_a, (int, float))
        and isinstance(lat_b, (int, float))
        and min(lat_a, lat_b) > 0
    ):
        slow_index, slow = (index_a, a) if lat_a >= lat_b else (index_b, b)
        fast = b if lat_a >= lat_b else a
        ratio = max(lat_a, lat_b) / min(lat_a, lat_b)
        if ratio >= 2.0:
            stochastic = bool(
                (slow.get("traits") or {})
                .get("global", {})
                .get("anchor", "")
                .find("stochastic_global_planner=True")
                >= 0
            )
            if stochastic:
                yield Advice(
                    code="OC_LATENCY_PRICE_OF_SAMPLING",
                    kind="diagnosis",
                    severity="disclosure",
                    subject=str(slow.get("candidate_id") or ""),
                    claim=(
                        f"{slow.get('stack_label')} pays {ratio:.1f}x the tail latency of "
                        f"{fast.get('stack_label')}, and its own nature predicts that"
                    ),
                    ground=(
                        "the registry marks its global planner stochastic; tail latency is the "
                        "textbook price of sampling — the slowest episodes are where the tree "
                        "grew wrong before it grew right"
                    ),
                    field_path=f"report.candidates[{slow_index}].pooled_p99_latency_ms",
                    do=(
                        "treat the tail as inherent, not as a tuning bug: cap iterations if the "
                        "deadline matters more than path quality"
                    ),
                    do_not="tune expecting deterministic-planner latency from a sampling planner",
                )
            else:
                yield Advice(
                    code="OC_TRAIT_SURPRISE",
                    kind="diagnosis",
                    severity="material",
                    subject=str(slow.get("candidate_id") or ""),
                    claim=(
                        f"{slow.get('stack_label')} is {ratio:.1f}x slower at p99 than "
                        f"{fast.get('stack_label')}, and nothing in its nature predicts that"
                    ),
                    ground=(
                        "its global planner is deterministic, whose latency should be bounded "
                        "by the grid; a tail this long on a deterministic stack usually means "
                        "an oversized search space or replans nobody counted on"
                    ),
                    field_path=f"report.candidates[{slow_index}].pooled_p99_latency_ms",
                    do="check the map inflation and the replan rows before blaming the algorithm",
                    do_not="accept a surprising number because it favours the expected winner",
                )
