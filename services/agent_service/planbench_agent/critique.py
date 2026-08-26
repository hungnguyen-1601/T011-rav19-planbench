"""A model that argues with a decision run, on a short leash.

The rules in :mod:`planbench_decision.self_check` find what is
mechanically checkable: a sample under its minimum, an interval that
contains zero, a gate screened on the wrong machine. They cannot read a
run and notice that the baseline was a straw man, that the profile does
not describe the deployment somebody had in mind, or that a metric being
quoted does not measure the thing being claimed. That is judgement, and
it is the one job here worth handing to a model.

The published evidence sets the shape of this module. Intrinsic
self-correction — a model reviewing its own reasoning with no external
signal — does not work and often makes answers worse; a critic *grounded
in outside evidence* measurably does. So the model here never sees a
blank page. It receives the report and the rules' findings, and its
output is checked against the report the same way a citation is.

Four constraints, each of which exists because removing it produces
something that reads authoritative and is not:

**Rules first, always.** Rule findings are returned whether the model
runs, refuses or fails. The model may reorder and explain them; it can
never suppress one. A critic that can be talked out of an objection is
not a critic.

**Every model finding cites a field that resolves.** The same
`resolve()` the rules are held to. A finding pointing at a field that is
not in the report is dropped and counted, not shown — and the count is
published, because "the model fabricated two" is a measurement worth
having.

**Model findings are labelled as such.** ``source`` separates rule from
model on every finding, so an evaluation can score them apart and a
reader can tell which half is deterministic.

**No conclusion is stated in banned language.** The decision layer bans
"safe" and "TCO" beside a number; the same function is applied here
rather than a second copy of the rule.

Refusing is a valid outcome. A model with nothing to add says so, and
that is a better answer than an invented fourteenth objection.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from planbench_agent.provider import LLMMessage, LLMProvider, LLMRequest
from planbench_decision.gates import BannedLanguageError, assert_no_banned_language
from planbench_decision.self_check import RULE_CODES, Finding, resolve
from planbench_decision.self_check import critique as rule_critique

__all__ = [
    "CRITIQUE_MAX_TOKENS",
    "CRITIQUE_SYSTEM",
    "CritiqueResult",
    "ScoredFinding",
    "critique_schema",
    "critique_with_model",
]

#: Ceiling on what the model may add. Not a quality bar — a stop on the
#: failure mode where a critic pads a clean run with speculation until
#: something sounds serious. Three is enough for a genuine reading and
#: few enough that each one has to earn its place.
MAX_MODEL_FINDINGS = 3

#: Headroom for the completion. The default 8192 is generous for a
#: three-finding answer and much too tight once a reasoning model
#: spends part of the budget thinking: Gemini 3 stopped at 317 output
#: tokens mid-sentence and the whole answer was discarded as malformed.
#: Truncation is indistinguishable from a bad model at the call site,
#: so the budget is set where the answer fits with room to spare.
CRITIQUE_MAX_TOKENS = 32768

#: How much of the report the model is shown. The whole thing includes
#: per-episode tables that add length without adding judgement, and a
#: longer prompt measurably degrades structured output.
_SUMMARY_KEYS = (
    "identity",
    "sample",
    "early_stop",
    "measurement_environment",
    "decision_card",
    "why_no_card",
    "gate_only_deployment",
)

CRITIQUE_SYSTEM = """You are reviewing a robot-navigation benchmark for a \
human who is about to sign off on it. Your job is to find reasons the \
stated conclusion might not follow from the evidence. You are not \
summarising and you are not praising.

A deterministic rule set has already run and its findings are given to \
you. Do not repeat them. Look for what rules cannot see:

- a baseline that was never a real contender, so beating it means little
- a deployment profile that does not match the deployment being claimed
- a metric quoted in support of a claim it does not measure
- a scope claimed wider than the experiment run
- an assumption the run depends on that nobody declared

Rules you must follow:

1. Every finding must cite `field_path`: a real dotted path into the \
report JSON you were given, for example `sample.n_episodes` or \
`candidates[0].gates.G4.status`. Invent nothing.
2. If you have nothing to add beyond the rules, return an empty list. \
That is the correct answer for a sound run, and padding is worse than \
silence.
3. Never call a stack safe and never state a cost of ownership. Those \
words are reserved for claims this evidence cannot support.
4. Ground every finding in a value you can see. Do not estimate, \
interpolate, or reason about numbers that are not in front of you."""


class ScoredFinding(BaseModel):
    """A finding, with where it came from and how it was ranked."""

    model_config = ConfigDict(frozen=True)

    code: str
    severity: str
    kind: str
    claim: str
    ground: str
    field_path: str
    suggested_check: str
    #: ``rule`` is deterministic; ``model`` came from the LLM and is the
    #: half an evaluation must score separately.
    source: str
    #: The model's reading of what a reviewer should look at first.
    #: None on rule findings when the model did not run.
    rank: int | None = None


class CritiqueResult(BaseModel):
    """Rule findings, model findings, and what was thrown away.

    ``fabricated`` and ``refused`` are as much the point as ``findings``:
    they are how anyone tells a model that added judgement from one that
    added noise, without reading the prose.
    """

    model_config = ConfigDict(frozen=True)

    findings: tuple[ScoredFinding, ...]
    #: One paragraph a reviewer reads before the list. Empty when the
    #: model did not run or declined.
    summary: str = ""
    #: Model findings dropped for citing a field that does not resolve.
    fabricated: int = 0
    #: Set when the model produced nothing usable, with the reason.
    refused: str = ""
    provider: str = ""
    model: str = ""
    deterministic: bool = True

    @property
    def rules_applied(self) -> int:
        return len(RULE_CODES)


def critique_schema() -> dict[str, Any]:
    """The shape the provider is forced into.

    ``field_path`` is described rather than enumerated: the valid set is
    every path in a particular report, which is too large and too
    run-specific for an enum. It is validated after the fact instead,
    which is why `fabricated` exists.
    """
    return {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": (
                    "One paragraph: what a reviewer should look at first and why. "
                    "Empty string if there is nothing beyond the rule findings."
                ),
            },
            "findings": {
                "type": "array",
                "maxItems": MAX_MODEL_FINDINGS,
                "items": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "SHORT_UPPER_SNAKE label for this objection.",
                        },
                        "severity": {
                            "type": "string",
                            "enum": ["blocking", "material", "disclosure"],
                        },
                        "kind": {
                            "type": "string",
                            "enum": ["present", "omission"],
                            "description": (
                                "present: a contradiction visible in the data. "
                                "omission: something absent that should not be."
                            ),
                        },
                        "claim": {
                            "type": "string",
                            "description": "What the run asserts that this puts in doubt.",
                        },
                        "ground": {
                            "type": "string",
                            "description": "Why, in one sentence, citing a value you can see.",
                        },
                        "field_path": {
                            "type": "string",
                            "description": (
                                "Dotted path into the report JSON, e.g. sample.n_episodes "
                                "or candidates[0].gates.G4.status. Must exist."
                            ),
                        },
                        "suggested_check": {
                            "type": "string",
                            "description": "What a reader could do to settle it.",
                        },
                    },
                    "required": [
                        "code",
                        "severity",
                        "kind",
                        "claim",
                        "ground",
                        "field_path",
                        "suggested_check",
                    ],
                    "additionalProperties": False,
                },
            },
            "ranked_rule_codes": {
                "type": "array",
                "items": {"type": "string", "enum": list(RULE_CODES)},
                "description": (
                    "The rule findings you were given, most important first. "
                    "Include every one you were given; omit none."
                ),
            },
        },
        "required": ["summary", "findings", "ranked_rule_codes"],
        "additionalProperties": False,
    }


def _summarise(report: dict[str, Any]) -> dict[str, Any]:
    """What the model sees: the argument, not the episode tables."""
    summary = {key: report[key] for key in _SUMMARY_KEYS if key in report}
    summary["candidates"] = [
        {
            "candidate_id": c.get("candidate_id"),
            "stack_label": c.get("stack_label"),
            "local_controller_config": c.get("local_controller_config"),
            "n_episodes": c.get("n_episodes"),
            "n_distinct_episodes": c.get("n_distinct_episodes"),
            "success_rate": c.get("success_rate"),
            "pooled_p99_latency_ms": c.get("pooled_p99_latency_ms"),
            "cleared_gates": c.get("cleared_gates"),
            "blocking_gates": c.get("blocking_gates"),
            "gates": c.get("gates"),
        }
        for c in (report.get("candidates") or [])
    ]
    return summary


def _as_scored(finding: Finding, *, source: str, rank: int | None = None) -> ScoredFinding:
    return ScoredFinding(**finding.model_dump(), source=source, rank=rank)


def _rank_rules(rules: tuple[Finding, ...], ordering: list[str]) -> tuple[ScoredFinding, ...]:
    """Apply the model's ordering to the rule findings.

    Codes the model omitted keep their rule order at the end rather than
    disappearing. A model cannot drop an objection by forgetting it —
    that is the whole reason ranking and reporting are separate steps.
    """
    position = {code: i for i, code in enumerate(ordering)}
    ranked = sorted(
        enumerate(rules),
        key=lambda pair: (position.get(pair[1].code, len(ordering)), pair[0]),
    )
    return tuple(_as_scored(f, source="rule", rank=i + 1) for i, (_, f) in enumerate(ranked))


def critique_with_model(
    report: dict[str, Any],
    provider: LLMProvider,
) -> CritiqueResult:
    """Rule findings, read and extended by a model. Never raises.

    The rules run first and their findings survive every failure path
    below: a provider that errors, refuses, returns malformed JSON or
    fabricates every citation still yields the deterministic half. What
    a working model adds is an ordering, a paragraph, and up to
    :data:`MAX_MODEL_FINDINGS` objections of a kind rules cannot reach.
    """
    rules = rule_critique(report)
    base = tuple(_as_scored(f, source="rule") for f in rules)
    meta = {
        "provider": provider.name,
        "model": provider.model,
        "deterministic": provider.deterministic,
    }

    payload = {
        "report": _summarise(report),
        "rule_findings": [
            {"code": f.code, "severity": f.severity, "ground": f.ground} for f in rules
        ],
    }
    request = LLMRequest(
        system=CRITIQUE_SYSTEM,
        messages=(LLMMessage.user(json.dumps(payload, ensure_ascii=False, default=str)),),
        output_schema=critique_schema(),
        max_tokens=CRITIQUE_MAX_TOKENS,
    )

    try:
        response = provider.complete(request)
    except Exception as exc:  # provider errors are a refusal, not a crash
        return CritiqueResult(findings=base, refused=f"provider failed: {exc}", **meta)

    if not isinstance(response.structured, dict):
        return CritiqueResult(
            findings=base, refused="provider returned no structured output", **meta
        )

    try:
        parsed = _Payload.model_validate(response.structured)
    except ValidationError as exc:
        return CritiqueResult(
            findings=base,
            refused=f"structured output did not validate: {exc.error_count()}",
            **meta,
        )

    ranked_rules = _rank_rules(rules, list(parsed.ranked_rule_codes))

    kept: list[ScoredFinding] = []
    fabricated = 0
    for item in parsed.findings[:MAX_MODEL_FINDINGS]:
        if resolve(report, item.field_path) is None:
            fabricated += 1
            continue
        kept.append(
            ScoredFinding(
                code=item.code,
                severity=item.severity,
                kind=item.kind,
                claim=item.claim,
                ground=item.ground,
                field_path=item.field_path,
                suggested_check=item.suggested_check,
                source="model",
                rank=len(ranked_rules) + len(kept) + 1,
            )
        )

    summary = parsed.summary.strip()
    try:
        assert_no_banned_language({"summary": summary, "findings": [f.ground for f in kept]})
    except BannedLanguageError as exc:
        # The prose is dropped, the rules are not. A model that reached
        # for a banned claim has said something this evidence cannot
        # support, and the honest move is to show the deterministic half
        # and say why the rest is missing.
        return CritiqueResult(
            findings=ranked_rules,
            fabricated=fabricated,
            refused=f"model used language the contract bans: {exc}",
            **meta,
        )

    return CritiqueResult(
        findings=ranked_rules + tuple(kept),
        summary=summary,
        fabricated=fabricated,
        **meta,
    )


class _ModelFinding(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    severity: str
    kind: str
    claim: str
    ground: str
    field_path: str
    suggested_check: str


class _Payload(BaseModel):
    """What the provider must return, validated before anything is used."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    summary: str = ""
    findings: tuple[_ModelFinding, ...] = ()
    ranked_rule_codes: tuple[str, ...] = ()
