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

from planbench_api.decision_text import DEFAULT_LOCALE, Locale, text
from planbench_api.decision_text import lines as text_lines

__all__ = [
    "Caveat",
    "Locale",
    "NOT_MEASURED",
    "NOT_RECORDED",
    "as_number",
    "as_ratio",
    "as_text",
    "card_rows",
    "episode_columns",
    "gate_columns",
    "outcome_columns",
    "decision_evidence_rows",
    "environment_warning",
    "episode_rows",
    "gate_rows",
    "human_rows",
    "mixed_observation",
    "no_card_reason",
    "outcome_rows",
    "provenance_rows",
    "recommended_config",
    "retired_candidates",
    "sample_rows",
    "scope_of",
    "sensitivity_rows",
]

#: What a missing number says, in the default language. Read from the
#: text table rather than written twice: a constant here and an entry
#: there would be one wording per language plus one belonging to
#: neither. Spelled out rather than left blank because HĐ-12 makes null
#: "not measured", which is a finding.
NOT_MEASURED = text("value.not_measured")


def as_text(value: Any, locale: Locale = DEFAULT_LOCALE) -> str:
    """A value as a cell that never comes out empty.

    **No Markdown escaping here.** An earlier version escaped ``|`` at
    this level, which was right while Markdown was the only reader and
    became wrong the moment a second one existed: a spreadsheet would
    have shown the backslashes. Escaping belongs to the renderer that
    needs it.
    """
    if value is None or value == "":
        return text("value.not_measured", locale)
    return str(value).replace("\n", " ")


def as_number(value: Any, unit: str = "", locale: Locale = DEFAULT_LOCALE) -> str:
    if value is None:
        return text("value.not_measured", locale)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{value:.3g}{(' ' + unit) if unit else ''}"
    return as_text(value, locale)


def as_ratio(value: Any, locale: Locale = DEFAULT_LOCALE) -> str:
    if value is None:
        return text("value.not_measured", locale)
    return f"{float(value) * 100:.1f}%"


def provenance_rows(
    run: Any, report: dict[str, Any], locale: Locale = DEFAULT_LOCALE
) -> list[tuple[str, str]]:
    """Where this came from, in enough detail to rebuild it (HĐ-13)."""
    identity = report.get("identity") or {}
    return [
        (text("label.run_id", locale), as_text(run.id, locale)),
        (text("label.deployment", locale), as_text(run.task_profile_id, locale)),
        (
            text("label.experiment_scope", locale),
            as_text(identity.get("experiment_scope") or run.experiment_scope, locale),
        ),
        (text("label.contracts_version", locale), as_text(run.contracts_version, locale)),
        (text("label.code_version", locale), as_text(identity.get("git_sha"), locale)),
        (
            text("label.anchor_config", locale),
            as_text(identity.get("anchor_config_version"), locale),
        ),
        (
            text("label.run_at", locale),
            as_text(identity.get("created_at") or run.created_at, locale),
        ),
    ]


def environment_warning(
    report: dict[str, Any], locale: Locale = DEFAULT_LOCALE
) -> str | None:
    """The unpinned-host caveat, when the platform wrote one.

    An unpinned host makes every latency number a measurement of that
    machine as much as of the candidate, so it travels with the document
    rather than staying on the screen.
    """
    warning = (report.get("measurement_environment") or {}).get("warning")
    return as_text(warning, locale) if warning else None


def sample_rows(
    report: dict[str, Any], locale: Locale = DEFAULT_LOCALE
) -> list[tuple[str, str]]:
    """What was measured, and what was asked for.

    Both, because an interrupted run whose requested count is missing
    reads as a deliberately short one — and a short run is exactly what
    a collision bound must not be computed from.
    """
    sample = report.get("sample") or {}
    measured = sample.get("n_episodes")
    requested = sample.get("n_episodes_requested")
    rows = [(text("label.episodes_measured", locale), as_text(measured, locale))]
    if requested is not None and requested != measured:
        rows.append((text("label.episodes_requested", locale), as_text(requested, locale)))
        rows.append((text("label.interrupted", locale), text("value.yes", locale)))
    rows.append(
        (
            text("label.minimum_required", locale),
            as_text(sample.get("n_min_required"), locale),
        )
    )
    return rows


#: ``Shown`` is a column because a comparison between candidates given
#: different inputs is measuring the inputs.
#: The keys, in order. A function rather than a tuple of strings
#: because the header is one of the things a language changes, and a
#: module-level constant would have been frozen at import in whichever
#: language happened to be the default.
_GATE_COLUMN_KEYS: tuple[str, ...] = (
    "column.gate.candidate",
    "column.gate.config",
    "column.gate.shown",
    "column.gate.distinct_episodes",
    "column.gate.success",
    "column.gate.p99",
    "column.gate.replans",
    "column.gate.verdict",
)


def gate_columns(locale: Locale = DEFAULT_LOCALE) -> tuple[str, ...]:
    return tuple(text(key, locale) for key in _GATE_COLUMN_KEYS)


def gate_rows(
    report: dict[str, Any], locale: Locale = DEFAULT_LOCALE
) -> list[tuple[str, ...]]:
    """The gate table — a first-class section, not an appendix.

    Six feasibility gates run before anything is scored, so a candidate
    that failed one was never ranked at all.
    """
    rows: list[tuple[str, ...]] = []
    for candidate in report.get("candidates") or []:
        blocking = candidate.get("blocking_gates") or []
        verdict = (
            text("value.passed", locale)
            if candidate.get("cleared_gates")
            else text("value.blocked", locale, gates=", ".join(blocking))
        )
        rows.append(
            (
                as_text(candidate.get("stack_label"), locale),
                as_text(candidate.get("local_controller_config"), locale),
                as_text(candidate.get("local_observation_class"), locale),
                as_text(candidate.get("n_distinct_episodes"), locale),
                as_ratio(candidate.get("success_rate"), locale),
                as_number(candidate.get("pooled_p99_latency_ms"), "ms", locale),
                # Evidence, not a score. On paper it matters more than on
                # screen: "timeout" alone leaves a reader unable to tell a
                # planner that never recovered from one that recovered
                # forty times too slowly.
                as_text(candidate.get("replan_count"), locale),
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


def mixed_observation(
    candidates: list[dict[str, Any]], locale: Locale = DEFAULT_LOCALE
) -> Caveat | None:
    """Say so when the field was not shown the same world.

    Two stacks reading different inputs answer different questions, so
    ΔU between them measures the privilege as much as the planner. On
    paper this matters more than on screen: the reader cannot ask.
    """
    classes = {candidate.get("local_observation_class") for candidate in candidates}
    if len(classes) < 2:
        return None
    named = ", ".join(sorted(as_text(entry, locale) for entry in classes))
    return Caveat(
        lead=text("caveat.mixed.lead", locale, classes=named),
        body=tuple(text_lines("caveat.mixed.body", locale)),
    )


def retired_candidates(
    candidates: list[dict[str, Any]], locale: Locale = DEFAULT_LOCALE
) -> list[tuple[str, str]]:
    """Every retired candidate and the sample it actually got."""
    rows: list[tuple[str, str]] = []
    for entry in candidates:
        stop = entry.get("stopped_early")
        if not stop:
            continue
        rows.append(
            (
                as_text(entry.get("stack_label"), locale),
                text(
                    "caveat.retired_detail",
                    locale,
                    gate=as_text(stop.get("gate"), locale),
                    run=as_text(stop.get("episodes_run"), locale),
                    planned=as_text(stop.get("episodes_planned"), locale),
                    rule=as_text(stop.get("rule"), locale),
                ),
            )
        )
    return rows


def no_card_reason(
    report: dict[str, Any], locale: Locale = DEFAULT_LOCALE
) -> str | None:
    """Why there is no recommendation, when the run recorded a reason.

    ``gate_only_deployment`` wins over ``why_no_card``: it is a property
    of the deployment rather than of the field, and no candidate would
    ever change it (HĐ-8.4).
    """
    gate_only = report.get("gate_only_deployment")
    if gate_only:
        return text("prose.gate_only_deployment", locale, reason=as_text(gate_only, locale))
    reason = report.get("why_no_card")
    return as_text(reason, locale) if reason else None


#: What a row says when the artifact simply does not carry the answer.
#: Distinct from ``NOT_MEASURED``: nothing was measured wrongly here, the
#: field predates the export that wants it.
NOT_RECORDED = text("value.not_recorded")


def recommended_config(
    report: dict[str, Any], candidate_id: Any, locale: Locale = DEFAULT_LOCALE
) -> str:
    """Which local-controller config the recommendation actually names.

    **The card cannot answer this.** ``card["recommended"]`` carries the
    stack and the candidate id, and a stack does not identify a
    recommendation: both sides of a local-controller comparison run
    ``astar+dwa``, and only ``local_controller_config`` tells
    ``dwa_coarse`` from ``dwa_balanced``. So the id is looked up among
    the candidate rows, which is where the config lives.

    Never the empty string. An older artifact whose candidate rows have
    no config leaves the reader with a blank cell that reads as "no
    config" rather than "this file does not say".
    """
    missing = text("value.not_recorded", locale)
    if not candidate_id:
        return missing
    for candidate in report.get("candidates") or []:
        if candidate.get("candidate_id") == candidate_id:
            return as_text(candidate.get("local_controller_config") or missing, locale)
    return missing


def card_rows(
    run: Any, report: dict[str, Any], locale: Locale = DEFAULT_LOCALE
) -> list[tuple[str, str]] | None:
    """The recommendation, or ``None`` when the run produced no card.

    ``Recommended`` keeps saying exactly what it always said — an export
    of an old run has to diff clean against the one somebody already
    filed — and the config it was missing arrives as a row of its own.
    """
    card = run.card or report.get("decision_card")
    if not card:
        return None
    recommended = card.get("recommended") or {}
    alternative = card.get("alternative") or {}
    return [
        (text("label.recommended", locale), as_text(recommended.get("stack"), locale)),
        (
            text("label.recommended_config", locale),
            recommended_config(report, recommended.get("candidate_id"), locale),
        ),
        (text("label.candidate_id", locale), as_text(recommended.get("candidate_id"), locale)),
        (text("label.alternative", locale), as_text(alternative.get("stack"), locale)),
        (text("label.status", locale), as_text(card.get("status"), locale)),
        (
            text("label.contracts_version", locale),
            as_text(card.get("contracts_version"), locale),
        ),
    ]


def scope_of(run: Any, report: dict[str, Any], locale: Locale = DEFAULT_LOCALE) -> str | None:
    """What the recommendation may be applied to, and nothing else."""
    card = run.card or report.get("decision_card")
    if not card:
        return None
    return as_text(card.get("recommendation_scope") or run.task_profile_id, locale)


def sensitivity_rows(
    evidence: dict[str, Any], locale: Locale = DEFAULT_LOCALE
) -> list[tuple[str, str]] | None:
    """The three margins. ``None`` when not one of them was measured.

    HĐ-12 makes null "not measured". Rendered blank, a card that measured
    none of them would look exactly like one that measured all three —
    which is why the caller says so in words rather than printing three
    empty cells.
    """
    rows = [
        (text("label.weight_stability", locale), evidence.get("weight_stability_margin")),
        (text("label.anchor_stability", locale), evidence.get("anchor_stability")),
        (text("label.robustness_margin", locale), evidence.get("robustness_margin")),
    ]
    if all(value is None for _, value in rows):
        return None
    return [(label, as_number(value, "", locale)) for label, value in rows]


def human_rows(run: Any, locale: Locale = DEFAULT_LOCALE) -> list[tuple[str, str]]:
    """Who read it and who approved it — two acts, kept apart (HĐ-14)."""
    return [
        (text("label.review_state", locale), as_text(run.review_state, locale)),
        (text("label.reviewed_by", locale), as_text(run.reviewed_by, locale)),
        (text("label.reviewed_at", locale), as_text(run.reviewed_at, locale)),
        (text("label.config_state", locale), as_text(run.config_state, locale)),
        (text("label.decided_by", locale), as_text(run.config_decided_by, locale)),
        (text("label.decided_at", locale), as_text(run.config_decided_at, locale)),
    ]


#: One row per candidate: what the sweep concluded about each of them.
#:
#: Separate from the gate table because the two answer different
#: questions — that one is "who was eliminated where", this one is "how
#: did each behave". Several of these columns are what a reader compares
#: stacks on, and until now none of them left the screen.
_OUTCOME_COLUMN_KEYS: tuple[str, ...] = (
    "column.outcome.candidate",
    "column.outcome.config",
    "column.outcome.utility",
    "column.outcome.u_r",
    "column.outcome.u_s",
    "column.outcome.u_e",
    "column.outcome.u_c",
    "column.outcome.success",
    "column.outcome.collisions",
    "column.outcome.collision_bound",
    "column.outcome.no_route",
    "column.outcome.worst_clearance",
    "column.outcome.median_episode",
    "column.outcome.p99",
    "column.outcome.memory",
    "column.outcome.distinct_episodes",
    "column.outcome.replans",
    "column.outcome.eligible",
)


def outcome_columns(locale: Locale = DEFAULT_LOCALE) -> tuple[str, ...]:
    return tuple(text(key, locale) for key in _OUTCOME_COLUMN_KEYS)


def _gate_number(candidate: dict[str, Any], gate: str, field: str) -> Any:
    verdict = (candidate.get("gates") or {}).get(gate)
    if not isinstance(verdict, dict):
        return None
    return verdict.get(field)


def outcome_rows(
    report: dict[str, Any], locale: Locale = DEFAULT_LOCALE
) -> list[tuple[str, ...]]:
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
                as_text(candidate.get("stack_label"), locale),
                as_text(candidate.get("local_controller_config"), locale),
                text("value.not_measured", locale)
                if utility is None
                else f"{float(utility) * 100:.1f}",
                as_number(objectives.get("U_R"), "", locale),
                as_number(objectives.get("U_S"), "", locale),
                as_number(objectives.get("U_E"), "", locale),
                as_number(objectives.get("U_C"), "", locale),
                as_ratio(candidate.get("success_rate"), locale),
                as_text(_gate_number(candidate, "G2", "observed"), locale),
                as_ratio(_gate_number(candidate, "G2", "upper_bound_95"), locale),
                as_ratio(_gate_number(candidate, "G1", "no_path_rate"), locale),
                as_number(candidate.get("worst_clearance_m"), "m", locale),
                as_number(candidate.get("median_travel_time_s"), "s", locale),
                as_number(candidate.get("pooled_p99_latency_ms"), "ms", locale),
                as_number(_gate_number(candidate, "G5", "memory_estimate_mb"), "MB", locale),
                as_text(candidate.get("n_distinct_episodes"), locale),
                as_text(candidate.get("replan_count"), locale),
                # Spelled out rather than left to be inferred from the
                # gate column: "scored lower" and "was never in the
                # running" are different claims, and a gate failure can
                # leave no mark on the utility at all — collisions are
                # excluded from U_S by contract (HĐ-6).
                text("value.yes" if eligible else "value.no", locale),
            )
        )
    return rows


def decision_evidence_rows(
    run: Any, report: dict[str, Any], locale: Locale = DEFAULT_LOCALE
) -> list[tuple[str, str]] | None:
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
        (
            text("label.decision_utility", locale),
            as_number(card.get("decision_utility"), "", locale),
        ),
        (text("label.pareto_label", locale), as_text(card.get("pareto_label"), locale)),
        (text("label.decision_mode", locale), as_text(card.get("decision_mode"), locale)),
        (
            text("label.delta_u_vs_second", locale),
            as_number(evidence.get("delta_u_vs_second"), "", locale),
        ),
        (
            text("label.delta_u_mean", locale),
            as_number(evidence.get("delta_u_mean"), "", locale),
        ),
        (
            text("label.delta_u_ci", locale),
            f"[{as_number(interval[0], '', locale)}, {as_number(interval[1], '', locale)}]"
            if isinstance(interval, (list, tuple)) and len(interval) == 2
            else text("value.not_measured", locale),
        ),
        (text("label.effect_size", locale), as_number(evidence.get("effect_size"), "", locale)),
        (
            text("label.episodes_compared", locale),
            as_text(evidence.get("n_episodes"), locale),
        ),
    ]
    objectives = card.get("objectives") or {}
    rows += [
        (
            text("label.objective", locale, name=name),
            as_number(objectives.get(name), "", locale),
        )
        for name in ("U_R", "U_S", "U_E", "U_C")
    ]
    return rows


#: One row per episode. Narrow on purpose — this is what the report
#: stores, and the trace endpoint serves the episode itself.
_EPISODE_COLUMN_KEYS: tuple[str, ...] = (
    "column.episode.candidate",
    "column.episode.episode",
    "column.episode.outcome",
    "column.episode.collisions",
    "column.episode.min_clearance",
    "column.episode.travel_time",
    "column.episode.p99",
    "column.episode.replans",
    "column.episode.utility",
)


def episode_columns(locale: Locale = DEFAULT_LOCALE) -> tuple[str, ...]:
    return tuple(text(key, locale) for key in _EPISODE_COLUMN_KEYS)


def episode_rows(
    report: dict[str, Any], locale: Locale = DEFAULT_LOCALE
) -> list[tuple[str, ...]]:
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
        label = as_text(candidate.get("stack_label"), locale)
        config = as_text(candidate.get("local_controller_config"), locale)
        for episode in candidate.get("episodes") or []:
            outcome = (
                text("value.passed", locale)
                if episode.get("success")
                else as_text(episode.get("failure_reason"), locale)
            )
            rows.append(
                (
                    f"{label} / {config}",
                    as_text(episode.get("episode_context_id"), locale),
                    outcome,
                    as_text(episode.get("collision_count"), locale),
                    as_number(episode.get("min_clearance"), "m", locale),
                    as_number(episode.get("travel_time_s"), "s", locale),
                    as_number(episode.get("p99_latency_ms"), "ms", locale),
                    as_text(episode.get("replan_count"), locale),
                    as_number(episode.get("episode_decision_utility"), "", locale),
                )
            )
    return rows
