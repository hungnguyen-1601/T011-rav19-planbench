"""One episode round, end to end against a scripted provider.

What this file is holding down:

* a round whose packet and arm vector disagree about the question is
  **refused**, both directions, because neither raises anywhere else —
  they run to completion and answer about the wrong thing;
* the register the model declared survives the trip through an engine
  whose output type has no field for it;
* the ten rules apply in the order that keeps their counts meaningful.
"""

from __future__ import annotations

import pytest
from test_explanation_episode_packet import build_packet

from planbench_agent.provider import LLMResponse, MockProvider
from planbench_analyst.episode_guard import CONTRAST, DIAGNOSIS
from planbench_analyst.episode_prompts import EPISODE_SYSTEM
from planbench_analyst.episode_runner import (
    EpisodeRound,
    EpisodeScopeRefusal,
    check_scope,
    declared_bearings,
    episode_runtime_config,
    run_episode_round,
)
from planbench_analyst.episode_view import build_episode_view
from planbench_analyst.features import FeatureRefusal, RoundFeatures
from planbench_explanation.catalog import TOOL_CATALOG

CONTRAST_REF = "contrast:detection_only_on_loser:1"
#: Read off the view rather than written out. A candidate id never
#: reaches the model — it is behind a label — so a ref naming one
#: would be a ref no round could produce.
OBSERVATION_REF = "obs:stuck_cluster:{label}@ep-004"


def answer(*hypotheses: dict[str, object]) -> LLMResponse:
    return LLMResponse(
        structured={"abstained": False, "hypotheses": list(hypotheses)},
        input_tokens=1200,
        output_tokens=340,
    )


def observation_ref() -> str:
    """The detection ref this packet actually carries, label and all."""
    view = build_episode_view(build_packet())
    return next(
        fact.ref
        for fact in view.facts
        if fact.ref.startswith("obs:stuck_cluster:") and "/" not in fact.ref
    )


def hypothesis(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "bearing": CONTRAST,
        "decision": "no_check",
        "statement": (
            "a pattern present on B and absent on the other side is consistent "
            "with local minimum entrapment"
        ),
        "proposition_type": "local_minimum_entrapment",
        "subject": "local_controller",
        "supports": [CONTRAST_REF, observation_ref()],
        "contradicts": [],
        "missing_evidence": [],
        "recommended_experiments": [],
    }
    base.update(overrides)
    return base


def analysis_for(view) -> EpisodeRound:  # type: ignore[no-untyped-def]
    return EpisodeRound(
        analysis_run_id="ar-1",
        analyst_bundle_id="ab-1",
        catalog=TOOL_CATALOG,
    )


def round_over(script: LLMResponse, *, features: RoundFeatures | None = None):
    view = build_episode_view(build_packet())
    return run_episode_round(
        analysis_for(view),
        view,
        MockProvider(script=[script]),
        features=features or RoundFeatures(episode_scope=True),
        catalog=TOOL_CATALOG,
    )


class TestTheScopeIsRefusedRatherThanAssumed:
    def test_an_episode_packet_under_a_run_vector_is_refused(self) -> None:
        with pytest.raises(EpisodeScopeRefusal):
            check_scope(RoundFeatures(), episode=True)

    def test_a_run_packet_under_an_episode_vector_is_refused(self) -> None:
        """The other direction matters as much: there would be no verdict to
        hold the answer against, and nothing else would say so."""
        with pytest.raises(EpisodeScopeRefusal):
            check_scope(RoundFeatures(episode_scope=True), episode=False)

    def test_a_matching_pair_passes_quietly(self) -> None:
        check_scope(RoundFeatures(episode_scope=True), episode=True)
        check_scope(RoundFeatures(), episode=False)

    def test_run_context_without_an_episode_is_refused_at_construction(self) -> None:
        """An arm reporting that it ran a setting which was quietly dropped is
        the one failure nothing downstream can detect."""
        with pytest.raises(FeatureRefusal):
            RoundFeatures(run_context=True)

    def test_the_scope_is_part_of_what_identifies_the_round(self) -> None:
        config = episode_runtime_config(
            RoundFeatures(episode_scope=True),
            source_manifest_hash="deadbeef",
            catalog_version="3.4.0",
        )
        assert config["scope"] == "episode"
        assert config["features"]["episode_scope"] is True  # type: ignore[index]

    def test_two_arm_vectors_do_not_share_an_identity(self) -> None:
        base = episode_runtime_config(
            RoundFeatures(episode_scope=True),
            source_manifest_hash="deadbeef",
            catalog_version="3.4.0",
        )
        with_context = episode_runtime_config(
            RoundFeatures(episode_scope=True, run_context=True),
            source_manifest_hash="deadbeef",
            catalog_version="3.4.0",
        )
        assert base != with_context


class TestTheRegisterSurvivesTheEngine:
    def test_a_declared_contrast_that_meets_the_contract_keeps_it(self) -> None:
        result = round_over(answer(hypothesis()))
        assert result.of(CONTRAST), "the model asked for contrast and earned it"
        assert not result.of(DIAGNOSIS)

    def test_a_declared_contrast_short_of_the_contract_is_demoted(self) -> None:
        result = round_over(answer(hypothesis(supports=[CONTRAST_REF])))
        assert result.of(DIAGNOSIS)
        assert not result.of(CONTRAST)
        assert "contrast_contract_unmet" in {item.rule for item in result.blocked}

    def test_a_declared_diagnosis_is_never_promoted(self) -> None:
        """The platform does not upgrade a register the model did not claim:
        a contrast is the stronger word and the model has to ask for it."""
        result = round_over(answer(hypothesis(bearing=DIAGNOSIS)))
        assert result.of(DIAGNOSIS)
        assert not result.of(CONTRAST)

    def test_an_answer_with_no_register_reads_as_the_weaker_one(self) -> None:
        stripped = hypothesis()
        del stripped["bearing"]
        result = round_over(answer(stripped))
        assert result.of(DIAGNOSIS)

    def test_the_register_is_read_off_the_raw_answer(self) -> None:
        """The engine builds a proposal type with no field for it, so the
        only place it can be taken from is what the model actually sent."""
        payload = {"hypotheses": [hypothesis(), hypothesis(bearing=DIAGNOSIS)]}
        assert declared_bearings(payload) == {0: CONTRAST, 1: DIAGNOSIS}

    def test_a_register_outside_the_two_is_ignored_rather_than_trusted(self) -> None:
        payload = {"hypotheses": [hypothesis(bearing="verified")]}
        assert declared_bearings(payload) == {}


class TestTheRulesStillApply:
    def test_a_statement_handing_the_episode_to_the_loser_is_dropped(self) -> None:
        # Written in the label the model was shown, because that is the
        # only name it has for the losing side — and rule 9 reads the
        # sentence the model actually wrote.
        loser = build_episode_view(build_packet()).aliases.label_for("B")
        result = round_over(
            answer(hypothesis(statement=f"{loser} outperforms the other side here"))
        )
        assert result.response.abstained
        assert "contradicts_verdict" in {item.rule for item in result.blocked}

    def test_a_number_in_a_statement_is_still_dropped(self) -> None:
        """Rule 2 is scope-blind, and it has to stay that way: the numbers
        are in the packet and the refs point at them."""
        result = round_over(
            answer(hypothesis(statement="B stalled for 4.1 seconds, which is entrapment"))
        )
        assert result.response.abstained
        assert "quantity_in_statement" in {item.rule for item in result.blocked}

    def test_a_fabricated_ref_is_still_dropped(self) -> None:
        result = round_over(answer(hypothesis(supports=["obs:nothing:like:this"])))
        assert result.response.abstained
        assert "ref_not_in_packet" in {item.rule for item in result.blocked}

    def test_an_abstention_passes_through(self) -> None:
        script = LLMResponse(
            structured={
                "abstained": True,
                "abstention_reason": "nothing here maps to a mechanism this catalog checks",
                "hypotheses": [],
            },
            input_tokens=900,
            output_tokens=40,
        )
        result = round_over(script)
        assert result.response.abstained
        assert result.annotations == {}


class TestWhatTheModelWasShown:
    def test_the_episode_system_message_is_the_one_used(self) -> None:
        provider = MockProvider(script=[answer(hypothesis())])
        view = build_episode_view(build_packet())
        run_episode_round(
            analysis_for(view),
            view,
            provider,
            features=RoundFeatures(episode_scope=True),
            catalog=TOOL_CATALOG,
        )
        assert provider.calls
        assert provider.calls[0].system == EPISODE_SYSTEM

    def test_run_context_appears_only_when_the_arm_asked_for_it(self) -> None:
        provider = MockProvider(script=[answer(hypothesis())])
        view = build_episode_view(build_packet())
        run_episode_round(
            analysis_for(view),
            view,
            provider,
            features=RoundFeatures(episode_scope=True, run_context=True),
            catalog=TOOL_CATALOG,
            run_measurements={"success_rate": "0.70 over 30"},
        )
        turn = provider.calls[0].messages[0].text
        assert "<<<RUN_CONTEXT" in turn
        assert "0.70 over 30" in turn

        quiet = MockProvider(script=[answer(hypothesis())])
        run_episode_round(
            analysis_for(view),
            view,
            quiet,
            features=RoundFeatures(episode_scope=True),
            catalog=TOOL_CATALOG,
        )
        assert "<<<RUN_CONTEXT" not in quiet.calls[0].messages[0].text


class TestTheArmThatAsksForTwoCitations:
    def test_the_rule_reaches_the_model_when_the_arm_is_on(self) -> None:
        from planbench_analyst.episode_prompts import CONTRAST_CITATION_RULE

        provider = MockProvider(script=[answer(hypothesis())])
        view = build_episode_view(build_packet())
        run_episode_round(
            analysis_for(view),
            view,
            provider,
            features=RoundFeatures(episode_scope=True, contrast_citation_rule=True),
            catalog=TOOL_CATALOG,
        )
        assert CONTRAST_CITATION_RULE in provider.calls[0].system

    def test_and_not_when_it_is_off(self) -> None:
        """`ep_b1` and this arm differ by this sentence and nothing else,
        so a difference in what survives rule 10 is attributable to it."""
        from planbench_analyst.episode_prompts import CONTRAST_CITATION_RULE

        provider = MockProvider(script=[answer(hypothesis())])
        view = build_episode_view(build_packet())
        run_episode_round(
            analysis_for(view),
            view,
            provider,
            features=RoundFeatures(episode_scope=True),
            catalog=TOOL_CATALOG,
        )
        assert CONTRAST_CITATION_RULE not in provider.calls[0].system


class TestAskingAgainWhenOnlyTheWordingWasWrong:
    """A round lost over punctuation is a round worth asking twice.

    On the episodes the analyst is best at - one side reached the goal
    and the other did not, where a blind scoring pass marked it right 43
    times out of 44 - nine of its eleven silences were "every proposal
    was refused (quantity_in_statement)". It knew the answer and wrote
    the number instead of citing it.

    What this must not become is a way to talk the guard round. A claim
    handing the episode to the wrong side is not badly worded, and
    inviting a rewrite there would invite the same claim in safer words.
    """

    def _numeric(self) -> dict[str, object]:
        return hypothesis(statement="the controller stopped for 51 seconds on the losing side")

    def test_a_second_turn_is_taken_and_can_rescue_the_round(self) -> None:
        provider = MockProvider(script=[answer(self._numeric()), answer(hypothesis())])
        result = run_episode_round(
            analysis_for(None),
            build_episode_view(build_packet()),
            provider,
            features=RoundFeatures(episode_scope=True, reword_once=True),
            catalog=TOOL_CATALOG,
        )
        assert len(provider.calls) == 2
        assert result.response.proposals, "the reworded answer was thrown away"
        assert ("reworded_once", "kept_second") in result.flags

    def test_the_second_turn_is_told_what_was_removed(self) -> None:
        provider = MockProvider(script=[answer(self._numeric()), answer(hypothesis())])
        run_episode_round(
            analysis_for(None),
            build_episode_view(build_packet()),
            provider,
            features=RoundFeatures(episode_scope=True, reword_once=True),
            catalog=TOOL_CATALOG,
        )
        second = provider.calls[1].messages[0].text
        assert "quantity_in_statement" in second

    def test_both_turns_are_paid_for(self) -> None:
        """A retry billed as one turn is a spend cap on nothing."""
        provider = MockProvider(script=[answer(self._numeric()), answer(hypothesis())])
        result = run_episode_round(
            analysis_for(None),
            build_episode_view(build_packet()),
            provider,
            features=RoundFeatures(episode_scope=True, reword_once=True),
            catalog=TOOL_CATALOG,
        )
        one = answer(hypothesis())
        assert result.cost.input_tokens == 2 * one.input_tokens

    def test_it_stops_at_one_retry(self) -> None:
        provider = MockProvider(script=[answer(self._numeric()), answer(self._numeric())])
        result = run_episode_round(
            analysis_for(None),
            build_episode_view(build_packet()),
            provider,
            features=RoundFeatures(episode_scope=True, reword_once=True),
            catalog=TOOL_CATALOG,
        )
        assert len(provider.calls) == 2, "a loop would spend a caller's money one turn at a time"
        assert result.response.abstained
        assert ("reworded_once", "kept_first") in result.flags

    def test_a_round_that_kept_something_is_not_retried(self) -> None:
        provider = MockProvider(script=[answer(hypothesis())])
        run_episode_round(
            analysis_for(None),
            build_episode_view(build_packet()),
            provider,
            features=RoundFeatures(episode_scope=True, reword_once=True),
            catalog=TOOL_CATALOG,
        )
        assert len(provider.calls) == 1

    def test_the_retry_is_off_unless_asked_for(self) -> None:
        provider = MockProvider(script=[answer(self._numeric()), answer(hypothesis())])
        run_episode_round(
            analysis_for(None),
            build_episode_view(build_packet()),
            provider,
            features=RoundFeatures(episode_scope=True),
            catalog=TOOL_CATALOG,
        )
        assert len(provider.calls) == 1

    def test_a_wrong_claim_is_not_invited_to_try_again(self) -> None:
        """The property the whole retry hangs on.

        A statement handing the episode to the side the platform did not
        name is not badly worded — it is wrong. Offering a rewrite there
        asks for the same claim in safer words, and the guard would have
        one fewer reason to refuse it the second time. Written as a test
        rather than trusted to the constant, because adding one rule to
        `REWORDABLE_RULES` is a one-word change and nothing else here
        noticed when it was made.
        """
        from planbench_analyst.episode_runner import REWORDABLE_RULES

        assert "contradicts_verdict" not in REWORDABLE_RULES
        winner = build_episode_view(build_packet()).packet.verdict.winner
        provider = MockProvider(
            script=[
                answer(hypothesis(statement=f"{winner} lost this episode to the other stack")),
                answer(hypothesis()),
            ]
        )
        run_episode_round(
            analysis_for(None),
            build_episode_view(build_packet()),
            provider,
            features=RoundFeatures(episode_scope=True, reword_once=True),
            catalog=TOOL_CATALOG,
        )
        assert len(provider.calls) == 1, "a claim about the wrong side was offered a second try"
