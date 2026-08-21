"""What a selection-run export contains, once, for every format it takes.

There are two exports now — Markdown and Excel — and they describe the
same run. **The thing they must never do is disagree.** A card that says
94.2% in one file and 94% in the other, or one that carries the scope
caveat and one that does not, is worse than having a single format:
somebody will forward whichever copy suits them, and the two will be
quoted against each other.

So this module owns *what the export says* and each renderer owns *how
it looks*. Every number below is read from the stored report and
formatted here; `decision_markdown` lays it out as tables and
`decision_xlsx` as sheets, and neither one reaches past this module for
a value.

The three structural properties `decision_markdown` was written around
belong here now, because they are properties of the content:

1. **A run with no card still exports.** Fewer than two candidates
   through the gates means no ΔU (HĐ-7), and the gate table is then the
   whole deliverable.
2. **Null renders as "not measured", never as a blank.** HĐ-12 defines
   null that way. In a spreadsheet this matters more than on a page: an
   empty cell reads as zero, sorts as zero, and sums as zero.
3. **The caveats travel.** The scope limit, the unpinned host, the
   mixed observation classes — each one qualifies numbers that will be
   read far away from the screen they came from.
"""

from __future__ import annotations

from typing import Any, NamedTuple

__all__ = [
    "EPISODE_COLUMNS",
    "GATE_COLUMNS",
    "OUTCOME_COLUMNS",
    "Caveat",
    "NOT_MEASURED",
    "as_number",
    "as_ratio",
    "as_text",
    "card_rows",
    "decision_evidence_rows",
    "environment_warning",
    "episode_rows",
    "gate_rows",
    "human_rows",
    "mixed_observation",
    "no_card_reason",
    "outcome_rows",
    "provenance_rows",
    "retired_candidates",
    "sample_rows",
    "scope_of",
    "sensitivity_rows",
]

#: What a missing number says. Spelled out rather than left blank
#: because HĐ-12 makes null "not measured", which is a finding.
NOT_MEASURED = "not measured"


def as_text(value: Any) -> str:
    """A value as a cell that never comes out empty.

    **No Markdown escaping here.** An earlier version escaped ``|`` at
    this level, which was right while Markdown was the only reader and
    became wrong the moment a second one existed: a spreadsheet would
    have shown the backslashes. Escaping belongs to the renderer that
    needs it.
    """
    if value is None or value == "":
        return NOT_MEASURED
    return str(value).replace("\n", " ")


def as_number(value: Any, unit: str = "") -> str:
    if value is None:
        return NOT_MEASURED
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{value:.3g}{(' ' + unit) if unit else ''}"
    return as_text(value)


def as_ratio(value: Any) -> str:
    if value is None:
        return NOT_MEASURED
    return f"{float(value) * 100:.1f}%"


def provenance_rows(run: Any, report: dict[str, Any]) -> list[tuple[str, str]]:
    """Where this came from, in enough detail to rebuild it (HĐ-13)."""
    identity = report.get("identity") or {}
    return [
        ("Run id", as_text(run.id)),
        ("Deployment", as_text(run.task_profile_id)),
        (
            "Experiment scope",
            as_text(identity.get("experiment_scope") or run.experiment_scope),
        ),
        ("Contracts version", as_text(run.contracts_version)),
        ("Code version", as_text(identity.get("git_sha"))),
        ("Anchor config", as_text(identity.get("anchor_config_version"))),
        ("Run", as_text(identity.get("created_at") or run.created_at)),
    ]


def environment_warning(report: dict[str, Any]) -> str | None:
    """The unpinned-host caveat, when the platform wrote one.

    An unpinned host makes every latency number a measurement of that
    machine as much as of the candidate, so it travels with the document
    rather than staying on the screen.
    """
    warning = (report.get("measurement_environment") or {}).get("warning")
    return as_text(warning) if warning else None


def sample_rows(report: dict[str, Any]) -> list[tuple[str, str]]:
    """What was measured, and what was asked for.

    Both, because an interrupted run whose requested count is missing
    reads as a deliberately short one — and a short run is exactly what
    a collision bound must not be computed from.
    """
    sample = report.get("sample") or {}
    measured = sample.get("n_episodes")
    requested = sample.get("n_episodes_requested")
    rows = [("Episodes measured", as_text(measured))]
    if requested is not None and requested != measured:
        rows.append(("Episodes requested", as_text(requested)))
        rows.append(("Interrupted", "yes"))
    rows.append(("Minimum required (HĐ-7.1)", as_text(sample.get("n_min_required"))))
    return rows


#: ``Shown`` is a column because a comparison between candidates given
#: different inputs is measuring the inputs.
GATE_COLUMNS: tuple[str, ...] = (
    "Candidate",
    "Config",
    "Shown",
    "Distinct episodes",
    "Success",
    "p99 latency",
    "Replans",
    "Verdict",
)


def gate_rows(report: dict[str, Any]) -> list[tuple[str, ...]]:
    """The gate table — a first-class section, not an appendix.

    Six feasibility gates run before anything is scored, so a candidate
    that failed one was never ranked at all.
    """
    rows: list[tuple[str, ...]] = []
    for candidate in report.get("candidates") or []:
        blocking = candidate.get("blocking_gates") or []
        verdict = "passed" if candidate.get("cleared_gates") else f"blocked: {', '.join(blocking)}"
        rows.append(
            (
                as_text(candidate.get("stack_label")),
                as_text(candidate.get("local_controller_config")),
                as_text(candidate.get("local_observation_class")),
                as_text(candidate.get("n_distinct_episodes")),
                as_ratio(candidate.get("success_rate")),
                as_number(candidate.get("pooled_p99_latency_ms"), "ms"),
                # Evidence, not a score. On paper it matters more than on
                # screen: "timeout" alone leaves a reader unable to tell a
                # planner that never recovered from one that recovered
                # forty times too slowly.
                as_text(candidate.get("replan_count")),
                verdict,
            )
        )
    return rows


class Caveat(NamedTuple):
    """A warning, in the two pieces every renderer needs.

    ``lead`` is the sentence that gets the emphasis; ``body`` continues
    it. Split here rather than in a renderer because both formats need
    the same split and neither should be re-deriving it from punctuation
    — an earlier version recovered the lead with ``text.split(".")[0]``,
    which is a parser for English, in a module that has no business
    owning one.

    ``body`` carries its own line breaks. Markdown wraps a blockquote at
    those points and a spreadsheet joins them with spaces, so the words
    and the shape of them live together instead of one copy per format.
    """

    lead: str
    body: tuple[str, ...]

    def sentence(self) -> str:
        """One line, for a container with no line breaks."""
        return " ".join((self.lead, *self.body))


def mixed_observation(candidates: list[dict[str, Any]]) -> Caveat | None:
    """Say so when the field was not shown the same world.

    Two stacks reading different inputs answer different questions, so
    ΔU between them measures the privilege as much as the planner. On
    paper this matters more than on screen: the reader cannot ask.
    """
    classes = {candidate.get("local_observation_class") for candidate in candidates}
    if len(classes) < 2:
        return None
    named = ", ".join(sorted(as_text(entry) for entry in classes))
    return Caveat(
        lead=f"These candidates were shown different things ({named}).",
        body=(
            "Most of the gap",
            "between their numbers is the gap between their inputs, so any ranking below",
            "is measuring the privilege as much as the planner.",
        ),
    )


def retired_candidates(candidates: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """Every retired candidate and the sample it actually got."""
    rows: list[tuple[str, str]] = []
    for entry in candidates:
        stop = entry.get("stopped_early")
        if not stop:
            continue
        rows.append(
            (
                as_text(entry.get("stack_label")),
                f"{as_text(stop.get('gate'))} after {as_text(stop.get('episodes_run'))} of "
                f"{as_text(stop.get('episodes_planned'))} episodes "
                f"({as_text(stop.get('rule'))})",
            )
        )
    return rows


def no_card_reason(report: dict[str, Any]) -> str | None:
    """Why there is no recommendation, when the run recorded a reason.

    ``gate_only_deployment`` wins over ``why_no_card``: it is a property
    of the deployment rather than of the field, and no candidate would
    ever change it (HĐ-8.4).
    """
    gate_only = report.get("gate_only_deployment")
    if gate_only:
        return f"This deployment cannot rank (HĐ-8.4): {as_text(gate_only)}"
    reason = report.get("why_no_card")
    return as_text(reason) if reason else None


def card_rows(run: Any, report: dict[str, Any]) -> list[tuple[str, str]] | None:
    """The recommendation, or ``None`` when the run produced no card."""
    card = run.card or report.get("decision_card")
    if not card:
        return None
    recommended = card.get("recommended") or {}
    alternative = card.get("alternative") or {}
    return [
        ("Recommended", as_text(recommended.get("stack"))),
        ("Candidate id", as_text(recommended.get("candidate_id"))),
        ("Alternative", as_text(alternative.get("stack"))),
        ("Status", as_text(card.get("status"))),
        ("Contracts version", as_text(card.get("contracts_version"))),
    ]


def scope_of(run: Any, report: dict[str, Any]) -> str | None:
    """What the recommendation may be applied to, and nothing else."""
    card = run.card or report.get("decision_card")
    if not card:
        return None
    return as_text(card.get("recommendation_scope") or run.task_profile_id)


def sensitivity_rows(evidence: dict[str, Any]) -> list[tuple[str, str]] | None:
    """The three margins. ``None`` when not one of them was measured.

    HĐ-12 makes null "not measured". Rendered blank, a card that measured
    none of them would look exactly like one that measured all three —
    which is why the caller says so in words rather than printing three
    empty cells.
    """
    rows = [
        ("Weight stability margin", evidence.get("weight_stability_margin")),
        ("Anchor stability", evidence.get("anchor_stability")),
        ("Robustness margin", evidence.get("robustness_margin")),
    ]
    if all(value is None for _, value in rows):
        return None
    return [(label, as_number(value)) for label, value in rows]


def human_rows(run: Any) -> list[tuple[str, str]]:
    """Who read it and who approved it — two acts, kept apart (HĐ-14)."""
    return [
        ("Review state", as_text(run.review_state)),
        ("Reviewed by", as_text(run.reviewed_by)),
        ("Reviewed at", as_text(run.reviewed_at)),
        ("Configuration decision", as_text(run.config_state)),
        ("Decided by", as_text(run.config_decided_by)),
        ("Decided at", as_text(run.config_decided_at)),
    ]


#: One row per candidate: what the sweep concluded about each of them.
#:
#: Separate from the gate table because the two answer different
#: questions — that one is "who was eliminated where", this one is "how
#: did each behave". Several of these columns are what a reader compares
#: stacks on, and until now none of them left the screen.
OUTCOME_COLUMNS: tuple[str, ...] = (
    "Candidate",
    "Config",
    "Utility /100",
    "U_R",
    "U_S",
    "U_E",
    "U_C",
    "Success",
    "Collisions",
    "Collision bound 95%",
    "No route found",
    "Worst clearance",
    "Median episode",
    "p99 latency",
    "Memory estimate",
    "Distinct episodes",
    "Replans",
    "Eligible to recommend",
)


def _gate_number(candidate: dict[str, Any], gate: str, field: str) -> Any:
    verdict = (candidate.get("gates") or {}).get(gate)
    if not isinstance(verdict, dict):
        return None
    return verdict.get(field)


def outcome_rows(report: dict[str, Any]) -> list[tuple[str, ...]]:
    """Every candidate's end-of-run numbers, in one table.

    Read out of the report rather than recomputed: the gate payloads
    already carry the collision count, the 95% bound, the no-path rate
    and the memory estimate, and the scoring pass already wrote the
    utility, the objectives and the two episode reductions. A second
    derivation here could disagree with the gate verdict printed two
    rows above it, and both would render as the same quantity.
    """
    rows: list[tuple[str, ...]] = []
    for candidate in report.get("candidates") or []:
        objectives = candidate.get("objectives") or {}
        utility = candidate.get("decision_utility")
        eligible = candidate.get("recommendation_eligible")
        rows.append(
            (
                as_text(candidate.get("stack_label")),
                as_text(candidate.get("local_controller_config")),
                NOT_MEASURED if utility is None else f"{float(utility) * 100:.1f}",
                as_number(objectives.get("U_R")),
                as_number(objectives.get("U_S")),
                as_number(objectives.get("U_E")),
                as_number(objectives.get("U_C")),
                as_ratio(candidate.get("success_rate")),
                as_text(_gate_number(candidate, "G2", "observed")),
                as_ratio(_gate_number(candidate, "G2", "upper_bound_95")),
                as_ratio(_gate_number(candidate, "G1", "no_path_rate")),
                as_number(candidate.get("worst_clearance_m"), "m"),
                as_number(candidate.get("median_travel_time_s"), "s"),
                as_number(candidate.get("pooled_p99_latency_ms"), "ms"),
                as_number(_gate_number(candidate, "G5", "memory_estimate_mb"), "MB"),
                as_text(candidate.get("n_distinct_episodes")),
                as_text(candidate.get("replan_count")),
                # Spelled out rather than left to be inferred from the
                # gate column: "scored lower" and "was never in the
                # running" are different claims, and a gate failure can
                # leave no mark on the utility at all — collisions are
                # excluded from U_S by contract (HĐ-6).
                "yes" if eligible else "no",
            )
        )
    return rows


def decision_evidence_rows(run: Any, report: dict[str, Any]) -> list[tuple[str, str]] | None:
    """The margin between the top two, with the interval that qualifies it.

    ``None`` when the run produced no card. Printing ΔU without its
    interval would turn "ahead, but not measurably" into a result, so the
    two never appear apart.
    """
    card = run.card or report.get("decision_card")
    if not card:
        return None
    evidence = card.get("evidence") or {}
    interval = evidence.get("ci95")
    rows = [
        ("Decision utility", as_number(card.get("decision_utility"))),
        ("Pareto label", as_text(card.get("pareto_label"))),
        ("Decision mode", as_text(card.get("decision_mode"))),
        ("ΔU vs the runner-up", as_number(evidence.get("delta_u_vs_second"))),
        ("ΔU mean", as_number(evidence.get("delta_u_mean"))),
        (
            "ΔU 95% interval",
            f"[{as_number(interval[0])}, {as_number(interval[1])}]"
            if isinstance(interval, (list, tuple)) and len(interval) == 2
            else NOT_MEASURED,
        ),
        ("Effect size", as_number(evidence.get("effect_size"))),
        ("Episodes compared", as_text(evidence.get("n_episodes"))),
    ]
    objectives = card.get("objectives") or {}
    rows += [(f"Objective {name}", as_number(objectives.get(name))) for name in
             ("U_R", "U_S", "U_E", "U_C")]
    return rows


#: One row per episode. Narrow on purpose — this is what the report
#: stores, and the trace endpoint serves the episode itself.
EPISODE_COLUMNS: tuple[str, ...] = (
    "Candidate",
    "Episode",
    "Outcome",
    "Collisions",
    "Min clearance",
    "Travel time",
    "p99 latency",
    "Replans",
    "Episode utility",
)


def episode_rows(report: dict[str, Any]) -> list[tuple[str, ...]]:
    """Every episode of every candidate.

    **The aggregate was never the whole answer.** `success_rate: 0.70`
    says seventy per cent of something happened; it does not say which
    thirty per cent did not, nor whether they were collisions or
    timeouts — and those two ask for different work.

    Failure reason rather than a bare "failed": that is the column a
    reader scans to find the episode worth opening.
    """
    rows: list[tuple[str, ...]] = []
    for candidate in report.get("candidates") or []:
        label = as_text(candidate.get("stack_label"))
        config = as_text(candidate.get("local_controller_config"))
        for episode in candidate.get("episodes") or []:
            outcome = (
                "passed" if episode.get("success") else as_text(episode.get("failure_reason"))
            )
            rows.append(
                (
                    f"{label} / {config}",
                    as_text(episode.get("episode_context_id")),
                    outcome,
                    as_text(episode.get("collision_count")),
                    as_number(episode.get("min_clearance"), "m"),
                    as_number(episode.get("travel_time_s"), "s"),
                    as_number(episode.get("p99_latency_ms"), "ms"),
                    as_text(episode.get("replan_count")),
                    as_number(episode.get("episode_decision_utility")),
                )
            )
    return rows
