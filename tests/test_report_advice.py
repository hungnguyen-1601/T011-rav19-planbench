"""What a finished run may be written down as — and what it may not.

Three stored runs carry these tests, because the sentences being barred
are the ones a real report invites:

* ``open_hall_v2_global_planner_selection`` has **no card** — `astar+dwa`
  failed G3 — so the only thing it can be read into is a winner it never
  named.
* ``open_hall_v2_local_controller_selection`` has a **CLEAR_RECOMMENDATION**
  whose three sensitivity margins are all null and whose Pareto label is
  ``UNCERTAIN_DOMINANCE``: four fields that are present, empty, and read
  as reassurance.
* ``open_hall_2_global_planner_selection`` is **NEAR_EQUIVALENT** with a
  CI of [-0.0043, +0.0085] and a median of +0.0090 sitting outside it —
  a real run where the headline number and the interval printed beside it
  are two different statistics.

Every citation is asserted against the stored file rather than trusted.
An unresolvable ``field_path`` is dropped silently by ``keep_resolvable``,
so a typo and a rule that chose not to fire look exactly alike from the
outside; only an exhaustive check tells them apart.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from planbench_decision.advice import Advice
from planbench_decision.report_advice import (
    REPORT_ADVICE_CODES,
    build_reporting_source,
    report_advice,
)
from planbench_decision.self_check import exists

RUNS = Path(__file__).resolve().parent.parent / "artifacts/runs"

#: 1 of 2 candidates through the gates, so no ΔU and no card.
GATED = RUNS / "2026-08-11/open_hall_v2_global_planner_selection_ce26fe87/comparison_report.json"

#: A card with a decisive interval and nothing swept around it.
CARDED = RUNS / "2026-08-11/open_hall_v2_local_controller_selection_3edf8fe6/comparison_report.json"

#: A card whose interval spans zero, and whose median sits outside it.
TIED = RUNS / "2026-08-12/open_hall_2_global_planner_selection_ce26fe87/comparison_report.json"


def load(path: Path) -> dict[str, Any]:
    if not path.exists():
        pytest.skip(f"stored run {path.name} not present in this checkout")
    return json.loads(path.read_text())


@pytest.fixture
def gated() -> dict[str, Any]:
    return load(GATED)


@pytest.fixture
def carded() -> dict[str, Any]:
    return load(CARDED)


@pytest.fixture
def tied() -> dict[str, Any]:
    return load(TIED)


def codes(items: tuple[Advice, ...]) -> set[str]:
    return {item.code for item in items}


def one(items: tuple[Advice, ...], code: str) -> Advice:
    found = [item for item in items if item.code == code]
    assert found, f"{code} did not fire; emitted {sorted(codes(items))}"
    return found[0]


def advise(report: dict[str, Any], card: dict[str, Any] | None = None) -> tuple[Advice, ...]:
    return report_advice(build_reporting_source(report, card))


class TestARunThatNamedNobody:
    def test_it_says_there_is_no_winner_to_quote(self, gated: dict[str, Any]) -> None:
        found = one(advise(gated), "RP_NO_CARD_NO_WINNER")
        assert found.severity == "blocking"
        assert "winner" in found.do_not

    def test_the_reason_the_run_gave_is_carried_as_the_ground(self, gated: dict[str, Any]) -> None:
        """The report already explains itself in `why_no_card`; repeating
        it in our own words would be a second, unversioned explanation."""
        found = one(advise(gated), "RP_NO_CARD_NO_WINNER")
        assert found.ground == gated["why_no_card"]

    def test_it_falls_back_to_the_null_card_when_no_reason_was_given(self) -> None:
        """`decision_card: null` is present-and-null, which `exists`
        accepts. A rule insisting on `why_no_card` would go silent on
        exactly the reports that explain themselves least."""
        found = one(advise({"decision_card": None}), "RP_NO_CARD_NO_WINNER")
        assert found.field_path == "report.decision_card"

    def test_a_run_with_a_card_draws_no_such_advice(self, carded: dict[str, Any]) -> None:
        assert "RP_NO_CARD_NO_WINNER" not in codes(advise(carded))


class TestACandidateThatNeverClearedTheGates:
    def test_it_may_not_be_placed_in_a_ranking(self, gated: dict[str, Any]) -> None:
        found = one(advise(gated), "RP_BLOCKED_CANDIDATE_NOT_RANKABLE")
        assert found.subject == "60c8e26fe591"
        assert found.severity == "blocking"

    def test_the_words_a_reader_would_reach_for_are_named(self, gated: dict[str, Any]) -> None:
        """ "Be careful with eliminated candidates" is advice nobody acts
        on. "Do not call it the runner-up" is."""
        found = one(advise(gated), "RP_BLOCKED_CANDIDATE_NOT_RANKABLE")
        assert "runner-up" in found.do_not
        assert "G3" in found.claim

    def test_a_candidate_that_cleared_them_draws_none(self, gated: dict[str, Any]) -> None:
        blocked = [
            item for item in advise(gated) if item.code == "RP_BLOCKED_CANDIDATE_NOT_RANKABLE"
        ]
        assert [item.subject for item in blocked] == ["60c8e26fe591"]


class TestATieIsNotAWin:
    def test_near_equivalent_is_flagged(self, tied: dict[str, Any]) -> None:
        found = one(advise(tied), "RP_NEAR_EQUIVALENT_IS_NOT_A_WIN")
        assert found.severity == "blocking"
        assert found.subject == tied["decision_card"]["recommended"]["candidate_id"]

    def test_the_barred_verbs_are_spelled_out(self, tied: dict[str, Any]) -> None:
        found = one(advise(tied), "RP_NEAR_EQUIVALENT_IS_NOT_A_WIN")
        for verb in ("beat", "outperformed", "won"):
            assert verb in found.do_not

    def test_a_clear_recommendation_is_left_alone(self, carded: dict[str, Any]) -> None:
        """The status exists to be believed when it is decisive; objecting
        there would flag the platform for being honest."""
        assert "RP_NEAR_EQUIVALENT_IS_NOT_A_WIN" not in codes(advise(carded))


class TestAnIntervalThatContainsZero:
    def test_it_may_not_be_quoted_as_a_difference(self, tied: dict[str, Any]) -> None:
        found = one(advise(tied), "RP_CI_CONTAINS_ZERO")
        assert found.severity == "blocking"
        assert found.field_path == "card.evidence.ci95"

    def test_both_ends_of_the_interval_are_in_the_claim(self, tied: dict[str, Any]) -> None:
        low, high = tied["decision_card"]["evidence"]["ci95"]
        found = one(advise(tied), "RP_CI_CONTAINS_ZERO")
        assert f"{low:+.4f}" in found.claim
        assert f"{high:+.4f}" in found.claim

    def test_the_point_estimate_is_named_as_the_thing_not_to_quote(
        self, tied: dict[str, Any]
    ) -> None:
        median = tied["decision_card"]["evidence"]["delta_u_vs_second"]
        found = one(advise(tied), "RP_CI_CONTAINS_ZERO")
        assert f"{median:+.4f}" in found.do_not

    def test_an_interval_clear_of_zero_draws_nothing(self, carded: dict[str, Any]) -> None:
        assert "RP_CI_CONTAINS_ZERO" not in codes(advise(carded))

    def test_it_fires_even_when_the_card_already_says_near_equivalent(
        self, tied: dict[str, Any]
    ) -> None:
        """Unlike `self_check`, which stays quiet under NEAR_EQUIVALENT
        because the card is agreeing with itself. Here the subject is the
        sentence, and "ΔU = +0.009" is quotable off a NEAR_EQUIVALENT card
        exactly as easily as off a decisive one."""
        assert tied["decision_card"]["status"] == "NEAR_EQUIVALENT"
        assert "RP_CI_CONTAINS_ZERO" in codes(advise(tied))


class TestTwoStatisticsOnOneLine:
    """`delta_u_vs_second` is a median; `ci95` is the interval of the mean
    (HĐ-11.2). Printed side by side they read as one number and its error
    bar, and on this stored run the median falls outside its own apparent
    interval — which looks like a bug and is really two statistics."""

    def test_the_separation_is_reported(self, tied: dict[str, Any]) -> None:
        evidence = tied["decision_card"]["evidence"]
        low, high = evidence["ci95"]
        median = evidence["delta_u_vs_second"]
        assert not low <= median <= high, "fixture no longer shows the separation"
        found = one(advise(tied), "RP_MEDIAN_OUTSIDE_ITS_INTERVAL")
        assert found.field_path == "card.evidence.delta_u_vs_second"

    def test_the_mean_is_offered_as_the_third_number(self, tied: dict[str, Any]) -> None:
        mean = tied["decision_card"]["evidence"]["delta_u_mean"]
        found = one(advise(tied), "RP_MEDIAN_OUTSIDE_ITS_INTERVAL")
        assert f"{mean:+.6f}" in found.ground
        assert "delta_u_mean" in found.do or "mean" in found.do

    def test_a_median_inside_its_interval_says_nothing(self, carded: dict[str, Any]) -> None:
        assert "RP_MEDIAN_OUTSIDE_ITS_INTERVAL" not in codes(advise(carded))


class TestNullIsNotZero:
    """Four fields that are present and empty. `resolve()` cannot tell
    them from absent; `exists()` can, and that is the whole reason these
    rules can cite the field they are about."""

    def test_an_unmeasured_effect_size_is_not_no_effect(self, carded: dict[str, Any]) -> None:
        report = deepcopy(carded)
        report["decision_card"]["evidence"]["effect_size"] = None
        found = one(advise(report), "RP_EFFECT_SIZE_NOT_MEASURED")
        assert found.field_path == "card.evidence.effect_size"
        assert "no effect" in found.do_not

    def test_the_citation_survives_pointing_at_a_null(self, carded: dict[str, Any]) -> None:
        """`keep_resolvable` uses `exists`, so citing a field that is
        present and null is allowed. Under `resolve() is not None` this
        advice would vanish without a word."""
        report = deepcopy(carded)
        report["decision_card"]["evidence"]["effect_size"] = None
        source = build_reporting_source(report)
        assert exists(source, "card.evidence.effect_size")
        assert "RP_EFFECT_SIZE_NOT_MEASURED" in codes(report_advice(source))

    def test_a_measured_effect_size_draws_nothing(self, carded: dict[str, Any]) -> None:
        assert carded["decision_card"]["evidence"]["effect_size"] is not None
        assert "RP_EFFECT_SIZE_NOT_MEASURED" not in codes(advise(carded))

    def test_unswept_margins_are_not_stability(self, carded: dict[str, Any]) -> None:
        found = one(advise(carded), "RP_SENSITIVITY_NOT_MEASURED")
        assert "3 of the 3" in found.claim
        assert found.field_path == "card.evidence.weight_stability_margin"

    def test_it_cites_the_one_that_is_missing_when_only_one_is(self, tied: dict[str, Any]) -> None:
        """This run swept weights and anchors and not the neighbourhood,
        so the citation has to land on `robustness_margin` — pointing at a
        margin that *was* measured would be a claim the reader can refute
        at a glance."""
        found = one(advise(tied), "RP_SENSITIVITY_NOT_MEASURED")
        assert found.field_path == "card.evidence.robustness_margin"
        assert "robust" in found.do_not

    def test_all_three_measured_says_nothing(self, carded: dict[str, Any]) -> None:
        report = deepcopy(carded)
        report["decision_card"]["evidence"].update(
            {
                "weight_stability_margin": 1.0,
                "anchor_stability": "unchanged_at_±10%",
                "robustness_margin": 0.4,
            }
        )
        assert "RP_SENSITIVITY_NOT_MEASURED" not in codes(advise(report))

    def test_uncertain_dominance_is_not_dominance(self, carded: dict[str, Any]) -> None:
        found = one(advise(carded), "RP_DOMINANCE_NOT_ESTABLISHED")
        assert "dominates" in found.do_not

    def test_a_frontier_label_draws_nothing(self, tied: dict[str, Any]) -> None:
        assert tied["decision_card"]["pareto_label"] == "PARETO_FRONTIER"
        assert "RP_DOMINANCE_NOT_ESTABLISHED" not in codes(advise(tied))

    def test_the_runner_up_is_not_offered_as_the_alternative(self, carded: dict[str, Any]) -> None:
        assert carded["decision_card"]["alternative"] is None
        found = one(advise(carded), "RP_RUNNER_UP_IS_NOT_THE_ALTERNATIVE")
        assert found.field_path == "card.alternative"
        assert "runner-up" in found.do_not

    def test_a_card_that_names_one_draws_nothing(self, carded: dict[str, Any]) -> None:
        report = deepcopy(carded)
        report["decision_card"]["alternative"] = {"candidate_id": "x", "reason": "trên biên"}
        assert "RP_RUNNER_UP_IS_NOT_THE_ALTERNATIVE" not in codes(advise(report))


class TestTheResultBelongsToOneDeployment:
    def test_the_deployment_is_named(self, carded: dict[str, Any]) -> None:
        found = one(advise(carded), "RP_SCOPE_IS_ONE_DEPLOYMENT")
        assert "open_hall_v2" in found.claim
        assert "open_hall_v2" in found.do

    def test_the_generalisation_is_quoted_verbatim(self, carded: dict[str, Any]) -> None:
        """The failure mode is a person reaching for a stronger noun, and
        a general warning does not compete with a stronger noun."""
        found = one(advise(carded), "RP_SCOPE_IS_ONE_DEPLOYMENT")
        assert "warehouses" in found.do_not

    def test_the_claim_level_is_reported_as_the_weakest_of_three(
        self, carded: dict[str, Any]
    ) -> None:
        found = one(advise(carded), "RP_CLAIM_IS_MISSION_LEVEL")
        assert "ROBUST_DEPLOYMENT_LEVEL" in found.do_not

    def test_a_partial_scope_says_which_layer_was_held_fixed(self, carded: dict[str, Any]) -> None:
        """`local_controller_selection` ranks controllers under one
        planner. "DWA beats A*" is a methodological error, not a result."""
        found = one(advise(carded), "RP_SCOPE_HELD_ONE_LAYER_FIXED")
        assert "global planner" in found.claim
        assert "local controllers" in found.do

    def test_the_other_scope_reads_the_other_way_round(self, tied: dict[str, Any]) -> None:
        found = one(advise(tied), "RP_SCOPE_HELD_ONE_LAYER_FIXED")
        assert "local controller" in found.claim
        assert "global planners" in found.do

    def test_a_full_stack_run_holds_nothing_fixed_and_draws_nothing(
        self, carded: dict[str, Any]
    ) -> None:
        report = deepcopy(carded)
        report["decision_card"]["experiment_scope"] = "full_stack_selection"
        assert "RP_SCOPE_HELD_ONE_LAYER_FIXED" not in codes(advise(report))


class TestAScreeningIsNotAGuarantee:
    def test_a_host_only_latency_may_not_be_called_real_time(self, carded: dict[str, Any]) -> None:
        found = one(advise(carded), "RP_HOST_ONLY_LATENCY")
        assert "real-time guarantee" in found.do_not
        assert found.severity == "disclosure"

    def test_the_gates_own_caveat_is_carried(self, carded: dict[str, Any]) -> None:
        caveat = carded["candidates"][0]["gates"]["G4"]["caveat"]
        found = one(advise(carded), "RP_HOST_ONLY_LATENCY")
        assert caveat in found.ground

    def test_a_confirmed_measurement_draws_nothing(self, carded: dict[str, Any]) -> None:
        report = deepcopy(carded)
        for candidate in report["candidates"]:
            candidate["gates"]["G4"]["status"] = "measured_on_target"
        assert "RP_HOST_ONLY_LATENCY" not in codes(advise(report))

    def test_an_estimated_memory_figure_is_not_a_fit(self, carded: dict[str, Any]) -> None:
        """G5 screens in one direction: over budget certainly does not
        fit, under budget establishes nothing about the reverse."""
        found = one(advise(carded), "RP_MEMORY_NEVER_MEASURED")
        assert "fits in the robot's memory" in found.do_not
        assert found.field_path.endswith("gates.G5.status")


class TestARateCarriesItsDenominator:
    def test_the_episode_count_is_stated(self, carded: dict[str, Any]) -> None:
        found = one(advise(carded), "RP_RATE_NEEDS_ITS_DENOMINATOR")
        assert "30 episodes" in found.claim

    def test_the_resolution_of_one_episode_is_computed(self, carded: dict[str, Any]) -> None:
        """30 episodes makes one episode worth 3.3 points, so a 3-point
        gap between two candidates is one episode landing differently."""
        found = one(advise(carded), "RP_RATE_NEEDS_ITS_DENOMINATOR")
        assert "3.3 percentage points" in found.ground
        assert "3.3 points" in found.do_not

    def test_the_denominator_is_shown_in_the_form_it_should_be_written(
        self, gated: dict[str, Any]
    ) -> None:
        found = one(advise(gated), "RP_RATE_NEEDS_ITS_DENOMINATOR")
        assert "70% (21 of 30)" in found.do

    def test_a_run_quoting_no_rate_draws_nothing(self, carded: dict[str, Any]) -> None:
        report = deepcopy(carded)
        for candidate in report["candidates"]:
            candidate["success_rate"] = None
        assert "RP_RATE_NEEDS_ITS_DENOMINATOR" not in codes(advise(report))

    def test_rows_resting_on_different_samples_are_flagged(self, carded: dict[str, Any]) -> None:
        report = deepcopy(carded)
        report["candidates"][0]["n_distinct_episodes"] = 12
        found = one(advise(report), "RP_UNEQUAL_EPISODE_COUNTS")
        assert found.subject == report["candidates"][0]["candidate_id"]
        assert "12" in found.claim and "30" in found.claim

    def test_equal_samples_draw_nothing(self, carded: dict[str, Any]) -> None:
        assert "RP_UNEQUAL_EPISODE_COUNTS" not in codes(advise(carded))


class TestWhoSignedAndUnderWhichWeights:
    def test_a_pending_card_is_not_an_approved_one(self, carded: dict[str, Any]) -> None:
        found = one(advise(carded), "RP_NOT_APPROVED_YET")
        assert "signed off" in found.do_not

    def test_an_approved_card_draws_nothing(self, carded: dict[str, Any]) -> None:
        """HĐ-14 is about a signature that has not happened, not about
        casting doubt on one that has."""
        report = deepcopy(carded)
        report["decision_card"]["approval"] = {"status": "APPROVED", "by": "an", "at": "now"}
        assert "RP_NOT_APPROVED_YET" not in codes(advise(report))

    def test_a_rejected_card_is_flagged_too(self, carded: dict[str, Any]) -> None:
        report = deepcopy(carded)
        report["decision_card"]["approval"]["status"] = "REJECTED"
        assert "REJECTED" in one(advise(report), "RP_NOT_APPROVED_YET").claim

    def test_a_business_adjusted_ranking_is_not_a_measurement(self, carded: dict[str, Any]) -> None:
        report = deepcopy(carded)
        report["decision_card"]["decision_mode"] = "business_adjusted"
        report["decision_card"]["decision_mode_label"] = "Có điều chỉnh theo chi phí vận hành"
        found = one(advise(report), "RP_BUSINESS_ADJUSTED_IS_NOT_A_MEASUREMENT")
        assert "Có điều chỉnh theo chi phí vận hành" in found.ground
        assert "measurement result" in found.do_not

    def test_the_technical_mode_draws_nothing(self, carded: dict[str, Any]) -> None:
        assert carded["decision_card"]["decision_mode"] == "technical"
        assert "RP_BUSINESS_ADJUSTED_IS_NOT_A_MEASUREMENT" not in codes(advise(carded))


class TestTheCardCanComeFromElsewhere:
    def test_it_defaults_to_the_report_own_card(self, carded: dict[str, Any]) -> None:
        assert build_reporting_source(carded)["card"] == carded["decision_card"]

    def test_an_explicit_card_wins(self, carded: dict[str, Any]) -> None:
        """The API's run row keeps the approved card of record, and
        `render_decision_markdown` reads `run.card or
        report["decision_card"]`. A reviewer whose signature lives there
        must not be told their card is unapproved."""
        approved = deepcopy(carded["decision_card"])
        approved["approval"] = {"status": "APPROVED", "by": "an", "at": "2026-08-12"}
        assert "RP_NOT_APPROVED_YET" not in codes(advise(carded, approved))

    def test_a_report_with_no_card_at_all_carries_none(self) -> None:
        assert build_reporting_source({"candidates": []})["card"] is None


class TestEveryCitationResolves:
    @pytest.mark.parametrize("path", [GATED, CARDED, TIED])
    def test_against_every_stored_run(self, path: Path) -> None:
        """An unresolvable path is dropped without a message, so a typo
        and a rule that chose not to fire are indistinguishable from the
        outside. This is the only thing that tells them apart."""
        source = build_reporting_source(load(path))
        found = report_advice(source)
        assert found, f"{path.name} produced no advice at all"
        for item in found:
            assert exists(source, item.field_path), f"{item.code} cites {item.field_path}"

    def test_against_the_synthetic_cases_too(self, carded: dict[str, Any]) -> None:
        report = deepcopy(carded)
        report["decision_card"]["evidence"]["effect_size"] = None
        report["decision_card"]["decision_mode"] = "business_adjusted"
        report["candidates"][0]["n_distinct_episodes"] = 12
        source = build_reporting_source(report)
        for item in report_advice(source):
            assert exists(source, item.field_path), f"{item.code} cites {item.field_path}"


class TestEveryPublishedCodeIsReachable:
    """A code in the tuple that no input can produce is a rule that was
    renamed, or one whose citation silently stopped resolving."""

    def test_fifteen_of_them_fire_on_real_stored_runs(self) -> None:
        seen: set[str] = set()
        for path in (GATED, CARDED, TIED):
            seen |= codes(advise(load(path)))
        assert seen <= set(REPORT_ADVICE_CODES)
        assert len(seen) == 15, sorted(set(REPORT_ADVICE_CODES) - seen)

    def test_the_remaining_three_fire_on_shapes_the_card_supports(
        self, carded: dict[str, Any]
    ) -> None:
        report = deepcopy(carded)
        report["decision_card"]["evidence"]["effect_size"] = None
        report["decision_card"]["decision_mode"] = "business_adjusted"
        report["candidates"][0]["n_distinct_episodes"] = 12
        assert {
            "RP_EFFECT_SIZE_NOT_MEASURED",
            "RP_BUSINESS_ADJUSTED_IS_NOT_A_MEASUREMENT",
            "RP_UNEQUAL_EPISODE_COUNTS",
        } <= codes(advise(report))


class TestWhatIsPublished:
    def test_every_emitted_code_is_declared(self, carded: dict[str, Any]) -> None:
        assert codes(advise(carded)) <= set(REPORT_ADVICE_CODES)

    def test_the_codes_are_unique(self) -> None:
        assert len(REPORT_ADVICE_CODES) == len(set(REPORT_ADVICE_CODES))

    def test_everything_is_tagged_as_reporting(self, carded: dict[str, Any]) -> None:
        assert all(item.kind == "reporting" for item in advise(carded))

    def test_every_blocking_advice_names_the_barred_move(self) -> None:
        for path in (GATED, CARDED, TIED):
            for item in advise(load(path)):
                if item.severity == "blocking":
                    assert item.do_not, item.code

    def test_every_advice_names_a_legitimate_move(self) -> None:
        for path in (GATED, CARDED, TIED):
            for item in advise(load(path)):
                assert item.do.strip(), item.code


class TestItNeverBreaks:
    def test_an_empty_source_returns_nothing(self) -> None:
        assert report_advice({}) == ()

    def test_a_malformed_report_returns_nothing_rather_than_raising(self) -> None:
        assert report_advice({"report": {"candidates": "not a list"}}) == ()

    def test_a_card_of_an_unexpected_type_is_ignored(self, carded: dict[str, Any]) -> None:
        source = {"report": dict(carded), "card": "not a card"}
        for item in report_advice(source):
            assert not item.field_path.startswith("card.")

    def test_an_interval_that_is_not_a_pair_is_ignored(self, carded: dict[str, Any]) -> None:
        report = deepcopy(carded)
        report["decision_card"]["evidence"]["ci95"] = None
        found = codes(advise(report))
        assert "RP_CI_CONTAINS_ZERO" not in found
        assert "RP_MEDIAN_OUTSIDE_ITS_INTERVAL" not in found

    def test_a_report_with_no_sample_still_advises(self, carded: dict[str, Any]) -> None:
        report = deepcopy(carded)
        report.pop("sample")
        assert "RP_RATE_NEEDS_ITS_DENOMINATOR" not in codes(advise(report))
        assert advise(report)

    def test_the_order_is_stable(self, carded: dict[str, Any]) -> None:
        first = [item.code for item in advise(carded)]
        second = [item.code for item in advise(carded)]
        assert first == second

    def test_blocking_advice_is_read_first(self, gated: dict[str, Any]) -> None:
        severities = [item.severity for item in advise(gated)]
        assert severities == sorted(
            severities, key={"blocking": 0, "material": 1, "disclosure": 2}.get
        )
