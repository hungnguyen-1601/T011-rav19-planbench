"""One episode: who won, and which differences may be offered as reasons.

Two questions this file keeps apart, because conflating them is the
failure the whole episode layer exists to prevent:

* **who won** — deterministic, four bases, and one of them (`not_comparable`)
  exists solely so a missing row is never read as a defeat;
* **what may be said about why** — a difference needs a losing side to be
  stated against, and a detection on the winning side is a diagnosis
  however true it is.

The tests are written as pairs wherever a rule has an obvious wrong
reading: one case where the rule fires, one where it deliberately does
not.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from planbench_explanation.case_packet import (
    STANDING_UNKNOWNS,
    EpisodeTimeline,
    RobotFacts,
)
from planbench_explanation.contrast import CandidateComponents
from planbench_explanation.detectors import Detection
from planbench_explanation.episode_packet import (
    CONTRAST_STRENGTH,
    DETECTION_MECHANISM,
    EPISODE_VERDICT_CAVEAT,
    ONLY_ON_WINNER,
    PRESENT_ON_BOTH,
    VERDICT_HAS_NO_DIRECTION,
    CandidateOutcome,
    EpisodeContrast,
    EpisodePacket,
    EpisodePacketRefusal,
    EpisodeVerdict,
    build_contrasts,
    build_diagnoses,
    build_verdict,
    classify_unknown,
    episode_unknowns,
    fit_to_budget,
    outcome_from_row,
    packet_bytes,
)
from planbench_explanation.knowledge import KNOWLEDGE_BASE_VERSION
from planbench_explanation.ledger import KnownUnknown
from planbench_explanation.map_features import RouteFeatures
from planbench_explanation.propositions import (
    ASSERTABLE_PROPOSITIONS,
    EFFECT_DIRECTION,
    effect_direction,
)
from planbench_explanation.versioning import ExplanationArtifactHeader
from planbench_schemas.identity import canonical_json

TOOL_CATALOG_VERSION_FOR_HEADER = "3.4.0"

EPISODE = "ep-004"
EPSILON = 0.005


def outcome(candidate_id: str, **overrides: object) -> CandidateOutcome:
    fields: dict[str, object] = {
        "candidate_id": candidate_id,
        "success": True,
        "collision_count": 0,
        "min_clearance": 0.40,
        "travel_time_s": 22.0,
        "decision_utility": 0.80,
    }
    fields.update(overrides)
    return CandidateOutcome(**fields)  # type: ignore[arg-type]


def components(candidate_id: str, *, global_planner: str = "astar") -> CandidateComponents:
    return CandidateComponents(
        candidate_id=candidate_id,
        global_planner=global_planner,
        local_controller="dwa",
        local_controller_config="default",
    )


def detection(detection_type: str, candidate_id: str, **measurements: float) -> Detection:
    return Detection(
        type=detection_type,  # type: ignore[arg-type]
        candidate_id=candidate_id,
        episode_context_id=EPISODE,
        measurements=measurements,
    )


def verdict_for(
    outcome_a: CandidateOutcome | None,
    outcome_b: CandidateOutcome | None,
) -> EpisodeVerdict:
    return build_verdict(
        episode_context_id=EPISODE,
        candidate_a="A",
        candidate_b="B",
        outcome_a=outcome_a,
        outcome_b=outcome_b,
        tie_epsilon=EPSILON,
    )


class TestWhoWon:
    def test_utility_decides_when_both_sides_were_scored(self) -> None:
        result = verdict_for(outcome("A", decision_utility=0.87), outcome("B"))
        assert result.basis == "episode_decision_utility"
        assert (result.winner, result.loser) == ("A", "B")
        assert result.has_direction

    def test_the_margin_carries_the_denominator_that_says_one_episode(self) -> None:
        """A utility figure with no denominator is the claim this layer refuses."""
        result = verdict_for(outcome("A", decision_utility=0.87), outcome("B"))
        assert result.delta_utility is not None
        assert result.delta_utility.denominator == 1
        assert result.delta_utility.unit == "utility"

    def test_a_margin_inside_epsilon_is_a_tie_and_names_nobody(self) -> None:
        result = verdict_for(outcome("A", decision_utility=0.8010), outcome("B"))
        assert result.tie is True
        assert result.winner is None and result.loser is None
        assert str(EPSILON) in result.undecided_reason

    def test_epsilon_is_a_parameter_not_a_constant_in_here(self) -> None:
        """Preregistered upstream. The same pair decides differently under a
        different margin, which is exactly why the number may not be chosen
        after the distribution has been seen."""
        pair = (outcome("A", decision_utility=0.8010), outcome("B"))
        wide = build_verdict(
            episode_context_id=EPISODE,
            candidate_a="A",
            candidate_b="B",
            outcome_a=pair[0],
            outcome_b=pair[1],
            tie_epsilon=0.05,
        )
        narrow = build_verdict(
            episode_context_id=EPISODE,
            candidate_a="A",
            candidate_b="B",
            outcome_a=pair[0],
            outcome_b=pair[1],
            tie_epsilon=0.0001,
        )
        assert wide.tie and not narrow.tie

    def test_a_missing_row_is_not_a_defeat(self) -> None:
        """The most tempting mistake in this module.

        No row can mean the candidate never ran the episode, that a gate
        eliminated it first, or that the recording is incomplete. Reading
        it as "it lost" invents a comparison nobody made.
        """
        result = verdict_for(outcome("A"), None)
        assert result.basis == "not_comparable"
        assert result.winner is None
        assert "losing" in result.undecided_reason

    def test_success_against_failure_ranks_without_any_utility(self) -> None:
        result = verdict_for(
            outcome("A", decision_utility=None),
            outcome("B", decision_utility=None, success=False, failure_reason="timeout"),
        )
        assert result.basis == "outcome_only"
        assert result.winner == "A"

    def test_two_unlike_failures_do_not_rank(self) -> None:
        """No ordering over failure reasons exists in this platform, and one
        invented here would decide episodes by a rule nobody wrote down."""
        result = verdict_for(
            outcome("A", decision_utility=None, success=False, failure_reason="collision"),
            outcome("B", decision_utility=None, success=False, failure_reason="timeout"),
        )
        assert result.basis == "undecidable"
        assert result.winner is None

    def test_two_successes_without_utility_do_not_rank_either(self) -> None:
        result = verdict_for(
            outcome("A", decision_utility=None, travel_time_s=10.0),
            outcome("B", decision_utility=None, travel_time_s=99.0),
        )
        assert result.basis == "undecidable", (
            "a faster run is not a scored win: utility weighs four objectives and "
            "travel time is one of them"
        )

    def test_the_caveat_cannot_be_reworded(self) -> None:
        base = verdict_for(outcome("A", decision_utility=0.87), outcome("B"))
        with pytest.raises((EpisodePacketRefusal, ValidationError)):
            base.model_copy(update={"caveat": "one episode, roughly"}).model_validate(
                base.model_dump() | {"caveat": "one episode, roughly"}
            )

    def test_the_caveat_says_it_is_not_the_run(self) -> None:
        assert "not the run's verdict" in EPISODE_VERDICT_CAVEAT

    def test_a_verdict_with_no_winner_has_to_say_why(self) -> None:
        with pytest.raises((EpisodePacketRefusal, ValidationError)):
            EpisodeVerdict(
                episode_context_id=EPISODE,
                candidate_a="A",
                candidate_b="B",
                basis="undecidable",
            )

    def test_a_winner_arrives_with_a_loser(self) -> None:
        with pytest.raises((EpisodePacketRefusal, ValidationError)):
            EpisodeVerdict(
                episode_context_id=EPISODE,
                candidate_a="A",
                candidate_b="B",
                basis="episode_decision_utility",
                winner="A",
            )


class TestPolarity:
    def test_every_mapped_mechanism_is_a_fault(self) -> None:
        assert set(EFFECT_DIRECTION.values()) == {"harms_subject"}

    def test_the_table_only_speaks_about_assertable_types(self) -> None:
        assert set(EFFECT_DIRECTION) <= set(ASSERTABLE_PROPOSITIONS)

    def test_an_unmapped_type_reads_as_ambiguous_rather_than_raising(self) -> None:
        """Asked about whatever a model proposed. A lookup that raises turns
        the guard's own table into a place a round can die."""
        assert effect_direction("component_specific_attribution") == "ambiguous"
        assert effect_direction("nothing_like_this") == "ambiguous"

    def test_a_helpful_mechanism_cannot_be_stated_against_the_loser(self) -> None:
        """No member today; the rule is what keeps the day one arrives from
        producing "B lost because of the thing that helps whoever has it"."""
        import planbench_explanation.propositions as propositions

        original = dict(propositions.EFFECT_DIRECTION)
        propositions.EFFECT_DIRECTION["clearance_refusal"] = "benefits_subject"
        try:
            with pytest.raises((EpisodePacketRefusal, ValidationError)):
                EpisodeContrast(
                    kind="detection_only_on_loser",
                    against_candidate_id="B",
                    proposition_type="clearance_refusal",
                    detail="stated against the loser",
                )
        finally:
            propositions.EFFECT_DIRECTION.clear()
            propositions.EFFECT_DIRECTION.update(original)


class TestWhatMayBeOffered:
    def _contrasts(
        self,
        detections: list[Detection],
        *,
        result: EpisodeVerdict | None = None,
        outcomes: dict[str, CandidateOutcome | None] | None = None,
    ) -> tuple[tuple[EpisodeContrast, ...], tuple[object, ...]]:
        scored = outcomes or {"A": outcome("A", decision_utility=0.87), "B": outcome("B")}
        return build_contrasts(
            verdict=result or verdict_for(scored["A"], scored["B"]),
            outcomes=scored,
            components={"A": components("A"), "B": components("B", global_planner="rrtstar")},
            detections=detections,
        )

    def test_a_detection_only_on_the_loser_is_offered_with_its_mechanism(self) -> None:
        found, _ = self._contrasts([detection("stuck_cluster", "B", stopped_seconds=4.1)])
        offered = [item for item in found if item.kind == "detection_only_on_loser"]
        assert len(offered) == 1
        assert offered[0].against_candidate_id == "B"
        assert offered[0].proposition_type == "local_minimum_entrapment"
        assert offered[0].strength == "support"

    def test_the_same_detection_on_both_sides_is_ruled_out_not_dropped(self) -> None:
        """It describes the pairing, not either candidate — the reading
        ``rules_out_component_specific_attribution`` makes at run level. Written
        down, because a list that simply omits it reads as though nobody looked.
        """
        _, withheld = self._contrasts(
            [
                detection("stuck_cluster", "B", stopped_seconds=4.1),
                detection("stuck_cluster", "A", stopped_seconds=3.9),
            ]
        )
        reasons = {item.reason for item in withheld}  # type: ignore[attr-defined]
        assert PRESENT_ON_BOTH in reasons

    def test_the_same_detection_much_worse_on_the_loser_is_a_difference(self) -> None:
        found, _ = self._contrasts(
            [
                detection("near_miss_cluster", "B", min_clearance_m=0.03),
                detection("near_miss_cluster", "A", min_clearance_m=0.12),
            ]
        )
        offered = [item for item in found if item.kind == "detection_worse_on_loser"]
        assert len(offered) == 1
        assert offered[0].measurements["severity_ratio"] == pytest.approx(4.0)

    def test_a_detection_only_on_the_winner_explains_nothing(self) -> None:
        found, withheld = self._contrasts([detection("stuck_cluster", "A", stopped_seconds=4.1)])
        assert not [item for item in found if item.kind.startswith("detection_")]
        assert ONLY_ON_WINNER in {item.reason for item in withheld}  # type: ignore[attr-defined]

    def test_a_verdict_with_no_direction_offers_no_difference_at_all(self) -> None:
        """Nothing may pick a losing side when the verdict declined to."""
        tied = {"A": outcome("A", decision_utility=0.8010), "B": outcome("B")}
        found, withheld = self._contrasts(
            [detection("stuck_cluster", "B", stopped_seconds=4.1)],
            result=verdict_for(tied["A"], tied["B"]),
            outcomes=tied,
        )
        assert found == ()
        assert {item.reason for item in withheld} == {VERDICT_HAS_NO_DIRECTION}  # type: ignore[attr-defined]

    def test_the_outcome_difference_needs_no_detector(self) -> None:
        """The cheapest evidence there is, and the first thing a reader asks."""
        scored = {
            "A": outcome("A", decision_utility=0.87, travel_time_s=20.0, min_clearance=0.50),
            "B": outcome("B", travel_time_s=31.0, min_clearance=0.20),
        }
        found, _ = self._contrasts([], outcomes=scored)
        outcome_kinds = [item for item in found if item.kind == "outcome_differs"]
        assert len(outcome_kinds) == 1
        assert outcome_kinds[0].strength == "context"
        assert outcome_kinds[0].measurements["travel_time_s_loser"] == pytest.approx(31.0)

    def test_two_identical_endings_offer_no_outcome_difference(self) -> None:
        """The winner won on utility while every recorded ending matched.

        Saying "A ended ahead" there would be an outcome difference made of
        nothing — and the pair matters, because the obvious implementation
        emits this contrast for every episode that has a winner.
        """
        found, _ = self._contrasts([])
        assert not [item for item in found if item.kind == "outcome_differs"]

    def test_the_winner_being_behind_on_a_field_is_not_offered(self) -> None:
        """Utility weighs four objectives, so the winner can be slower. A
        contrast listing the field it lost on would read as an argument for
        the other side."""
        scored = {
            "A": outcome("A", decision_utility=0.87, travel_time_s=40.0),
            "B": outcome("B", travel_time_s=20.0),
        }
        found, _ = self._contrasts([], outcomes=scored)
        assert not [item for item in found if item.kind == "outcome_differs"]

    def test_a_component_difference_is_context_and_never_support(self) -> None:
        """Otherwise: pick any known weakness of the losing component and call
        it the reason, with nothing having fired at all."""
        found, _ = self._contrasts([])
        component = [item for item in found if item.kind == "component_differs"]
        assert len(component) == 1
        assert component[0].strength == "context"
        assert CONTRAST_STRENGTH["component_differs"] == "context"

    def test_identical_stacks_rule_the_component_difference_out(self) -> None:
        scored = {"A": outcome("A", decision_utility=0.87), "B": outcome("B")}
        found, withheld = build_contrasts(
            verdict=verdict_for(scored["A"], scored["B"]),
            outcomes=scored,
            components={"A": components("A"), "B": components("B")},
            detections=[],
        )
        assert not [item for item in found if item.kind == "component_differs"]
        assert any(
            item.kind == "component_differs" and item.reason == PRESENT_ON_BOTH  # type: ignore[attr-defined]
            for item in withheld
        )

    def test_support_is_ordered_ahead_of_context(self) -> None:
        """The budgeter takes the top of this list when it cannot take all of
        it, so the order is a decision and not a rendering detail."""
        found, _ = self._contrasts([detection("stuck_cluster", "B", stopped_seconds=4.1)])
        strengths = [item.strength for item in found]
        assert strengths == sorted(strengths, key=lambda value: 0 if value == "support" else 1)


class TestDiagnosisStaysSeparate:
    def test_each_candidate_gets_only_its_own_detections(self) -> None:
        scored = {"A": outcome("A", decision_utility=0.87), "B": outcome("B")}
        diagnoses = build_diagnoses(
            verdict=verdict_for(scored["A"], scored["B"]),
            outcomes=scored,
            detections=[
                detection("stuck_cluster", "B", stopped_seconds=4.1),
                detection("latency_spike", "A", peak_latency_ms=310.0),
            ],
        )
        assert [item.candidate_id for item in diagnoses] == ["A", "B"]
        assert [len(item.detections) for item in diagnoses] == [1, 1]
        assert diagnoses[0].detections[0].type == "latency_spike"

    def test_a_diagnosis_refuses_another_candidates_detection(self) -> None:
        from planbench_explanation.episode_packet import EpisodeDiagnosis

        with pytest.raises((EpisodePacketRefusal, ValidationError)):
            EpisodeDiagnosis(
                candidate_id="A",
                detections=(detection("stuck_cluster", "B", stopped_seconds=1.0),),
            )


class TestReadingTheScoredRow:
    def test_every_number_is_copied_and_none_recomputed(self) -> None:
        row = {
            "episode_context_id": EPISODE,
            "success": True,
            "failure_reason": None,
            "collision_count": 0,
            "min_clearance": 0.5407,
            "travel_time_s": 24.65,
            "p99_latency_ms": 6.4286,
            "replan_count": 1,
            "episode_decision_utility": 0.8654,
        }
        read = outcome_from_row(row, candidate_id="A")
        assert read.decision_utility == pytest.approx(0.8654)
        assert read.travel_time_s == pytest.approx(24.65)

    def test_a_row_without_utility_reads_as_absent_not_zero(self) -> None:
        """Zero reads as 'scored, and scored badly'."""
        read = outcome_from_row({"success": False, "collision_count": 1}, candidate_id="B")
        assert read.decision_utility is None

    def test_a_row_whose_utility_is_not_a_number_reads_as_absent(self) -> None:
        read = outcome_from_row(
            {"success": True, "collision_count": 0, "episode_decision_utility": float("nan")},
            candidate_id="A",
        )
        assert read.decision_utility is None

    def test_the_mechanism_table_covers_the_detectors_that_map(self) -> None:
        """Same six pairs the model-free floor uses. A seventh detector
        arriving without an entry means it can be diagnosed and not offered
        as a difference, which is a decision somebody should make on purpose.
        """
        assert set(DETECTION_MECHANISM) == {
            "narrow_gap_refusal",
            "stuck_cluster",
            "oscillation",
            "detour",
            "latency_spike",
            "replan_storm",
        }


class TestWhatBlocksAClaimHere:
    """A run-level gap is not automatically an episode-level one."""

    def test_a_platform_gap_holds_at_every_scope(self) -> None:
        for unknown in STANDING_UNKNOWNS:
            assert classify_unknown(unknown).scope == "global"
            assert classify_unknown(unknown).blocks

    def test_a_run_statistical_gap_carries_no_force_here(self) -> None:
        """The run could not settle a pattern over thirty episodes. This
        episode has its own recording, and inheriting the run's block would
        drop exactly the claims this layer was built to allow — silently,
        because rule 3 reports the packet blocking the type either way."""
        gap = KnownUnknown(
            id="prevalence_unavailable",
            blocks_claim_types=("sampling_budget_insufficiency",),
            source="fewer episodes than the detector needs to call a pattern",
        )
        scoped = classify_unknown(gap)
        assert scoped.scope == "run_statistical"
        assert not scoped.blocks

    def test_an_episode_without_a_sidecar_blocks_the_replayable_claim(self) -> None:
        gaps = episode_unknowns(
            sidecar_present=False,
            route=None,
            robot=None,
            has_clearance=True,
            has_latency=True,
        )
        blocked = {kind for gap in gaps for kind in gap.blocks_claim_types}
        assert "sampling_budget_insufficiency" in blocked

    def test_an_episode_that_recorded_everything_blocks_nothing(self) -> None:
        gaps = episode_unknowns(
            sidecar_present=True,
            route=RouteFeatures(
                narrowest_passage_m=0.9,
                narrowest_at_progress_m=12.0,
                narrowest_lower_bound_m=0.9,
                obstacle_density=0.2,
                density_band_m=1.0,
                route_length_m=30.0,
                unmeasured_samples=0,
                samples_limited_by_coverage=0,
            ),
            robot=RobotFacts(radius_m=0.25, inflation_margin_m=0.08),
            has_clearance=True,
            has_latency=True,
        )
        assert gaps == ()

    def test_a_missing_column_blocks_the_detector_that_reads_it(self) -> None:
        """The detector never ran, so it never found anything — which is not
        the same as having looked and seen nothing."""
        gaps = episode_unknowns(
            sidecar_present=True,
            route=None,
            robot=None,
            has_clearance=False,
            has_latency=False,
        )
        blocked = {kind for gap in gaps for kind in gap.blocks_claim_types}
        assert {"clearance_refusal", "expansion_latency_association"} <= blocked


def build_packet(**overrides: object) -> EpisodePacket:
    scored_a = outcome("A", decision_utility=0.87)
    scored_b = outcome("B")
    result = verdict_for(scored_a, scored_b)
    detections = [detection("stuck_cluster", "B", stopped_seconds=4.1)]
    contrasts, ruled_out = build_contrasts(
        verdict=result,
        outcomes={"A": scored_a, "B": scored_b},
        components={"A": components("A"), "B": components("B", global_planner="rrtstar")},
        detections=detections,
    )
    fields: dict[str, object] = {
        "header": ExplanationArtifactHeader.for_current_code(
            source_manifest_ref="runs/2026-08-27/abc/manifest.json",
            source_manifest_checksum="a" * 64,
            detector_version="0.1.0",
            knowledge_base_version=KNOWLEDGE_BASE_VERSION,
            tool_catalog_version=TOOL_CATALOG_VERSION_FOR_HEADER,
        ),
        "run_id": "run-1",
        "episode_context_id": EPISODE,
        "verdict": result,
        "diagnoses": build_diagnoses(
            verdict=result,
            outcomes={"A": scored_a, "B": scored_b},
            detections=detections,
        ),
        "contrasts": contrasts,
        "ruled_out": ruled_out,
        "candidates": (components("A"), components("B", global_planner="rrtstar")),
    }
    fields.update(overrides)
    return EpisodePacket(**fields)  # type: ignore[arg-type]


class TestThePacket:
    def test_it_refuses_to_be_about_one_candidate(self) -> None:
        with pytest.raises((EpisodePacketRefusal, ValidationError)):
            build_packet(candidates=(components("A"),))

    def test_it_refuses_a_verdict_about_other_candidates(self) -> None:
        with pytest.raises((EpisodePacketRefusal, ValidationError)):
            build_packet(candidates=(components("C"), components("D")))

    def test_it_refuses_a_timeline_from_another_episode(self) -> None:
        stray = EpisodeTimeline(
            episode_context_id="ep-999",
            candidate_id="A",
            role="selected",
            points=(),
        )
        with pytest.raises((EpisodePacketRefusal, ValidationError)):
            build_packet(timelines=(stray,))

    def test_blocked_types_come_from_the_episode_and_the_platform(self) -> None:
        packet = build_packet(
            known_unknowns=(
                *STANDING_UNKNOWNS,
                *episode_unknowns(
                    sidecar_present=False,
                    route=None,
                    robot=None,
                    has_clearance=True,
                    has_latency=True,
                ),
            ),
            run_context_unknowns=(
                KnownUnknown(
                    id="prevalence_unavailable",
                    blocks_claim_types=("local_minimum_entrapment",),
                    source="the run has too few episodes to call it a pattern",
                ),
            ),
        )
        blocked = set(packet.blocked_claim_types)
        assert "sampling_budget_insufficiency" in blocked, "the episode's own gap holds"
        assert "candidate_latency_attribution" in blocked, "a platform gap holds everywhere"
        assert "local_minimum_entrapment" not in blocked, (
            "a run-statistical gap must not remove a claim this episode can support"
        )


class TestTheBudget:
    def test_a_packet_that_fits_loses_nothing(self) -> None:
        assert fit_to_budget(build_packet(), max_bytes=1_000_000).dropped == ()

    def test_it_drops_from_the_cheap_end_first(self) -> None:
        """Order is a decision, not a rendering detail: a reader can rebuild
        an outcome difference from rows the packet carries anyway, and cannot
        rebuild a detection from anything."""
        packet = build_packet()
        first = fit_to_budget(packet, max_bytes=packet_bytes(packet) - 1).dropped
        assert first, "a budget one byte under the size has to drop something"
        assert "supported_contrast" not in first

    def test_a_supported_contrast_is_the_last_thing_to_go(self) -> None:
        squeezed = fit_to_budget(build_packet(), max_bytes=1)
        if "supported_contrast" in squeezed.dropped:
            assert squeezed.dropped[-1] == "supported_contrast"

    def test_the_verdict_survives_any_budget(self) -> None:
        """Everything else elaborates on the one thing the reader opened the
        panel for."""
        squeezed = fit_to_budget(build_packet(), max_bytes=1)
        assert squeezed.packet.verdict.winner == "A"
        assert squeezed.packet.verdict.caveat == EPISODE_VERDICT_CAVEAT

    def test_every_drop_is_written_down(self) -> None:
        squeezed = fit_to_budget(build_packet(), max_bytes=1)
        assert squeezed.dropped
        for name in squeezed.dropped:
            assert f"dropped:{name}" in squeezed.packet.omissions

    def test_a_budget_of_nothing_is_refused_rather_than_served_empty(self) -> None:
        with pytest.raises(EpisodePacketRefusal):
            fit_to_budget(build_packet(), max_bytes=0)

    def test_the_size_is_measured_the_way_it_is_serialised(self) -> None:
        packet = build_packet()
        assert packet_bytes(packet) == len(
            canonical_json(packet.model_dump(mode="json")).encode("utf-8")
        )
