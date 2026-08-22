"""Challenge a stored decision run before a human signs it (HĐ-14).

Every other check in this codebase runs *during* a sweep and raises: an
acceptance criterion that fails means the run was not valid and must not
produce a card. This module is the opposite shape. It runs *after*, on a
report already written to disk, it never raises, and its output is a list
of objections for a reader to weigh.

The reason it exists: today nothing stands between a well-formed
``comparison_report.json`` and a reviewer's signature. Every number in
that file can be correct and the conclusion drawn from it still
unsupported — thirty runs of the same seed replayed, a confidence
interval straddling zero, a latency gate that was only ever screened on a
laptop. Those are not bugs; the pipeline is working exactly as specified.
They are reasons a conclusion does not follow from its evidence, and
noticing them is currently a job nobody has.

Three design rules, each of which the LLM layer above this one inherits:

**Every objection cites a field that exists.** ``field_path`` is a real
path into the report dict, and :func:`resolve` walks it. An objection
that cannot point at its own evidence is worse than no objection — it
reads as verified and is not. The same rule is what makes an LLM layer
checkable: it may rank and rephrase what the rules found, it may not
invent a fourteenth finding pointing at a field that is not there.

**Silence is a claim too.** Findings carry ``kind``: a ``present``
finding is a contradiction visible in the data, an ``omission`` finding
is something absent that should not be. Published work on planted-error
detection finds that automated reviewers catch contradictions well and
miss deletions badly, so the two are counted separately here rather than
summed into one number that hides the weaker half.

**Severity says what to do, not how bad it feels.** ``blocking`` means
the stated conclusion does not stand on this evidence; ``material``
means it stands only with a condition attached; ``disclosure`` means it
stands and the report must still say this out loud.

A clean run returns an empty tuple. That is a result, not a failure —
and it is the measurement that makes a false-alarm rate computable.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

__all__ = [
    "RULE_CODES",
    "Finding",
    "Kind",
    "Severity",
    "critique",
    "exists",
    "resolve",
]

Severity = Literal["blocking", "material", "disclosure"]
Kind = Literal["present", "omission"]

#: Below this, a "significant" difference rests on a handful of episodes
#: whichever way the interval falls. Cohen's conventional small-effect
#: boundary, used here only to decide whether to *say something*, never
#: to decide anything.
SMALL_EFFECT_SIZE = 0.2


class Finding(BaseModel):
    """One reason a conclusion may not follow from its evidence."""

    model_config = ConfigDict(frozen=True)

    #: Stable identifier, so a finding can be tracked across re-runs and
    #: an evaluation harness can score per-rule recall.
    code: str
    severity: Severity
    kind: Kind
    #: What the run asserts that this finding puts in doubt.
    claim: str
    #: Why, in one sentence a reviewer can check against the field.
    ground: str
    #: Dotted path into the report. Always resolvable — see `resolve`.
    field_path: str
    #: What a reader could do to settle it.
    suggested_check: str


def resolve(report: dict[str, Any], field_path: str) -> Any:
    """Walk a dotted path, ``[i]`` for list indices. None when absent.

    Findings are validated against this rather than trusted: a path that
    does not resolve is a bug in a rule, and the same call is what an LLM
    layer's citations get checked with.
    """
    found = _walk(report, field_path)
    return None if found is _MISSING else found


#: Returned by :func:`_walk` when a path runs off the data. Distinct from
#: ``None``, which is a value a field can legitimately hold.
_MISSING = object()


def _walk(report: Mapping[str, Any], field_path: str) -> Any:
    """The path walk both :func:`resolve` and :func:`exists` share.

    Tests against ``Mapping`` and ``Sequence`` rather than ``dict`` and
    ``list``. Every module in this family type-hints its source as a
    ``Mapping``, and a caller who honoured that hint with a
    ``MappingProxyType`` — the obvious way to hand out a read-only report —
    had **every** citation fail and every piece of advice deleted without
    a word. The narrowing was invisible because a dropped citation and a
    rule that chose not to fire look identical from outside.

    ``str`` and ``bytes`` are Sequences and must not be indexed as one:
    ``summary.note[0]`` would otherwise resolve to a character.
    """
    node: Any = report
    for part in field_path.split("."):
        index: int | None = None
        if part.endswith("]") and "[" in part:
            part, _, raw = part.partition("[")
            index = int(raw.rstrip("]"))
        if part:
            if not isinstance(node, Mapping) or part not in node:
                return _MISSING
            node = node[part]
        if index is not None:
            if isinstance(node, (str, bytes)) or not isinstance(node, Sequence):
                return _MISSING
            if index >= len(node):
                return _MISSING
            node = node[index]
    return node


def exists(report: Mapping[str, Any], field_path: str) -> bool:
    """Whether the path is present, **even when its value is null**.

    :func:`resolve` answers ``None`` for two different situations — a
    field that is absent, and a field that is present and holds null —
    and a caller that treats the second as the first drops exactly the
    findings that exist to point at it. "This run recorded no effect
    size" is a claim about a field that is there and empty; refusing to
    cite it would leave the reader with the impression it was never
    asked about.

    Added rather than folded into :func:`resolve` because that function's
    "None means nothing there" contract is what the existing rules in
    this module are written against, and quietly widening it would change
    what fourteen of them mean.
    """
    return _walk(report, field_path) is not _MISSING


def _gate(candidate: dict[str, Any], name: str) -> dict[str, Any] | None:
    """A gate's detail dict, or None when it is a bare verdict string.

    G1, G3 and G6 report ``"pass"``/``"fail"`` with nothing to inspect;
    G2, G4 and G5 report a dict. Callers that want a field want the dict.
    """
    gate = (candidate.get("gates") or {}).get(name)
    return gate if isinstance(gate, dict) else None


def _ranked(report: dict[str, Any]) -> bool:
    """Whether this run actually recommended somebody.

    A gate-only run eliminated everyone or could not rank; most findings
    about a recommendation are vacuous there, and reporting them would
    bury the one finding that matters.
    """
    return bool(report.get("decision_card"))


# --------------------------------------------------------------------
# Rules. Each yields zero or more findings and touches only the report.
# --------------------------------------------------------------------


def _rule_replayed_seeds(report: dict[str, Any]) -> Iterator[Finding]:
    """G2's bound assumes distinct episodes; replays inflate confidence.

    Thirty runs of six distinct conditions is not thirty observations of
    the collision rate. The rule-of-three bound reads the count, so a
    replayed set produces an interval that is arithmetically right and
    epistemically too narrow.
    """
    for i, candidate in enumerate(report.get("candidates") or []):
        g2 = _gate(candidate, "G2")
        if not g2:
            continue
        distinct = g2.get("n_distinct_episodes")
        runs = g2.get("n_runs")
        if isinstance(distinct, int) and isinstance(runs, int) and distinct < runs:
            yield Finding(
                code="G2_REPLAYED_EPISODES",
                severity="blocking",
                kind="present",
                claim=f"{candidate.get('stack_label', '?')} cleared G2 over {runs} runs",
                ground=(
                    f"only {distinct} of those {runs} runs were distinct episodes, so the "
                    "95% upper bound is computed on repeated conditions and reads tighter "
                    "than the evidence supports"
                ),
                field_path=f"candidates[{i}].gates.G2.n_distinct_episodes",
                suggested_check="re-run with distinct seeds until n_distinct_episodes == n_min",
            )


def _rule_below_n_min(report: dict[str, Any]) -> Iterator[Finding]:
    """The episode count is a consequence of declared risk, not taste."""
    sample = report.get("sample") or {}
    ran = sample.get("n_episodes")
    required = sample.get("n_min_required")
    if isinstance(ran, int) and isinstance(required, int) and ran < required:
        yield Finding(
            code="SAMPLE_BELOW_N_MIN",
            severity="blocking",
            kind="present",
            claim="the run reports a comparison over its evaluation set",
            ground=(
                f"{ran} episodes ran against the {required} the profile's accepted collision "
                "risk requires, so zero observed collisions cannot support the risk claim"
            ),
            field_path="sample.n_episodes",
            suggested_check=f"run {required - ran} more episodes, or raise the declared risk",
        )


def _rule_interrupted(report: dict[str, Any]) -> Iterator[Finding]:
    """A stopped sweep is a smaller valid comparison — if it says so."""
    if (report.get("sample") or {}).get("interrupted"):
        yield Finding(
            code="SAMPLE_INTERRUPTED",
            severity="material",
            kind="present",
            claim="the reported numbers describe the intended experiment",
            ground=(
                "the sweep was interrupted, so these are the episodes it managed rather "
                "than the episode set that was asked for"
            ),
            field_path="sample.interrupted",
            suggested_check="compare n_episodes against n_episodes_requested before quoting",
        )


def _rule_early_stopped(report: dict[str, Any]) -> Iterator[Finding]:
    """Retired candidates have fewer episodes than the survivors."""
    stopped = (report.get("early_stop") or {}).get("stopped") or []
    if stopped:
        names = ", ".join(str(s) for s in stopped[:4])
        yield Finding(
            code="EARLY_STOP_APPLIED",
            severity="disclosure",
            kind="present",
            claim="every candidate faced the same evaluation",
            ground=(
                f"{len(stopped)} candidate(s) were retired early ({names}); their numbers "
                "rest on fewer episodes and are not comparable with the survivors'"
            ),
            field_path="early_stop.stopped",
            suggested_check="check that no retired candidate is quoted alongside the survivors",
        )


def _rule_interval_straddles_zero(report: dict[str, Any]) -> Iterator[Finding]:
    """A *clear* recommendation whose own interval admits no difference.

    Deliberately silent when the card already says ``NEAR_EQUIVALENT``.
    An interval containing zero is exactly what that status is for, so
    objecting there would flag the system for being honest — the precise
    failure mode that makes a reviewer stop reading a critic. This module
    only speaks when the card claims more than its interval supports.
    """
    if not _ranked(report):
        return
    card = report.get("decision_card") or {}
    if card.get("status") != "CLEAR_RECOMMENDATION":
        return
    evidence = card.get("evidence") or {}
    ci = evidence.get("ci95")
    if isinstance(ci, (list, tuple)) and len(ci) == 2:
        low, high = ci
        if isinstance(low, (int, float)) and isinstance(high, (int, float)) and low <= 0 <= high:
            yield Finding(
                code="DELTA_U_CI_STRADDLES_ZERO",
                severity="blocking",
                kind="present",
                claim="one candidate is recommended over the next",
                ground=(
                    f"the 95% interval for ΔU is [{low:.4f}, {high:.4f}], which contains zero — "
                    "the evidence is consistent with no difference between them"
                ),
                field_path="decision_card.evidence.ci95",
                suggested_check="add episodes until the interval clears zero, or report a tie",
            )


def _rule_small_effect(report: dict[str, Any]) -> Iterator[Finding]:
    """Statistically separable and practically indistinguishable.

    Same restraint as the interval rule: a small effect under
    ``NEAR_EQUIVALENT`` is the card agreeing with itself, not a finding.
    """
    if not _ranked(report):
        return
    card = report.get("decision_card") or {}
    if card.get("status") != "CLEAR_RECOMMENDATION":
        return
    evidence = card.get("evidence") or {}
    effect = evidence.get("effect_size")
    if isinstance(effect, (int, float)) and abs(effect) < SMALL_EFFECT_SIZE:
        yield Finding(
            code="EFFECT_SIZE_SMALL",
            severity="material",
            kind="present",
            claim="the recommended candidate is better",
            ground=(
                f"the effect size is {effect:.3f}; a difference this small can be real and "
                "still not worth acting on"
            ),
            field_path="decision_card.evidence.effect_size",
            suggested_check="decide whether this margin matters for the deployment at hand",
        )


def _rule_tie_break(report: dict[str, Any]) -> Iterator[Finding]:
    """Won by a rule, not by a number."""
    if not _ranked(report):
        return
    reason = (report.get("decision_card") or {}).get("tie_break_reason")
    if reason:
        yield Finding(
            code="WON_ON_TIE_BREAK",
            severity="material",
            kind="present",
            claim="the recommendation follows from the measurements",
            ground=f"the candidates tied and the winner was chosen by rule: {reason}",
            field_path="decision_card.tie_break_reason",
            suggested_check="treat this as a tie unless the tie-break rule is itself agreed",
        )


def _rule_g4_host_only(report: dict[str, Any]) -> Iterator[Finding]:
    """Latency screened on a workstation says little about a board."""
    for i, candidate in enumerate(report.get("candidates") or []):
        g4 = _gate(candidate, "G4")
        if g4 and g4.get("status") == "screened_on_host":
            yield Finding(
                code="G4_HOST_ONLY",
                severity="disclosure",
                kind="present",
                claim=f"{candidate.get('stack_label', '?')} meets its control-period budget",
                ground=(
                    f"G4 passed at {g4.get('p99_ms', float('nan')):.1f} ms against a "
                    f"{g4.get('threshold_ms', float('nan')):.0f} ms budget, but only on the "
                    "benchmark host — the target board was never measured"
                ),
                field_path=f"candidates[{i}].gates.G4.status",
                suggested_check="re-measure p99 on the target device before deploying",
            )


def _rule_g5_declared(report: dict[str, Any]) -> Iterator[Finding]:
    """A memory figure nobody measured."""
    for i, candidate in enumerate(report.get("candidates") or []):
        g5 = _gate(candidate, "G5")
        if g5 and g5.get("status") == "declared_by_author":
            yield Finding(
                code="G5_DECLARED_NOT_MEASURED",
                severity="material",
                kind="present",
                claim=f"{candidate.get('stack_label', '?')} fits the memory budget",
                ground="the memory figure was declared by the author, not measured or estimated",
                field_path=f"candidates[{i}].gates.G5.status",
                suggested_check="estimate from data structures or measure peak RSS on target",
            )


def _rule_unpinned_host(report: dict[str, Any]) -> Iterator[Finding]:
    """Latency read off an unpinned host is not the same measurement."""
    warning = (report.get("measurement_environment") or {}).get("warning")
    if warning:
        yield Finding(
            code="HOST_NOT_PINNED",
            severity="material",
            kind="present",
            claim="the latency figures describe the stacks",
            ground=f"the measurement environment reported: {str(warning)[:160]}",
            field_path="measurement_environment.warning",
            suggested_check="pin cores and re-measure before comparing latency between stacks",
        )


def _rule_no_sensor_noise(report: dict[str, Any]) -> Iterator[Finding]:
    """Zero noise makes every seed the same experiment.

    An omission finding: nothing in the report is wrong, and that is the
    problem — the variance a reader will read as run-to-run spread has
    no sensor component in it at all.
    """
    noise = (report.get("identity") or {}).get("sensor_noise")
    if (
        isinstance(noise, dict)
        and noise
        and not any(isinstance(v, (int, float)) and v > 0 for v in noise.values())
    ):
        yield Finding(
            code="SENSOR_NOISE_ZERO",
            severity="material",
            kind="omission",
            claim="the spread across seeds reflects real run-to-run variation",
            ground=(
                "every sensor-noise term is zero, so seeds differ only in traffic timing and "
                "the reported variance omits perception entirely"
            ),
            field_path="identity.sensor_noise",
            suggested_check="declare the deployment's real noise and re-run before quoting spread",
        )


def _rule_missing_provenance(report: dict[str, Any]) -> Iterator[Finding]:
    """Without a commit, the run cannot be rebuilt — an omission."""
    if not (report.get("identity") or {}).get("git_sha"):
        yield Finding(
            code="PROVENANCE_MISSING_GIT_SHA",
            severity="material",
            kind="omission",
            claim="this result is reproducible",
            ground="no git sha was recorded, so the code that produced it cannot be identified",
            field_path="identity.git_sha",
            suggested_check="re-run from a committed tree",
        )


def _rule_no_card_reason(report: dict[str, Any]) -> Iterator[Finding]:
    """A gate-only run ranks nobody; say so before anyone reads a winner."""
    if _ranked(report):
        return
    reason = report.get("why_no_card")
    yield Finding(
        code="NO_RECOMMENDATION",
        severity="disclosure",
        kind="present",
        claim="this run answers which candidate to choose",
        ground=(
            f"no decision card was issued: {reason}"
            if reason
            else "no decision card was issued, so the run eliminated rather than ranked"
        ),
        field_path="why_no_card" if reason else "decision_card",
        suggested_check="read the gate table for who was eliminated where, not for a winner",
    )


def _rule_blocked_candidate_quoted(report: dict[str, Any]) -> Iterator[Finding]:
    """Candidates that failed a gate are not scored, ranked or compared."""
    for i, candidate in enumerate(report.get("candidates") or []):
        if candidate.get("cleared_gates") is False and candidate.get("success_rate") is not None:
            blocking = ", ".join(str(g) for g in (candidate.get("blocking_gates") or []))
            yield Finding(
                code="BLOCKED_CANDIDATE_HAS_SCORES",
                severity="disclosure",
                kind="present",
                claim=f"{candidate.get('stack_label', '?')} can be compared with the others",
                ground=(
                    f"it failed {blocking or 'a gate'}, so its success rate is reported but is "
                    "not a ranking position — a gate is a condition of entry, not a score"
                ),
                field_path=f"candidates[{i}].blocking_gates",
                suggested_check="quote this candidate only as eliminated, never as runner-up",
            )


def _rule_single_candidate(report: dict[str, Any]) -> Iterator[Finding]:
    """One candidate is a measurement, not a comparison."""
    candidates = report.get("candidates") or []
    if len(candidates) == 1:
        yield Finding(
            code="SINGLE_CANDIDATE",
            severity="disclosure",
            kind="omission",
            claim="this run compares candidates",
            ground="only one candidate ran, so there is nothing to compare it against",
            field_path="candidates",
            suggested_check="read this as a measurement report, not a selection",
        )


#: Order matters only for reading: blocking findings sort first anyway,
#: but within a severity the sequence below is the order a reviewer would
#: naturally work through — sample, then statistics, then gates, then
#: provenance.
_RULES = (
    _rule_below_n_min,
    _rule_replayed_seeds,
    _rule_interrupted,
    _rule_early_stopped,
    _rule_interval_straddles_zero,
    _rule_small_effect,
    _rule_tie_break,
    _rule_g4_host_only,
    _rule_g5_declared,
    _rule_unpinned_host,
    _rule_no_sensor_noise,
    _rule_missing_provenance,
    _rule_no_card_reason,
    _rule_blocked_candidate_quoted,
    _rule_single_candidate,
)

_SEVERITY_ORDER: dict[str, int] = {"blocking": 0, "material": 1, "disclosure": 2}

#: Every code a rule can emit. Published beside the findings so an
#: empty result reads as "the rules ran and found nothing" rather than
#: "no rules ran", and so an evaluation harness knows the full label
#: space without importing the rule functions.
RULE_CODES: tuple[str, ...] = (
    "BLOCKED_CANDIDATE_HAS_SCORES",
    "DELTA_U_CI_STRADDLES_ZERO",
    "EARLY_STOP_APPLIED",
    "EFFECT_SIZE_SMALL",
    "G2_REPLAYED_EPISODES",
    "G4_HOST_ONLY",
    "G5_DECLARED_NOT_MEASURED",
    "HOST_NOT_PINNED",
    "NO_RECOMMENDATION",
    "PROVENANCE_MISSING_GIT_SHA",
    "SAMPLE_BELOW_N_MIN",
    "SAMPLE_INTERRUPTED",
    "SENSOR_NOISE_ZERO",
    "SINGLE_CANDIDATE",
    "WON_ON_TIE_BREAK",
)


def critique(report: dict[str, Any]) -> tuple[Finding, ...]:
    """Every objection the rules can raise against ``report``.

    Never raises. A report from an older schema simply produces fewer
    findings, because each rule reads only the fields it needs and skips
    when they are absent — a missing field is not evidence of a problem,
    and inventing a finding out of one would put noise where a reviewer
    is looking for signal.

    Findings come back sorted by severity so the first thing read is the
    thing that decides whether to read on.
    """
    findings: list[Finding] = []
    for rule in _RULES:
        findings.extend(rule(report))
    # Guard against a rule pointing at a field that is not there. This is
    # the same invariant the LLM layer is held to, applied to ourselves
    # first; a rule that cannot cite its evidence is dropped rather than
    # shown, because an uncheckable objection is the failure mode this
    # whole module exists to prevent.
    findings = [f for f in findings if resolve(report, f.field_path) is not None]
    findings.sort(key=lambda f: (_SEVERITY_ORDER[f.severity], f.code))
    return tuple(findings)
