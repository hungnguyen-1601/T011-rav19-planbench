"""The loop: propose, guard, declare, check, revise — and stop.

The graph is small and the interesting part is where it stops. Four
exits, and every one of them goes through the same closing step, so an
audit trail has exactly one end event per round however it got there:

``final``
    the model had nothing more to ask for.
``revisions_exhausted``
    it kept asking; the budget for revisions is a number, not a mood.
``no_progress``
    it asked for a check it had already run, with the same arguments.
    The checkers are **deterministic**: the second call returns what the
    first returned, so the round would spend a model call and a tool
    call to learn nothing. This one is worth stating plainly because it
    is the failure a retry loop wears as diligence.
``budget_exceeded``
    an axis ran out. Recorded as its own ending rather than folded into
    an abstention: "I had nothing to say" and "I was stopped" are
    different answers and must not score the same.

**Declare before request, always.** The host binds evidence to the
hypothesis it was gathered for, so a request that arrives before its
proposal was declared is refused as ``unknown_hypothesis``. Revising
therefore means declaring the new batch *before* the next request, and
that ordering is the loop's one invariant.

**The runner never sees the session.** It holds a
:class:`~planbench_analyst.round_host.RoundHostProtocol` — two verbs —
so the in-process lane and the container lane are the same code path
here. The accounting the score is read from belongs to the host.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, replace

from planbench_agent.provider import LLMProvider
from planbench_analyst.analyst import (
    DEFAULT_TIMEOUT_S,
    AnalystRefusal,
    CheckFeedback,
    RoundCost,
    RoundReport,
    propose,
)
from planbench_analyst.candidates import (
    MechanismCandidate,
    generate_candidates,
    render_candidates,
)
from planbench_analyst.features import FeatureRefusal, RoundFeatures
from planbench_analyst.guard import GuardResult, guard
from planbench_analyst.knowledge_provider import query_for, retrieve, trait_offers
from planbench_analyst.packet_view import build_packet_view
from planbench_analyst.round_host import PreparedRound
from planbench_analyst.routing import RouteRequest, effective_menu, route_for
from planbench_benchmark.traits_store import TraitSource
from planbench_explanation.knowledge_contract import ResolvedReference, resolve_candidates
from planbench_explanation.protocol import (
    AnalysisResponse,
    ProtocolRejection,
    ToolRequest,
    ToolResult,
)

__all__ = ["DEFAULT_MAX_REVISIONS", "RoundOutcome", "run_round"]

#: How many times the model may look at check results and try again.
#: Two, because the third revision has never been observed to add
#: anything the second did not — and because every revision is a model
#: call the deployment pays for on every case.
DEFAULT_MAX_REVISIONS = 2


@dataclass(frozen=True)
class RoundOutcome:
    """Everything that happened, and the one sentence for why it ended."""

    response: AnalysisResponse
    guard: GuardResult
    #: One per model turn, in order. The last one produced
    #: :attr:`response`; the earlier ones are how it got there.
    reports: tuple[RoundReport, ...]
    results: tuple[ToolResult, ...]
    cost: RoundCost
    stopped_because: str
    #: The audit trail. Exactly one ``finalize`` event, whichever way
    #: the round ended.
    events: tuple[str, ...]
    #: W2's shortlist **as the generator produced it**, before the model
    #: saw it and before any harness touched it. ``generator_recall@K``
    #: is scored here: a recall read off the model's answer measures the
    #: pair, and a recall read after distractors were injected measures
    #: the harness. Empty when the shortlist was not offered.
    shortlist: tuple[MechanismCandidate, ...] = ()

    @property
    def rejections(self) -> tuple[str, ...]:
        """Host refusal codes, in order. A refused request is an outcome."""
        return tuple(
            event.split("rejected:", 1)[1] for event in self.events if "rejected:" in event
        )


@dataclass(frozen=True)
class _RoutedCheck:
    """A code-chosen check, in the shape the request loop already takes.

    A small adapter rather than a second request path: one loop builds
    every ``ToolRequest``, so budget accounting, the repeat guard and the
    transcript cannot drift between a model-chosen call and a routed one.
    """

    route: RouteRequest

    @property
    def tool_id(self) -> str:
        return self.route.tool_id

    @property
    def tool_version(self) -> str:
        return self.route.tool_version

    @property
    def arguments(self) -> dict[str, object]:
        return dict(self.route.arguments)


def _request_key(hypothesis_id: str, check) -> tuple[str, str, tuple[tuple[str, str], ...]]:  # type: ignore[no-untyped-def]
    """What makes two checks the same piece of work.

    The hypothesis is **not** in the key. Two hypotheses asking the same
    tool the same question get the same answer, and paying twice for it
    is the same waste whichever proposal asked.
    """
    return (
        check.tool_id,
        check.tool_version,
        tuple((name, str(value)) for name, value in sorted(check.arguments.items())),
    )


def _feedback_for(hypothesis_id: str, result: ToolResult) -> CheckFeedback:
    return CheckFeedback(
        hypothesis_id=hypothesis_id,
        tool_id=result.tool_id,
        execution_status=result.execution_status,
        failure_code=result.failure_code or "",
        verdicts=tuple(
            f"{outcome.proposition_type}: {outcome.result}"
            for outcome in result.supported_propositions
        ),
    )


def run_round(
    prepared: PreparedRound,
    provider: LLMProvider,
    *,
    max_revisions: int = DEFAULT_MAX_REVISIONS,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    features: RoundFeatures | None = None,
    traits: TraitSource | None = None,
) -> RoundOutcome:
    """Drive one analysis round to one of its four endings.

    ``knowledge`` and ``traits`` are the two retrieval inputs, and both
    are **off by default** (W1.5). Off is not timidity: each one costs
    prompt budget on every case and each is a separate arm of the input
    ablation, so a default that quietly turned them on would make the
    baseline unmeasurable — B1 would already contain what E1 is meant to
    add. W1.7 puts the same two flags into ``runtime_config_checksum``,
    so a bundle cannot be graded with one setting and replayed with the
    other.

    Retrieval offers **keys**, and the platform resolves them: an entry
    the curated base does not hold is rejected here rather than carried
    into a prompt, which is the boundary A5 drew and the reason nothing
    a provider names can widen the base.
    """
    analysis = prepared.analysis
    budget = prepared.effective_budget
    features = features or RoundFeatures()
    if traits is not None and not features.traits:
        raise FeatureRefusal(
            "a trait source was handed to a round whose feature vector does not "
            "declare traits. Refused rather than used: the checksum would say the "
            "arm was off while the prompt carried the natures."
        )

    started = time.monotonic()
    events: list[str] = [f"start:{analysis.analysis_run_id}"]

    offered: tuple[ResolvedReference, ...] = ()
    rejected_offers = 0
    if features.knowledge:
        outcome = resolve_candidates(retrieve(query_for(analysis.packet)))
        offered = outcome.resolved
        rejected_offers = len(outcome.rejected)

    view = build_packet_view(
        analysis.packet,
        tool_catalog_version=analysis.catalog.catalog_version,
        traits=traits if features.traits else None,
        knowledge=offered,
        features=features,
    )

    # W2. The platform proposes the space; the model chooses inside it.
    # Built from the same three sources the view was, so the shortlist
    # and the facts behind it cannot disagree — and rendered only when
    # the flag says so, because a prior nobody declared would be part of
    # the baseline it is supposed to be measured against.
    shortlist: tuple[MechanismCandidate, ...] = ()
    candidates_text = ""
    if features.candidate_shortlist:
        shortlist = generate_candidates(
            analysis.packet,
            catalog=analysis.catalog,
            available_evidence=analysis.available_evidence,
            knowledge=offered,
            traits=trait_offers(analysis.packet, traits) if features.traits and traits else (),
            verification_options=features.verification_options,
        )
        candidates_text = render_candidates(shortlist)

    # W3. The menu the model is shown, after the cards this run could
    # never serve are taken out. A tool refused at admission reads to a
    # model as a broken platform, and it spends the next turn working
    # around a wall that was never there.
    menu = analysis.catalog
    if features.filter_tool_menu:
        menu = effective_menu(
            analysis.catalog,
            available_evidence=analysis.available_evidence,
            mechanisms=[item.mechanism_id for item in shortlist],
        )
        events.append(f"menu:{len(menu.cards)}/{len(analysis.catalog.cards)}")


    if features.knowledge:
        # Counted in the transcript, both halves. "Nothing was offered"
        # and "five things were offered and none resolved" are different
        # runs, and only one of them is a retrieval problem.
        events.append(f"knowledge:{len(offered)}/{len(offered) + rejected_offers}")
    if features.traits and traits is not None:
        events.append(f"traits:{len(trait_offers(analysis.packet, traits))}")
    if features.candidate_shortlist:
        # The shortlist as it left the generator, before the model saw
        # it: ``generator_recall@K`` is scored on this and not on what
        # came back, and a count in the transcript is what makes the two
        # separable afterwards.
        events.append(f"candidates:{len(shortlist)}")
    reports: list[RoundReport] = []
    results: list[ToolResult] = []
    feedback: list[CheckFeedback] = []
    spent = RoundCost()
    seen: set[tuple[str, str, tuple[tuple[str, str], ...]]] = set()
    #: What the code route has already asked, so a second turn does not
    #: re-ask a question whose verdict is in hand.
    routed_keys: set[tuple[str, str, tuple[tuple[str, str], ...]]] = set()
    sequence = 0
    guarded: GuardResult | None = None
    stopped = "final"
    #: W4. One repair turn for a malformed answer, and one only. It is a
    #: model call and is counted as one, which is what keeps it from
    #: being a retry wearing another word: A7's rule is that a case gets
    #: one attempt, and a repair does not buy a second.
    repaired = False
    #: Statement ids that were drafts when they were declared. Nothing
    #: renders or scores these until a verdict comes back.
    drafts_declared: dict[str, str] = {}

    for attempt in range(max_revisions + 1):
        if spent.model_calls >= budget.max_model_calls:
            stopped = "budget_exceeded"
            events.append("budget:model_calls")
            break
        if (time.monotonic() - started) * 1000 >= budget.max_wall_time_ms:
            stopped = "budget_exceeded"
            events.append("budget:wall_time")
            break

        try:
            report = propose(
                analysis,
                view,
                provider,
                feedback=tuple(feedback),
                candidates_text=candidates_text,
                menu=menu,
                discriminated_union=features.discriminated_union,
                timeout_s=timeout_s,
            )
        except AnalystRefusal as refused:
            events.append(f"model_failed:{refused}")
            guarded = GuardResult(
                response=AnalysisResponse(
                    analysis_run_id=analysis.analysis_run_id,
                    analyst_bundle_id=analysis.analyst_bundle_id,
                    abstained=True,
                    abstention_reason=f"the round could not be completed: {refused}",
                )
            )
            stopped = "model_failed"
            break

        reports.append(report)
        if (
            report.dropped
            and not report.response.proposals
            and not repaired
            and spent.model_calls + 1 < budget.max_model_calls
        ):
            # Everything the model said was malformed in a way this
            # module could name. One turn to say what was wrong is
            # cheaper than an abstention nobody can act on — and it is
            # bounded at one, because a loop that repairs until it
            # parses is a loop that pays for agreement.
            repaired = True
            feedback.append(
                CheckFeedback(
                    hypothesis_id="repair",
                    tool_id="",
                    execution_status="malformed",
                    rejected_as="; ".join(report.dropped[:3]),
                )
            )
            events.append(f"repair:{len(report.dropped)}")
            spent = replace(
                spent,
                model_calls=spent.model_calls + report.cost.model_calls,
                input_tokens=spent.input_tokens + report.cost.input_tokens,
                output_tokens=spent.output_tokens + report.cost.output_tokens,
            )
            continue
        spent = replace(
            spent,
            model_calls=spent.model_calls + report.cost.model_calls,
            input_tokens=spent.input_tokens + report.cost.input_tokens,
            output_tokens=spent.output_tokens + report.cost.output_tokens,
        )
        events.append(f"proposed:{len(report.response.proposals)}")

        guarded = guard(
            report.response, view, catalog=analysis.catalog, critic=features.critic
        )
        events.extend(f"blocked:{item.rule}" for item in guarded.blocked)

        # Declare before any request. The host binds evidence to the
        # hypothesis it was gathered for, so a request that arrives
        # first is refused as unknown_hypothesis — and the refusal would
        # read as the platform being broken.
        prepared.host.declare(guarded.response)
        events.append(f"declared:{len(guarded.response.proposals)}")

        # W4's audit link. A revised statement is different content, so
        # it carries a different id — rewriting under the old one is
        # already impossible by protocol. What was missing is the line
        # that says which draft this replaced, so a reader of the
        # transcript can follow a refuted claim to what became of it.
        for proposal in guarded.response.proposals:
            key = f"{proposal.proposition_type}:{proposal.proposed_subject}"
            previous = drafts_declared.get(key)
            if previous and previous != proposal.hypothesis_id:
                events.append(f"supersedes:{previous}:{proposal.hypothesis_id}")
            if proposal.requested_checks:
                drafts_declared[key] = proposal.hypothesis_id
                events.append(f"draft:{proposal.hypothesis_id}")
            else:
                drafts_declared.pop(key, None)
                events.append(f"final:{proposal.hypothesis_id}")

        if guarded.response.abstained:
            stopped = "final"
            break

        wanted = [
            (proposal.hypothesis_id, check)
            for proposal in guarded.response.proposals
            for check in proposal.requested_checks
        ]

        # W3. The code picks the checker, **after** declare and
        # admission: the host binds evidence to the hypothesis it was
        # gathered for, so a request routed before the declaration is
        # refused as unknown_hypothesis and the refusal reads as a
        # broken platform rather than a router running early.
        #
        # This is the one flag in this layer that changes what a metric
        # *means*: with it on, ``checker_selection`` is the code's
        # choice and not the model's, and the report has to say which.
        if features.auto_route_checker:
            for proposal in guarded.response.proposals:
                if proposal.requested_checks:
                    continue
                answered = tuple(
                    (tool, arguments) for _hypothesis, tool, arguments in routed_keys
                )
                route, reason = route_for(
                    proposal,
                    catalog=analysis.catalog,
                    packet=analysis.packet,
                    available_evidence=analysis.available_evidence,
                    answered=answered,
                )
                if route is None:
                    # Four failures, counted apart: a menu that hid the
                    # tool, a run that never recorded the evidence, an
                    # argument nobody could fill, and a question already
                    # answered. One number for all four would point at
                    # no fix.
                    events.append(f"route_declined:{reason}")
                    continue
                shaped = tuple(
                    sorted((name, str(value)) for name, value in route.arguments.items())
                )
                routed_keys.add((proposal.hypothesis_id, route.tool_id, shaped))
                wanted.append((proposal.hypothesis_id, _RoutedCheck(route)))
                events.append(f"routed:{route.tool_id}:{route.chosen_by}")
        fresh = [item for item in wanted if _request_key(*item) not in seen]
        if wanted and not fresh:
            # The checkers are deterministic. Asking again buys the
            # answer already in hand, at the price of a model call.
            stopped = "no_progress"
            events.append("no_progress:same_checks_again")
            break
        if not wanted:
            stopped = "final"
            break

        if spent.input_tokens > budget.max_input_tokens or (
            spent.output_tokens > budget.max_output_tokens
        ):
            stopped = "budget_exceeded"
            events.append("budget:tokens")
            break

        for hypothesis_id, check in fresh:
            if spent.tool_requests >= budget.max_tool_requests:
                stopped = "budget_exceeded"
                events.append("budget:tool_requests")
                break
            seen.add(_request_key(hypothesis_id, check))
            sequence += 1
            request = ToolRequest(
                request_id=f"req-{sequence:03d}",
                analysis_run_id=analysis.analysis_run_id,
                case_packet_checksum=analysis.case_packet_checksum,
                tool_catalog_version=analysis.catalog.catalog_version,
                analyst_bundle_id=analysis.analyst_bundle_id,
                sequence=sequence,
                tool_id=check.tool_id,
                tool_version=check.tool_version,
                hypothesis_id=hypothesis_id,
                arguments=dict(check.arguments),
            )
            spent = replace(spent, tool_requests=spent.tool_requests + 1)
            try:
                result = prepared.host.call(request)
            except ProtocolRejection as refused:
                # An outcome, not a crash: the round continues and the
                # refusal is visible in what the host did not admit.
                events.append(f"rejected:{refused.code}")
                feedback.append(
                    CheckFeedback(
                        hypothesis_id=hypothesis_id,
                        tool_id=check.tool_id,
                        execution_status="refused",
                        rejected_as=refused.code,
                    )
                )
                continue
            results.append(result)
            events.append(f"result:{result.tool_id}:{result.execution_status}")
            feedback.append(_feedback_for(hypothesis_id, result))

        if stopped == "budget_exceeded":
            break
        if attempt == max_revisions:
            stopped = "revisions_exhausted"

    assert guarded is not None  # the loop runs at least once
    events.append(f"finalize:{stopped}")
    return RoundOutcome(
        response=guarded.response,
        guard=guarded,
        reports=tuple(reports),
        results=tuple(results),
        cost=spent,
        stopped_because=stopped,
        events=tuple(events),
        shortlist=shortlist,
    )
