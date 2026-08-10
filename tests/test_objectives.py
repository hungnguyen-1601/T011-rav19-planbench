"""Objectives and Decision Utility (CONTRACTS HĐ-9).

Two things decide whether these numbers mean anything: which scale each
metric was put on (anchors, tested in ``test_anchors``) and which weights
folded them together. The tests below are about the second, plus the two
rules that stop a metric being counted twice or a cost being counted at
zero because nobody declared it.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from task_profile_fakes import constraints, make_profile

from planbench_decision.anchors import load_anchors
from planbench_decision.candidate import Candidate
from planbench_decision.objectives import (
    DEFAULT_BETA,
    PREFERENCE_PROFILES,
    DecisionSettings,
    ObjectiveError,
    PreferenceWeights,
    _efficiency,
    episode_objectives,
    set_objectives,
)
from planbench_metrics.definitions import EpisodeMetricSet

STRUCTURAL: dict[str, object] = {
    "kind": "structural",
    "target_implementation": "cpp_ros2",
    "bytes_per_search_node": 40,
    "bytes_per_tree_node": 40,
    "bytes_per_costmap_cell": 1,
    "costmap_layers": 3,
    "fixed_overhead_mb": 8.0,
}

TUNING: dict[str, object] = {
    "tuning_trials_used": 30,
    "tuning_wall_clock_h": 24.0,
    "n_tunable_params": 12,
    "evidence_log": "artifacts/tuning/k2_optuna.log",
}

MODULAR: dict[str, object] = {
    "type": "modular",
    "global_planner": {"name": "astar", "version": "v1"},
    "local_controller": {"name": "dwa", "version": "v1"},
    "params": {"astar": {"heuristic": "euclidean"}, "dwa": {"sim_time": 1.5}},
    "observation_requirements": ["lidar_2d"],
    "resource_profile": dict(STRUCTURAL),
    "tuning": dict(TUNING),
}


def candidate(**overrides: object) -> Candidate:
    return Candidate.model_validate({**MODULAR, **overrides})


def anchors():  # type: ignore[no-untyped-def]
    return load_anchors().resolve(make_profile())


def episode(owner: Candidate, seed: int = 0, **overrides: object) -> EpisodeMetricSet:
    payload: dict[str, object] = {
        "episode_context_id": f"ctx{seed:04d}",
        "candidate_id": owner.candidate_id,
        "success": True,
        "failure_reason": None,
        "collision_count": 0,
        "min_clearance": 0.52,
        "near_miss_rate": 0.0,
        "path_length_m": 44.0,
        "travel_time_s": 60.0,
        "l_ref_m": 40.0,
        "path_efficiency": 1.0,
        "t_ideal_s": 50.0,
        "time_efficiency": 1.0,
        "smoothness": 1.2,
        "stop_and_go_count": 2,
        "p99_latency_ms": 10.0,
        "peak_search_nodes": 412_000,
        "peak_tree_nodes": 0,
        "costmap_cells": 400_000,
        "memory_estimate_mb": 19.0,
        "peak_rss_mb": 340.0,
        "cpu_time_per_mission_s": 0.5,
    }
    payload.update(overrides)
    return EpisodeMetricSet.model_validate(payload)


class TestPreferenceProfiles:
    """HĐ-9.2's four defaults, and what a weight vector has to satisfy."""

    def test_the_four_contract_profiles_exist(self) -> None:
        assert set(PREFERENCE_PROFILES) == {
            "kho_ban_dem",
            "benh_vien_gio_cao_diem",
            "pilot_demo",
            "measured_only",
        }

    @pytest.mark.parametrize("name", sorted(PREFERENCE_PROFILES))
    def test_every_profile_sums_to_one(self, name: str) -> None:
        weights = PREFERENCE_PROFILES[name]
        assert weights.w_r + weights.w_s + weights.w_e + weights.w_c == pytest.approx(1.0)
        assert sum(weights.beta) == pytest.approx(1.0)

    def test_contract_numbers_are_the_ones_shipped(self) -> None:
        night = PREFERENCE_PROFILES["kho_ban_dem"]
        assert (night.w_r, night.w_s, night.w_e, night.w_c) == (0.30, 0.10, 0.25, 0.35)
        hospital = PREFERENCE_PROFILES["benh_vien_gio_cao_diem"]
        assert (hospital.w_r, hospital.w_s, hospital.w_e, hospital.w_c) == (0.25, 0.50, 0.10, 0.15)
        assert night.beta == DEFAULT_BETA

    def test_measured_only_drops_beta4_and_renormalises(self) -> None:
        """HĐ-9.1. Leaving the rest at 0.70 would quietly shrink U_C as a
        whole relative to every other profile."""
        beta = PREFERENCE_PROFILES["measured_only"].beta
        assert beta[3] == 0.0
        assert sum(beta) == pytest.approx(1.0)
        assert beta[0] == pytest.approx(0.30 / 0.70)

    def test_weights_that_do_not_sum_to_one_are_refused(self) -> None:
        with pytest.raises(ValidationError, match="sum to 1.0"):
            PreferenceWeights(w_r=0.5, w_s=0.5, w_e=0.5, w_c=0.5)

    def test_beta_that_does_not_sum_to_one_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="beta"):
            PreferenceWeights(w_r=0.25, w_s=0.25, w_e=0.25, w_c=0.25, beta=(0.5, 0.2, 0.2, 0.2))


class TestSettingsValidation:
    """Refused at construction, so a run cannot get 200 episodes in
    before finding out the combination was never legal. Pydantic wraps a
    model validator's error, so these surface as ``ValidationError`` —
    the same shape ``AnchorSet`` uses for its own file-level laws.
    """

    def test_unknown_profile_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="unknown preference profile"):
            DecisionSettings(preference_profile="kho_ban_sang")

    def test_monetized_travel_time_needs_business_mode(self) -> None:
        """§17 ban 9: travel time gets exactly one home."""
        with pytest.raises(ValidationError, match="monetized_cost"):
            DecisionSettings(travel_time_accounting="monetized_cost")

    def test_business_mode_needs_declared_assumptions(self) -> None:
        with pytest.raises(ValidationError, match="business_profile"):
            DecisionSettings(decision_mode="business_adjusted")

    def test_technical_mode_refuses_stray_assumptions(self) -> None:
        """Carrying assumptions that are never applied invites a reader to
        assume they were."""
        with pytest.raises(ValidationError, match="never used"):
            DecisionSettings(
                decision_mode="technical",
                business_profile={  # type: ignore[arg-type]
                    "engineer_cost_per_hour": 30.0,
                    "deployment_horizon_missions": 50_000,
                    "hardware_upgrade_cost": 0.0,
                },
            )

    def test_business_mode_is_validated_but_not_computable_yet(self) -> None:
        """Refused rather than approximated: there is no anchor for a
        cost in currency per mission."""
        settings = DecisionSettings(
            decision_mode="business_adjusted",
            business_profile={  # type: ignore[arg-type]
                "engineer_cost_per_hour": 30.0,
                "deployment_horizon_missions": 50_000,
                "hardware_upgrade_cost": 0.0,
            },
        )
        with pytest.raises(ObjectiveError, match="not implemented"):
            episode_objectives(episode(candidate()), anchors(), candidate(), settings)

    def test_card_label_is_the_mandated_sentence(self) -> None:
        assert DecisionSettings().card_label == (
            "Khuyến nghị kỹ thuật — chỉ dựa trên số liệu đo được"
        )


class TestTwoAggregationLevels:
    """HĐ-9.1: episode level feeds ΔU, set level feeds the card."""

    def test_episode_reliability_is_binary(self) -> None:
        resolved, owner = anchors(), candidate()
        assert episode_objectives(episode(owner), resolved, owner).u_r == 1.0
        failed = episode(owner, success=False, failure_reason="timeout")
        assert episode_objectives(failed, resolved, owner).u_r == 0.0

    def test_set_reliability_scores_the_margin_over_the_declared_floor(self) -> None:
        """The number the card prints, and the reading §6.2 works by hand.

        29 of 30 successes is 96.67% against a declared floor of 95%, so
        the credit is the 1.67 points of margin out of the 5 available:
        0.333 — not 0.967, which is what averaging the episode level
        gives and which would ignore the customer's floor entirely.
        """
        resolved, owner = anchors(), candidate()
        metrics = [episode(owner, seed=i) for i in range(29)]
        metrics.append(episode(owner, seed=29, success=False, failure_reason="timeout"))

        over_set = set_objectives(metrics, resolved, owner)
        per_episode = [episode_objectives(m, resolved, owner).u_r for m in metrics]

        assert over_set.u_r == pytest.approx(0.3333, abs=1e-4)
        assert sum(per_episode) / len(per_episode) == pytest.approx(0.9667, abs=1e-4)
        assert over_set.level == "set"

    def test_the_two_levels_agree_where_nothing_clips(self) -> None:
        """The divergence is entirely the clip, not two different formulas.

        U_S here is built from metrics strictly inside their anchors, and
        the set level equals the mean of the episode levels to the last
        digit.
        """
        resolved, owner = anchors(), candidate()
        metrics = [
            episode(owner, seed=0, min_clearance=0.40, near_miss_rate=0.10),
            episode(owner, seed=1, min_clearance=0.44, near_miss_rate=0.20),
        ]
        over_set = set_objectives(metrics, resolved, owner)
        mean_of_episodes = sum(episode_objectives(m, resolved, owner).u_s for m in metrics) / len(
            metrics
        )
        assert over_set.u_s == pytest.approx(mean_of_episodes)

    def test_set_level_needs_episodes(self) -> None:
        with pytest.raises(ObjectiveError, match="undefined"):
            set_objectives([], anchors(), candidate())

    def test_pooling_two_candidates_is_refused(self) -> None:
        mine = candidate()
        theirs = candidate(params={"astar": {"heuristic": "manhattan"}})
        with pytest.raises(ObjectiveError, match="averaged across candidates"):
            set_objectives([episode(mine), episode(theirs, seed=1)], anchors(), mine)


class TestObjectiveFormulas:
    def test_safety_is_half_clearance_half_near_miss(self) -> None:
        """HĐ-9.1. min_clearance 0.3965 is the midpoint of [0.273, 0.52];
        near_miss_rate 0.25 is the midpoint of [0.5, 0.0]."""
        resolved, owner = anchors(), candidate()
        metric = episode(owner, min_clearance=0.3965, near_miss_rate=0.25)
        assert episode_objectives(metric, resolved, owner).u_s == pytest.approx(0.5, abs=1e-3)

    def test_efficiency_is_half_path_half_time(self) -> None:
        resolved, owner = anchors(), candidate()
        metric = episode(owner, path_efficiency=1.0, time_efficiency=0.35)
        assert episode_objectives(metric, resolved, owner).u_e == pytest.approx(0.5)

    def test_collisions_never_enter_the_safety_score(self) -> None:
        """HĐ-6: collision_count belongs to gate G2 and nowhere else.

        Letting it also lower U_S would imply a collision can be traded
        against speed, which is exactly what having a gate rules out.
        """
        resolved, owner = anchors(), candidate()
        clean = episode(owner, min_clearance=0.40)
        crashed = episode(owner, min_clearance=0.40, collision_count=3)
        assert (
            episode_objectives(crashed, resolved, owner).u_s
            == episode_objectives(clean, resolved, owner).u_s
        )

    def test_cost_uses_the_declared_tuning_hours(self) -> None:
        """β = (0.30, 0.20, 0.20, 0.30) over latency, memory, CPU, effort.

        With latency at its ``good`` anchor (u = 1), memory at 19 MB
        (u = 1), CPU at 0.5 s (u = 1) and 24 declared tuning hours
        (u = 1 − 24/40 = 0.4), U_C = 0.70 + 0.30·0.4 = 0.82.
        """
        resolved, owner = anchors(), candidate()
        assert episode_objectives(episode(owner), resolved, owner).u_c == pytest.approx(0.82)

    def test_monetized_accounting_moves_travel_time_out_of_o3(self) -> None:
        """HĐ-9.3. Reached through the helper rather than a settings
        object because ``business_adjusted`` is refused end to end for
        now; the rule is implemented so it cannot be forgotten when that
        mode lands.
        """
        resolved = anchors()
        efficiency = DecisionSettings()
        monetized = DecisionSettings.model_construct(
            preference_profile="kho_ban_dem",
            decision_mode="business_adjusted",
            travel_time_accounting="monetized_cost",
            business_profile=None,
        )
        assert _efficiency(resolved, efficiency, 1.0, 0.35) == pytest.approx(0.5)
        assert _efficiency(resolved, monetized, 1.0, 0.35) == pytest.approx(1.0)


class TestEngineeringCostMustBeDeclared:
    def test_missing_declaration_is_refused_not_zeroed(self) -> None:
        """HĐ-1.6: "did not say" must not score as "cost nothing", or the
        candidate that skipped the paperwork wins O4."""
        owner = candidate(tuning=None)
        with pytest.raises(ObjectiveError, match="no tuning declaration"):
            episode_objectives(episode(owner), anchors(), owner)

    def test_measured_only_scores_without_a_declaration(self) -> None:
        """That profile prices nothing the platform did not measure, so
        β4 = 0 and the declaration is genuinely not needed."""
        owner = candidate(tuning=None)
        settings = DecisionSettings(preference_profile="measured_only")
        result = episode_objectives(episode(owner), anchors(), owner, settings)
        assert result.u_c == pytest.approx(1.0)

    def test_declaration_does_not_change_the_candidate_id(self) -> None:
        """HĐ-1.6: hours spent searching do not change how the robot
        drives; the parameters found do, and they are already hashed."""
        assert candidate(tuning=None).candidate_id == candidate().candidate_id
        cheaper = candidate(tuning={**TUNING, "tuning_wall_clock_h": 1.0})
        assert cheaper.candidate_id == candidate().candidate_id

    def test_evidence_log_is_required(self) -> None:
        """The figure is self-reported and goes straight into a score."""
        payload = {k: v for k, v in TUNING.items() if k != "evidence_log"}
        with pytest.raises(ValueError, match="evidence_log"):
            candidate(tuning=payload)


class TestDecisionUtility:
    def test_it_is_the_weighted_sum(self) -> None:
        resolved, owner = anchors(), candidate()
        result = set_objectives([episode(owner)], resolved, owner)
        weights = PREFERENCE_PROFILES["kho_ban_dem"]
        expected = (
            weights.w_r * result.u_r
            + weights.w_s * result.u_s
            + weights.w_e * result.u_e
            + weights.w_c * result.u_c
        )
        assert result.decision_utility == pytest.approx(expected)

    def test_the_preference_profile_can_flip_the_ranking(self) -> None:
        """The thesis, as one assertion.

        The careful candidate keeps its distance and costs more to run;
        the brisk one is cheap and drives closer to the shelves. A night
        warehouse (w_S = 0.10, w_C = 0.35) prefers the brisk one; a
        hospital at peak hour (w_S = 0.50, w_C = 0.15) prefers the
        careful one. Same metrics, same anchors, opposite answers — which
        is why "the best planner" is not a thing the platform can print.
        """
        resolved = anchors()
        careful = candidate(params={"astar": {"heuristic": "euclidean"}})
        brisk = candidate(params={"astar": {"heuristic": "manhattan"}})
        careful_metrics = [episode(careful, min_clearance=0.52, p99_latency_ms=45.0)]
        brisk_metrics = [episode(brisk, min_clearance=0.30, p99_latency_ms=10.0)]

        night = DecisionSettings(preference_profile="kho_ban_dem")
        hospital = DecisionSettings(preference_profile="benh_vien_gio_cao_diem")

        careful_night = set_objectives(careful_metrics, resolved, careful, night)
        brisk_night = set_objectives(brisk_metrics, resolved, brisk, night)
        careful_hospital = set_objectives(careful_metrics, resolved, careful, hospital)
        brisk_hospital = set_objectives(brisk_metrics, resolved, brisk, hospital)

        assert brisk_night.decision_utility > careful_night.decision_utility
        assert careful_hospital.decision_utility > brisk_hospital.decision_utility

    def test_it_is_never_called_score(self) -> None:
        """HĐ-9.2 fixes the name. "Score" reads as a property of the
        planner; this is a property of the planner under one deployment's
        weights."""
        fields = set(set_objectives([episode(candidate())], anchors(), candidate()).model_dump())
        assert "decision_utility" in fields
        assert not [name for name in fields if "score" in name]

    def test_card_block_uses_the_contracts_names(self) -> None:
        block = set_objectives([episode(candidate())], anchors(), candidate()).to_card()
        assert set(block) == {"U_R", "U_S", "U_E", "U_C"}

    def test_missing_memory_estimate_is_refused(self) -> None:
        owner = candidate()
        with pytest.raises(ObjectiveError, match="memory_estimate_mb"):
            episode_objectives(episode(owner, memory_estimate_mb=None), anchors(), owner)

    def test_anchors_follow_the_deployment(self) -> None:
        """Same episode, two deployments: the stricter floor scores the
        same success rate lower, because the margin over it is smaller."""
        owner = candidate()
        metrics = [episode(owner, seed=i) for i in range(29)]
        metrics.append(episode(owner, seed=29, success=False, failure_reason="timeout"))

        lenient = load_anchors().resolve(make_profile())
        strict = load_anchors().resolve(
            make_profile(constraints=constraints(success_rate_min=0.96))
        )
        assert set_objectives(metrics, lenient, owner).u_r == pytest.approx(0.3333, abs=1e-4)
        assert set_objectives(metrics, strict, owner).u_r == pytest.approx(0.1667, abs=1e-4)
