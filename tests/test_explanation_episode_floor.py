"""The bar a model has to clear on one episode.

The floor is only worth having if it is honest, so most of this file is
about what it refuses to say: no mechanism where the packet found no
difference, no comparison where the verdict named no loser, no claim the
packet's own gaps have blocked, and no number in any sentence — the last
one having already cost the run-level floor its entire comparison once,
when a guarded floor abstained on every packet that had anything in it.
"""

from __future__ import annotations

from test_explanation_episode_packet import (
    build_contrasts,
    build_packet,
    components,
    detection,
    outcome,
    verdict_for,
)

from planbench_explanation.episode_floor import (
    CONTRAST,
    DIAGNOSIS,
    episode_floor,
)
from planbench_explanation.episode_packet import build_diagnoses
from planbench_explanation.ledger import KnownUnknown
from planbench_explanation.levels import check_phrases
from planbench_explanation.propositions import ASSERTABLE_PROPOSITIONS


class TestWhatTheFloorSays:
    def test_a_detection_becomes_a_diagnosis(self) -> None:
        answer = episode_floor(build_packet())
        assert len(answer.of(DIAGNOSIS)) == 1

    def test_a_supported_difference_becomes_a_contrast(self) -> None:
        answer = episode_floor(build_packet())
        offered = answer.of(CONTRAST)
        assert len(offered) == 1
        assert offered[0].proposition_type == "local_minimum_entrapment"
        assert offered[0].proposed_subject == "local_controller"

    def test_a_diagnosis_blames_no_component(self) -> None:
        """It reports that a detector fired. Naming the candidate's own
        controller there would make every observation an accusation."""
        answer = episode_floor(build_packet())
        for proposal in answer.of(DIAGNOSIS):
            assert proposal.proposed_subject == "task_geometry"

    def test_the_two_registers_never_share_a_hypothesis(self) -> None:
        answer = episode_floor(build_packet())
        ids = [proposal.hypothesis_id for proposal in answer.proposals]
        assert len(ids) == len(set(ids))
        assert set(answer.bearings.values()) <= {DIAGNOSIS, CONTRAST}


class TestWhatTheFloorRefusesToSay:
    def test_no_sentence_carries_a_number(self) -> None:
        """The run-level floor once wrote "in 9 of 30 episodes" into a
        statement. The guard drops a quantity in a statement whoever wrote
        it, so that floor abstained on every packet that had anything in it
        and the comparison the harness ran against it measured nothing."""
        answer = episode_floor(build_packet())
        for proposal in answer.proposals:
            assert not any(char.isdigit() for char in proposal.hypothesis_statement)

    def test_no_sentence_reaches_past_association(self) -> None:
        answer = episode_floor(build_packet())
        for proposal in answer.proposals:
            assert check_phrases(proposal.hypothesis_statement, "associated") == ()

    def test_a_blocked_mechanism_is_not_proposed(self) -> None:
        """The packet says it cannot be claimed here; proposing it anyway is
        the blocked-claim leak the suite counts."""
        packet = build_packet(
            known_unknowns=(
                KnownUnknown(
                    id="episode_local_minimum_unverifiable",
                    blocks_claim_types=("local_minimum_entrapment",),
                    source="this episode recorded nothing the checker reads",
                ),
            )
        )
        answer = episode_floor(packet)
        assert answer.of(CONTRAST) == ()
        assert answer.of(DIAGNOSIS), "the observation itself is still reportable"

    def test_a_tie_produces_no_contrast_at_all(self) -> None:
        tied_a = outcome("A", decision_utility=0.8010)
        tied_b = outcome("B")
        result = verdict_for(tied_a, tied_b)
        contrasts, ruled_out = build_contrasts(
            verdict=result,
            outcomes={"A": tied_a, "B": tied_b},
            components={"A": components("A"), "B": components("B", global_planner="rrtstar")},
            detections=[detection("stuck_cluster", "B", stopped_seconds=4.1)],
        )
        packet = build_packet(
            verdict=result,
            contrasts=contrasts,
            ruled_out=ruled_out,
            diagnoses=build_diagnoses(
                verdict=result,
                outcomes={"A": tied_a, "B": tied_b},
                detections=[detection("stuck_cluster", "B", stopped_seconds=4.1)],
            ),
        )
        answer = episode_floor(packet)
        assert answer.of(CONTRAST) == ()
        assert answer.of(DIAGNOSIS), "what fired is still worth saying"

    def test_an_episode_with_nothing_in_it_abstains(self) -> None:
        """Both stacks drove to the goal and no detector fired. Saying
        anything there would be saying something about nothing."""
        quiet_a = outcome("A", decision_utility=0.87)
        quiet_b = outcome("B")
        result = verdict_for(quiet_a, quiet_b)
        contrasts, ruled_out = build_contrasts(
            verdict=result,
            outcomes={"A": quiet_a, "B": quiet_b},
            components={"A": components("A"), "B": components("B")},
            detections=[],
        )
        packet = build_packet(
            verdict=result,
            contrasts=contrasts,
            ruled_out=ruled_out,
            diagnoses=build_diagnoses(
                verdict=result,
                outcomes={"A": quiet_a, "B": quiet_b},
                detections=[],
            ),
            candidates=(components("A"), components("B")),
        )
        answer = episode_floor(packet)
        assert answer.abstained

    def test_every_proposition_it_uses_is_assertable(self) -> None:
        """An inference-only type exists so a card can forbid it by name.
        A floor that proposed one would be proposing something no evidence
        can ever promote."""
        answer = episode_floor(build_packet())
        for proposal in answer.proposals:
            assert proposal.proposition_type in ASSERTABLE_PROPOSITIONS

    def test_every_citation_names_the_episode_it_is_about(self) -> None:
        """An observation ref that omits the episode is a ref into the run,
        and the run is thirty of these."""
        answer = episode_floor(build_packet())
        for proposal in answer.of(DIAGNOSIS):
            for ref in proposal.supports:
                assert ref.ref.endswith("@ep-004")
