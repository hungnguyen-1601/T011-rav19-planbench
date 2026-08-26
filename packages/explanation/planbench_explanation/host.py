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

**The replay checker arrives as an argument, not as an import.** A
replay needs a planner, and this package must not contain one — see
:mod:`planbench_explanation.replay`. So a host is given a
:class:`~planbench_explanation.replay.ReplayPlanner` or it is not, and
without one ``replay_global_plan`` stays ``not_checkable`` exactly as it
was. The dependency points from the simulator into here and never back.

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
from planbench_explanation.packet_facts import FactRefusal, serve_from_packet
from planbench_explanation.protocol import (
    HOST_FAILURE_CODES,
    AnalysisRequest,
    EvidenceReference,
    ToolRequest,
    ToolResult,
    ToolSession,
    stamped_result,
)
from planbench_explanation.provenance import InputProvenance
from planbench_explanation.replay import (
    ConvergenceEvidence,
    ReplayEvidence,
    ReplayPlanner,
    ReplayUnavailable,
    check_replay_global_plan,
    check_rrt_convergence,
)
from planbench_explanation.sidecar_writer import read_sidecar, snapshot_for
from planbench_explanation.tools import ToolCard
from planbench_explanation.versioning import artifact_checksum

#: Checks whose evidence the platform does not record yet. Named here so
#: the gap is one list rather than a condition scattered through the
#: dispatch, and so removing one is a visible diff.
#: Tools with no implementation behind them yet, whatever evidence
#: exists. **Empty since E6b.** ``replay_global_plan`` left when E4.5
#: gave it inputs and a planner could be injected; ``rrt_convergence``
#: left when its evidence grew the run's own seed set, which is where a
#: deployment's seeds live — the sidecar records the attempt that
#: happened and this check is about the attempts that did not.
#:
#: Kept as a named empty set rather than deleted: a host still answers
#: ``checker_not_implemented`` for a tool with no branch, and the next
#: card added to the catalog lands in exactly this situation.
AWAITING_SIDECAR: frozenset[str] = frozenset()

#: The name of the one region a case packet carries: the route the run
#: was measured along. A packet holds a single :class:`RouteFeatures`, so
#: there is one corridor to ask about, and a checker whose region id had
#: to be guessed is a checker nobody can call.
ROUTE_REGION_ID = "route"


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

    def replay_evidence(
        self, *, candidate_id: str, episode_context_id: str, planning_attempt: int
    ) -> ReplayEvidence | None: ...

    def convergence_evidence(
        self, *, candidate_id: str, episode_context_id: str, planning_attempt: int
    ) -> ConvergenceEvidence | None: ...


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

    def replay_evidence(
        self, *, candidate_id: str, episode_context_id: str, planning_attempt: int
    ) -> ReplayEvidence | None:
        return None

    def convergence_evidence(
        self, *, candidate_id: str, episode_context_id: str, planning_attempt: int
    ) -> ConvergenceEvidence | None:
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
        sidecar_directory: Path | None = None,
        sidecar_directories: Mapping[str, Path] = MappingProxyType({}),
    ) -> None:
        self.report = report
        self.packet = packet
        #: Where this run's ``<episode>.planning_inputs.jsonl`` files
        #: live. Handed in rather than derived: the address is the
        #: **trace layout's** rule (class, conditions fingerprint,
        #: candidate), and re-deriving it here would put a second copy of
        #: that rule in the layer least able to keep it current.
        self.sidecar_directory = sidecar_directory
        #: The same address, per candidate. The trace layout files a
        #: sidecar under the candidate that produced it, and two
        #: candidates of one comparison record the *same* episode: in one
        #: flat directory the second file is the first file's name. A run
        #: with one candidate still passes ``sidecar_directory`` and
        #: every candidate resolves to it.
        self.sidecar_directories = sidecar_directories
        self._identity = identity_of(packet)
        self.regions = regions
        self._verify_report_is_about(packet)

    def _sidecar_for(self, candidate_id: str) -> Path | None:
        """Where this candidate's sidecars live, or nowhere."""
        return self.sidecar_directories.get(candidate_id, self.sidecar_directory)

    @classmethod
    def from_packet(
        cls,
        packet: CasePacket,
        *,
        sidecar_directory: Path | None = None,
        sidecar_directories: Mapping[str, Path] = MappingProxyType({}),
    ) -> ReportEvidence:
        """Evidence for a run that left a packet and its sidecars, and no report.

        A golden fixture is a packet on disk. The route through the map
        was measured when the fixture was built and travels in
        ``task.route``, so the clearance check has the geometry it
        compares against — and it is the geometry the analyst was shown,
        not a second measurement taken here.

        What a fixture does not carry is a scoring report, so
        ``latency_vs_expanded_nodes`` finds no per-episode search costs
        and answers ``not_checkable``. That is the honest answer for a
        run whose expansion counts nobody kept, and W1.1 changes it by
        putting candidate measurements in the packet rather than by
        inventing rows here.

        The route is registered for every candidate under one region id,
        because the packet carries one route. A request naming any other
        region resolves to nothing — a refusal, rather than a
        measurement of a corridor the caller did not ask about.
        """
        route = packet.task.route
        regions = (
            {(candidate.candidate_id, ROUTE_REGION_ID): route for candidate in packet.candidates}
            if route is not None
            else {}
        )
        return cls(
            {},
            packet=packet,
            regions=regions,
            sidecar_directory=sidecar_directory,
            sidecar_directories=sidecar_directories,
        )

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


    def replay_evidence(
        self, *, candidate_id: str, episode_context_id: str, planning_attempt: int
    ) -> ReplayEvidence | None:
        """One recorded attempt and the snapshot it pins, or ``None``.

        ``None`` where the run predates the sidecar or the attempt was
        never recorded — the host turns that into ``not_checkable``,
        which is the truthful answer and the one the evidence ladder
        already prices.
        """
        directory = self._sidecar_for(candidate_id)
        if directory is None:
            return None
        path = directory / f"{episode_context_id}.planning_inputs.jsonl"
        if not path.exists():
            return None
        header, records = read_sidecar(path)
        if header.candidate_id != candidate_id:
            raise EvidenceMismatch(
                f"the sidecar at {path} is {header.candidate_id!r}'s and the request "
                f"is about {candidate_id!r}"
            )
        for record in records:
            if record.planning_attempt == planning_attempt:
                return ReplayEvidence(
                    record=record,
                    snapshot=snapshot_for(path, record),
                    inputs_loaded_from_record=True,
                )
        return None

    def convergence_evidence(
        self, *, candidate_id: str, episode_context_id: str, planning_attempt: int
    ) -> ConvergenceEvidence | None:
        """One recorded query, plus the seeds this candidate actually ran.

        **The seed set comes from the run's own sidecars**, one per
        episode, not from the report and not from the caller. The report
        does not carry seeds — its episodes are context hashes — and a
        caller-supplied set would be the same self-declared value the
        evidence identity already had to stop being. What the run drew
        from is recorded in the runs it made.

        Sampling planners only: an episode whose snapshot records no
        seed contributes none, and a candidate that never records one
        yields no evidence rather than a sweep over a seed set of
        ``[0]``.
        """
        directory = self._sidecar_for(candidate_id)
        replay = self.replay_evidence(
            candidate_id=candidate_id,
            episode_context_id=episode_context_id,
            planning_attempt=planning_attempt,
        )
        if replay is None or directory is None:
            return None

        seeds: list[int] = []
        for path in sorted(directory.glob("*.planning_inputs.jsonl")):
            header, records = read_sidecar(path)
            if header.candidate_id != candidate_id or not records:
                continue
            seed = snapshot_for(path, records[0]).seed
            if seed is not None and seed not in seeds:
                seeds.append(seed)
        if not seeds:
            return None
        return ConvergenceEvidence(
            record=replay.record, snapshot=replay.snapshot, seeds=tuple(seeds)
        )


class ToolHost:
    """Serves one analysis round against one evidence source."""

    def __init__(
        self,
        analysis: AnalysisRequest,
        evidence: EvidenceSource,
        *,
        implementation_ref: str,
        sink: EvidenceSink,
        replay_planner: ReplayPlanner | None = None,
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
        self.replay_planner = replay_planner
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
        if card.tool_id == "replay_global_plan":
            return self._replay(card, request)
        if card.tool_id == "rrt_convergence":
            return self._convergence(card, request)
        served = serve_from_packet(card, self.analysis.packet, request.arguments)
        if isinstance(served, FactRefusal):
            return self._unavailable(card, request, served.code)
        if served is not None:
            return self._from_packet(card, request, *served)
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

    def _replay(self, card: ToolCard, request: ToolRequest) -> ToolResult:
        if self.replay_planner is None:
            # No planner was injected. Not a failure of the run: this
            # host was built without the half that can re-run a query.
            return self._unavailable(card, request, "checker_not_implemented")
        evidence = self.evidence.replay_evidence(
            candidate_id=str(request.arguments["candidate_id"]),
            episode_context_id=str(request.arguments["episode_context_id"]),
            planning_attempt=int(request.arguments["attempt_index"]),
        )
        if evidence is None:
            return self._unavailable(card, request, "planning_inputs_missing")
        try:
            outcome = check_replay_global_plan(evidence, planner=self.replay_planner)
        except CheckerRefusal as error:
            return self._unavailable(card, request, error.code)
        except ReplayUnavailable as error:
            # The harness said it cannot rebuild this planner. A harness
            # that cannot run has refuted nothing.
            return self._unavailable(card, request, str(error.code))
        return self._completed(card, request, outcome)

    def _convergence(self, card: ToolCard, request: ToolRequest) -> ToolResult:
        if self.replay_planner is None:
            return self._unavailable(card, request, "checker_not_implemented")
        evidence = self.evidence.convergence_evidence(
            candidate_id=str(request.arguments["candidate_id"]),
            episode_context_id=str(request.arguments["episode_context_id"]),
            planning_attempt=1,
        )
        if evidence is None:
            return self._unavailable(card, request, "planning_inputs_missing")
        try:
            outcome = check_rrt_convergence(evidence, planner=self.replay_planner)
        except CheckerRefusal as error:
            return self._unavailable(card, request, error.code)
        except ReplayUnavailable as error:
            return self._unavailable(card, request, str(error.code))
        return self._completed(card, request, outcome)

    def _from_packet(
        self,
        card: ToolCard,
        request: ToolRequest,
        measurements: dict[str, float],
        references: tuple[EvidenceReference, ...],
    ) -> ToolResult:
        """A fact query answered from the packet, signed like any result.

        Reading the packet is not a new capability: it is the artifact
        this host was built around and the one the analyst was shown.
        What the stub host had and this one did not was the *reading*,
        which meant a round on the real lane could verify a mechanism and
        be told in the same breath that the packet's own decomposition
        was unavailable.

        The answer goes through the sink like a checker's, so it has an
        artifact behind it and is signed with this build rather than with
        the stub's zeros. A transcript still says which host ran.
        """
        stored = self.sink.store(
            tool_id=card.tool_id,
            request_id=request.request_id,
            payload={
                "tool": list(card.key),
                "request": request.request_id,
                "run_id": self.analysis.packet.run_id,
                "arguments": dict(request.arguments),
                "measurements": measurements,
                "references": [reference.model_dump() for reference in references],
            },
        )
        return stamped_result(
            card,
            request,
            execution_status="completed",
            input_provenance=self.input_provenance,
            measurements=measurements,
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
            failure_code=self._declared(card, code),
        )

    @staticmethod
    def _declared(card: ToolCard, code: str) -> str:
        """The code as the card allows it to be reported.

        ``ToolSession.record`` refuses a failure code the card does not
        declare, and it is right to: an unenumerated failure cannot be
        told from a typo. But the refusal is raised at *record* time,
        which kills the round — an analyst loses its whole analysis
        because a checker and its card disagree about a word.

        That disagreement is the platform's, so it is reported as the
        platform's: ``host_internal_error`` is a declared host code, and
        the round survives to say the check could not answer. W1.0 found
        two of these by running the replay checkers through a session for
        the first time; the fix for each is a card that declares what its
        checker can raise, which is a wire change and belongs with the
        other contract work.
        """
        if code in card.failure_modes or code in HOST_FAILURE_CODES:
            return code
        return "host_internal_error"


def _positive(value: object) -> bool:
    """A node count that says something happened."""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0
