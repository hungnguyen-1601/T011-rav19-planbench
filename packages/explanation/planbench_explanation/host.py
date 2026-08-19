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

**The evidence source is bound to the packet before anything runs.**
A host given an :class:`AnalysisRequest` for one run and an evidence
source pointed at another would admit every request correctly and then
answer them from the wrong run's data, stamped ``recorded``. Nothing
downstream could see it: the result names a tool and a request, not a
run. So a source declares an :class:`EvidenceIdentity` and the
constructor refuses a mismatch — before a checker exists to be wrong.

**A result's artifact reference points at a file that exists.** The
first version composed a path and a checksum and wrote nothing there, so
every completed result carried a reference an auditor could not resolve
— a traceability field that traced to nothing, which is worse than an
absent one because it looks like diligence. Writing goes through an
:class:`EvidenceSink`, and the reference on the result is the one the
sink returned after storing the bytes.

**The host signs with its own build, and that is a real limitation.**
``implementation_ref`` names the code that produced a result, and here
it is whatever the caller declares the platform build to be. Within one
process that is a statement of intent rather than proof; what actually
binds a result to a run is the session's admitted request. The signature
becomes load-bearing when results cross a process boundary, and this
module is where that will need doing.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import MappingProxyType
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from planbench_explanation.case_packet import CasePacket
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


class EvidenceMismatch(ValueError):
    """An evidence source that is not about the packet being analysed."""


class EvidenceIdentity(BaseModel):
    """Which run an evidence source speaks for.

    Compared against the packet at construction. Map checksum is
    deliberately **not** here: the case packet does not carry one, so a
    host cannot check it, and a field nobody compares is a field that
    reads as a guarantee without being one. When the packet grows one,
    this grows one.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str = Field(min_length=1)
    source_manifest_ref: str = Field(min_length=1)
    source_manifest_checksum: str = Field(min_length=64, max_length=64)
    task_profile_id: str = Field(min_length=1)
    candidate_ids: frozenset[str]


class StoredEvidence(BaseModel):
    """Where a sink put an artifact, and the hash of what it wrote."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    artifact_ref: str = Field(min_length=1)
    checksum: str = Field(min_length=64, max_length=64)


class EvidenceSink(Protocol):
    """Where a checker's artifact is written before its result is returned."""

    def store(
        self, *, tool_id: str, request_id: str, payload: dict[str, object]
    ) -> StoredEvidence: ...


class InMemoryEvidenceSink:
    """Keeps artifacts in a dict. For tests and for a dry run.

    Not a null sink: a sink that discards would put the dangling
    reference back, and the point of the protocol is that the reference
    resolves to something. What it resolves to here is memory, and
    :attr:`artifacts` is how a caller reads it.

    **Chosen explicitly, never defaulted to.** It was the host's default
    sink, which meant a production host wrote every artifact into a dict
    that dies with the process while its results kept a ``memory://``
    reference that outlived it — a dangling pointer with a plausible
    scheme. A host now requires a sink, and picking this one is a
    statement that the results are not being kept.
    """

    def __init__(self, prefix: str = "memory://explain") -> None:
        self.prefix = prefix
        self.artifacts: dict[str, dict[str, object]] = {}

    def store(self, *, tool_id: str, request_id: str, payload: dict[str, object]) -> StoredEvidence:
        ref = f"{self.prefix}/{tool_id}/{request_id}.json"
        self.artifacts[ref] = payload
        return StoredEvidence(artifact_ref=ref, checksum=artifact_checksum(payload))


def _safe_name(value: str) -> str:
    """A filename derived from an untrusted string.

    ``request_id`` comes from the analyst. The first version pasted it
    into a path — ``../../outside`` would have written wherever it
    pointed. The id is hashed rather than sanitised: a filter has to
    anticipate every spelling of "go up a level", and a digest has
    nothing to anticipate. The id itself is stored inside the artifact,
    so a reader loses nothing.
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]


class FileEvidenceSink:
    """Writes artifacts under a root directory, one JSON file each.

    Two independent defences, because the first is a judgement about
    strings and the second is a fact about paths: the filename comes
    from a digest, and the resolved path is checked to be under the root
    before anything is written.
    """

    def __init__(self, root: Path, *, relative_to: Path | None = None) -> None:
        self.root = root
        self.relative_to = relative_to or root

    def store(self, *, tool_id: str, request_id: str, payload: dict[str, object]) -> StoredEvidence:
        body = {"request_id": request_id, "tool_id": tool_id, **payload}
        path = self.root / _safe_name(tool_id) / f"{_safe_name(request_id)}.json"
        root = self.root.resolve()
        if not path.resolve().is_relative_to(root):
            raise EvidenceMismatch(
                f"refusing to write {path.resolve()} outside the artifact root {root}"
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(body, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8"
        )
        try:
            ref = path.relative_to(self.relative_to).as_posix()
        except ValueError:
            ref = path.as_posix()
        return StoredEvidence(artifact_ref=ref, checksum=artifact_checksum(body))


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

    @property
    def identity(self) -> EvidenceIdentity: ...

    def gap_evidence(self, *, candidate_id: str, region_id: str) -> GapEvidence | None: ...

    def latency_evidence(self, *, candidate_id: str) -> LatencyEvidence | None: ...


def identity_of(packet: CasePacket) -> EvidenceIdentity:
    """The identity a source must match to serve this packet."""
    return EvidenceIdentity(
        run_id=packet.run_id,
        source_manifest_ref=packet.header.source_manifest_ref,
        source_manifest_checksum=packet.header.source_manifest_checksum,
        task_profile_id=packet.task.task_profile_id,
        candidate_ids=frozenset(candidate.candidate_id for candidate in packet.candidates),
    )


class PacketEvidence:
    """Fact queries answered from the case packet, checks from nothing.

    The packet is the analyst's view and it holds no map and no
    per-episode search costs, so both mechanism checks come back
    unavailable. Useful for exercising a round end to end without a run
    on disk, and honest about what it cannot do.
    """

    def __init__(self, packet: CasePacket) -> None:
        self._identity = identity_of(packet)

    @property
    def identity(self) -> EvidenceIdentity:
        return self._identity

    def gap_evidence(self, *, candidate_id: str, region_id: str) -> GapEvidence | None:
        return None

    def latency_evidence(self, *, candidate_id: str) -> LatencyEvidence | None:
        return None


class ReportEvidence:
    """Evidence read off a scoring report and a measured map.

    Built **from the packet it will serve**, not told what it is about.
    The report's own identity block and candidate rows are checked
    against the packet at construction; the robot's radius, inflation
    margin and required passage width are read off the packet rather
    than accepted from the caller.

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
        packet: CasePacket,
        regions: Mapping[tuple[str, str], RouteFeatures] = MappingProxyType({}),
    ) -> None:
        self.report = report
        self.packet = packet
        self._identity = identity_of(packet)
        self.regions = regions
        self._verify_report_is_about(packet)

    def _verify_report_is_about(self, packet: CasePacket) -> None:
        """Check the report against the packet, rather than being told.

        The identity used to be a constructor argument beside the
        report, so a caller could hand over run B's report and run A's
        identity and pass the host's check — the binding stopped
        accidental miswiring and was not a trust boundary. What can be
        compared is compared here, from the report's own fields.

        What **cannot** be compared is named rather than skipped:
        ``run_uri`` and ``run_checksum`` have no counterpart on the
        packet, and neither does a map checksum, so those are recorded
        below and not cross-checked. A reader should know which of these
        the platform actually verified.
        """
        identity = self.report.get("identity")
        if isinstance(identity, Mapping):
            profile = identity.get("task_profile_id")
            if profile is not None and profile != packet.task.task_profile_id:
                raise EvidenceMismatch(
                    f"the report is about task profile {profile!r} and the packet "
                    f"about {packet.task.task_profile_id!r}"
                )
        reported = {
            entry.get("candidate_id")
            for entry in self.report.get("candidates", [])  # type: ignore[union-attr]
            if isinstance(entry, Mapping)
        }
        if reported:
            missing = sorted(
                candidate.candidate_id
                for candidate in packet.candidates
                if candidate.candidate_id not in reported
            )
            if missing:
                raise EvidenceMismatch(
                    f"the report has no rows for {missing}, which the packet compares"
                )

    #: What the report says about itself that the packet cannot confirm.
    #: Kept for an auditor and deliberately **not** treated as verified.
    @property
    def unverified_report_identity(self) -> dict[str, object]:
        return {
            "run_uri": self.report.get("run_uri"),
            "run_checksum": self.report.get("run_checksum"),
        }

    @property
    def identity(self) -> EvidenceIdentity:
        return self._identity

    def gap_evidence(self, *, candidate_id: str, region_id: str) -> GapEvidence | None:
        """Robot facts come from the **packet**, never from the caller.

        They were constructor arguments, which meant the radius and the
        margin a check compared against were whatever the caller said —
        beside a packet that carries its own. Two sources for one fact
        is one source too many, and the packet is the one the analyst
        was shown.
        """
        features = self.regions.get((candidate_id, region_id))
        if features is None:
            return None
        robot = self.packet.task.robot
        if robot.inflation_margin_m is None or robot.required_passage_width_m is None:
            # The run did not record the inflation. Absent rather than
            # assumed — a clearance argument on a guessed margin is an
            # argument about a costmap nobody configured.
            return None
        return GapEvidence(
            region_id=region_id,
            features=features,
            robot_radius_m=robot.radius_m,
            inflation_margin_m=robot.inflation_margin_m,
            required_passage_width_m=robot.required_passage_width_m,
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
        sink: EvidenceSink,
        input_provenance: InputProvenance = "recorded",
    ) -> None:
        expected = identity_of(analysis.packet)
        actual = evidence.identity
        if actual != expected:
            differing = sorted(
                field
                for field in expected.model_dump()
                if getattr(actual, field) != getattr(expected, field)
            )
            raise EvidenceMismatch(
                f"the evidence source is about a different run than the packet: "
                f"{differing} differ. Admission would have passed every request and "
                "answered it from the wrong run, stamped 'recorded', and nothing "
                "downstream names a run to notice with."
            )
        self.session = ToolSession(analysis)
        self.analysis = analysis
        self.evidence = evidence
        self.implementation_ref = implementation_ref
        self.sink = sink
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
        except CheckerRefusal as error:
            # The checker's own code, forwarded. It used to be inferred
            # from the message, so improving a sentence relabelled the
            # failure.
            return self._unavailable(card, request, error.code)
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
            return self._unavailable(card, request, error.code)
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
        stored = self.sink.store(
            tool_id=card.tool_id,
            request_id=request.request_id,
            payload={
                "tool": list(card.key),
                "request": request.request_id,
                "run_id": self.analysis.packet.run_id,
                "arguments": dict(request.arguments),
                "proposition_type": outcome.proposition_type,
                "verdict": outcome.verdict,
                "measurements": outcome.measurements,
                "references": [reference.model_dump() for reference in references],
                "note": outcome.note,
            },
        )
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
            evidence_artifact_ref=stored.artifact_ref,
            evidence_checksum=stored.checksum,
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
