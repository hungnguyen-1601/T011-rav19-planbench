"""Turn a failed gate into a next step, and name the step that is barred.

A gate table says ``G3: fail``. True, checkable, and it leaves the reader
to work out alone whether the answer is a better candidate, a different
scenario split, or the one move that makes the symptom vanish without
making the conclusion true: edit ``success_rate_min`` down and run again.

That move is one field away in a form the same person is authorised to
edit. Every gate here has one like it — loosen the threshold, widen the
collision risk so ``N_min`` shrinks, declare an observation token the
robot does not really carry — and a reader told only "this failed" is
being invited to go looking.

So each piece of advice carries both halves. ``do`` is the legitimate
route; ``do_not`` names the barred one explicitly, because leaving it
implicit is how it gets taken. The report already says this once, in
``why_no_card``, for the run as a whole: *"the valid way out is to
register a new candidate, not to loosen the deployment"*. This module
says it per candidate and per gate, where the reader is actually looking.

**Two sources, one dict.** A gate's threshold lives on the task profile
and its observation lives on the report — ``G3: "fail"`` is a bare string
with no number in it. :func:`build_diagnosis` merges them under
``report.`` and ``task_profile.`` so every citation resolves against one
object, the way ``keep_resolvable`` requires.

**It never re-decides.** The verdicts are read, never recomputed. A
module that could disagree with a gate would be a second gate with no
contract behind it.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from planbench_decision.advice import Advice, keep_resolvable, order

__all__ = [
    "GATE_ADVICE_CODES",
    "build_diagnosis",
    "gate_advice",
]

GATE_ADVICE_CODES: tuple[str, ...] = (
    "GA_G1_NO_PATH",
    "GA_G2_COLLISION",
    "GA_G2_TOO_FEW_EPISODES",
    "GA_G3_SUCCESS_RATE",
    "GA_G4_TOO_SLOW",
    "GA_G4_HOST_ONLY",
    "GA_G5_MEMORY",
    "GA_G6_OBSERVATION",
    "GA_NOBODY_CLEARED",
    "GA_UNPINNED_MEASUREMENT",
)

#: Gate verdicts that mean "did not pass". Read rather than recomputed —
#: this module explains gates, it does not get a vote.
_FAILED = {"fail", "failed", "blocked"}


def build_diagnosis(
    report: Mapping[str, Any], profile: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """One dict holding both halves of the evidence.

    The report says what happened; the task profile says what was
    required. ``G3: "fail"`` carries neither the rate observed nor the
    rate demanded, so advice that named only one of them would be advice
    a reader could not check.
    """
    return {"report": dict(report), "task_profile": dict(profile or {})}


def gate_advice(diagnosis: Mapping[str, Any]) -> tuple[Advice, ...]:
    """Advice for every gate a candidate did not clear. Never raises."""
    try:
        found = tuple(_rules(diagnosis))
    except Exception:  # noqa: BLE001 — advice must never take a caller down
        return ()
    return order(keep_resolvable(found, dict(diagnosis)))


def _verdict(gate: Any) -> str:
    """The verdict, whichever shape this gate reports in.

    G1, G3 and G6 are bare strings; G2, G4 and G5 are dicts with a
    ``result`` key. A caller that assumed one shape would silently skip
    half the gates.
    """
    if isinstance(gate, str):
        return gate
    if isinstance(gate, dict):
        return str(gate.get("result", ""))
    return ""


def _rules(diagnosis: Mapping[str, Any]) -> Any:
    report = dict(diagnosis.get("report") or {})
    profile = dict(diagnosis.get("task_profile") or {})
    constraints = dict(profile.get("constraints") or {})
    candidates = list(report.get("candidates") or [])

    for index, entry in enumerate(candidates):
        gates = dict(entry.get("gates") or {})
        label = entry.get("stack_label") or entry.get("candidate_id") or f"entry {index}"
        subject = str(entry.get("candidate_id") or label)
        at = f"report.candidates[{index}]"

        yield from _g1(gates, constraints, entry, label, subject, at)
        yield from _g2(gates, label, subject, at)
        yield from _g3(gates, constraints, entry, label, subject, at)
        yield from _g4(gates, label, subject, at)
        yield from _g5(gates, label, subject, at)
        yield from _g6(gates, label, subject, at)

    yield from _run_rules(report, candidates)


def _g1(
    gates: Mapping[str, Any],
    constraints: Mapping[str, Any],
    entry: Mapping[str, Any],
    label: str,
    subject: str,
    at: str,
) -> Any:
    if _verdict(gates.get("G1")) not in _FAILED:
        return
    allowed = constraints.get("no_path_rate_max")
    yield Advice(
        code="GA_G1_NO_PATH",
        kind="diagnosis",
        severity="blocking",
        subject=subject,
        claim=f"{label} failed to find a path more often than this deployment allows",
        ground=(
            f"G1 compares the no-path rate against no_path_rate_max"
            f"{f' = {allowed}' if allowed is not None else ''}; a planner that returns no path "
            "never reaches the controller, so nothing downstream is measured"
        ),
        field_path=f"{at}.gates.G1",
        do=(
            "check the missions actually fit the map for this robot radius, then try a "
            "planner that searches harder — this is usually geometry, not tuning"
        ),
        do_not=(
            "raise no_path_rate_max so the gate passes; the rate is what the deployment "
            "can tolerate, not what this candidate happened to achieve"
        ),
    )


def _g2(gates: Mapping[str, Any], label: str, subject: str, at: str) -> Any:
    gate = gates.get("G2")
    if not isinstance(gate, dict) or _verdict(gate) not in _FAILED:
        return
    observed = gate.get("observed")
    n_runs = gate.get("n_distinct_episodes") or gate.get("n_runs")
    n_min = gate.get("n_min")

    if isinstance(observed, int) and observed > 0:
        yield Advice(
            code="GA_G2_COLLISION",
            kind="diagnosis",
            severity="blocking",
            subject=subject,
            claim=f"{label} collided {observed} time(s)",
            ground=(
                "G2 requires zero collisions over the evaluation set; one is enough to fail "
                "it, because the claim being made is about safety and not about an average"
            ),
            field_path=f"{at}.gates.G2.observed",
            do=(
                "open the trace for a colliding episode and read what the clearance did "
                "before impact; raise safety_margin if the controller cut it fine"
            ),
            do_not=(
                "average the collisions away over more episodes — the gate is a zero, not a rate"
            ),
        )

    if isinstance(n_runs, int) and isinstance(n_min, int) and n_runs < n_min:
        yield Advice(
            code="GA_G2_TOO_FEW_EPISODES",
            kind="diagnosis",
            severity="blocking",
            subject=subject,
            claim=f"{n_runs} clean episodes cannot support the declared collision risk",
            ground=(
                f"the rule of three needs {n_min} for this deployment's declared risk; "
                "zero collisions in too few runs is not evidence of safety"
            ),
            field_path=f"{at}.gates.G2.n_min",
            do=f"run at least {n_min} episodes per candidate",
            do_not=(
                "raise collision_probability_max to shrink N_min — the declared risk is a "
                "statement about the world, not a budget for compute"
            ),
        )


def _g3(
    gates: Mapping[str, Any],
    constraints: Mapping[str, Any],
    entry: Mapping[str, Any],
    label: str,
    subject: str,
    at: str,
) -> Any:
    if _verdict(gates.get("G3")) not in _FAILED:
        return
    rate = entry.get("success_rate")
    threshold = constraints.get("success_rate_min")
    seen = f"{rate:.0%}" if isinstance(rate, (int, float)) else "its success rate"
    wanted = f" against {threshold:.0%} required" if isinstance(threshold, (int, float)) else ""
    yield Advice(
        code="GA_G3_SUCCESS_RATE",
        kind="diagnosis",
        severity="blocking",
        subject=subject,
        claim=f"{label} reached the goal {seen} of the time{wanted}",
        ground=(
            "G3 is the deployment's own success floor; the gate says how often, and the "
            "traces say whether the misses were timeouts, collisions or no-paths — which "
            "are three different problems"
        ),
        field_path=f"{at}.success_rate",
        do=(
            "read the failure reasons per episode before tuning: timeouts point at speed "
            "or lookahead, no-paths at geometry, collisions at clearance"
        ),
        do_not=(
            "lower success_rate_min to obtain a Decision Card — that is the move the "
            "contract bars, and the report's own why_no_card says so"
        ),
    )


def _g4(gates: Mapping[str, Any], label: str, subject: str, at: str) -> Any:
    gate = gates.get("G4")
    if not isinstance(gate, dict):
        return
    if _verdict(gate) in _FAILED:
        observed = gate.get("p99_ms")
        limit = gate.get("threshold_ms")
        yield Advice(
            code="GA_G4_TOO_SLOW",
            kind="diagnosis",
            severity="blocking",
            subject=subject,
            claim=f"{label} misses the control deadline at the 99th percentile",
            ground=(
                f"p99 {observed} ms against a {limit} ms budget; the deadline is the "
                "deployment's control period, so a miss means the robot has no command "
                "when it needs one"
            ),
            field_path=f"{at}.gates.G4.p99_ms",
            do=(
                "reduce the search — fewer velocity samples, a shorter horizon — and "
                "re-measure; latency is the one gate tuning reliably moves"
            ),
            do_not=(
                "lengthen the deployment's control period; that is a claim about what the "
                "vehicle can wait for, not a knob"
            ),
        )
        return

    if str(gate.get("status", "")) == "screened_on_host":
        yield Advice(
            code="GA_G4_HOST_ONLY",
            kind="diagnosis",
            severity="disclosure",
            subject=subject,
            claim=f"{label} passed G4 on a development host, not on the target device",
            ground=str(gate.get("caveat") or "the gate records that it was screened on the host"),
            field_path=f"{at}.gates.G4.status",
            do="say in the report that the latency result is a host screening",
            do_not="present a host screening as a real-time guarantee on the robot",
        )


def _g5(gates: Mapping[str, Any], label: str, subject: str, at: str) -> Any:
    gate = gates.get("G5")
    if not isinstance(gate, dict) or _verdict(gate) not in _FAILED:
        return
    estimate = gate.get("memory_estimate_mb")
    available = gate.get("available_ram_mb")
    yield Advice(
        code="GA_G5_MEMORY",
        kind="diagnosis",
        severity="blocking",
        subject=subject,
        claim=f"{label} needs more memory than the target device has",
        ground=(
            f"{estimate} MB estimated against {available} MB available; the estimate is "
            "derived from the peak search nodes this run actually reached"
        ),
        field_path=f"{at}.gates.G5.memory_estimate_mb",
        do=(
            "shrink the search space — a coarser costmap or a tighter node budget — or "
            "declare a device with the RAM this planner needs"
        ),
        do_not=(
            "raise available_ram_mb to clear the gate; the number describes hardware that "
            "either exists or does not"
        ),
    )


def _g6(gates: Mapping[str, Any], label: str, subject: str, at: str) -> Any:
    gate = gates.get("G6")
    if _verdict(gate) not in _FAILED:
        return
    missing = gate.get("missing") if isinstance(gate, dict) else None
    named = ", ".join(missing) if isinstance(missing, list) and missing else "an observation"
    yield Advice(
        code="GA_G6_OBSERVATION",
        kind="diagnosis",
        severity="blocking",
        subject=subject,
        claim=f"{label} needs {named}, which this deployment does not provide",
        ground=(
            "G6 compares what the stack requires against what the deployment declares; "
            "both lists exist before a single episode runs, so this was knowable up front"
        ),
        field_path=f"{at}.gates.G6",
        do="choose a stack that fits the deployment, or declare a deployment that has the sensor",
        do_not=(
            "add the token to available_observations to pass the gate — that list is a "
            "claim about what the robot really carries"
        ),
    )


def _run_rules(report: Mapping[str, Any], candidates: list[dict[str, Any]]) -> Any:
    if report.get("why_no_card") and not report.get("decision_card"):
        cleared = sum(1 for entry in candidates if entry.get("cleared_gates"))
        yield Advice(
            code="GA_NOBODY_CLEARED",
            kind="diagnosis",
            severity="material",
            claim=(
                f"{cleared} of {len(candidates)} candidates cleared every gate, so there is no card"
            ),
            ground=(
                "a Decision Card needs two candidates through all six gates; with fewer, "
                "the gate table is the whole result — and it is a result, not a failure"
            ),
            field_path="report.why_no_card",
            do="register a candidate that clears the gates the current field could not",
            do_not=(
                "loosen the deployment until a card appears; the card would then describe "
                "a deployment nobody is going to run"
            ),
        )

    warning = ((report.get("measurement_environment") or {}).get("warning")) or None
    if warning:
        yield Advice(
            code="GA_UNPINNED_MEASUREMENT",
            kind="diagnosis",
            severity="material",
            claim="the host flagged a problem with how this run was measured",
            ground=str(warning),
            field_path="report.measurement_environment.warning",
            do="re-run pinned to dedicated cores before quoting any latency number",
            do_not="compare p99 latencies across runs measured under different host conditions",
        )
