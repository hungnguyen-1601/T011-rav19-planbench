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

So nothing here builds a request. A :class:`RoundEvidence` is built
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

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Protocol

from planbench_analyst.identity import source_manifest_hash
from planbench_explanation.budget import PLATFORM_BUDGET_CAP, AnalysisBudget
from planbench_explanation.bundle import AnalystBundle
from planbench_explanation.case_packet import CasePacket
from planbench_explanation.host import (
    ROUTE_REGION_ID,
    EvidenceSink,
    InMemoryEvidenceSink,
    ReportEvidence,
    ToolHost,
)
from planbench_explanation.integration import (
    PRE_SIDECAR_AVAILABLE_EVIDENCE,
    TYPICAL_AVAILABLE_EVIDENCE,
)
from planbench_explanation.packet_artifact import PacketArtifact
from planbench_explanation.protocol import (
    AnalysisRequest,
    AnalysisResponse,
    ToolRequest,
    ToolResult,
    ToolSession,
)
from planbench_explanation.replay import ReplayPlanner
from planbench_explanation.tools import ToolCatalog
from planbench_explanation.versioning import artifact_checksum

__all__ = [
    "SIDECAR_EVIDENCE",
    "platform_implementation_ref",
    "InProcessHost",
    "RoundEvidence",
    "PreparedRound",
    "RoundHostProtocol",
    "RoundSource",
    "evidence_for",
    "in_process_round",
]


#: Where the checker code this host runs actually lives. Resolved once
#: per process: hashing the tree is cheap but not free, and the tree does
#: not change under a running round.
_IMPLEMENTATION_GLOBS: tuple[str, ...] = (
    "packages/explanation/planbench_explanation/*.py",
)


@lru_cache(maxsize=1)
def platform_implementation_ref() -> str:
    """A ref for the build whose checkers signed a result.

    Content, not a version string somebody remembers to bump: a result
    says which code produced it, and ``MockToolHost``'s answer to that
    question was sixty-four zeros. Falls back to naming the absence
    rather than to a placeholder that reads like a real build.
    """
    root = Path(__file__).resolve().parents[3]
    digest = source_manifest_hash(root, globs=_IMPLEMENTATION_GLOBS)
    return f"sha256:{digest[7:]}" if digest.startswith("sha256:") else f"sha256:{digest}"


class RoundHostProtocol(Protocol):
    """What a runner may do to a host, and nothing else.

    Two verbs. The session behind them belongs to the host — a runner
    that could reach it could declare a proposal without the host
    admitting it, which is the accounting the score is read from.
    """

    def declare(self, response: AnalysisResponse) -> None: ...

    def call(self, request: ToolRequest) -> ToolResult: ...


@dataclass(frozen=True)
class RoundEvidence:
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


#: The evidence a planning-input sidecar carries, in the cards' own
#: vocabulary. Named here because the seam is where "this run recorded
#: it" is decided; the host still answers ``planning_inputs_missing``
#: when the file for a particular episode is not there.
SIDECAR_EVIDENCE: frozenset[str] = frozenset(
    {
        "planning_inputs",
        "planner_parameters",
        "planner_implementation_version",
        "seed_set",
    }
)


def evidence_for(packet: CasePacket, *, sidecar_present: bool) -> RoundEvidence:
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
    if sidecar_present:
        # What the sidecar is: the query the planner was handed, the
        # configuration it ran under, the build that ran it and the seed
        # it drew from. The typical set never named them, so the two
        # replay checks were refused at admission on every run whether or
        # not the file existed — a menu that offered a check nothing
        # could reach, which reads to an analyst as the platform having
        # no answer rather than as the analyst not asking.
        available |= SIDECAR_EVIDENCE
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
    if not packet.measurements:
        # M1's block is absent, so there is nothing for
        # ``get_candidate_measurements`` to read. Derived from the
        # packet like every other token here: a run that recorded no
        # measurements and a run whose measurements nobody attached look
        # the same to an analyst, and both should be refused at
        # admission rather than answered with an empty result.
        available -= {"candidate_measurements"}
    if not packet.timelines:
        # M2's block is absent. A packet may carry measurements and no
        # timelines — the exemplar traces are the expensive half — so
        # the two are withheld separately rather than together.
        available -= {"episode_timeline"}
    return RoundEvidence(
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

    Wraps :class:`~planbench_explanation.host.ToolHost` — the real one,
    with the four mechanism checkers behind it — rather than the stub
    that answered ``checker_not_implemented`` to every check. A lane
    measured against a stub measures whether the analyst *asks* for
    verification, never whether asking gets it, and the two numbers were
    being read as one.

    Admission is still the host's :class:`ToolSession`. Two
    implementations of "may this tool run" is two answers waiting to
    disagree, and the one that would be wrong is the one nobody graded
    against.

    ``replay_planner`` stays an argument. The planner that re-runs a
    recorded query lives in the simulator, and this module ships inside
    the analyst image: importing it here would put the whole simulator
    behind an import the container cannot satisfy. A host built without
    one answers ``checker_not_implemented`` for the two replay checks,
    which is what it is.
    """

    def __init__(
        self,
        analysis: AnalysisRequest,
        evidence: ReportEvidence,
        *,
        implementation_ref: str,
        sink: EvidenceSink | None = None,
        replay_planner: ReplayPlanner | None = None,
    ) -> None:
        self._host = ToolHost(
            analysis,
            evidence,
            implementation_ref=implementation_ref,
            sink=sink or InMemoryEvidenceSink(),
            replay_planner=replay_planner,
        )

    @property
    def session(self) -> ToolSession:
        return self._host.session

    def declare(self, response: AnalysisResponse) -> None:
        self._host.session.declare(response)

    def call(self, request: ToolRequest) -> ToolResult:
        return self._host.call(request)


def _route_regions(packet: CasePacket) -> dict[tuple[str, str], object]:
    """The packet's one measured route, under the id the host resolves.

    The same rule ``ReportEvidence.from_packet`` follows, lifted out so a
    fixture that also carries a report keeps the geometry the analyst was
    shown rather than losing it to the report path.
    """
    route = packet.task.route
    if route is None:
        return {}
    return {(candidate.candidate_id, ROUTE_REGION_ID): route for candidate in packet.candidates}


def in_process_round(
    supplied: PacketArtifact | CasePacket,
    bundle: AnalystBundle,
    *,
    catalog: ToolCatalog,
    analysis_run_id: str,
    budget_cap: AnalysisBudget = PLATFORM_BUDGET_CAP,
    implementation_ref: str | None = None,
    sink: EvidenceSink | None = None,
    sidecar_directory: Path | None = None,
    sidecar_directories: Mapping[str, Path] = MappingProxyType({}),
    replay_planner: ReplayPlanner | None = None,
    report: Mapping[str, object] | None = None,
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
    # Built from the same packet the request is built from, and pointed
    # at the same run's sidecars. A second packet here would be a host
    # answering about a different run in the analyst's own round.
    # A fixture may carry the scoring report its run produced. The
    # latency check reads per-episode search costs, and a packet holds
    # per-candidate aggregates — so without the report that check is
    # honestly ``not_checkable``, and with it the fixture can be graded
    # on the mechanism it plants. G6.
    evidence = (
        ReportEvidence(
            report,
            packet=source.packet,
            regions=_route_regions(source.packet),
            sidecar_directory=sidecar_directory,
            sidecar_directories=sidecar_directories,
        )
        if report is not None
        else ReportEvidence.from_packet(
            source.packet,
            sidecar_directory=sidecar_directory,
            sidecar_directories=sidecar_directories,
        )
    )
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
        host=InProcessHost(
            analysis,
            evidence,
            implementation_ref=implementation_ref or platform_implementation_ref(),
            sink=sink,
            replay_planner=replay_planner,
        ),
        effective_budget=effective,
        requested_budget_checksum=bundle.requested_budget.checksum,
        effective_budget_checksum=effective.checksum,
        evidence_identity_checksum=source.identity_checksum,
    )
