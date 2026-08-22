"""Say what a finished run supports as a sentence, and what it does not.

``GET /decisions/{run_id}/report.md`` already renders the run — provenance,
sample, gate table, card, human record — and every number in that document
is correct. What it cannot do is stop the document from being read into a
sentence it does not support. The same gate table supports *"rrtstar+dwa
reached the goal 100% of the time on open_hall_v2 over 30 episodes"* and
*"RRT\\* is the better planner for warehouses"*, and the distance between
those two is the whole value of the platform.

So this module writes no prose about the result. It writes the guardrail:
for each thing the reader is about to quote, the sentence that is
available and the neighbouring sentence that is not. ``do`` is the phrasing
the evidence carries; ``do_not`` is the phrasing one adjective away from it
that nothing here establishes.

**The barred sentence is quoted, not described.** "Be careful about
generalising" is advice nobody has ever acted on. "Do not write 'in
warehouses'" is. Each ``do_not`` names the actual words, because the
failure mode is a person under deadline reaching for a stronger verb, and
a general warning does not compete with a stronger verb.

**Absence is the hardest half.** Four of these rules exist because a null
reads as a reassuring zero: a null ``effect_size`` is "undefined", not "no
effect"; null sensitivity margins are "never swept", not "stable"; a null
``alternative`` is "none established", not "none needed";
``UNCERTAIN_DOMINANCE`` is HĐ-10.1's name for *not enough data*. Each of
those cites a field that is **present and holds null** — which
:func:`~planbench_decision.advice.keep_resolvable` allows precisely so
this kind of advice can exist, since a rule that could not cite a null
would be silent about exactly the fields that mislead.

**It never re-decides and never re-renders.** The status, the interval and
the verdicts are read as written. A module that could disagree with the
card would be a second card with no contract behind it, and one that
restated the tables would be a second renderer to keep in sync.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from planbench_decision.advice import Advice, keep_resolvable, order

__all__ = [
    "REPORT_ADVICE_CODES",
    "build_reporting_source",
    "report_advice",
]

#: Every code a rule here can emit. Published for the same reason
#: ``PREFLIGHT_CODES`` and ``RULE_CODES`` are: "no advice" alone does not
#: tell a reader whether anything looked.
REPORT_ADVICE_CODES: tuple[str, ...] = (
    "RP_BLOCKED_CANDIDATE_NOT_RANKABLE",
    "RP_BUSINESS_ADJUSTED_IS_NOT_A_MEASUREMENT",
    "RP_CI_CONTAINS_ZERO",
    "RP_CLAIM_IS_MISSION_LEVEL",
    "RP_DOMINANCE_NOT_ESTABLISHED",
    "RP_EFFECT_SIZE_NOT_MEASURED",
    "RP_HOST_ONLY_LATENCY",
    "RP_MEDIAN_OUTSIDE_ITS_INTERVAL",
    "RP_MEMORY_NEVER_MEASURED",
    "RP_NEAR_EQUIVALENT_IS_NOT_A_WIN",
    "RP_NO_CARD_NO_WINNER",
    "RP_NOT_APPROVED_YET",
    "RP_RATE_NEEDS_ITS_DENOMINATOR",
    "RP_RUNNER_UP_IS_NOT_THE_ALTERNATIVE",
    "RP_SCOPE_HELD_ONE_LAYER_FIXED",
    "RP_SCOPE_IS_ONE_DEPLOYMENT",
    "RP_SENSITIVITY_NOT_MEASURED",
    "RP_UNEQUAL_EPISODE_COUNTS",
)

#: The three phase-5 analyses, in the order HĐ-12 lists them, paired with
#: the sentence each one would have licensed had it run. Iterated in this
#: fixed order so the advice cites the same field on every run of one
#: report — a citation that moved between identical runs would be one a
#: reader cannot diff.
_SENSITIVITY_FIELDS: tuple[tuple[str, str], ...] = (
    ("weight_stability_margin", "stable under other weightings"),
    ("anchor_stability", "unchanged under other anchors"),
    ("robustness_margin", "robust in the neighbourhood of this deployment"),
)

#: What each partial scope held fixed, and therefore what the ranking is
#: a ranking *of*. HĐ-1.4 puts the scope on every card because the same
#: numbers support different sentences depending on the answer.
_SCOPE_HELD_FIXED: dict[str, tuple[str, str]] = {
    "global_planner_selection": (
        "the local controller",
        "global planners under that one controller",
    ),
    "local_controller_selection": (
        "the global planner",
        "local controllers under that one planner",
    ),
}


def build_reporting_source(
    report: Mapping[str, Any], card: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """One dict holding the run and the card a reader has in front of them.

    ``card`` is separate because the two travel separately: a stored
    ``comparison_report.json`` carries its card under ``decision_card``,
    while the API's run row keeps an approved card of its own and
    ``render_decision_markdown`` reads ``run.card or
    report["decision_card"]``. Passing the card explicitly is how a
    caller says *this* is the card being quoted — an approval stamped on
    the run row is exactly the field ``RP_NOT_APPROVED_YET`` reads, and
    taking it from the report instead would tell a reviewer their own
    signature is missing.

    Defaults to the report's own card, so the common case is one
    argument. ``None`` when there is none, which the card rules skip on
    and ``RP_NO_CARD_NO_WINNER`` speaks about.
    """
    chosen = card if card is not None else report.get("decision_card")
    return {
        "report": dict(report),
        "card": dict(chosen) if isinstance(chosen, Mapping) else None,
    }


def report_advice(source: Mapping[str, Any]) -> tuple[Advice, ...]:
    """Which sentences this finished run supports. Never raises.

    An empty tuple is a result: paired with ``len(REPORT_ADVICE_CODES)``
    it says eighteen rules read the run and none of them found a sentence
    worth barring. It is not a licence to write anything — it means these
    rules found nothing, not that the report is quotable in any words.
    """
    try:
        found = tuple(_rules(source))
    except Exception:  # noqa: BLE001 — advice must never take a caller down
        return ()
    return order(keep_resolvable(found, dict(source)))


def _rules(source: Mapping[str, Any]) -> Any:
    report = dict(source.get("report") or {})
    raw_card = source.get("card")
    card = dict(raw_card) if isinstance(raw_card, Mapping) else {}
    candidates = list(report.get("candidates") or [])

    yield from _no_card_rules(report, card)
    yield from _statistics_rules(card)
    yield from _unmeasured_rules(card)
    yield from _scope_rules(report, card)
    yield from _sample_rules(report, candidates)
    yield from _candidate_rules(candidates)


def _recommended(card: Mapping[str, Any]) -> tuple[str, str]:
    """``(candidate_id, stack)`` off the card, both possibly empty.

    Read together because they are two views of one thing and a reader
    needs both: the stack is what a sentence names, the id is what
    identifies it (HĐ-1.3), and two candidates differing only in
    parameters share the stack label.
    """
    block = card.get("recommended")
    if not isinstance(block, Mapping):
        return "", ""
    return str(block.get("candidate_id") or ""), str(block.get("stack") or "")


def _evidence(card: Mapping[str, Any]) -> dict[str, Any]:
    """The card's ``evidence`` block as a plain dict, empty when absent."""
    block = card.get("evidence")
    return dict(block) if isinstance(block, Mapping) else {}


def _interval(card: Mapping[str, Any]) -> tuple[float, float] | None:
    """``ci95`` as two floats, or None when it is not a usable pair."""
    ci = _evidence(card).get("ci95")
    if not isinstance(ci, (list, tuple)) or len(ci) != 2:
        return None
    low, high = ci
    if not isinstance(low, (int, float)) or not isinstance(high, (int, float)):
        return None
    return float(low), float(high)


# --------------------------------------------------------------------
# A run with no card. The gate table is the result, and it names nobody.
# --------------------------------------------------------------------


def _no_card_rules(report: Mapping[str, Any], card: Mapping[str, Any]) -> Any:
    if card:
        return
    reason = report.get("why_no_card")
    yield Advice(
        code="RP_NO_CARD_NO_WINNER",
        kind="reporting",
        severity="blocking",
        claim="this run produced no Decision Card, so it names no winner",
        ground=(
            str(reason)
            if reason
            else (
                "fewer than two candidates cleared all six gates, so no ΔU was computed and "
                "there is no statistic that would separate anybody"
            )
        ),
        # `why_no_card` when the run said why, `decision_card` — present
        # and null — when it only said no. Both are checkable; a rule that
        # insisted on the first would go silent on the reports that
        # explain themselves least.
        field_path="report.why_no_card" if reason else "report.decision_card",
        do=(
            "report the gate table as the finding: who was eliminated, at which gate, and on "
            "how many episodes"
        ),
        do_not=(
            "name a winner from the gate table — clearing every gate is eligibility, not a "
            "ranking, and nothing here compared the survivors to each other"
        ),
    )


# --------------------------------------------------------------------
# The statistics. What the interval will and will not carry.
# --------------------------------------------------------------------


def _statistics_rules(card: Mapping[str, Any]) -> Any:
    if not card:
        return
    evidence = _evidence(card)
    subject, stack = _recommended(card)
    named = stack or subject or "the recommended candidate"
    interval = _interval(card)
    median = evidence.get("delta_u_vs_second")

    if card.get("status") == "NEAR_EQUIVALENT":
        yield Advice(
            code="RP_NEAR_EQUIVALENT_IS_NOT_A_WIN",
            kind="reporting",
            severity="blocking",
            subject=subject,
            claim=f"the card recommends {named} with status NEAR_EQUIVALENT",
            ground=(
                "NEAR_EQUIVALENT is what HĐ-11.3 calls a comparison whose paired interval did "
                "not separate the two candidates; the name on the card came off the declared "
                "tie-break ladder, which always yields a winner and never establishes one"
            ),
            field_path="card.status",
            do=(
                f"write that the run could not tell the two apart and that {named} was chosen "
                "by the declared tie-break"
            ),
            do_not=(
                f"write that {named} beat, outperformed or won against the runner-up — the "
                "status is this platform's word for 'we could not tell'"
            ),
        )

    if interval is not None and interval[0] <= 0.0 <= interval[1]:
        low, high = interval
        point = f"{median:+.4f}" if isinstance(median, (int, float)) else "the point estimate"
        yield Advice(
            code="RP_CI_CONTAINS_ZERO",
            kind="reporting",
            severity="blocking",
            subject=subject,
            claim=f"the 95% interval for ΔU is [{low:+.4f}, {high:+.4f}], which contains zero",
            ground=(
                "the interval is the evidence about the difference, and one that spans zero is "
                "consistent with the two candidates being identical — including with the sign "
                "of the point estimate being the other way round"
            ),
            field_path="card.evidence.ci95",
            do="quote the interval and say the run did not separate the two candidates",
            do_not=(
                f"quote ΔU = {point} as the improvement, or as a gain, or as a percentage "
                "better — this evidence supports a difference of zero just as well"
            ),
        )

    if interval is not None and isinstance(median, (int, float)):
        low, high = interval
        if not low <= median <= high:
            mean = evidence.get("delta_u_mean")
            spelled = f"{mean:+.6f}" if isinstance(mean, (int, float)) else "delta_u_mean"
            yield Advice(
                code="RP_MEDIAN_OUTSIDE_ITS_INTERVAL",
                kind="reporting",
                severity="material",
                subject=subject,
                claim=(
                    f"ΔU's headline {median:+.6f} falls outside the interval "
                    f"[{low:+.6f}, {high:+.6f}] printed beside it"
                ),
                ground=(
                    "they are two different statistics: delta_u_vs_second is the *median* "
                    "paired difference (HĐ-11.3) and ci95 is the bootstrap interval of the "
                    f"*mean* (HĐ-11.2), which here is {spelled}. On a skewed set they separate "
                    "visibly, and side by side they read as one number and its error bar"
                ),
                field_path="card.evidence.delta_u_vs_second",
                do=(
                    "print median, mean and interval as three labelled numbers, so a reader can "
                    "see which one the interval belongs to"
                ),
                do_not=(
                    f"write 'ΔU = {median:+.6f} (95% CI [{low:+.6f}, {high:+.6f}])' — that "
                    "sentence hands the mean's interval to the median"
                ),
            )


# --------------------------------------------------------------------
# The nulls. Each of these cites a field that is there and empty.
# --------------------------------------------------------------------


def _unmeasured_rules(card: Mapping[str, Any]) -> Any:
    if not card:
        return
    evidence = _evidence(card)
    subject, stack = _recommended(card)
    named = stack or subject or "the recommended candidate"

    if "effect_size" in evidence and evidence["effect_size"] is None:
        yield Advice(
            code="RP_EFFECT_SIZE_NOT_MEASURED",
            kind="reporting",
            severity="material",
            subject=subject,
            claim="this run recorded no effect size",
            ground=(
                "effect_size is null, which HĐ-11 uses for *undefined*: every episode gave the "
                "identical paired difference, so the standardised effect would divide by a "
                "spread of zero. A missing measurement, not a measurement of zero"
            ),
            field_path="card.evidence.effect_size",
            do=(
                "say the effect size is undefined for this run, and quote the median difference "
                "and its interval instead"
            ),
            do_not=(
                "read the blank as 'no effect', 'a negligible effect' or 'effect size ≈ 0' — "
                "the run did not answer that question either way"
            ),
        )

    unmeasured = [
        (field, sentence)
        for field, sentence in _SENSITIVITY_FIELDS
        if field in evidence and evidence[field] is None
    ]
    if unmeasured:
        names = ", ".join(field for field, _ in unmeasured)
        yield Advice(
            code="RP_SENSITIVITY_NOT_MEASURED",
            kind="reporting",
            severity="material",
            subject=subject,
            claim=f"{len(unmeasured)} of the 3 sensitivity analyses did not run ({names})",
            ground=(
                "HĐ-12 writes an analysis that was never run as null, so the card can say "
                "'not measured' rather than a plausible default that would read as "
                "'measured, and fine'"
            ),
            field_path=f"card.evidence.{unmeasured[0][0]}",
            do="state which sweeps ran and which did not, wherever the recommendation is quoted",
            do_not=(
                f"describe {named} as {unmeasured[0][1]} — nothing was swept, and null is the "
                "absence of the answer rather than a reassuring one"
            ),
        )

    if card.get("pareto_label") == "UNCERTAIN_DOMINANCE":
        yield Advice(
            code="RP_DOMINANCE_NOT_ESTABLISHED",
            kind="reporting",
            severity="material",
            subject=subject,
            claim="the card's pareto_label is UNCERTAIN_DOMINANCE",
            ground=(
                "HĐ-10.1's own name for *not enough data to conclude* — either no Pareto "
                "analysis ran, or the per-objective intervals overlapped. It is the label for "
                "an unanswered question, not for a close one"
            ),
            field_path="card.pareto_label",
            do="report the four objectives one at a time, as the numbers they are",
            do_not=(
                f"write that {named} dominates the field, or that it is better on every "
                "objective — the label says that was not established"
            ),
        )

    if "alternative" in card and card["alternative"] is None:
        yield Advice(
            code="RP_RUNNER_UP_IS_NOT_THE_ALTERNATIVE",
            kind="reporting",
            severity="material",
            subject=subject,
            claim="this card offers no alternative",
            ground=(
                "alternative is null, and HĐ-12 fills it only from the Pareto frontier. The "
                "statistical runner-up is a different claim — second on one weighted sum, "
                "which a candidate worse on every objective at once can still be"
            ),
            field_path="card.alternative",
            do="report the ranking as a ranking, and say no second option was established",
            do_not=(
                "present the runner-up as 'the alternative' or as a safe second choice; those "
                "are the words this field was left empty rather than say"
            ),
        )


# --------------------------------------------------------------------
# Scope. Which world, which layer, and whose signature.
# --------------------------------------------------------------------


def _scope_rules(report: Mapping[str, Any], card: Mapping[str, Any]) -> Any:
    if not card:
        return
    identity = report.get("identity") if isinstance(report.get("identity"), Mapping) else {}
    deployment = str((identity or {}).get("task_profile_id") or "")
    subject, stack = _recommended(card)
    named = stack or subject or "the recommended candidate"

    if deployment:
        yield Advice(
            code="RP_SCOPE_IS_ONE_DEPLOYMENT",
            kind="reporting",
            severity="disclosure",
            subject=subject,
            claim=f"every number in this run was measured on {deployment} and on nothing else",
            ground=(
                "HĐ-1.4 limits a recommendation to the deployment it was measured on: the map, "
                "the mission set, the traffic and the declared sensor noise are all part of "
                "what produced these numbers, and no other environment was run"
            ),
            field_path="report.identity.task_profile_id",
            do=f"name {deployment} in the same sentence as the result, every time it is quoted",
            do_not=(
                "generalise it to 'in warehouses', 'for AMRs' or 'in general' — carrying it to "
                "another deployment is a claim this run did not make"
            ),
        )

    if card.get("recommendation_scope") == "MISSION_LEVEL":
        yield Advice(
            code="RP_CLAIM_IS_MISSION_LEVEL",
            kind="reporting",
            severity="material",
            subject=subject,
            claim="the card's recommendation_scope is MISSION_LEVEL",
            ground=(
                "the weakest of HĐ-2.2's three claim levels: these missions were run, the "
                "neighbourhood around the deployment was not, so the result holds for this "
                "mission set rather than for the deployment as a whole"
            ),
            field_path="card.recommendation_scope",
            do="say the result holds for the missions this profile declares",
            do_not=(
                "call it a deployment-level or a robust recommendation; DEPLOYMENT_LEVEL and "
                "ROBUST_DEPLOYMENT_LEVEL are two further rungs this run did not reach"
            ),
        )

    scope = str(card.get("experiment_scope") or "")
    if scope in _SCOPE_HELD_FIXED:
        held, ranks = _SCOPE_HELD_FIXED[scope]
        yield Advice(
            code="RP_SCOPE_HELD_ONE_LAYER_FIXED",
            kind="reporting",
            severity="material",
            subject=subject,
            claim=f"the experiment scope is {scope}, so {held} was identical across candidates",
            ground=(
                "HĐ-1.4 puts the scope on the card because the same numbers support different "
                f"sentences depending on what was held fixed; this run ranks {ranks}"
            ),
            field_path="card.experiment_scope",
            do=f"quote the result as a ranking of {ranks}",
            do_not=(
                f"drop {held} from the sentence — the ranking was measured with one of them and "
                "says nothing about the pairing with another"
            ),
        )

    mode = str(card.get("decision_mode") or "")
    if mode == "business_adjusted":
        label = str(card.get("decision_mode_label") or "")
        yield Advice(
            code="RP_BUSINESS_ADJUSTED_IS_NOT_A_MEASUREMENT",
            kind="reporting",
            severity="material",
            subject=subject,
            claim="this ranking was produced in business_adjusted mode",
            ground=(
                (f"{label}; " if label else "")
                + "the utility weights carry declared business assumptions, so the ordering is "
                "a function of those assumptions as much as of the measurements"
            ),
            field_path="card.decision_mode",
            do="quote the declared assumptions in the same breath as the recommendation",
            do_not=(
                "report a business-adjusted ranking as a measurement result; under the "
                "technical weights it may not be this ordering"
            ),
        )

    approval = card.get("approval") if isinstance(card.get("approval"), Mapping) else {}
    status = str((approval or {}).get("status") or "")
    if status and status != "APPROVED":
        yield Advice(
            code="RP_NOT_APPROVED_YET",
            kind="reporting",
            severity="disclosure",
            subject=subject,
            claim=f"the card's approval status is {status}",
            ground=(
                "HĐ-14 keeps reading the evidence and approving the configuration as two "
                "separate acts; a freshly built card is always PENDING, and nothing in the "
                "decision layer can stamp it otherwise"
            ),
            field_path="card.approval.status",
            do=f"circulate it as evidence awaiting a decision, and say {named} is proposed",
            do_not="describe it as approved, signed off or agreed",
        )


# --------------------------------------------------------------------
# The sample. Every rate in the document came out of it.
# --------------------------------------------------------------------


def _sample_rules(report: Mapping[str, Any], candidates: list[dict[str, Any]]) -> Any:
    sample = report.get("sample") if isinstance(report.get("sample"), Mapping) else {}
    measured = (sample or {}).get("n_episodes")
    quotes_a_rate = any(entry.get("success_rate") is not None for entry in candidates)
    if not quotes_a_rate or not isinstance(measured, int) or measured <= 0:
        return

    step = 100.0 / measured
    example = next(
        (entry for entry in candidates if isinstance(entry.get("success_rate"), (int, float))),
        None,
    )
    shown = ""
    if example is not None:
        rate = float(example["success_rate"])
        shown = f" — write '{rate:.0%} ({round(rate * measured)} of {measured})'"

    yield Advice(
        code="RP_RATE_NEEDS_ITS_DENOMINATOR",
        kind="reporting",
        severity="material",
        claim=f"every rate in this report is a count over {measured} episodes",
        ground=(
            f"one episode is worth {step:.1f} percentage points at this sample size, so a gap "
            f"narrower than that between two candidates is one episode landing differently — "
            "which a bare percentage hides and a count does not"
        ),
        field_path="report.sample.n_episodes",
        do=f"carry the count beside the rate wherever it is quoted{shown}",
        do_not=(
            f"quote a percentage on its own, or read a gap smaller than {step:.1f} points as a "
            "difference between candidates"
        ),
    )


# --------------------------------------------------------------------
# Per candidate. Rows that a ranking table will happily swallow.
# --------------------------------------------------------------------


def _candidate_rules(candidates: list[dict[str, Any]]) -> Any:
    counts = {
        index: entry.get("n_distinct_episodes")
        for index, entry in enumerate(candidates)
        if isinstance(entry.get("n_distinct_episodes"), int)
    }
    largest = max(counts.values(), default=0)

    for index, entry in enumerate(candidates):
        label = entry.get("stack_label") or entry.get("candidate_id") or f"entry {index}"
        subject = str(entry.get("candidate_id") or label)
        at = f"report.candidates[{index}]"
        gates = entry.get("gates") if isinstance(entry.get("gates"), Mapping) else {}
        gates = dict(gates or {})

        yield from _blocked_rule(entry, label, subject, at)
        yield from _latency_rule(gates, label, subject, at)
        yield from _memory_rule(gates, label, subject, at)

        count = counts.get(index)
        if count is not None and count < largest:
            yield Advice(
                code="RP_UNEQUAL_EPISODE_COUNTS",
                kind="reporting",
                severity="material",
                subject=subject,
                claim=(
                    f"{label}'s row rests on {count} distinct episodes where another candidate "
                    f"got {largest}"
                ),
                ground=(
                    "two rates over different denominators are not comparable at a glance, and "
                    "a table column is exactly the place a reader compares them at a glance"
                ),
                field_path=f"{at}.n_distinct_episodes",
                do=f"put the episode count in {label}'s row wherever its numbers appear",
                do_not=(
                    "place its rate in a column beside the others as though the two rested on "
                    "the same evidence"
                ),
            )


def _blocked_rule(entry: Mapping[str, Any], label: str, subject: str, at: str) -> Any:
    if entry.get("cleared_gates") is not False:
        return
    blocking = [str(gate) for gate in (entry.get("blocking_gates") or [])]
    named = ", ".join(blocking) if blocking else "a gate"
    yield Advice(
        code="RP_BLOCKED_CANDIDATE_NOT_RANKABLE",
        kind="reporting",
        severity="blocking",
        subject=subject,
        claim=f"{label} failed {named} and was therefore never scored",
        ground=(
            "gates run before scoring (HĐ-7): a candidate that fails one is not a worse choice, "
            "it is not a choice. It holds no rank, and the numbers on its row describe a "
            "configuration that was eliminated"
        ),
        field_path=f"{at}.cleared_gates",
        do=f"quote {label} as eliminated at {named}, with the number that eliminated it",
        do_not=(
            f"place {label} second, call it the runner-up, or include its row in anything a "
            "reader will read as a ranking"
        ),
    )


def _latency_rule(gates: Mapping[str, Any], label: str, subject: str, at: str) -> Any:
    gate = gates.get("G4")
    if not isinstance(gate, Mapping) or gate.get("status") != "screened_on_host":
        return
    p99 = gate.get("p99_ms")
    budget = gate.get("threshold_ms")
    measured = f"{p99:.1f} ms" if isinstance(p99, (int, float)) else "its p99"
    against = f" against a {budget:.0f} ms budget" if isinstance(budget, (int, float)) else ""
    yield Advice(
        code="RP_HOST_ONLY_LATENCY",
        kind="reporting",
        severity="disclosure",
        subject=subject,
        claim=f"{label}'s latency of {measured}{against} was screened on the benchmark host",
        ground=str(gate.get("caveat") or "the gate records that it was screened on the host")
        + " — the target device was never measured, and a workstation and an embedded board "
        "do not differ by a constant factor",
        field_path=f"{at}.gates.G4.status",
        do=f"write 'screened on the development host at p99 {measured}{against}'",
        do_not=(
            f"call it a real-time guarantee, or write that {label} meets its control deadline "
            "on the robot — no measurement here is about the robot"
        ),
    )


def _memory_rule(gates: Mapping[str, Any], label: str, subject: str, at: str) -> Any:
    gate = gates.get("G5")
    if not isinstance(gate, Mapping):
        return
    status = str(gate.get("status") or "")
    if status not in {"estimated_from_structure", "declared_by_author"}:
        return
    estimate = gate.get("memory_estimate_mb")
    target = gate.get("target_implementation")
    figure = f"{estimate:.1f} MB" if isinstance(estimate, (int, float)) else "its memory figure"
    for_target = f" for {target}" if target else ""
    yield Advice(
        code="RP_MEMORY_NEVER_MEASURED",
        kind="reporting",
        severity="disclosure",
        subject=subject,
        claim=f"{label}'s {figure} is {status}, not a measurement on the target device",
        ground=(
            "G5 screens in one direction only (HĐ-7.3): over the budget certainly does not fit, "
            "under it establishes nothing about the reverse, because the figure is counts times "
            f"declared byte sizes{for_target} rather than an observed footprint"
        ),
        field_path=f"{at}.gates.G5.status",
        do=f"report {figure} as an estimate{for_target}, and say how it was arrived at",
        do_not=(
            f"write that {label} fits in the robot's memory — passing this screening is not "
            "capable of establishing that"
        ),
    )
