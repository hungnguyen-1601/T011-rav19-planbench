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


class TestNotAskingTheModelWhereItIsAlwaysWrong:
    """An episode with no losing side is one the model must not be asked about.

    The evidence is a scored sweep, not a hunch: on `undecidable`
    episodes the analyst made 28 statements and a person scoring them
    blind marked all 28 wrong, while the rounds where it declined were
    all marked correct declines. On `outcome_only` episodes of the same
    cluster - same map, same pairing - it scored 43 right out of 44. A
    mechanism needs a side to be the mechanism of, and where there is
    none the model supplies one anyway.

    So the gate is not about the model being weak. It is about asking a
    question that has no answer, which the platform can tell before it
    spends anything.
    """

    def _undecided_view(self):  # type: ignore[no-untyped-def]
        packet = build_packet()
        verdict = packet.verdict.model_copy(
            update={"basis": "undecidable", "winner": None, "loser": None}
        )
        return build_episode_view(packet.model_copy(update={"verdict": verdict}))

    def test_no_provider_call_is_made(self) -> None:
        provider = MockProvider(script=[answer(hypothesis())])
        run_episode_round(
            analysis_for(None),
            self._undecided_view(),
            provider,
            features=RoundFeatures(episode_scope=True, model_only_where_it_helps=True),
            catalog=TOOL_CATALOG,
        )
        assert not provider.calls, "the model was asked about an episode with no losing side"

    def test_the_round_costs_nothing(self) -> None:
        result = run_episode_round(
            analysis_for(None),
            self._undecided_view(),
            MockProvider(script=[answer(hypothesis())]),
            features=RoundFeatures(episode_scope=True, model_only_where_it_helps=True),
            catalog=TOOL_CATALOG,
        )
        assert result.cost.input_tokens == 0
        assert result.cost.output_tokens == 0

    def test_it_says_the_model_was_not_asked(self) -> None:
        """Not the same as an abstention. An abstention says the analyst
        looked and found nothing; this says nobody looked, and scoring
        the two the same way would credit a gate as a judgement."""
        result = run_episode_round(
            analysis_for(None),
            self._undecided_view(),
            MockProvider(script=[answer(hypothesis())]),
            features=RoundFeatures(episode_scope=True, model_only_where_it_helps=True),
            catalog=TOOL_CATALOG,
        )
        assert ("model_not_asked", "undecidable") in result.flags

    def test_a_decided_episode_still_reaches_the_model(self) -> None:
        provider = MockProvider(script=[answer(hypothesis())])
        run_episode_round(
            analysis_for(None),
            build_episode_view(build_packet()),
            provider,
            features=RoundFeatures(episode_scope=True, model_only_where_it_helps=True),
            catalog=TOOL_CATALOG,
        )
        assert provider.calls, "a decided episode is exactly what the model is for"

    def test_the_gate_is_off_unless_asked_for(self) -> None:
        """Every arm already measured ran with the model asked on every
        episode; a default that changed that would re-run those
        measurements under a system they never ran."""
        provider = MockProvider(script=[answer(hypothesis())])
        run_episode_round(
            analysis_for(None),
            self._undecided_view(),
            provider,
            features=RoundFeatures(episode_scope=True),
            catalog=TOOL_CATALOG,
        )
        assert provider.calls
