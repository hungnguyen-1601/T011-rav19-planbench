"""What a fact query can be answered from the packet alone — W1.0.

The four mechanism checks measure something the packet does not carry: a
map, a sidecar, a planner run again. The fact queries do not. Every one
of them is a read of the case packet, which is the same artifact the
analyst was shown and the same artifact the host is already holding.

This lived inside the stub host, which had a consequence nobody wrote
down: the **real** host answered ``tool_unavailable`` for every fact
query, so a round on the real lane could verify a mechanism and be told
in the same breath that the packet's own objective decomposition was
unavailable. Two hosts answering one question two ways is the shape this
layer keeps refusing elsewhere, and it had it here.

So the reading is one function, and both hosts call it. What differs
between them is what they *sign* the answer with — the stub stamps a
zero implementation ref and a ``mock://`` artifact, the real host stores
through its sink and signs with its build — and that difference is the
one a reader of a transcript needs to see.

``None`` means *the packet does not hold this*. It is not an error and
it is not zero: the card says which measurements a completed result
owes, and a reader that cannot produce them says so rather than filling
them in.

W1.1 adds a third answer. ``None`` became too coarse once a query took
an argument: "this platform serves no such tool" and "you asked about a
candidate this packet does not compare" are different facts, and both
would have been stamped ``tool_unavailable`` — a reader of the
transcript could not tell a missing feature from a mistyped id. A
:class:`FactRefusal` carries the card's **own** declared failure code,
which is also the only kind the session accepts.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from planbench_explanation.case_packet import CandidateMeasurements, CasePacket
from planbench_explanation.protocol import EvidenceReference
from planbench_explanation.tools import ToolCard

__all__ = ["FactRefusal", "serve_from_packet"]

_NO_ARGUMENTS: Mapping[str, object] = MappingProxyType({})


@dataclass(frozen=True)
class FactRefusal:
    """The query was understood and the packet cannot answer it.

    ``code`` must be one the card declares in ``failure_modes``. A host
    that returns an undeclared code is rejected by its own session,
    which ends the analysis over one word — E6b found that the hard way.
    """

    code: str


def serve_from_packet(
    card: ToolCard, packet: CasePacket, arguments: Mapping[str, object] = _NO_ARGUMENTS
) -> tuple[dict[str, float], tuple[EvidenceReference, ...]] | FactRefusal | None:
    """The packet's answer to one fact query, a refusal, or ``None``."""
    if card.tool_id == "get_objective_decomposition":
        waterfall = packet.decision.waterfall
        if waterfall is None:
            # Nobody was ranked, so there is no ΔU to decompose. The seam
            # already withholds the evidence this tool requires, so a
            # request should not arrive; a reader that assumed otherwise
            # would raise on ``None`` rather than refuse.
            return None
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
        blocked = {kind for unknown in packet.known_unknowns for kind in unknown.blocks_claim_types}
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
    if card.tool_id == "get_candidate_measurements":
        return _measurements(packet, str(arguments.get("candidate_id", "")))
    if card.tool_id == "get_episode_timeline":
        return _timeline(packet, arguments)
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


def _measurements(
    packet: CasePacket, candidate_id: str
) -> tuple[dict[str, float], tuple[EvidenceReference, ...]] | FactRefusal:
    """What one candidate scored, as the card asks for it — W1.1.

    Two refusals rather than one silence. A candidate the packet does
    not compare is the analyst's mistake and is worth telling it about;
    a candidate that is in the packet with nothing recorded is the
    **run's** gap, and the difference decides whether asking again with
    a different id could work.

    ``n_episodes`` is required by the card and is read from the
    denominators the packet carries, never assumed: every rate in this
    platform arrives with the number it was computed over, and a
    measurement set that lost its denominator is one this reader
    declines rather than reports over an invented one. Where the
    denominators disagree — different measurements over different
    episode counts — the smallest is reported, because it is the one
    every number here is at least true of.
    """
    known = {candidate.candidate_id for candidate in packet.candidates}
    if candidate_id not in known:
        return FactRefusal("candidate_not_in_packet")
    row: CandidateMeasurements | None = next(
        (item for item in packet.measurements if item.candidate_id == candidate_id), None
    )
    if row is None:
        return FactRefusal("measurements_not_recorded")
    recorded = row.recorded
    denominators = [
        value.denominator for value in recorded.values() if value.denominator is not None
    ]
    if not recorded or not denominators:
        return FactRefusal("measurements_not_recorded")
    measurements = {name: float(value.value) for name, value in recorded.items()}
    measurements["n_episodes"] = float(min(denominators))
    # No reference. The card declares none, and the session rejects a
    # result carrying a kind its card does not name — rightly: a
    # reference is a pointer into evidence a reader can open, and the
    # candidate id is already in the request the transcript recorded.
    return (measurements, ())


def _timeline(
    packet: CasePacket, arguments: Mapping[str, object]
) -> tuple[dict[str, float], tuple[EvidenceReference, ...]] | FactRefusal:
    """One exemplar episode as it went, on **one** clock — W1.2.

    The clock is an argument and not a default because the two answer
    different questions: at equal wall-clock time the robots are at
    different places on the task, and at equal progress they are at the
    same place having taken different times. A reader handed the wrong
    one gets a number about neither candidate, so an unrecognised clock
    is refused rather than quietly resolved to one of them.

    The candidate is an argument too, and optional. An
    ``episode_context_id`` is a hash of the *conditions*, so both
    candidates of a comparison share one; when both drove the episode
    this refuses rather than picking, because an answer that does not
    say whose run it is describes neither.

    The measurements are the state at the **last** mark of the series,
    which is what the card's names mean: progress reached, worst
    clearance so far, latency budget used so far.
    """
    episode = str(arguments.get("episode_context_id", ""))
    clock = str(arguments.get("clock", ""))
    if clock not in ("at_time", "at_progress"):
        return FactRefusal("clock_not_recognised")
    matching = [item for item in packet.timelines if item.episode_context_id == episode]
    if not matching:
        # Either the episode is not in this packet at all, or it is in it
        # and was not chosen as an exemplar. The card has one code for
        # both, and it is the right one: only exemplars carry timelines,
        # so from this tool's side they are the same fact.
        return FactRefusal("episode_not_an_exemplar")
    candidate = str(arguments.get("candidate_id", "") or "")
    if candidate:
        matching = [item for item in matching if item.candidate_id == candidate]
        if not matching:
            return FactRefusal("timeline_not_recorded")
    elif len(matching) > 1:
        return FactRefusal("candidate_required_for_episode")
    points = [point for point in matching[0].points if point.clock == clock]
    if not points:
        return FactRefusal("timeline_not_recorded")
    last = points[-1]
    return (
        {
            "n_points": float(len(points)),
            "progress_fraction": last.progress_fraction,
            "safety_margin": last.safety_margin,
            "compute_budget": last.compute_budget,
            "path_efficiency": last.path_efficiency,
        },
        (),
    )
