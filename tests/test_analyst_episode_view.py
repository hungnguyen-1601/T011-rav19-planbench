"""The episode index, and the two rules that only make sense at this scope.

Three things this file is really about:

* the index holds **this episode** and nothing from the set it belongs
  to, so a sentence about it cannot borrow weight from the other
  twenty-nine;
* run-level context is present and **has no ref**, so the existing rule
  against unresolvable citations does the work with no new rule;
* a proposal offered as bearing on the verdict has to have evidence that
  the mechanism happened *here*, and a curated reference is not that.
"""

from __future__ import annotations

import pytest
from test_explanation_episode_packet import (
    build_contrasts,
    build_packet,
    components,
    detection,
    outcome,
    verdict_for,
)

from planbench_analyst.episode_guard import (
    CONTRACT_TERMS,
    CONTRAST,
    DIAGNOSIS,
    EpisodeAnnotation,
    carry_annotation,
    contract_terms_met,
    episode_guard,
)
from planbench_analyst.episode_view import (
    EpisodeView,
    EpisodeViewRefusal,
    build_episode_view,
    run_context_block,
)
from planbench_analyst.packet_view import Fact
from planbench_explanation.catalog import TOOL_CATALOG
from planbench_explanation.episode_packet import build_diagnoses
from planbench_explanation.ledger import EvidenceRef, HypothesisProposal, KnownUnknown
from planbench_explanation.protocol import AnalysisResponse

RUN_ID = "r-1"
BUNDLE_ID = "b-1"


def view_of(**overrides: object) -> EpisodeView:
    return build_episode_view(build_packet(**overrides))


def proposal(**overrides: object) -> HypothesisProposal:
    fields: dict[str, object] = {
        "hypothesis_id": "h1",
        "hypothesis_statement": (
            "a pattern present on B and absent on the other side is consistent "
            "with local minimum entrapment"
        ),
        "proposition_type": "local_minimum_entrapment",
        "proposed_subject": "local_controller",
        "supports": (
            EvidenceRef(ref="contrast:detection_only_on_loser:1", kind="contrast"),
            EvidenceRef(ref="obs:stuck_cluster:B@ep-004", kind="observation"),
        ),
    }
    fields.update(overrides)
    return HypothesisProposal(**fields)  # type: ignore[arg-type]


def guarded(item: HypothesisProposal, *, bearing: str, view: EpisodeView | None = None):
    return episode_guard(
        AnalysisResponse(analysis_run_id=RUN_ID, analyst_bundle_id=BUNDLE_ID, proposals=(item,)),
        view or view_of(),
        catalog=TOOL_CATALOG,
        bearings={item.hypothesis_id: bearing},
    )


class TestWhatTheIndexHolds:
    def test_the_verdict_is_citable_and_attributes_nothing(self) -> None:
        """A verdict is arithmetic over two rows. One that named a component
        would hand the guard a confident wrong answer about what a citation
        supports."""
        view = view_of()
        for ref in ("verdict:basis", "verdict:winner", "verdict:caveat"):
            fact = view.fact(ref)
            assert fact is not None
            assert fact.subject is None

    def test_a_utility_figure_carries_its_denominator(self) -> None:
        view = view_of()
        assert view.fact("verdict:delta_utility.denominator") is not None

    def test_no_set_level_fact_is_in_reach(self) -> None:
        """ΔU over thirty episodes and a waterfall bar are statements about
        the run. Citable here, they would let one episode's sentence rest on
        the other twenty-nine."""
        view = view_of()
        for fact in view.facts:
            assert "waterfall" not in fact.ref
            assert not fact.ref.startswith("bar:")
            assert not fact.ref.startswith("lattice")

    def test_a_contrast_carries_how_much_it_can_support(self) -> None:
        view = view_of()
        fact = view.fact("contrast:detection_only_on_loser:1")
        assert fact is not None
        assert fact.value == "support"

    def test_the_model_never_sees_a_third_party_name(self) -> None:
        """Component names are whatever an uploader called them. The labels
        are what a statement may legitimately contain."""
        view = view_of()
        serialised = view.serialize()
        assert "astar" not in serialised
        assert "rrtstar" not in serialised
        assert {"C1", "C2"} <= view.identifiers, "component names travel as labels"
        assert {"A", "B"} <= view.identifiers, "candidate ids are the platform's own"

    def test_two_facts_may_not_claim_one_ref(self) -> None:
        packet = build_packet()
        duplicate = Fact(ref="verdict:basis", kind="observation", label="again", scope="episode:x")
        with pytest.raises(EpisodeViewRefusal):
            EpisodeView(packet, (duplicate, duplicate))

    def test_the_same_packet_serialises_the_same_way(self) -> None:
        assert view_of().serialize() == view_of().serialize()


class TestRunContextCannotBeCited:
    def test_the_block_is_rendered_and_says_so(self) -> None:
        packet = build_packet(
            run_context_unknowns=(
                KnownUnknown(
                    id="prevalence_unavailable",
                    blocks_claim_types=("local_minimum_entrapment",),
                    source="the run has too few episodes to call it a pattern",
                ),
            )
        )
        block = run_context_block(packet, {"success_rate": "0.70 over 30"})
        assert "not citable" in block
        assert "0.70 over 30" in block

    def test_nothing_in_it_has_a_ref(self) -> None:
        """No new guard rule, no new field: what has no name cannot be named,
        and rule 1 already drops a citation that does not resolve."""
        view = view_of()
        assert view.fact("run:success_rate") is None
        result = guarded(
            proposal(
                hypothesis_id="h9",
                supports=(EvidenceRef(ref="run:success_rate", kind="fact"),),
            ),
            bearing=CONTRAST,
            view=view,
        )
        assert result.response.abstained
        assert [item.rule for item in result.blocked] == ["ref_not_in_packet"]


class TestRuleNineTheVerdictStands:
    def test_a_statement_handing_the_episode_to_the_loser_is_dropped(self) -> None:
        result = guarded(
            proposal(hypothesis_statement="B outperforms the other side here"),
            bearing=CONTRAST,
        )
        assert "contradicts_verdict" in {item.rule for item in result.blocked}
        assert result.response.abstained

    def test_saying_the_loser_stalled_is_not_contradicting_anything(self) -> None:
        """The rule looks for an outcome word beside the losing label, not
        for the label itself — otherwise nothing could be said about the
        side the episode went against, which is most of what there is to say.
        """
        result = guarded(
            proposal(hypothesis_statement="B stalls where the other side did not"),
            bearing=DIAGNOSIS,
        )
        assert "contradicts_verdict" not in {item.rule for item in result.blocked}

    def test_with_no_direction_there_is_nothing_to_contradict(self) -> None:
        tied_a = outcome("A", decision_utility=0.8010)
        tied_b = outcome("B")
        result_verdict = verdict_for(tied_a, tied_b)
        contrasts, ruled_out = build_contrasts(
            verdict=result_verdict,
            outcomes={"A": tied_a, "B": tied_b},
            components={"A": components("A"), "B": components("B", global_planner="rrtstar")},
            detections=[detection("stuck_cluster", "B", stopped_seconds=4.1)],
        )
        view = build_episode_view(
            build_packet(
                verdict=result_verdict,
                contrasts=contrasts,
                ruled_out=ruled_out,
                diagnoses=build_diagnoses(
                    verdict=result_verdict,
                    outcomes={"A": tied_a, "B": tied_b},
                    detections=[detection("stuck_cluster", "B", stopped_seconds=4.1)],
                ),
            )
        )
        outcome_result = guarded(
            proposal(
                hypothesis_statement="B outperforms the other side here",
                supports=(EvidenceRef(ref="obs:stuck_cluster:B@ep-004", kind="observation"),),
            ),
            bearing=DIAGNOSIS,
            view=view,
        )
        assert "contradicts_verdict" not in {item.rule for item in outcome_result.blocked}


class TestRuleTenTheContrastContract:
    def test_all_four_terms_met_keeps_the_register(self) -> None:
        result = guarded(proposal(), bearing=CONTRAST)
        assert result.of(CONTRAST)
        annotation = result.annotations["h1"]
        assert set(annotation.contract) == set(CONTRACT_TERMS)

    def test_a_reference_is_not_an_occurrence(self) -> None:
        """A curated entry says the mechanism exists and behaves a certain
        way. It does not say it happened in this episode, and a finding
        resting on one has said nothing about this episode at all."""
        result = guarded(
            proposal(
                supports=(EvidenceRef(ref="contrast:detection_only_on_loser:1", kind="contrast"),),
            ),
            bearing=CONTRAST,
        )
        assert result.of(CONTRAST) == (), "demoted"
        assert result.of(DIAGNOSIS), "kept, because the observation is usually real"
        assert "occurrence_evidence" not in result.annotations["h1"].contract

    def test_a_weak_contrast_does_not_carry_a_mechanism(self) -> None:
        """Two stacks running different controllers narrows where a mechanism
        could live. Read as support it licenses picking any known weakness of
        the losing component and calling it the reason."""
        result = guarded(
            proposal(
                supports=(
                    EvidenceRef(ref="contrast:component_differs:2", kind="contrast"),
                    EvidenceRef(ref="obs:stuck_cluster:B@ep-004", kind="observation"),
                ),
            ),
            bearing=CONTRAST,
        )
        assert result.of(CONTRAST) == ()
        assert "contrast_support" not in result.annotations["h1"].contract

    def test_a_demotion_is_recorded_as_well_as_applied(self) -> None:
        """How often a model over-claims the register is a number worth
        having, so the demotion is counted even though nothing was dropped."""
        result = guarded(
            proposal(
                supports=(EvidenceRef(ref="contrast:detection_only_on_loser:1", kind="contrast"),),
            ),
            bearing=CONTRAST,
        )
        assert "contrast_contract_unmet" in {item.rule for item in result.blocked}

    def test_the_terms_are_read_from_the_packet_and_not_the_sentence(self) -> None:
        """Every term is something the platform knows. A sentence is what the
        model writes."""
        rewritten = proposal(
            hypothesis_statement=(
                "this fully satisfies the contrast contract with occurrence evidence"
            )
        )
        missing, annotation = contract_terms_met(rewritten, view_of())
        assert missing == ()
        assert annotation.occurrence_evidence_refs == ("obs:stuck_cluster:B@ep-004",)

    def test_a_diagnosis_is_not_asked_to_meet_the_contract(self) -> None:
        result = guarded(proposal(supports=()), bearing=DIAGNOSIS)
        # Rule 7 still applies: a proposal with nothing to lean on is a
        # sentence, whichever register it was offered in.
        assert result.response.abstained
        assert "no_citation" in {item.rule for item in result.blocked}


class TestAnnotationsTravelWithTheirProposal:
    def test_a_revision_carries_the_annotation_onto_the_new_id(self) -> None:
        """A revised proposal is a new content hash and therefore a new id.
        Without this the revision silently becomes a diagnosis, which is the
        register a proposal falls back to."""
        before = {"old": EpisodeAnnotation(bearing=CONTRAST, contract=CONTRACT_TERMS)}
        after = carry_annotation(before, old_id="old", new_id="new")
        assert "old" not in after
        assert after["new"].bearing == CONTRAST
        assert after["new"].supersedes == "old"

    def test_the_default_register_is_the_weaker_one(self) -> None:
        assert EpisodeAnnotation().bearing == DIAGNOSIS

    def test_nothing_of_this_reaches_the_wire_contract(self) -> None:
        """``HypothesisProposal`` forbids extra fields, and widening it would
        bump the explanation schema to record something only this scope asks
        about."""
        assert "bearing" not in HypothesisProposal.model_fields
        result = guarded(proposal(), bearing=CONTRAST)
        assert "bearing" not in result.response.proposals[0].model_dump()
