"""The tool host: admission, evidence, execution, signature — E6a.

E5 built the protocol and a mock that answered from the packet. This is
the real thing: the same :class:`~planbench_explanation.protocol.ToolSession`
admission, evidence fetched from a declared source, checkers run, and
results stamped with the card's refusals and the build that produced
them.

**Three responsibilities, kept apart on purpose.**

*Admission* is the session's, and this module does not re-implement any
of it. *Evidence* is an :class:`EvidenceSource`'s — a narrow protocol
with one method per thing a tool needs, so a host can be pointed at a
run directory, at a test fixture, or at nothing without any tool
knowing. *Checking* is :mod:`planbench_explanation.checkers`', which are
pure functions that never learn their request id or their card. The host
is the only place the three meet, and it is the only place that may
produce a :class:`~planbench_explanation.protocol.ToolResult`.

**Absence has a code, never a zero.** Every path where the evidence is
not there returns ``not_checkable`` with a failure code from the card or
from :data:`~planbench_explanation.protocol.HOST_FAILURE_CODES`. Two of
the four mechanism checks are in that state permanently for now:
``replay_global_plan`` and ``rrt_convergence`` need planning inputs
recorded as the run happened, which is the E4.5 sidecar and does not
exist. They report ``checker_not_implemented``, which is the truth, and
they will keep reporting it until there is something to replay from
rather than something to reconstruct.

**The host signs with its own build, and that is a real limitation.**
``implementation_ref`` names the code that produced a result, and here
it is whatever the caller declares the platform build to be. Within one
process that is a statement of intent rather than proof; what actually
binds a result to a run is the session's admitted request. The signature
becomes load-bearing when results cross a process boundary, and this
module is where that will need doing.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Protocol

from planbench_explanation.checkers import (
    CheckerRefusal,
    CheckOutcome,
    EpisodeSearchCost,
    GapEvidence,
    LatencyEvidence,
    check_gap_vs_footprint,
    check_latency_vs_expanded_nodes,
)
from planbench_explanation.ledger import PropositionOutcome
from planbench_explanation.map_features import RouteFeatures
from planbench_explanation.protocol import (
    AnalysisRequest,
    EvidenceReference,
    ToolRequest,
    ToolResult,
    ToolSession,
    stamped_result,
)
from planbench_explanation.provenance import InputProvenance
from planbench_explanation.tools import ToolCard
from planbench_explanation.versioning import artifact_checksum

#: Checks whose evidence the platform does not record yet. Named here so
#: the gap is one list rather than a condition scattered through the
#: dispatch, and so removing one is a visible diff.
AWAITING_SIDECAR: frozenset[str] = frozenset({"replay_global_plan", "rrt_convergence"})


class EvidenceSource(Protocol):
    """Where a host gets what a tool needs.

    One method per tool's evidence rather than a general "give me the
    run": a source that can hand over anything is a source no tool's
    requirements are written down against, and the point of the cards is
    that they are.

    Returning ``None`` means *this run does not hold it*, which the host
    turns into ``not_checkable``. Raising means the source itself is
    broken, which is a different thing and should not be mistaken for
    evidence being absent.
    """

    def gap_evidence(self, *, candidate_id: str, region_id: str) -> GapEvidence | None: ...

    def latency_evidence(self, *, candidate_id: str) -> LatencyEvidence | None: ...


class PacketEvidence:
    """Fact queries answered from the case packet, checks from nothing.

    The packet is the analyst's view and it holds no map and no
    per-episode search costs, so both mechanism checks come back
    unavailable. Useful for exercising a round end to end without a run
    on disk, and honest about what it cannot do.
    """

    def gap_evidence(self, *, candidate_id: str, region_id: str) -> GapEvidence | None:
        return None

    def latency_evidence(self, *, candidate_id: str) -> LatencyEvidence | None:
        return None


class ReportEvidence:
    """Evidence read off a scoring report and a measured map.

    The report is where the columns the latency check needs live, written
    per episode at scoring time: ``peak_search_nodes``,
    ``peak_tree_nodes`` and ``p99_latency_ms``.

    **The two node columns are not added together.** HĐ-6 separates a
    grid search's expanded nodes from a sampling planner's tree size
    because they count different things, and a candidate uses one or the
    other. This picks whichever column the candidate's episodes actually
    populate, and refuses when both are populated — a candidate reporting
    both is one this reader does not understand, and guessing which
    number is the search would be inventing the measurement.

    Latency is ``p99_latency_ms``, the pooled control-tick figure. Every
    replan writes its own control-step row carrying the global planner's
    latency (HĐ-6's ``replan_count`` note), so an episode with a large
    search shows it there. It is a p99 over ticks rather than the
    search's own wall time, which is one more reason the card's ceiling
    is ``associated``.

    The map side takes an already-measured
    :class:`~planbench_explanation.map_features.RouteFeatures` per
    region rather than a grid, because measuring a route is E3's job and
    doing it twice would be two answers to one question.
    """

    def __init__(
        self,
        report: Mapping[str, object],
        *,
        regions: Mapping[tuple[str, str], RouteFeatures] = MappingProxyType({}),
        robot_radius_m: float,
        inflation_radius_m: float,
    ) -> None:
        self.report = report
        self.regions = regions
        self.robot_radius_m = robot_radius_m
        self.inflation_radius_m = inflation_radius_m

    def gap_evidence(self, *, candidate_id: str, region_id: str) -> GapEvidence | None:
        features = self.regions.get((candidate_id, region_id))
        if features is None:
            return None
        return GapEvidence(
            region_id=region_id,
            features=features,
            robot_radius_m=self.robot_radius_m,
            inflation_radius_m=self.inflation_radius_m,
        )

    def latency_evidence(self, *, candidate_id: str) -> LatencyEvidence | None:
        rows = self._episode_rows(candidate_id)
        column = self._node_column(rows)
        if column is None:
            return None
        episodes = []
        for row in rows:
            nodes = row.get(column)
            latency = row.get("p99_latency_ms")
            context = row.get("episode_context_id")
            if nodes is None or latency is None or not context:
                continue
            episodes.append(
                EpisodeSearchCost(
                    episode_context_id=str(context),
                    expanded_nodes=int(nodes),
                    planner_latency_ms=float(latency),
                )
            )
        if not episodes:
            return None
        return LatencyEvidence(candidate_id=candidate_id, episodes=tuple(episodes))

    @staticmethod
    def _node_column(rows: Sequence[Mapping[str, object]]) -> str | None:
        """Which of the two node columns this candidate populates.

        ``None`` when neither does — nothing to rank — and also when
        both do, because a candidate reporting a grid frontier *and* a
        sampling tree is one this reader has no rule for, and picking
        one would be a guess presented as a measurement.
        """
        search = any(_positive(row.get("peak_search_nodes")) for row in rows)
        tree = any(_positive(row.get("peak_tree_nodes")) for row in rows)
        if search and tree:
            return None
        if search:
            return "peak_search_nodes"
        if tree:
            return "peak_tree_nodes"
        return None

    def _episode_rows(self, candidate_id: str) -> list[Mapping[str, object]]:
        candidates = self.report.get("candidates")
        if not isinstance(candidates, list):
            return []
        for entry in candidates:
            if not isinstance(entry, Mapping) or entry.get("candidate_id") != candidate_id:
                continue
            episodes = entry.get("episodes")
            if isinstance(episodes, list):
                return [row for row in episodes if isinstance(row, Mapping)]
        return []


class ToolHost:
    """Serves one analysis round against one evidence source."""

    def __init__(
        self,
        analysis: AnalysisRequest,
        evidence: EvidenceSource,
        *,
        implementation_ref: str,
        input_provenance: InputProvenance = "recorded",
    ) -> None:
        self.session = ToolSession(analysis)
        self.analysis = analysis
        self.evidence = evidence
        self.implementation_ref = implementation_ref
        self.input_provenance = input_provenance

    def call(self, request: ToolRequest) -> ToolResult:
        """Admit, execute, record. Rejections propagate untouched.

        A rejection is not converted into a failed result: "the host
        would not accept this request" and "the check ran and could not
        answer" are different facts, and collapsing them would let an
        analyst read a malformed request as evidence of absence.
        """
        card = self.session.admit(request)
        result = self._execute(card, request)
        self.session.record(result)
        return result

    def _execute(self, card: ToolCard, request: ToolRequest) -> ToolResult:
        if card.tool_id in AWAITING_SIDECAR:
            return self._unavailable(card, request, "checker_not_implemented")
        if card.tool_id == "gap_vs_footprint":
            return self._gap(card, request)
        if card.tool_id == "latency_vs_expanded_nodes":
            return self._latency(card, request)
        return self._unavailable(card, request, "tool_unavailable")

    # -- the two checks this platform can run ----------------------------

    def _gap(self, card: ToolCard, request: ToolRequest) -> ToolResult:
        evidence = self.evidence.gap_evidence(
            candidate_id=str(request.arguments["candidate_id"]),
            region_id=str(request.arguments["region_id"]),
        )
        if evidence is None:
            return self._unavailable(card, request, "region_not_resolved")
        try:
            outcome = check_gap_vs_footprint(evidence)
        except CheckerRefusal:
            # The map never bounded the route on both sides, so the only
            # figure is a lower bound — which cannot show a passage is
            # too narrow. Reported as ambiguous geometry, not as a width.
            return self._unavailable(card, request, "ambiguous_passage_geometry")
        return self._completed(
            card,
            request,
            outcome,
            references=(
                EvidenceReference(
                    kind="map_region",
                    ref=f"region:{evidence.region_id}",
                    label="the passage the check measured",
                ),
            ),
        )

    def _latency(self, card: ToolCard, request: ToolRequest) -> ToolResult:
        evidence = self.evidence.latency_evidence(
            candidate_id=str(request.arguments["candidate_id"])
        )
        if evidence is None:
            return self._unavailable(card, request, "expansion_counts_missing")
        try:
            outcome = check_latency_vs_expanded_nodes(evidence)
        except CheckerRefusal as error:
            code = (
                "no_variation_to_rank"
                if "same expanded-node" in str(error)
                else "insufficient_episodes"
            )
            return self._unavailable(card, request, code)
        return self._completed(card, request, outcome)

    # -- shaping ---------------------------------------------------------

    def _completed(
        self,
        card: ToolCard,
        request: ToolRequest,
        outcome: CheckOutcome,
        *,
        references: tuple[EvidenceReference, ...] = (),
    ) -> ToolResult:
        artifact = {
            "tool": card.key,
            "request": request.request_id,
            "measurements": outcome.measurements,
            "note": outcome.note,
        }
        return stamped_result(
            card,
            request,
            execution_status="completed",
            input_provenance=self.input_provenance,
            proposition_verdict=outcome.verdict,
            supported_propositions=(
                PropositionOutcome(
                    proposition_id=f"{outcome.proposition_type}:{request.request_id}",
                    proposition_type=outcome.proposition_type,
                    result=outcome.verdict,
                ),
            ),
            measurements=outcome.measurements,
            references=references,
            evidence_artifact_ref=(f"artifacts/explain/{card.tool_id}/{request.request_id}.json"),
            evidence_checksum=artifact_checksum(artifact),
            implementation_ref=self.implementation_ref,
        )

    def _unavailable(self, card: ToolCard, request: ToolRequest, code: str) -> ToolResult:
        return stamped_result(
            card,
            request,
            execution_status="not_checkable",
            input_provenance="missing",
            failure_code=code,
        )


def _positive(value: object) -> bool:
    """A node count that says something happened."""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0
