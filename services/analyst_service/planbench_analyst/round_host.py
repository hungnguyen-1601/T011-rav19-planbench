"""The seam: one evidence source, and a request and a host bound to it.

The bug this shape exists to prevent is specific and was found by
reading, not by running. ``AnalysisRequest.available_evidence`` is a
frozen field defaulting to the empty set, and ``ToolSession.admit``
refuses any tool whose ``required_evidence`` is not inside it. Build the
request first and the host second — the obvious order — and the host can
be sitting on a full trace while every request dies at
``missing_required_evidence``. The analyst then reads its own round as
"the platform has nothing", which is a sentence about the platform that
is not true.

So nothing here builds a request. An :class:`EvidenceSource` is built
first, the available set is **derived** from it, and the request and the
host are both handed that same object. They cannot disagree, because
neither of them was asked.

:class:`PreparedRound` is what a runner is given: the pair, plus the
checksums that let a gate artifact say what the round was assembled
from. ``RoundSource`` is the callable the platform implements per lane —
in-process here, a container proxy at A4-iv — and the runner never knows
which one it is holding.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from planbench_explanation.budget import PLATFORM_BUDGET_CAP, AnalysisBudget
from planbench_explanation.bundle import AnalystBundle
from planbench_explanation.case_packet import CasePacket
from planbench_explanation.integration import (
    PRE_SIDECAR_AVAILABLE_EVIDENCE,
    TYPICAL_AVAILABLE_EVIDENCE,
    MockToolHost,
)
from planbench_explanation.packet_artifact import PacketArtifact
from planbench_explanation.protocol import (
    AnalysisRequest,
    AnalysisResponse,
    ToolRequest,
    ToolResult,
    ToolSession,
)
from planbench_explanation.tools import ToolCatalog
from planbench_explanation.versioning import artifact_checksum

__all__ = [
    "EvidenceSource",
    "PreparedRound",
    "RoundHostProtocol",
    "RoundSource",
    "evidence_for",
    "in_process_round",
]


class RoundHostProtocol(Protocol):
    """What a runner may do to a host, and nothing else.

    Two verbs. The session behind them belongs to the host — a runner
    that could reach it could declare a proposal without the host
    admitting it, which is the accounting the score is read from.
    """

    def declare(self, response: AnalysisResponse) -> None: ...

    def call(self, request: ToolRequest) -> ToolResult: ...


@dataclass(frozen=True)
class EvidenceSource:
    """What this run recorded, as one object both halves are built from."""

    packet: CasePacket
    available_evidence: frozenset[str]
    #: Whether the planning-input sidecar was attached to the run. The
    #: replay-based checks are simply not servable without it, and an
    #: analyst that assumes otherwise finds out at admission.
    sidecar_present: bool

    @property
    def identity_checksum(self) -> str:
        """What the round was assembled from, as one value a gate can store."""
        return artifact_checksum(
            {
                "packet": self.packet.model_dump(mode="json"),
                "available_evidence": sorted(self.available_evidence),
                "sidecar_present": self.sidecar_present,
            }
        )


def evidence_for(packet: CasePacket, *, sidecar_present: bool) -> EvidenceSource:
    """Derive the available set rather than accept one.

    A caller that passes its own set is a caller that can widen it, and
    the party most motivated to widen it is the one being graded: every
    tool then admits, the checkers return ``not_checkable``, and the
    round looks like a platform failure rather than a request that
    should never have been made.
    """
    available = set(
        TYPICAL_AVAILABLE_EVIDENCE if sidecar_present else PRE_SIDECAR_AVAILABLE_EVIDENCE
    )
    if packet.task.route is None:
        # No route was measured against the map, so the geometry a
        # clearance check needs does not exist for this run.
        available -= {"region_geometry"}
    if packet.task.robot.inflation_margin_m is None:
        available -= {"inflation_parameters", "inflation_implementation_version"}
    if packet.decision.waterfall is None:
        # Nobody was ranked, so there is no pair and no per-episode
        # utility to decompose.
        available -= {"comparison_pair", "episode_decision_utility"}
    return EvidenceSource(
        packet=packet,
        available_evidence=frozenset(available),
        sidecar_present=sidecar_present,
    )


@dataclass(frozen=True)
class PreparedRound:
    """A request and a host that were built from the same evidence."""

    analysis: AnalysisRequest
    host: RoundHostProtocol
    effective_budget: AnalysisBudget
    requested_budget_checksum: str
    effective_budget_checksum: str
    #: Proof the pair came from one source. A gate artifact stores it so
    #: "this round was assembled from that evidence" is checkable later
    #: rather than assumed.
    evidence_identity_checksum: str


#: How the platform prepares one round for one case. In-process below;
#: the container lane at A4-iv implements the same signature, and the
#: runner cannot tell them apart.
RoundSource = Callable[[PacketArtifact | CasePacket, AnalystBundle], PreparedRound]


class InProcessHost:
    """The dev lane: the platform's own host, called directly.

    Wraps :class:`~planbench_explanation.integration.MockToolHost`
    rather than reimplementing admission, because two implementations of
    "may this tool run" is two answers waiting to disagree — and the one
    that would be wrong is the one nobody graded against.
    """

    def __init__(self, analysis: AnalysisRequest) -> None:
        self._host = MockToolHost(analysis)

    @property
    def session(self) -> ToolSession:
        return self._host.session

    def declare(self, response: AnalysisResponse) -> None:
        self._host.session.declare(response)

    def call(self, request: ToolRequest) -> ToolResult:
        return self._host.call(request)


def in_process_round(
    supplied: PacketArtifact | CasePacket,
    bundle: AnalystBundle,
    *,
    catalog: ToolCatalog,
    analysis_run_id: str,
    budget_cap: AnalysisBudget = PLATFORM_BUDGET_CAP,
) -> PreparedRound:
    """Prepare one round in this process, from one evidence source.

    The sidecar flag is read from the artifact's provenance when there
    is one. A bare packet is assumed to have **no** sidecar: assuming
    otherwise would hand the analyst replay tools the run cannot serve,
    and the honest default when provenance is missing is the smaller set.
    """
    if isinstance(supplied, PacketArtifact):
        packet = supplied.packet
        sidecar = supplied.provenance.sidecar_present
    else:
        packet = supplied
        sidecar = False

    source = evidence_for(packet, sidecar_present=sidecar)
    analysis = AnalysisRequest(
        analysis_run_id=analysis_run_id,
        analyst_bundle_id=bundle.bundle_id,
        packet=source.packet,
        catalog=catalog,
        available_evidence=source.available_evidence,
        max_tool_requests=bundle.requested_budget.capped_by(budget_cap).max_tool_requests,
    )
    effective = bundle.requested_budget.capped_by(budget_cap)
    return PreparedRound(
        analysis=analysis,
        host=InProcessHost(analysis),
        effective_budget=effective,
        requested_budget_checksum=bundle.requested_budget.checksum,
        effective_budget_checksum=effective.checksum,
        evidence_identity_checksum=source.identity_checksum,
    )
