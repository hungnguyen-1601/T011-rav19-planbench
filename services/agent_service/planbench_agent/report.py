"""Cited report generation, with fabrication checks after the fact.

The prompt asks the model to cite; the validator makes citing the only
way through. After generation:

1. Every ``[kind:locator]`` token must exist in the evidence bundle.
   One unknown id fails the whole report — a fabricated citation is
   worse than no report, because it looks checkable and isn't.
2. At least one citation must be present. Uncited prose is opinion.
3. A benchmark that a reviewer has not accepted produces a report
   marked provisional, with the safety disclaimer attached.

The model never decides whether a stack is safe. It summarises recorded
evidence; the verdict is a human's (spec section 25).
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict

from planbench_agent.evidence import EvidenceBundle, InsufficientEvidence, extract_citations
from planbench_agent.provider import (
    LLMMessage,
    LLMProvider,
    LLMRequest,
    StopReason,
)

ACCEPTED_STATE = "accepted"

SAFETY_DISCLAIMER = (
    "This report summarises recorded simulation results. It is not a safety "
    "certification: no simulated benchmark can establish that a planner is safe "
    "on real hardware. The safety judgement belongs to a human reviewer."
)

PROVISIONAL_NOTICE = (
    "PROVISIONAL — a reviewer has not accepted these results yet, so they must "
    "not be published as a conclusion."
)

REPORT_SYSTEM = """You write benchmark analyses for a robotics planning \
benchmark platform.

Absolute rules:
1. Use ONLY the numbered evidence supplied below. If the evidence does not \
answer the question, reply with exactly: INSUFFICIENT EVIDENCE followed by one \
sentence naming what is missing.
2. Every factual claim must end with a citation in square brackets copied \
verbatim from the evidence, e.g. [aggregate:abc123#astar+dwa]. Never invent, \
abbreviate, or reformat an id.
3. Never state or imply that a planner is safe, production-ready, or approved. \
Report what the data shows and stop.
4. Do not compare results whose conditions_checksum differs; say so instead.
5. Do not report a number that is not in the evidence. No estimates, no \
rounding beyond what is given, no interpolation.

Write plain prose: a short summary, then the comparison, then limitations."""


class FabricatedCitation(Exception):
    """The model cited an id that is not in the evidence bundle."""

    def __init__(self, unknown: tuple[str, ...]) -> None:
        self.unknown = unknown
        super().__init__(f"report cites unknown evidence: {list(unknown)}")


class GeneratedReport(BaseModel):
    """A generated answer plus everything needed to audit it."""

    model_config = ConfigDict(frozen=True)

    text: str
    citations: tuple[str, ...] = ()
    refused: bool = False
    refusal_reason: str = ""
    provisional: bool = True
    provider: str = ""
    model: str = ""
    deterministic: bool = False
    evidence_count: int = 0


def build_prompt(bundle: EvidenceBundle, question: str) -> str:
    return (
        f"Question: {question}\n\n"
        f"Evidence ({len(bundle.items)} items):\n{bundle.render()}\n\n"
        "Answer the question using only the evidence above."
    )


def generate_report(
    provider: LLMProvider,
    bundle: EvidenceBundle,
    question: str,
    *,
    benchmark_state: str = "",
    min_evidence: int = 1,
    max_tokens: int = 4096,
) -> GeneratedReport:
    """Ask for a report, then verify it before returning it.

    Refusal is a normal outcome, returned as a value rather than raised:
    "not enough evidence" is a legitimate answer to a question and the
    caller should be able to show it to a user unchanged.
    """
    provisional = benchmark_state != ACCEPTED_STATE
    base = GeneratedReport(
        text="",
        provider=provider.name,
        model=provider.model,
        deterministic=provider.deterministic,
        provisional=provisional,
        evidence_count=len(bundle.items),
    )

    try:
        bundle.require(min_evidence)
    except InsufficientEvidence as exc:
        return base.model_copy(
            update={
                "text": f"INSUFFICIENT EVIDENCE — {exc}",
                "refused": True,
                "refusal_reason": str(exc),
            }
        )

    response = provider.complete(
        LLMRequest(
            system=REPORT_SYSTEM,
            messages=(LLMMessage.user(build_prompt(bundle, question)),),
            max_tokens=max_tokens,
        )
    )

    if response.stop_reason is StopReason.REFUSAL:
        return base.model_copy(
            update={
                "text": "The model declined to answer this request.",
                "refused": True,
                "refusal_reason": "provider refusal",
            }
        )

    text = response.text.strip()
    if not text:
        return base.model_copy(
            update={
                "text": "INSUFFICIENT EVIDENCE — the model returned no text.",
                "refused": True,
                "refusal_reason": "empty response",
            }
        )

    cited = extract_citations(text)
    unknown = tuple(dict.fromkeys(c for c in cited if c not in bundle.ids))
    if unknown:
        raise FabricatedCitation(unknown)

    if text.upper().startswith("INSUFFICIENT EVIDENCE"):
        return base.model_copy(
            update={
                "text": text,
                "citations": cited,
                "refused": True,
                "refusal_reason": "model reported insufficient evidence",
            }
        )

    if not cited:
        return base.model_copy(
            update={
                "text": (
                    "INSUFFICIENT EVIDENCE — the generated answer cited no evidence, "
                    "so it cannot be verified and was discarded."
                ),
                "refused": True,
                "refusal_reason": "no citations",
            }
        )

    return base.model_copy(update={"text": _append_notices(text, provisional), "citations": cited})


def _append_notices(text: str, provisional: bool) -> str:
    parts = [text.rstrip(), "", SAFETY_DISCLAIMER]
    if provisional:
        parts.append(PROVISIONAL_NOTICE)
    return "\n".join(parts)


_SAFE_CLAIM = re.compile(
    r"\b(is safe|are safe|production[- ]ready|certified|guaranteed safe|no risk)\b",
    re.IGNORECASE,
)


def contains_safety_claim(text: str) -> bool:
    """True when text makes the one claim the agent may never make.

    Used by tests and by callers that want to hard-fail rather than
    attach a disclaimer.
    """
    body = text.split(SAFETY_DISCLAIMER)[0]
    return bool(_SAFE_CLAIM.search(body))


__all__ = [
    "ACCEPTED_STATE",
    "PROVISIONAL_NOTICE",
    "REPORT_SYSTEM",
    "SAFETY_DISCLAIMER",
    "FabricatedCitation",
    "GeneratedReport",
    "build_prompt",
    "contains_safety_claim",
    "generate_report",
]
