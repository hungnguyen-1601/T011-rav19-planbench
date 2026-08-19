"""A tool host and an analyst the AI team can build against today — E5.

The real host and the real checkers are E6. The AI team cannot wait for
them: integration work — request shapes, sequencing, rejection handling,
what a ``not_checkable`` looks like coming back — is most of the effort
and none of it needs a working checker.

So this module ships two stubs that are honest about being stubs.

:class:`MockToolHost` admits requests through the real
:class:`~planbench_explanation.protocol.ToolSession` — the same
admission rules, the same rejection codes, the same card lookups — and
then serves fact queries and navigation from the packet, which really
does hold that data. Mechanism checks come back ``not_checkable`` with
``failure_code="checker_not_implemented"``. That is the truthful answer
today and, more usefully, it is a shape the analyst has to handle
anyway: a checker that cannot run is an ordinary outcome in production,
not a mock artefact.

:func:`reference_analyst` is a deterministic analyst with no model in
it. It reads the packet's observations, proposes the mechanism each
detection is consistent with, asks for the checks those hypotheses need,
and abstains when there is nothing to see. It exists to be the *floor*:
a submitted bundle that does not beat it on the visible suite has not
demonstrated that its model is contributing anything. It is not a
baseline to copy — it proposes from detections without weighing them,
which is precisely the shallow reading a real analyst should improve on.

**Nothing here is graded.** The gate runs a submitted bundle in a
platform environment (E6). These are integration fixtures.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from planbench_explanation.catalog import TOOL_CATALOG
from planbench_explanation.detectors import Observation
from planbench_explanation.ledger import EvidenceRef, HypothesisProposal, RequestedCheck
from planbench_explanation.propositions import PropositionType
from planbench_explanation.protocol import (
    AnalysisRequest,
    AnalysisResponse,
    EvidenceReference,
    ProtocolRejection,
    ToolRequest,
    ToolResult,
    ToolSession,
    stamped_result,
)
from planbench_explanation.subjects import Subject
from planbench_explanation.tools import ToolCard
from planbench_explanation.versioning import artifact_checksum

#: What a detection is *consistent with* — not what it proves — and the
#: next tool to reach for. The mapping is one-to-one and dull because
#: the reference analyst is meant to be a floor, not a good analyst: a
#: real one weighs the map, the contrast and the decomposition before
#: choosing.
#:
#: The tool named is the one whose arguments this stub can **actually
#: fill** from a detection. ``narrow_gap_refusal`` points at measuring
#: the route rather than at ``gap_vs_footprint``, because the gap check
#: needs a region id and an observation does not carry one — inventing a
#: plausible ``region_id`` to make the call go through is the failure
#: this layer exists to prevent, in miniature.
DETECTION_HYPOTHESES: dict[str, tuple[PropositionType, Subject, str]] = {
    "narrow_gap_refusal": (
        "geometric_infeasibility",
        "costmap_inflation",
        "get_map_region_features",
    ),
    "stuck_cluster": (
        "local_minimum_entrapment",
        "local_controller",
        "get_episode_observations",
    ),
    "oscillation": (
        "local_minimum_entrapment",
        "local_controller",
        "get_episode_observations",
    ),
    "detour": (
        "sampling_budget_insufficiency",
        "global_planner",
        "rrt_convergence",
    ),
    "latency_spike": (
        "expansion_latency_association",
        "global_planner",
        "latency_vs_expanded_nodes",
    ),
    "replan_storm": (
        "replan_instability",
        "global_planner",
        "latency_vs_expanded_nodes",
    ),
}

#: The mechanism check each hypothesis would ultimately need, and the
#: argument it is short of. Reported as ``missing_evidence`` rather than
#: guessed at.
BLOCKED_BY_ARGUMENT: dict[str, tuple[str, str]] = {
    "narrow_gap_refusal": ("gap_vs_footprint", "region_id"),
}


def _arguments_for(card: ToolCard, observation: Observation) -> dict[str, object] | None:
    """Arguments this stub can honestly supply, or ``None`` if it cannot.

    ``None`` is a real answer: an analyst that cannot name the arguments
    a tool needs has not earned the call, and filling them with
    plausible values is how a checker ends up answering about a passage
    nobody looked at.
    """
    arguments: dict[str, object] = {}
    for spec in card.io.arguments:
        if spec.name == "candidate_id":
            arguments[spec.name] = observation.candidate_id
        elif spec.name == "episode_context_id":
            if observation.worst_episode_context_id is None:
                if spec.required:
                    return None
                continue
            arguments[spec.name] = observation.worst_episode_context_id
        elif spec.required:
            return None
    return arguments


#: The evidence keys a run built by this repository's own pipeline holds
#: today. Handed to :class:`~planbench_explanation.protocol.AnalysisRequest`
#: so integration sees realistic admission failures rather than a host
#: that can serve everything.
TYPICAL_AVAILABLE_EVIDENCE = frozenset(
    {
        "comparison_pair",
        "episode_decision_utility",
        "preference_profile",
        "candidate_components",
        "map_checksum",
        "region_geometry",
        "robot_footprint",
        "inflation_parameters",
        "inflation_implementation_version",
        "task_profile_id",
        "detector_version",
        "trace",
        "reference_line",
        "episode_expanded_nodes",
        "episode_latency",
    }
)

#: What a run recorded before the planning-input sidecar can offer. The
#: replay-based checks are simply not servable, and an analyst that
#: assumes otherwise finds out at admission.
PRE_SIDECAR_AVAILABLE_EVIDENCE = TYPICAL_AVAILABLE_EVIDENCE - {"trace", "reference_line"}


class MockToolHost:
    """A host with real admission and stub execution."""

    #: Named so a reader of a transcript can tell mock output from a
    #: real checker's at a glance.
    IMPLEMENTATION_REF = "sha256:" + "0" * 64

    def __init__(self, analysis: AnalysisRequest) -> None:
        self.session = ToolSession(analysis)
        self.analysis = analysis

    def call(self, request: ToolRequest) -> ToolResult:
        """Admit, execute, record. Rejections propagate untouched."""
        card = self.session.admit(request)
        result = self._execute(card, request)
        self.session.record(result)
        return result

    def _execute(self, card: ToolCard, request: ToolRequest) -> ToolResult:
        if card.tool_class == "mechanism_check":
            return stamped_result(
                card,
                request,
                execution_status="not_checkable",
                input_provenance="missing",
                failure_code="checker_not_implemented",
            )
        served = self._serve(card)
        if served is None:
            # The honest answer for a tool whose data the packet does not
            # carry. Returning zeros with a completed status would be a
            # stub inventing evidence, which is the one thing a stub of
            # this system must not do.
            return stamped_result(
                card,
                request,
                execution_status="not_checkable",
                input_provenance="missing",
                failure_code="tool_unavailable",
            )
        measurements, references = served
        return stamped_result(
            card,
            request,
            execution_status="completed",
            input_provenance="recorded",
            measurements=measurements,
            references=references,
            evidence_artifact_ref=f"mock://{card.tool_id}/{request.request_id}",
            evidence_checksum=artifact_checksum(
                {
                    "tool": card.tool_id,
                    "request": request.request_id,
                    "measurements": measurements,
                    "references": [reference.model_dump() for reference in references],
                }
            ),
            implementation_ref=self.IMPLEMENTATION_REF,
        )

    def _serve(
        self, card: ToolCard
    ) -> tuple[dict[str, float], tuple[EvidenceReference, ...]] | None:
        """What the packet can actually answer, or ``None``.

        ``None`` where the packet does not hold the data — the trace
        tools, mostly. The card says which measurements a completed
        result owes, and a stub that cannot produce them says so rather
        than filling in zeros.
        """
        packet = self.analysis.packet
        if card.tool_id == "get_objective_decomposition":
            waterfall = packet.decision.waterfall
            contributions = {
                f"contribution_{bar.objective.lower()}": bar.contribution for bar in waterfall.bars
            }
            return (
                {
                    "delta_utility_mean": waterfall.delta_utility_mean,
                    "delta_utility_median": waterfall.delta_utility_median,
                    "n_episodes": float(waterfall.n_episodes),
                    **contributions,
                },
                (),
            )
        if card.tool_id == "get_candidate_contrast":
            # The lattice names a component only in the two verdicts that
            # are about one; the refusals name none, and counting them as
            # an axis would report attribution where the reading declined
            # to attribute.
            axes = {finding.subject for finding in packet.lattice if finding.subject is not None}
            return (
                {
                    "n_findings": float(len(packet.lattice)),
                    "n_differing_axes": float(len(axes)),
                },
                (),
            )
        if card.tool_id == "get_known_unknowns":
            blocked = {
                kind for unknown in packet.known_unknowns for kind in unknown.blocks_claim_types
            }
            return (
                {
                    "n_known_unknowns": float(len(packet.known_unknowns)),
                    "n_blocked_claim_types": float(len(blocked)),
                },
                (),
            )
        if card.tool_id == "get_episode_observations":
            if not packet.observations:
                return None
            first = packet.observations[0]
            episodes = tuple(
                EvidenceReference(
                    kind="episode",
                    ref=f"episode:{observation.worst_episode_context_id}",
                    label=f"worst {observation.type}",
                )
                for observation in packet.observations
                if observation.worst_episode_context_id is not None
            )
            if not episodes:
                return None
            return (
                {
                    "n_observations": float(len(packet.observations)),
                    "episodes_seen": float(first.episodes_seen),
                    "episodes_total": float(first.episodes_total),
                    "prevalence": first.prevalence,
                },
                episodes,
            )
        if card.tool_id == "find_exemplar_episodes":
            chosen = packet.representative_episodes
            if chosen is None or not chosen.exemplars:
                return None
            return (
                {"n_exemplars": float(len(chosen.exemplars))},
                tuple(
                    EvidenceReference(
                        kind="episode",
                        ref=f"episode:{exemplar.episode_context_id}",
                        label=exemplar.role,
                    )
                    for exemplar in chosen.exemplars
                ),
            )
        return None


def _observations_by_type(observations: Iterable[Observation]) -> dict[str, Observation]:
    """First observation of each type, in the packet's order.

    One hypothesis per detection type rather than per detection: six
    stalls in one run are one thing to explain, and proposing six
    hypotheses about them would score as six chances at precision.
    """
    seen: dict[str, Observation] = {}
    for observation in observations:
        seen.setdefault(observation.type, observation)
    return seen


def reference_analyst(analysis: AnalysisRequest) -> AnalysisResponse:
    """A deterministic floor: propose what the detections are consistent with.

    Abstains when the packet holds no detection, which is the correct
    answer on the negative-control family and the reason this stub is
    worth keeping around: any analyst that cannot beat "abstain unless
    something was detected" is not adding anything a filter could not.
    """
    packet = analysis.packet
    blocked = {kind for unknown in packet.known_unknowns for kind in unknown.blocks_claim_types}

    proposals: list[HypothesisProposal] = []
    for index, (detection_type, observation) in enumerate(
        _observations_by_type(packet.observations).items(), start=1
    ):
        mapped = DETECTION_HYPOTHESES.get(detection_type)
        if mapped is None:
            continue
        proposition, subject, tool_id = mapped
        if proposition in blocked:
            # The packet says this cannot be claimed here. Proposing it
            # anyway is the blocked-claim leak the suite counts.
            continue
        try:
            card = analysis.catalog.card(tool_id, "1.0.0")
        except Exception:  # pragma: no cover - catalog is fixed in practice
            continue
        arguments = _arguments_for(card, observation)
        gaps = sorted(set(card.required_evidence) - analysis.available_evidence)
        blocked = BLOCKED_BY_ARGUMENT.get(detection_type)
        if blocked is not None:
            gaps.append(f"{blocked[1]} for {blocked[0]}")
        if arguments is None:
            gaps.append(f"arguments for {card.tool_id}")
        proposals.append(
            HypothesisProposal(
                hypothesis_id=f"hyp-{index:03d}",
                hypothesis_statement=(
                    f"the {detection_type} seen on {observation.candidate_id} in "
                    f"{observation.episodes_seen} of {observation.episodes_total} episodes "
                    f"is consistent with {proposition.replace('_', ' ')}"
                ),
                proposition_type=proposition,
                proposed_subject=subject,
                supports=(
                    EvidenceRef(
                        ref=f"obs:{detection_type}:{observation.candidate_id}",
                        kind="observation",
                    ),
                ),
                missing_evidence=tuple(gaps),
                requested_checks=()
                if arguments is None
                else (
                    RequestedCheck(
                        tool_id=card.tool_id,
                        tool_version=card.tool_version,
                        arguments=arguments,
                    ),
                ),
            )
        )

    if not proposals:
        return AnalysisResponse(
            analysis_run_id=analysis.analysis_run_id,
            analyst_bundle_id=analysis.analyst_bundle_id,
            abstained=True,
            abstention_reason=(
                "no detection in this packet maps to a mechanism this catalog can "
                "check, or every candidate mechanism is blocked by a declared gap"
            ),
        )
    return AnalysisResponse(
        analysis_run_id=analysis.analysis_run_id,
        analyst_bundle_id=analysis.analyst_bundle_id,
        proposals=tuple(proposals),
    )


def run_round(
    analysis: AnalysisRequest,
    analyst: Callable[[AnalysisRequest], AnalysisResponse] = reference_analyst,
    *,
    host: MockToolHost | None = None,
) -> tuple[AnalysisResponse, MockToolHost]:
    """Drive one round: analyst proposes, host serves every requested check.

    The host is returned alongside the response because the *session* is
    half the evidence about what happened — which tools were asked for,
    in what order, and which were refused. Scoring reads the session's
    account rather than the analyst's.
    """
    running = host or MockToolHost(analysis)
    response = analyst(analysis)
    running.session.declare(response)

    sequence = 0
    for proposal in response.proposals:
        for check in proposal.requested_checks:
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
                hypothesis_id=proposal.hypothesis_id,
                arguments=dict(check.arguments),
            )
            try:
                running.call(request)
            except ProtocolRejection:
                # A refused request is an outcome, not a crash: the round
                # continues and the refusal is visible in what the
                # session did *not* admit.
                continue
    return response, running


def open_round(
    packet_analysis_run_id: str,
    *,
    packet,  # noqa: ANN001 - CasePacket, imported lazily to avoid a cycle
    bundle_id: str,
    available_evidence: frozenset[str] = TYPICAL_AVAILABLE_EVIDENCE,
) -> AnalysisRequest:
    """Open a round against the shipped catalog. Convenience for integration."""
    return AnalysisRequest(
        analysis_run_id=packet_analysis_run_id,
        analyst_bundle_id=bundle_id,
        packet=packet,
        catalog=TOOL_CATALOG,
        available_evidence=available_evidence,
    )
