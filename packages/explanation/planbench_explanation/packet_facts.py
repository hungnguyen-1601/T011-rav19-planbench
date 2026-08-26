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
"""

from __future__ import annotations

from planbench_explanation.case_packet import CasePacket
from planbench_explanation.protocol import EvidenceReference
from planbench_explanation.tools import ToolCard

__all__ = ["serve_from_packet"]


def serve_from_packet(
    card: ToolCard, packet: CasePacket
) -> tuple[dict[str, float], tuple[EvidenceReference, ...]] | None:
    """The packet's answer to one fact query, or ``None``."""
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
