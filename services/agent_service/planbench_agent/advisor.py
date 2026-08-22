"""Let a model rank and extend rule advice, never overrule it.

Five deterministic advisory modules exist — pre-flight, gate diagnosis,
trace review, reproduction diff, reporting guardrails. Each returns
:class:`~planbench_decision.advice.Advice` grounded in a field of its
source dict. This module is the one LLM layer over all five, and it
inherits the critique layer's constitution wholesale:

**The rules' advice is the floor.** The model may reorder it and may add
to it; it may not remove, soften or contradict a rule's item. A model
that could argue a rule away would make every rule as reliable as the
model's worst day.

**Every model addition cites a field that exists.** The citation is
checked with the same :func:`~planbench_decision.self_check.exists` the
rules are held to; an addition pointing nowhere is dropped and counted
in ``fabricated``, published beside the advice. A reader weighing the
prose is entitled to know how often this model pointed at nothing.

**The forbidden move survives verbatim.** ``do_not`` on rule advice is
the load-bearing half — the model's rephrasing keeps its own words only
for its own additions.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from planbench_agent.provider import LLMMessage, LLMProvider, LLMRequest
from planbench_decision.advice import Advice, AdviceKind
from planbench_decision.self_check import exists

__all__ = ["MAX_MODEL_ADVICE", "AdvisedResult", "ScoredAdvice", "advise_with_model"]

#: The model earns at most this many additions. More would drown the
#: deterministic floor it is supposed to decorate.
MAX_MODEL_ADVICE = 3

#: Reasoning models spend output budget thinking before the first token
#: of JSON; a small cap truncates the whole answer (measured: 8192 died
#: at 317 tokens on Gemini 3).
ADVISOR_MAX_TOKENS = 32768

ADVISOR_SYSTEM = """You are reviewing advisory findings about a robot-\
navigation benchmark, for the person who has to act on them.

A deterministic rule set has already produced advice; it is given to \
you with stable codes. Your job:

1. `ranking`: order those codes by what the reader should act on first. \
Include every code exactly once. You may not drop any.
2. `additions`: at most {max} further pieces of advice the rules cannot \
see — a pattern across candidates, a mismatch between two fields, an \
assumption nobody declared. Each must cite `field_path`, a real dotted \
path into the source JSON you were given (e.g. `report.candidates[0].\
success_rate`). Invent nothing; an empty list is the right answer for a \
clean source.
3. `summary`: one paragraph the reader sees first. State what to do, \
not how the run feels.

Never call anything safe, never state a cost of ownership, and never \
contradict a rule's advice — if you disagree with a rule, say so in \
your own addition's ground, citing the same field."""


class ScoredAdvice(BaseModel):
    """One piece of advice, tagged with which half produced it."""

    model_config = ConfigDict(frozen=True)

    code: str
    kind: str
    severity: str
    claim: str
    ground: str
    field_path: str
    do: str
    do_not: str = ""
    subject: str = ""
    #: ``rule`` is deterministic; ``model`` is the half an evaluation
    #: must score separately.
    source: str
    rank: int | None = None


class AdvisedResult(BaseModel):
    """Rule advice, model additions, and what was thrown away."""

    model_config = ConfigDict(frozen=True)

    advice: tuple[ScoredAdvice, ...]
    summary: str = ""
    #: Model additions dropped for citing a field that does not resolve.
    fabricated: int = 0
    refused: str = ""
    provider: str = ""
    model: str = ""
    deterministic: bool = True


def advisor_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "summary": {"type": "string", "maxLength": 1200},
            "ranking": {"type": "array", "items": {"type": "string", "maxLength": 60}},
            "additions": {
                "type": "array",
                "maxItems": MAX_MODEL_ADVICE,
                "items": {
                    "type": "object",
                    "properties": {
                        "severity": {
                            "type": "string",
                            "enum": ["blocking", "material", "disclosure"],
                        },
                        "claim": {"type": "string", "maxLength": 300},
                        "ground": {"type": "string", "maxLength": 400},
                        "field_path": {"type": "string", "maxLength": 200},
                        "do": {"type": "string", "maxLength": 300},
                        "do_not": {"type": "string", "maxLength": 300},
                    },
                    "required": ["severity", "claim", "ground", "field_path", "do"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["summary", "ranking", "additions"],
        "additionalProperties": False,
    }


class _Addition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    severity: str
    claim: str
    ground: str
    field_path: str
    do: str
    do_not: str = ""


class _Payload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = ""
    ranking: tuple[str, ...] = ()
    additions: tuple[_Addition, ...] = ()


def _as_scored(item: Advice, *, source: str, rank: int | None = None) -> ScoredAdvice:
    return ScoredAdvice(**item.model_dump(), source=source, rank=rank)


def _ranked(rules: tuple[Advice, ...], ordering: tuple[str, ...]) -> tuple[ScoredAdvice, ...]:
    """The model's ordering, applied without letting it drop anything.

    A code the model forgot keeps its place at the end; a code it
    invented is ignored. Reordering is the only power this grants.
    """
    position = {code: i for i, code in enumerate(ordering)}
    indexed = sorted(
        enumerate(rules), key=lambda pair: (position.get(pair[1].code, len(ordering)), pair[0])
    )
    return tuple(_as_scored(item, source="rule", rank=i + 1) for i, (_, item) in enumerate(indexed))


def advise_with_model(
    kind: AdviceKind,
    source: dict[str, Any],
    rules: tuple[Advice, ...],
    provider: LLMProvider,
) -> AdvisedResult:
    """The full result: rules always, the model's layer when it helps.

    Any provider failure degrades to the rules alone with ``refused``
    saying why — a broken model must cost the reader the prose, never
    the deterministic floor.
    """
    meta = {
        "provider": provider.name,
        "model": provider.model,
        "deterministic": provider.deterministic,
    }
    base = tuple(_as_scored(item, source="rule") for item in rules)

    import json

    request = LLMRequest(
        system=ADVISOR_SYSTEM.replace("{max}", str(MAX_MODEL_ADVICE)),
        messages=(
            LLMMessage.user(
                "RULE ADVICE:\n"
                + json.dumps([a.model_dump() for a in rules], ensure_ascii=False)
                + "\n\nSOURCE:\n"
                + json.dumps(source, ensure_ascii=False, default=str)[:60_000]
            ),
        ),
        output_schema=advisor_schema(),
        max_tokens=ADVISOR_MAX_TOKENS,
    )
    try:
        response = provider.complete(request)
    except Exception as exc:
        return AdvisedResult(advice=base, refused=f"provider failed: {exc}", **meta)
    if not isinstance(response.structured, dict):
        return AdvisedResult(advice=base, refused="provider returned no structured output", **meta)
    try:
        payload = _Payload.model_validate(response.structured)
    except ValidationError as exc:
        return AdvisedResult(
            advice=base,
            refused=f"structured output did not validate: {exc.error_count()} error(s)",
            **meta,
        )

    fabricated = 0
    additions: list[ScoredAdvice] = []
    for index, item in enumerate(payload.additions):
        if not exists(source, item.field_path):
            fabricated += 1
            continue
        additions.append(
            ScoredAdvice(
                code=f"MODEL_{index + 1}",
                kind=kind,
                severity=item.severity,
                claim=item.claim,
                ground=item.ground,
                field_path=item.field_path,
                do=item.do,
                do_not=item.do_not,
                source="model",
            )
        )

    return AdvisedResult(
        advice=_ranked(rules, payload.ranking) + tuple(additions),
        summary=payload.summary,
        fabricated=fabricated,
        **meta,
    )
