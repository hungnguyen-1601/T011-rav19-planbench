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

from dataclasses import dataclass
from typing import Any, NamedTuple

from planbench_api.decision_text import DEFAULT_LOCALE, Locale, text
from planbench_api.decision_text import lines as text_lines

__all__ = [
    "COUNT",
    "MEGABYTES",
    "METRES",
    "MILLISECONDS",
    "PERCENT",
    "SECONDS",
    "UTILITY",
    "Caveat",
    "Locale",
    "NOT_MEASURED",
    "NOT_RECORDED",
    "Quantity",
    "Unit",
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
#:
#: Keys rather than words, resolved by :func:`gate_columns`: a header is
#: one of the things a language changes, and a module-level tuple of
#: strings would have been frozen at import in whichever language
#: happened to be the default.
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


# --- Quantities a spreadsheet can actually use -----------------------------
#
# **Why the older cells are strings and these are not.** `as_number` uses
# `%.3g` — three significant digits, so the number of decimal places moves
# with the magnitude. Excel's `number_format` has no notion of significant
# digits, so there is no format string that reproduces `.3g`; a cell
# written as a float and formatted to a fixed width would print a
# different string from the Markdown, and the whole point of this module
# is that the two documents never quote one measurement two ways.
#
# The sheets built on `Quantity` take the other trade instead. They use
# the *fixed* decimal counts the comparison grid on screen already uses,
# which do translate to Excel exactly, and they store the raw float. So:
#
# - the older sheets agree with the Markdown, character for character;
# - the newer sheets agree with the screen, and can be sorted, summed and
#   charted, which a column of strings cannot;
# - and where the two disagree about how many digits to show, the newer
#   one carries the full value in the cell, so the question is answerable
#   by clicking it.


@dataclass(frozen=True)
class Unit:
    """How one kind of quantity is written, in both places it is written.

    ``excel_format`` and ``decimals`` are the same decision expressed
    twice — once for Excel and once for the assertion that proves Excel
    was told the right thing — so they live in one object rather than in
    two tables that could drift.
    """

    #: What follows the digits on screen. Empty for a bare count.
    symbol: str
    #: How a *difference* in this quantity reads. Not always ``symbol``:
    #: the gap between two percentages is percentage points, and calling
    #: it ``%`` would say the gap was a proportion of a proportion.
    delta_symbol: str
    decimals: int
    excel_format: str
    #: What the stored value is multiplied by to reach the displayed
    #: digits. Only ratios use it, and only because they are stored as
    #: 0.942 and read as 94.2 — Excel's ``%`` format does the same
    #: multiplication, which is why the raw ratio is what goes in the cell.
    display_scale: float = 1.0

    def digits(self, value: float) -> str:
        """The digits alone, as the screen writes them."""
        return f"{value * self.display_scale:.{self.decimals}f}"

    def as_delta(self) -> Unit:
        """The same quantity, as a *difference* between two of them.

        Only ratios differ. A rate is stored as 0.70 and read as 70.0 %,
        so the gap between two of them has to print as 2.0 **pp** — and
        Excel's ``%`` format would print `2.0%`, which says the gap is a
        proportion of a proportion. The difference is therefore stored
        already scaled, under a plain numeric format, and the column
        beside it names the unit.
        """
        if self.display_scale == 1.0:
            return self
        places = f"0.{'0' * self.decimals}" if self.decimals else "0"
        return Unit(
            symbol=self.delta_symbol,
            delta_symbol=self.delta_symbol,
            decimals=self.decimals,
            excel_format=places,
        )


PERCENT = Unit(symbol="%", delta_symbol="pp", decimals=1, excel_format="0.0%", display_scale=100.0)
MILLISECONDS = Unit(symbol="ms", delta_symbol="ms", decimals=2, excel_format='0.00" ms"')
SECONDS = Unit(symbol="s", delta_symbol="s", decimals=1, excel_format='0.0" s"')
METRES = Unit(symbol="m", delta_symbol="m", decimals=3, excel_format='0.000" m"')
MEGABYTES = Unit(symbol="MB", delta_symbol="MB", decimals=1, excel_format='0.0" MB"')
COUNT = Unit(symbol="", delta_symbol="", decimals=0, excel_format="0")
#: Four places rather than three: the objective sheet adds `weight × U`
#: down a column and asserts the total equals the card's own utility, and
#: at three places the rounding shows up in the sixth decimal of the sum.
UTILITY = Unit(symbol="", delta_symbol="", decimals=4, excel_format="0.0000")


@dataclass(frozen=True)
class Quantity:
    """One measured value, or the absence of one, with its unit.

    ``value is None`` means the run did not record it, and it must reach
    the sheet as an **empty cell** — never 0, which sums and sorts as a
    measurement, and never the words "not measured", which would make
    the column text and take sorting away from every other row in it.
    Whoever writes the row says "not measured" in a neighbouring cell
    that is already text.
    """

    value: float | None
    unit: Unit

    @property
    def missing(self) -> bool:
        return self.value is None

    def digits(self) -> str | None:
        return None if self.value is None else self.unit.digits(self.value)

    def display(self, locale: Locale = DEFAULT_LOCALE) -> str:
        """The value as a reader sees it, for tests and for text cells.

        Not called ``text``: that is the name of the translation
        function this module imports, and a method shadowing it inside
        the class would work right up until somebody needed both.
        """
        if self.value is None:
            return text("value.not_measured", locale)
        digits = self.unit.digits(self.value)
        return f"{digits} {self.unit.symbol}" if self.unit.symbol else digits


def quantity(value: Any, unit: Unit) -> Quantity:
    """A reading, coerced once so every caller does not have to.

    Anything that is not a real number becomes "not recorded" rather
    than raising: these come out of stored JSON, and an artifact written
    by an older version having a string where a float belongs is a
    reason to leave the cell empty, not to fail the export.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return Quantity(None, unit)
    return Quantity(float(value), unit)


# --- The one sheet somebody reads if they read nothing else ----------------


def summary_rows(
    run: Any, report: dict[str, Any], locale: Locale = DEFAULT_LOCALE
) -> list[tuple[str, str | Quantity]]:
    """What was run, on what, and what came out — in one place.

    **Built from the other row builders, not from the report.** Every
    value here already exists on some sheet; reaching into the report a
    second time to fetch it would be a second reading of the same field,
    free to disagree with the first the day one of them changes.

    A run with no card still gets a summary. It answers the same
    question — what came out of this? — and the answer "nobody was
    ranked, here is why" is one a reader needs at the top rather than
    four sheets in.
    """
    card = run.card or report.get("decision_card")
    identity = report.get("identity") or {}
    candidates = report.get("candidates") or []
    manifest = getattr(run, "manifest", None) or report.get("manifest") or {}

    rows: list[tuple[str, str | Quantity]] = [
        (
            text("label.run_at", locale),
            as_text(identity.get("created_at") or run.created_at, locale),
        ),
        (text("label.deployment", locale), as_text(run.task_profile_id, locale)),
        (
            text("label.experiment_scope", locale),
            as_text(identity.get("experiment_scope") or run.experiment_scope, locale),
        ),
        (
            text("label.anchor_config", locale),
            as_text(identity.get("anchor_config_version"), locale),
        ),
        (text("label.contracts_version", locale), as_text(run.contracts_version, locale)),
        (text("label.code_version", locale), as_text(identity.get("git_sha"), locale)),
    ]
    if manifest.get("preference_profile"):
        rows.append(
            (
                text("label.preference_profile", locale),
                as_text(manifest.get("preference_profile"), locale),
            )
        )

    # The candidates by name, because "Algorithm A" makes a reader who
    # opened the file a week later go and look up which one A was.
    for index, candidate in enumerate(candidates, start=1):
        rows.append(
            (
                text("label.candidate_n", locale, index=index),
                text(
                    "value.candidate_stack",
                    locale,
                    stack=as_text(candidate.get("stack_label"), locale),
                    config=as_text(candidate.get("local_controller_config"), locale),
                ),
            )
        )

    if not card:
        rows.append(
            (
                text("label.final_recommendation", locale),
                text("prose.final_recommendation_none", locale),
            )
        )
        reason = no_card_reason(report, locale)
        if reason:
            rows.append((text("heading.reason", locale), reason))
        return rows

    evidence = card.get("evidence") or {}
    interval = evidence.get("ci95")
    low, high = (
        (interval[0], interval[1])
        if isinstance(interval, (list, tuple)) and len(interval) == 2
        else (None, None)
    )
    recommended = card.get("recommended") or {}
    rows += [
        (
            text("label.episodes_compared", locale),
            quantity(evidence.get("n_episodes"), COUNT),
        ),
        (text("label.winner", locale), as_text(recommended.get("stack"), locale)),
        (
            text("label.overall_score", locale),
            quantity(card.get("decision_utility"), UTILITY),
        ),
        (text("label.delta_u_mean", locale), quantity(evidence.get("delta_u_mean"), UTILITY)),
        # The interval as two cells rather than the string "[a, b]": a
        # reader filtering for margins that clear zero needs the bound
        # to be a number, and that is exactly the reading the interval
        # exists to support.
        (text("label.confidence_low", locale), quantity(low, UTILITY)),
        (text("label.confidence_high", locale), quantity(high, UTILITY)),
        (text("label.effect_size", locale), quantity(evidence.get("effect_size"), UTILITY)),
        (text("label.decision_mode", locale), as_text(card.get("decision_mode"), locale)),
        (text("label.pareto_label", locale), as_text(card.get("pareto_label"), locale)),
        (
            text("label.final_recommendation", locale),
            text(
                "prose.final_recommendation",
                locale,
                stack=as_text(recommended.get("stack"), locale),
                config=recommended_config(report, recommended.get("candidate_id"), locale),
                scope=scope_of(run, report, locale),
            ),
        ),
    ]
    return rows


# --- The comparison, one row per metric ------------------------------------
#
# **The same ten rows the screen shows, in the same order.** The grid in
# `apps/web/src/lib/candidateMetrics.ts` already decides which metrics a
# reader compares stacks on, which way is better, what unit each is in,
# and how close counts as level. A second opinion here would mean the
# person looking at the page and the person opening the file are reading
# two different comparisons of one run — and neither would know.
#
# The table is declared here and a test reads the TypeScript to prove the
# two still agree, which is the cheap half of unifying them. The
# expensive half — the report carrying this table so the page reads it
# back — is worth doing later and is not worth blocking this on.

#: Differences below this share of the row's scale are not called. The
#: screen's value, not a new one: a row where the two are level should
#: not name a winner on the page and a different one in the file.
TIE_TOLERANCE = 1e-3


def _gate_field(candidate: dict[str, Any], gate: str, field: str) -> Any:
    """A number the gate already produced, read rather than recomputed.

    G1 carries the no-path rate, G2 the collision count and the 95%
    bound, G5 the memory estimate. Deriving any of them again here would
    be a second definition free to disagree with the verdict printed two
    sheets away — and the disagreement would be invisible, because both
    would render as the same quantity.
    """
    verdict = (candidate.get("gates") or {}).get(gate)
    return verdict.get(field) if isinstance(verdict, dict) else None


@dataclass(frozen=True)
class MetricSpec:
    """One row of the comparison: what to read, and how to read it."""

    #: The key the grid uses, so the parity test can line the two up.
    key: str
    unit: Unit
    #: ``"higher"``, ``"lower"``, or ``"none"`` for a row that is
    #: evidence rather than a score and therefore has no winner.
    direction: str
    #: How to get the value off one candidate.
    read: Any
    #: How to get the deployment's declared limit, if the gate set one.
    #: Read off the first candidate: the limit belongs to the deployment,
    #: not to the stack being measured against it.
    limit: Any = None
    #: Which weight this metric carries in the utility, given the run's
    #: resolved preference weights — or ``None`` for the seven rows that
    #: carry none. See the note on each for why.
    weigh: Any = None

    @property
    def label_key(self) -> str:
        return f"metric.{self.key}"

    @property
    def note_key(self) -> str:
        return f"note.{self.key}"


COMPARISON_METRICS: tuple[MetricSpec, ...] = (
    MetricSpec(
        key="successRate",
        unit=PERCENT,
        direction="higher",
        read=lambda c: c.get("success_rate"),
        limit=lambda c: _gate_field(c, "G3", "threshold"),
        weigh=lambda w: w.w_r,
    ),
    MetricSpec(
        key="collisions",
        unit=COUNT,
        direction="lower",
        read=lambda c: _gate_field(c, "G2", "observed"),
        # G2 demands exactly zero; the limit is the contract, not a
        # number somebody tuned.
        limit=lambda c: 0 if (c.get("gates") or {}).get("G2") else None,
    ),
    MetricSpec(
        key="collisionBound",
        unit=PERCENT,
        direction="lower",
        read=lambda c: _gate_field(c, "G2", "upper_bound_95"),
    ),
    MetricSpec(
        key="noPathRate",
        unit=PERCENT,
        direction="lower",
        read=lambda c: _gate_field(c, "G1", "no_path_rate"),
        limit=lambda c: _gate_field(c, "G1", "threshold"),
    ),
    MetricSpec(
        key="worstClearance",
        unit=METRES,
        direction="higher",
        read=lambda c: c.get("worst_clearance_m"),
    ),
    MetricSpec(
        key="medianTravel",
        unit=SECONDS,
        direction="lower",
        read=lambda c: c.get("median_travel_time_s"),
    ),
    MetricSpec(
        key="p99",
        unit=MILLISECONDS,
        direction="lower",
        read=lambda c: c.get("pooled_p99_latency_ms"),
        limit=lambda c: _gate_field(c, "G4", "threshold_ms"),
        weigh=lambda w: None if w.beta is None else w.w_c * w.beta[0],
    ),
    MetricSpec(
        key="memory",
        unit=MEGABYTES,
        direction="lower",
        read=lambda c: _gate_field(c, "G5", "memory_estimate_mb"),
        limit=lambda c: _gate_field(c, "G5", "available_ram_mb"),
        weigh=lambda w: None if w.beta is None else w.w_c * w.beta[1],
    ),
    MetricSpec(
        key="distinctEpisodes",
        unit=COUNT,
        direction="higher",
        read=lambda c: c.get("n_distinct_episodes"),
    ),
    MetricSpec(
        key="replans",
        # **No direction.** Replanning is already charged in travel time
        # and in latency, and the deployment declares no replan budget;
        # marking a winner here would price it twice and invent a rule
        # nobody wrote down. Shown because it is evidence about behaviour.
        unit=COUNT,
        direction="none",
        read=lambda c: c.get("replan_count"),
    ),
)


def leaders(values: list[Quantity], direction: str) -> list[int]:
    """Which candidates lead a row, as indices into ``values``.

    A *set*, not a winner: with three candidates two can be equally
    best, and picking one of them would be a coin toss rendered as a
    result.

    Empty when the row has no direction, when fewer than two candidates
    recorded it, and when every one of them ties — a row where nobody is
    ahead should not paint somebody green.
    """
    if direction == "none":
        return []
    known = [(index, q.value) for index, q in enumerate(values) if q.value is not None]
    if len(known) < 2:
        return []
    best = (max if direction == "higher" else min)(known, key=lambda entry: entry[1])[1]
    scale = max([abs(value) for _, value in known] + [1.0])
    ahead = [index for index, value in known if abs(value - best) <= TIE_TOLERANCE * scale]
    return [] if len(ahead) == len(known) else ahead


#: Weights print to three places. Distinct from `UTILITY` because a
#: weight is a declared preference and a utility is a measurement, and
#: showing 0.3000 for "thirty per cent" claims a precision nobody set.
WEIGHT = Unit(symbol="", delta_symbol="", decimals=3, excel_format="0.000")


@dataclass(frozen=True)
class ResolvedWeights:
    """The preference weights this run's card was actually scored under.

    **Read off the run's own manifest, never defaulted.** A card computed
    under ``benh_vien_gio_cao_diem`` (w_S = 0.50) exported with
    ``kho_ban_dem``'s numbers (w_S = 0.10) would print contributions that
    are all wrong and a total that still looks plausible, which is the
    worst shape a mistake can take.
    """

    profile: str | None
    w_r: float | None = None
    w_s: float | None = None
    w_e: float | None = None
    w_c: float | None = None
    beta: tuple[float, float, float, float] | None = None
    #: Which of the ways there are none this is, so the sheet can say the
    #: right one. ``None`` when the weights are known, or when the run
    #: names no profile at all and there is nothing to explain.
    reason: str | None = None

    @property
    def known(self) -> bool:
        return self.w_r is not None


def resolve_weights(run: Any, report: dict[str, Any]) -> ResolvedWeights:
    """The run's weights, or an honest absence.

    Three ways there are none, and each says something different:

    - no manifest at all — the run produced no card, so nothing was
      weighted and there is nothing to print;
    - a *perturbed* profile — the HĐ-11.5 stability sweep replaces the
      weights and does not record the replacements, so the numbers exist
      and this file cannot know them. Guessing the named profile's would
      attribute the card to weights it was not scored under;
    - a profile name the table no longer has — a profile removed after
      the run was filed. Naming it and printing nothing is the whole
      answer.

    A fourth is not about the run at all: the API can be deployed
    without ``planbench_decision`` beside it, and then no run's weights
    are resolvable. Kept apart from "unknown profile" because the two
    ask different people to do different things — one is a data
    question and one is a deployment one — and a sheet that said the
    profile was unknown when the table simply had not loaded would send
    the reader looking in the wrong place.
    """
    manifest = getattr(run, "manifest", None) or report.get("manifest") or {}
    label = manifest.get("preference_profile")
    if not label:
        return ResolvedWeights(profile=None)
    if label.endswith("(perturbed)"):
        return ResolvedWeights(profile=label, reason="perturbed")
    try:
        from planbench_decision.objectives import PREFERENCE_PROFILES
    except ImportError:  # pragma: no cover - the API can run without the sibling package
        return ResolvedWeights(profile=label, reason="table_unavailable")
    weights = PREFERENCE_PROFILES.get(label)
    if weights is None:
        return ResolvedWeights(profile=label, reason="unknown_profile")
    return ResolvedWeights(
        profile=label,
        w_r=weights.w_r,
        w_s=weights.w_s,
        w_e=weights.w_e,
        w_c=weights.w_c,
        beta=tuple(weights.beta),
    )


@dataclass(frozen=True)
class ComparisonRow:
    """One metric across every candidate, with everything a cell needs."""

    label: str
    unit: str
    values: list[Quantity]
    delta: Quantity | None
    delta_unit: str
    winner: str
    #: Indices into ``values``. Empty is not "everybody lost" — see
    #: :func:`leaders`.
    ahead: list[int]
    #: Indices whose value falls the wrong side of the declared limit.
    breaches: list[int]
    limit: Quantity | None
    weight: Quantity | None
    note: str


def _winner_text(
    spec: MetricSpec, values: list[Quantity], ahead: list[int], labels: list[str], locale: Locale
) -> str:
    """Who leads, or why nobody does — three different absences.

    "No direction", "tie" and "not measured" all render as no green
    cell, and collapsing them into one word would tell a reader that a
    row nobody measured is a row where the two were level.
    """
    if spec.direction == "none":
        return text("value.no_direction", locale)
    if len([q for q in values if q.value is not None]) < 2:
        return text("value.not_measured", locale)
    if not ahead:
        return text("value.tie", locale)
    return ", ".join(labels[index] for index in ahead)


def _breaches(spec: MetricSpec, values: list[Quantity], limit: Quantity | None) -> list[int]:
    """Which candidates fall the wrong side of the deployment's own bar.

    Not "worse than the other candidate" — worse than the number the
    customer declared. The two are different findings and only this one
    is absolute.
    """
    if limit is None or limit.value is None or spec.direction == "none":
        return []
    return [
        index
        for index, q in enumerate(values)
        if q.value is not None
        and (q.value < limit.value if spec.direction == "higher" else q.value > limit.value)
    ]


def comparison_rows(
    report: dict[str, Any], locale: Locale = DEFAULT_LOCALE, weights: ResolvedWeights | None = None
) -> list[ComparisonRow]:
    """The end-of-run comparison, one row per metric.

    Transposed from the per-candidate table on purpose: a spreadsheet
    reader compares *down* a column, and a metric per row is what lets
    them put the delta, the winner and the deployment's limit beside the
    two figures being compared.
    """
    candidates = list(report.get("candidates") or [])
    if not candidates:
        return []
    labels = [as_text(entry.get("stack_label"), locale) for entry in candidates]
    weights = weights or ResolvedWeights(profile=None)

    rows: list[ComparisonRow] = []
    for spec in COMPARISON_METRICS:
        values = [quantity(spec.read(entry), spec.unit) for entry in candidates]
        limit = quantity(spec.limit(candidates[0]), spec.unit) if spec.limit else None
        if limit is not None and limit.missing:
            limit = None
        ahead = leaders(values, spec.direction)
        # A delta only where there are exactly two candidates and both
        # recorded it: "B minus A" has no meaning across three, and one
        # side missing is not a difference of zero.
        delta = None
        if len(values) == 2 and not any(q.missing for q in values):
            gap = (values[1].value - values[0].value) * spec.unit.display_scale  # type: ignore[operator]
            delta = Quantity(gap, spec.unit.as_delta())
        weight = None
        if spec.weigh is not None and weights.known:
            weight = quantity(spec.weigh(weights), WEIGHT)
        rows.append(
            ComparisonRow(
                label=text(spec.label_key, locale),
                unit=spec.unit.symbol,
                values=values,
                delta=delta,
                delta_unit=spec.unit.delta_symbol,
                winner=_winner_text(spec, values, ahead, labels, locale),
                ahead=ahead,
                breaches=_breaches(spec, values, limit),
                limit=limit,
                weight=weight,
                note=text(spec.note_key, locale),
            )
        )
    return rows


# --- Where the decision was actually made ----------------------------------


@dataclass(frozen=True)
class ObjectiveRow:
    """One weighted axis, or the total the axes add up to."""

    label: str
    weight: Quantity | None
    values: list[Quantity]
    delta: Quantity | None
    #: ``weight × U`` per candidate. The column exists so a reader can
    #: sum it and land on the card's own utility — the check a column of
    #: strings never allowed.
    contributions: list[Quantity]
    note: str | None = None
    #: The total row, which is a sum rather than a measurement and is
    #: styled as one.
    total: bool = False


#: The four axes, and which key each reads off the candidate's
#: ``objectives`` block.
_OBJECTIVE_AXES: tuple[tuple[str, str, str], ...] = (
    ("U_R", "w_r", "label.objective"),
    ("U_S", "w_s", "label.objective"),
    ("U_E", "w_e", "label.objective"),
    ("U_C", "w_c", "label.objective"),
)

#: What U_C is made of, and in what proportion (HĐ-9.1). Only the first
#: two have an input anywhere in the report; the other two are weighted
#: and unmeasured, which is a finding rather than a blank.
_COST_COMPONENTS: tuple[tuple[str, int, bool], ...] = (
    ("metric.p99", 0, True),
    ("metric.memory", 1, True),
    ("objective.cpu_time", 2, False),
    ("objective.engineering_cost", 3, False),
)


def objective_rows(
    run: Any,
    report: dict[str, Any],
    locale: Locale = DEFAULT_LOCALE,
    weights: ResolvedWeights | None = None,
) -> list[ObjectiveRow] | None:
    """The four objectives, their weights, and the total they make.

    ``None`` when the run produced no card: nothing was weighted, so a
    sheet of empty weights would be a page about an arithmetic that did
    not happen.

    **This is the only place the weight column means anything in full.**
    Weights attach to objectives, not to the metrics a reader compares
    on — three of the ten comparison rows carry one and seven do not,
    and that is the contract rather than an omission.
    """
    card = run.card or report.get("decision_card")
    if not card:
        return None
    candidates = list(report.get("candidates") or [])
    if not candidates:
        return None
    weights = weights if weights is not None else resolve_weights(run, report)

    def gap(values: list[Quantity]) -> Quantity | None:
        if len(values) != 2 or any(q.missing for q in values):
            return None
        return Quantity(values[1].value - values[0].value, UTILITY)  # type: ignore[operator]

    rows: list[ObjectiveRow] = []
    for name, attribute, label_key in _OBJECTIVE_AXES:
        weight = getattr(weights, attribute)
        values = [
            quantity((entry.get("objectives") or {}).get(name), UTILITY) for entry in candidates
        ]
        contributions = [
            Quantity(None if q.missing or weight is None else q.value * weight, UTILITY)
            for q in values
        ]
        rows.append(
            ObjectiveRow(
                label=text(label_key, locale, name=name),
                weight=None if weight is None else Quantity(weight, WEIGHT),
                values=values,
                delta=gap(values),
                contributions=contributions,
            )
        )

    # The four pieces U_C is built from. Their weights are real and two
    # of their inputs are not in the report at all — said in a note
    # rather than left as an empty row somebody reads as zero.
    for label_key, index, measured in _COST_COMPONENTS:
        share = None
        if weights.known and weights.beta is not None:
            share = Quantity(weights.w_c * weights.beta[index], WEIGHT)  # type: ignore[operator]
        rows.append(
            ObjectiveRow(
                label=f"  ↳ {text(label_key, locale)}",
                weight=share,
                values=[Quantity(None, UTILITY) for _ in candidates],
                delta=None,
                contributions=[Quantity(None, UTILITY) for _ in candidates],
                note=text(
                    "note.component_measured" if measured else "note.component_unmeasured",
                    locale,
                ),
            )
        )

    totals = [quantity(entry.get("decision_utility"), UTILITY) for entry in candidates]
    rows.append(
        ObjectiveRow(
            label=text("label.decision_utility", locale),
            weight=Quantity(1.0, WEIGHT) if weights.known else None,
            values=totals,
            delta=gap(totals),
            contributions=totals,
            note=text("note.total_is_the_sum", locale),
            total=True,
        )
    )
    return rows


def eligibility_row(
    report: dict[str, Any], locale: Locale = DEFAULT_LOCALE
) -> tuple[str, list[str]] | None:
    """Whether each candidate was even allowed to be recommended.

    **Stated rather than left to be read off the gate column.** A gate
    failure can leave no mark on the utility at all — collisions are
    excluded from U_S by contract (HĐ-6) so that they cannot be traded
    against speed — so a reader comparing two utilities across that line
    is comparing "scored lower" with "was never in the running", which
    are different claims.

    Text rather than a number, and therefore not part of the numeric
    table it sits above: yes/no is a verdict, and a 1 or a 0 in a column
    of utilities would be summed with them.
    """
    candidates = report.get("candidates") or []
    if not candidates:
        return None
    return (
        text("column.outcome.eligible", locale),
        [
            text("value.yes" if entry.get("recommendation_eligible") else "value.no", locale)
            for entry in candidates
        ],
    )
