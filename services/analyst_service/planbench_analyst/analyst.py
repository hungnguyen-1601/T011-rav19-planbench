"""One round: the packet in, proposals out, and an account of the cost.

This module is the only place a model is called. What it owns, and what
it deliberately does not:

**It owns identity.** ``hypothesis_id`` is derived from the content of
the proposal, never taken from the model. Two rounds that say the same
thing say it under the same name, which is what makes deduplication
possible at all — an id the model chose would let the same hypothesis
arrive twice under two names, and the protocol's duplicate check would
wave both through.

**It owns the cost.** Tokens and calls are counted here and travel with
the round, because the budget the platform enforces at A4 is a number
somebody has to be able to compare against a measurement. A layer that
only discovers its spend when it exceeds a limit has no way to answer
"how much does one round cost".

**It does not judge.** A proposal that cites a ref this packet does not
hold is *kept* here and dropped by the guard at A3. That split is not
tidiness: the guard is where drops are counted, and an engine that
quietly filtered would make the guard's numbers say the model never
made the mistake.

**A call that does not come back ends the round.** The provider layer
has no timeout of its own, and a node that hangs takes the whole run
with it — no checkpoint, no partial result, nothing to resume from. The
completion therefore runs on a worker thread with a deadline. The
thread cannot be killed, and the docstring on :func:`_complete` says so
rather than pretending otherwise: the choice is between a round that
fails at a known time and a process that never returns.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from planbench_agent.provider import LLMMessage, LLMProvider, LLMRequest, LLMResponse
from planbench_analyst.packet_view import PacketView
from planbench_analyst.prompts import (
    ANALYST_SYSTEM,
    REVISION_PREFACE,
    analyst_schema,
    build_user_turn,
    prompt_checksum,
)
from planbench_explanation.catalog import ToolCatalog
from planbench_explanation.ledger import EvidenceRef, HypothesisProposal, RequestedCheck
from planbench_explanation.protocol import AnalysisRequest, AnalysisResponse
from planbench_explanation.tools import ToolCard
from planbench_explanation.versioning import artifact_checksum
from planbench_schemas.identity import canonical_json

__all__ = [
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_TIMEOUT_S",
    "AnalystRefusal",
    "CheckFeedback",
    "RoundCost",
    "RoundReport",
    "catalog_text",
    "propose",
]


class AnalystRefusal(RuntimeError):
    """The round cannot be completed, and no answer is better than a guess."""


#: Reasoning models spend output budget before the first token of JSON.
#: The advisor measured a small cap truncating the whole answer; the
#: provider adapters retry against a model's own lower ceiling, so this
#: is a budget rather than a demand.
DEFAULT_MAX_TOKENS = 32768

#: Deadline for one completion. Long enough for a reasoning model on a
#: full packet, short enough that a hung round is a failure somebody
#: sees today rather than a job that never returns.
DEFAULT_TIMEOUT_S = 180.0

#: Hypothesis ids are the first this many hex characters of the content
#: digest. Short enough to read in a report, long enough that a
#: collision between two different hypotheses in one round is a genuine
#: surprise — and one that :func:`propose` refuses rather than resolves.
ID_DIGITS = 16


@dataclass(frozen=True)
class RoundCost:
    """What one round spent. Filled here; extended by the runner at A4."""

    model_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    #: Tool requests the round went on to make. Zero here by
    #: construction: this module never calls a tool.
    tool_requests: int = 0


@dataclass(frozen=True)
class RoundReport:
    """The answer, and everything a reader needs to audit how it got here."""

    response: AnalysisResponse
    cost: RoundCost
    prompt_checksum: str
    packet_checksum: str
    #: Checksum of the model's structured answer, before any of this
    #: module's work. What a replay compares against.
    response_checksum: str
    #: One sentence per hypothesis this module refused to build, and
    #: why. Never silent: a malformed proposal that vanished would read
    #: as a model that proposed less.
    dropped: tuple[str, ...] = ()
    #: Problems that cost a hypothesis its **check** and not its life —
    #: a tool that is not on the catalog, an argument that will not
    #: convert. Kept apart from :attr:`dropped` because "the model
    #: proposed nothing usable" and "the model proposed something and
    #: asked for the wrong tool" are different failures, and A6 counts
    #: them against different metrics.
    checks_refused: tuple[str, ...] = ()
    #: Refs the model cited that this packet does not hold. Kept, not
    #: filtered — see the module docstring.
    refs_not_in_index: tuple[str, ...] = ()
    #: ``label -> what it tripped`` for third-party strings that read
    #: like an instruction rather than a name. Counted, never a reason
    #: to refuse the round: the label already made the string inert, and
    #: a platform that would not analyse a run because a plugin had a
    #: rude name is a platform denying service over a string.
    injection_suspected: tuple[tuple[str, tuple[str, ...]], ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class CheckFeedback:
    """What came back from one check, in the words the model may read.

    Deliberately not the raw :class:`~planbench_explanation.protocol.ToolResult`:
    a result carries measurements, and a model shown measurements will
    put them in its next statement — which the guard then drops for
    carrying a number. What it needs to revise is the *verdict* and the
    reason, so that is what it gets.
    """

    hypothesis_id: str
    tool_id: str
    execution_status: str
    failure_code: str = ""
    verdicts: tuple[str, ...] = ()
    rejected_as: str = ""

    def render(self) -> str:
        if self.rejected_as:
            return (
                f"- {self.tool_id} for {self.hypothesis_id}: the host refused the "
                f"request ({self.rejected_as})"
            )
        parts = [f"- {self.tool_id} for {self.hypothesis_id}: {self.execution_status}"]
        if self.failure_code:
            parts.append(f"({self.failure_code})")
        if self.verdicts:
            parts.append("— " + ", ".join(self.verdicts))
        return " ".join(parts)


@dataclass
class _Draft:
    """One hypothesis as the model sent it, before it is given a name.

    ``decision`` is W4's branch: ``no_check`` for a statement whose
    evidence is already in the packet, ``check`` for a draft that exists
    only so the host has something to bind a tool result to.
    """

    decision: str
    statement: str
    proposition_type: str
    subject: str
    supports: tuple[str, ...]
    contradicts: tuple[str, ...]
    missing_evidence: tuple[str, ...]
    tool_id: str
    arguments: dict[str, Any] = field(default_factory=dict)
    experiments: tuple[str, ...] = ()


def catalog_text(catalog: ToolCatalog) -> str:
    """The menu, rendered as the closed list it is.

    Rendered rather than dumped: a card carries prose, failure modes and
    schema references the model does not need, and a bigger prompt is a
    more expensive round for the same answer. What survives is what a
    caller has to get right — the id, the class, the propositions the
    card may support, the evidence it needs, and each argument's name,
    type and meaning.
    """
    lines: list[str] = []
    for card in catalog.cards:
        supported = ", ".join(card.proposition_policy.supported_proposition_types) or "none"
        needs = ", ".join(card.required_evidence) or "none"
        lines.append(
            f"- {card.tool_id} (v{card.tool_version}, {card.tool_class}); "
            f"supports: {supported}; needs evidence: {needs}"
        )
        for argument in card.io.arguments:
            flag = "required" if argument.required else "optional"
            lines.append(
                f"    · {argument.name} ({argument.kind}, {flag}) — {argument.description}"
            )
    return "\n".join(lines)


def _complete(
    provider: LLMProvider, request: LLMRequest, *, timeout_s: float
) -> LLMResponse:
    """One completion, with a deadline the provider layer does not offer.

    The worker thread is not cancellable — a blocked socket read stays
    blocked — so a timed-out call may still be in flight when this
    returns. That is the honest cost of a deadline at this layer, and it
    is cheaper than the alternative: without it a provider that stops
    answering takes the whole run, and the checkpoint that would have
    let it resume is never written.

    It is a **daemon** thread, and a plain one rather than a pool.
    ``ThreadPoolExecutor`` joins its workers on the way out of the
    ``with`` block, so a deadline expressed through it still waits for
    the call it just gave up on — measured at the full two seconds of a
    two-second stall against a 0.2s deadline, which is the deadline not
    working. A daemon thread lets both this round and the process move
    on.
    """
    outcome: dict[str, Any] = {}
    finished = threading.Event()

    def _worker() -> None:
        try:
            outcome["response"] = provider.complete(request)
        except BaseException as failed:  # noqa: BLE001 - re-raised on the caller's thread
            outcome["error"] = failed
        finally:
            finished.set()

    threading.Thread(target=_worker, name="analyst-model", daemon=True).start()
    if not finished.wait(timeout_s):
        raise AnalystRefusal(
            f"the model did not answer within {timeout_s:g}s; the round is "
            "recorded as failed rather than left waiting"
        )
    if "error" in outcome:
        raise outcome["error"]
    return outcome["response"]


def _payload(response: LLMResponse) -> Mapping[str, Any]:
    """The structured answer, or a refusal that names which half failed."""
    if isinstance(response.structured, Mapping):
        return response.structured
    if response.text.strip():
        try:
            parsed = json.loads(response.text)
        except json.JSONDecodeError as broken:
            raise AnalystRefusal(
                "the model answered with text that is not the requested object"
            ) from broken
        if isinstance(parsed, Mapping):
            return parsed
    raise AnalystRefusal("the model returned no structured output")


def _string_list(value: Any, *, limit: int) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return ()
    return tuple(item.strip() for item in value if isinstance(item, str) and item.strip())[:limit]


def _drafts(
    payload: Mapping[str, Any], *, discriminated_union: bool = True
) -> tuple[list[_Draft], list[str]]:
    drafts: list[_Draft] = []
    dropped: list[str] = []
    raw = payload.get("hypotheses")
    if not isinstance(raw, Sequence) or isinstance(raw, str | bytes):
        return drafts, dropped
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, Mapping):
            dropped.append(f"hypothesis {index}: not an object")
            continue
        statement = item.get("statement")
        proposition = item.get("proposition_type")
        subject = item.get("subject")
        parts = (statement, proposition, subject)
        if not all(isinstance(part, str) and part.strip() for part in parts):
            dropped.append(f"hypothesis {index}: statement, proposition_type or subject missing")
            continue
        decision = item.get("decision")
        if discriminated_union and decision not in ("no_check", "check"):
            dropped.append(f"hypothesis {index}: decision is neither no_check nor check")
            continue
        check = item.get("requested_check")
        tool_id = ""
        arguments: dict[str, Any] = {}
        if isinstance(check, Mapping):
            candidate = check.get("tool_id")
            tool_id = candidate.strip() if isinstance(candidate, str) else ""
            pairs = check.get("arguments")
            if isinstance(pairs, Sequence) and not isinstance(pairs, str | bytes):
                for pair in pairs:
                    if isinstance(pair, Mapping):
                        name = pair.get("name")
                        value = pair.get("value")
                        if isinstance(name, str) and isinstance(value, str):
                            arguments[name.strip()] = value
        # The union, enforced here because the schema cannot: a branch
        # that asked for no check and then asked for one, or promised a
        # check and named no tool, is a malformed answer with a name —
        # and a named failure is one a single repair turn can fix.
        if not discriminated_union:
            # E6's control arm: no branch was asked for, so the shape is
            # read back the way it was before W4 — a statement, and a
            # check if one came with it. Derived rather than absent, so
            # everything downstream still knows which kind it has.
            decision = "check" if tool_id else "no_check"
        if decision == "no_check" and tool_id:
            dropped.append(
                f"hypothesis {index}: decision=no_check carries a requested_check; "
                "a final statement is one whose evidence is already in hand"
            )
            continue
        if decision == "check" and not tool_id:
            dropped.append(
                f"hypothesis {index}: decision=check names no tool; a draft exists "
                "only because a check is coming"
            )
            continue
        drafts.append(
            _Draft(
                decision=str(decision),
                statement=statement.strip(),  # type: ignore[union-attr]
                proposition_type=proposition.strip(),  # type: ignore[union-attr]
                subject=subject.strip(),  # type: ignore[union-attr]
                supports=_string_list(item.get("supports"), limit=8),
                contradicts=_string_list(item.get("contradicts"), limit=8),
                missing_evidence=_string_list(item.get("missing_evidence"), limit=8),
                tool_id=tool_id,
                arguments=arguments,
                experiments=_string_list(item.get("recommended_experiments"), limit=3),
            )
        )
    return drafts, dropped


def _coerced(card: ToolCard, arguments: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Model strings turned into the kinds the card declares.

    The schema asks for strings because a strict schema mode has to
    declare every property, and the properties differ per card. So the
    types are recovered here, once, where a value that will not convert
    becomes a named problem — rather than three layers down, as a
    checker comparing a string to a float.
    """
    kinds = {argument.name: argument.kind for argument in card.io.arguments}
    coerced: dict[str, Any] = {}
    problems: list[str] = []
    for name, raw in arguments.items():
        kind = kinds.get(name)
        if kind is None:
            # Left as it is: the card's own ``check_arguments`` reports
            # unknown arguments, and swallowing them here would take the
            # message away from the layer that phrases it best.
            coerced[name] = raw
            continue
        text = raw if isinstance(raw, str) else str(raw)
        try:
            if kind == "integer":
                coerced[name] = int(text)
            elif kind == "number":
                coerced[name] = float(text)
            elif kind == "boolean":
                lowered = text.strip().lower()
                if lowered not in {"true", "false"}:
                    raise ValueError(text)
                coerced[name] = lowered == "true"
            else:
                coerced[name] = text
        except ValueError:
            problems.append(f"argument {name!r}={text!r} is not {kind}")
    return coerced, problems


def _hypothesis_id(draft: _Draft) -> str:
    """A name derived from what the hypothesis says.

    The check request is inside the digest. Two proposals with the same
    sentence asking for different checks are two different pieces of
    work, and giving them one id would silently drop one of them at the
    protocol's duplicate check.
    """
    digest = artifact_checksum(
        canonical_json(
            {
                "statement": draft.statement,
                "proposition_type": draft.proposition_type,
                "subject": draft.subject,
                "supports": sorted(draft.supports),
                "contradicts": sorted(draft.contradicts),
                "tool_id": draft.tool_id,
                "arguments": {name: str(value) for name, value in sorted(draft.arguments.items())},
            }
        )
    )
    return f"hyp-{digest[:ID_DIGITS]}"


def _refs(
    view: PacketView, refs: Sequence[str], unresolved: list[str]
) -> tuple[EvidenceRef, ...]:
    built: list[EvidenceRef] = []
    for ref in refs:
        fact = view.fact(ref)
        if fact is None:
            unresolved.append(ref)
            # ``fact`` is the kind an unresolvable pointer is least
            # wrong as, and the guard drops it either way. What matters
            # is that it survives to *be* dropped and counted.
            built.append(EvidenceRef(ref=ref, kind="fact"))
            continue
        built.append(EvidenceRef(ref=ref, kind=fact.kind))
    return tuple(built)


def propose(
    analysis: AnalysisRequest,
    view: PacketView,
    provider: LLMProvider,
    *,
    feedback: Sequence[CheckFeedback] = (),
    candidates_text: str = "",
    menu: ToolCatalog | None = None,
    discriminated_union: bool = True,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> RoundReport:
    """Ask the model for hypotheses about one packet.

    Raises :class:`AnalystRefusal` when there is no answer to report —
    a provider that failed, a deadline that passed, an answer that is
    not the requested object. Everything the model *did* say and this
    module could not use comes back in :attr:`RoundReport.dropped`,
    because a proposal that disappeared reads as one that was never made.
    """
    # The menu the model is *shown* may be narrower than the catalog
    # the round was opened against (W3): admission still runs against
    # the full catalog, so filtering is a presentation change and never
    # a permission one.
    turn = build_user_turn(
        view.serialize(), catalog_text(menu or analysis.catalog), candidates_text
    )
    if feedback:
        turn += "\n\n" + REVISION_PREFACE + "\n".join(item.render() for item in feedback)
    request = LLMRequest(
        system=ANALYST_SYSTEM,
        messages=(LLMMessage.user(turn),),
        output_schema=analyst_schema(discriminated_union=discriminated_union),
        max_tokens=max_tokens,
    )
    try:
        response = _complete(provider, request, timeout_s=timeout_s)
    except AnalystRefusal:
        raise
    except Exception as failed:  # noqa: BLE001 - this is the provider boundary
        raise AnalystRefusal(f"the provider failed: {failed}") from failed

    cost = RoundCost(
        model_calls=1,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
    )
    payload = _payload(response)
    response_checksum = artifact_checksum(canonical_json(dict(payload)))
    drafts, dropped = _drafts(payload, discriminated_union=discriminated_union)
    checks_refused: list[str] = []
    unresolved: list[str] = []
    proposals: list[HypothesisProposal] = []
    by_id: dict[str, str] = {}

    for index, draft in enumerate(drafts, start=1):
        hypothesis_id = _hypothesis_id(draft)
        content = canonical_json(
            {"statement": draft.statement, "type": draft.proposition_type, "subject": draft.subject}
        )
        if hypothesis_id in by_id:
            if by_id[hypothesis_id] == content:
                dropped.append(f"hypothesis {index}: identical to an earlier one, deduplicated")
                continue
            raise AnalystRefusal(
                f"two different hypotheses hash to {hypothesis_id}; the round is refused "
                "rather than renaming one, because an id that can be nudged is not an id"
            )
        checks: tuple[RequestedCheck, ...] = ()
        if draft.tool_id:
            card = next(
                (item for item in analysis.catalog.cards if item.tool_id == draft.tool_id), None
            )
            if card is None:
                checks_refused.append(
                    f"hypothesis {index}: asked for {draft.tool_id!r}, which is not on the catalog"
                )
            else:
                arguments, problems = _coerced(card, draft.arguments)
                if problems:
                    checks_refused.append(f"hypothesis {index}: {'; '.join(problems)}")
                else:
                    checks = (
                        RequestedCheck(
                            tool_id=card.tool_id,
                            tool_version=card.tool_version,
                            arguments=arguments,
                        ),
                    )
        try:
            proposals.append(
                HypothesisProposal(
                    hypothesis_id=hypothesis_id,
                    hypothesis_statement=draft.statement,
                    proposition_type=draft.proposition_type,  # type: ignore[arg-type]
                    proposed_subject=draft.subject,  # type: ignore[arg-type]
                    supports=_refs(view, draft.supports, unresolved),
                    contradicts=_refs(view, draft.contradicts, unresolved),
                    missing_evidence=draft.missing_evidence,
                    requested_checks=checks,
                    recommended_experiments=draft.experiments,
                )
            )
        except ValueError as refused:
            dropped.append(f"hypothesis {index}: {refused}")
            continue
        by_id[hypothesis_id] = content

    abstained = bool(payload.get("abstained")) or not proposals
    reason = payload.get("abstention_reason")
    if abstained:
        stated = reason.strip() if isinstance(reason, str) and reason.strip() else ""
        if not stated:
            stated = (
                "the model proposed nothing this module could build a proposal from"
                if dropped
                else "the model abstained without stating a reason"
            )
        answer = AnalysisResponse(
            analysis_run_id=analysis.analysis_run_id,
            analyst_bundle_id=analysis.analyst_bundle_id,
            abstained=True,
            abstention_reason=stated,
        )
    else:
        answer = AnalysisResponse(
            analysis_run_id=analysis.analysis_run_id,
            analyst_bundle_id=analysis.analyst_bundle_id,
            proposals=tuple(proposals),
        )

    return RoundReport(
        response=answer,
        cost=cost,
        prompt_checksum=prompt_checksum(),
        packet_checksum=view.checksum,
        response_checksum=response_checksum,
        dropped=tuple(dropped),
        checks_refused=tuple(checks_refused),
        injection_suspected=tuple(sorted(view.aliases.suspicious.items())),
        refs_not_in_index=tuple(unresolved),
        notes=(f"model={response.model or provider.model}", f"provider={provider.name}"),
    )
