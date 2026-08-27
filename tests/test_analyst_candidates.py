"""W2 — the platform proposes the space and the model chooses inside it.

Left to invent the mechanism space itself, a model reaches for whatever
the packet's prose suggests and the guard drops the result, which
measures the guard rather than the model. The shortlist moves that job
to the platform — and every rule below exists because the obvious way to
build one would have quietly changed what is being measured.
"""

from __future__ import annotations

import pytest
from test_analyst_packet_view import observation, packet
from test_analyst_retrieval_round import offers_for, traits_for
from test_analyst_runner import MEASURED_TASK, answer, hypothesis, prepared, scripted

from planbench_analyst.candidates import (
    UNKNOWN,
    CandidateRefusal,
    generate_candidates,
    generator_recall_at_k,
    inject_distractors,
    render_candidates,
)
from planbench_analyst.features import RoundFeatures
from planbench_analyst.knowledge_provider import trait_offers
from planbench_analyst.runner import run_round
from planbench_explanation.catalog import TOOL_CATALOG
from planbench_explanation.integration import TYPICAL_AVAILABLE_EVIDENCE


def built(**overrides):  # type: ignore[no-untyped-def]
    fields = {"observations": [observation()], "task": MEASURED_TASK}
    fields.update(overrides)
    return packet(**fields)


def shortlist(case=None, **overrides):  # type: ignore[no-untyped-def]
    fields = {
        "catalog": TOOL_CATALOG,
        "available_evidence": TYPICAL_AVAILABLE_EVIDENCE,
    }
    fields.update(overrides)
    return generate_candidates(case or built(), **fields)


# --------------------------------------------------------------------------
# What a candidate is, and is not
# --------------------------------------------------------------------------


def test_a_candidate_carries_no_evidence_refs() -> None:
    """The refs are the model's to choose and the guard's to score. A
    shortlist that arrived with citations attached would score the
    generator's reading while looking like the model's."""
    for candidate in shortlist():
        assert not hasattr(candidate, "supporting_refs")
        assert not hasattr(candidate, "evidence_refs")


def test_the_detector_mapping_reaches_the_shortlist() -> None:
    mechanisms = {item.mechanism_id for item in shortlist()}
    assert "geometric_infeasibility" in mechanisms


def test_unknown_is_always_on_the_list_and_always_last() -> None:
    """A shortlist with no way to decline is a forced choice, and a
    forced choice is what makes an analyst confidently wrong."""
    for case in (built(), packet(task=MEASURED_TASK)):
        offered = shortlist(case)
        assert offered[-1].mechanism_id == UNKNOWN
        assert offered[-1].subject is None


def test_a_packet_with_no_detections_still_gets_a_shortlist() -> None:
    offered = shortlist(packet(task=MEASURED_TASK))
    assert [item.mechanism_id for item in offered] == [UNKNOWN]


# --------------------------------------------------------------------------
# Three sources, merged, never doubled
# --------------------------------------------------------------------------


def test_one_mechanism_reached_twice_is_one_candidate_with_two_reasons() -> None:
    """Listed twice it would read as two mechanisms agreeing."""
    case = built()
    offered = shortlist(case, knowledge=offers_for(case))
    keys = [item.key for item in offered]
    assert len(keys) == len(set(keys))
    merged = [item for item in offered if len(item.sources) > 1]
    assert merged, "the knowledge base and the detector should meet on this packet"
    assert set(merged[0].sources) >= {"detector", "knowledge"}


def test_a_nature_raises_a_mechanism_and_cannot_invent_one() -> None:
    """A trait says what an algorithm is like, not what happened in this
    run. One that could conjure a candidate would be folklore arriving
    through the platform's own door."""
    case = built()
    natures = trait_offers(case, traits_for("dwa"))
    assert natures
    without = {item.key for item in shortlist(case)}
    with_traits = {item.key for item in shortlist(case, traits=natures)}
    assert with_traits == without


def test_a_nature_about_a_component_in_play_is_recorded_as_a_reason() -> None:
    case = built(observations=[observation("stuck_cluster")])
    natures = trait_offers(case, traits_for("dwa"))
    offered = shortlist(case, traits=natures)
    controller = [item for item in offered if item.subject == "local_controller"]
    assert controller
    assert "traits" in controller[0].sources
    assert any(reason.startswith("trait:") for reason in controller[0].triggered_by)


def test_the_order_is_the_same_on_two_runs_of_one_packet() -> None:
    case = built()
    assert [item.key for item in shortlist(case)] == [item.key for item in shortlist(case)]


# --------------------------------------------------------------------------
# Verification options are a separate variable
# --------------------------------------------------------------------------


def test_the_options_can_be_withheld_while_the_shortlist_stands() -> None:
    """E4a measures the prior and E4b the hint; bundled, a gain in
    either would be reported as a gain in both."""
    with_options = shortlist()
    without = shortlist(verification_options=False)
    assert [item.key for item in with_options] == [item.key for item in without]
    assert any(item.verification_options for item in with_options)
    assert not any(item.verification_options for item in without)


def test_an_option_this_run_cannot_serve_is_never_offered() -> None:
    """Naming it would send the analyst at a tool the host refuses at
    admission, and the refusal reads to a model as a broken platform."""
    offered = shortlist(available_evidence=frozenset())
    named = {option.tool_id for candidate in offered for option in candidate.verification_options}
    # Only the card that needs no evidence at all survives; every check
    # and every reader of a block this run does not hold is gone.
    assert named <= {"get_known_unknowns"}


def test_unknown_still_gets_the_evidence_capable_menu() -> None:
    """A round that cannot name a mechanism is exactly the one that
    needs to go and read something."""
    unknown = shortlist()[-1]
    assert unknown.mechanism_id == UNKNOWN
    assert unknown.verification_options


def test_every_offered_option_names_the_arguments_it_needs() -> None:
    for candidate in shortlist():
        for option in candidate.verification_options:
            assert isinstance(option.required_arguments, tuple)


# --------------------------------------------------------------------------
# generator_recall@K, scored on the generator's own output
# --------------------------------------------------------------------------


def test_recall_finds_the_planted_mechanism_in_the_first_k() -> None:
    assert generator_recall_at_k(
        shortlist(),
        expected_mechanism="geometric_infeasibility",
        expected_subject="costmap_inflation",
        k=5,
    )


def test_recall_is_false_when_the_mechanism_is_not_offered() -> None:
    assert not generator_recall_at_k(shortlist(), expected_mechanism="perception_attribution", k=5)


def test_recall_respects_the_cut_off() -> None:
    offered = shortlist()
    assert not generator_recall_at_k(offered, expected_mechanism=UNKNOWN, k=1) or len(offered) == 1


# --------------------------------------------------------------------------
# Distractors: eval only, fail-closed
# --------------------------------------------------------------------------


def test_distractors_are_refused_outside_a_development_partition() -> None:
    """A production shortlist carrying invented mechanisms is the
    platform lying to its own analyst."""
    for partition in ("confirmatory", "production", ""):
        with pytest.raises(CandidateRefusal, match="development"):
            inject_distractors(shortlist(), partition=partition, seed=1, rate=0.5)


def test_a_distractor_is_drawn_from_what_the_platform_knows() -> None:
    """Nothing here is told the answer; the scorer's labels never reach
    this module."""
    offered = inject_distractors(shortlist(), partition="development", seed=7, rate=1.0)
    injected = [item for item in offered if "distractor" in item.sources]
    assert injected
    assert all(item.triggered_by == ("eval:distractor",) for item in injected)


def test_distractors_keep_unknown_last() -> None:
    offered = inject_distractors(shortlist(), partition="development", seed=7, rate=1.0)
    assert offered[-1].mechanism_id == UNKNOWN


def test_the_same_seed_injects_the_same_distractors() -> None:
    first = inject_distractors(shortlist(), partition="development", seed=3, rate=0.5)
    again = inject_distractors(shortlist(), partition="development", seed=3, rate=0.5)
    assert [item.key for item in first] == [item.key for item in again]


def test_dropping_the_gold_candidate_has_to_be_told_which_one_it_is() -> None:
    """A harness that guessed would be scoring its own guess."""
    with pytest.raises(CandidateRefusal, match="which one"):
        inject_distractors(shortlist(), partition="development", seed=1, rate=0.0, drop_gold=True)


def test_a_negative_control_removes_the_right_answer_without_forcing_a_choice() -> None:
    offered = inject_distractors(
        shortlist(),
        partition="development",
        seed=1,
        rate=0.0,
        drop_gold=True,
        gold=("geometric_infeasibility", "costmap_inflation"),
    )
    assert not generator_recall_at_k(offered, expected_mechanism="geometric_infeasibility", k=10)
    assert offered[-1].mechanism_id == UNKNOWN


def test_a_rate_that_is_not_a_fraction_is_refused() -> None:
    with pytest.raises(CandidateRefusal, match="fraction"):
        inject_distractors(shortlist(), partition="development", seed=1, rate=1.5)


# --------------------------------------------------------------------------
# The round
# --------------------------------------------------------------------------


def test_the_shortlist_is_off_unless_the_arm_declares_it() -> None:
    outcome = run_round(prepared(), scripted(answer(hypothesis())))
    assert outcome.shortlist == ()
    assert not any(event.startswith("candidates:") for event in outcome.events)


def test_a_round_that_declares_it_records_what_the_generator_produced() -> None:
    outcome = run_round(
        prepared(),
        scripted(answer(hypothesis())),
        features=RoundFeatures(candidate_shortlist=True),
    )
    assert outcome.shortlist
    assert any(event.startswith("candidates:") for event in outcome.events)


def test_the_rendered_block_names_mechanisms_and_never_argues_for_one() -> None:
    text = render_candidates(shortlist())
    assert "geometric_infeasibility" in text
    assert UNKNOWN in text
    assert "likely" not in text and "probably" not in text
