"""Weight and anchor stability sweeps (CONTRACTS HĐ-11.5, HĐ-8.3 law 3).

Everything else in the decision layer produces the recommendation. This
produces the reason to trust it, so the tests are mostly about the two
ways a stability report can lie: claiming a margin the data does not
support, and claiming stability that is really a metric having gone dead
under the perturbation.
"""

from __future__ import annotations

import pytest
from task_profile_fakes import constraints, make_profile

from planbench_decision.anchors import load_anchors
from planbench_decision.candidate import Candidate
from planbench_decision.objectives import (
    PREFERENCE_PROFILES,
    DecisionSettings,
    PreferenceWeights,
)
from planbench_decision.sensitivity import (
    SENSITIVE_MARGIN,
    WEIGHT_NAMES,
    ScoredField,
    SensitivityError,
    _shifted_weights,
    anchor_stability,
    weight_stability,
)
from planbench_metrics.definitions import EpisodeMetricSet
from planbench_schemas.episode_context import EpisodeContext

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
    "evidence_log": "artifacts/tuning/optuna.log",
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

N_EPISODES = 12


def candidate(**overrides: object) -> Candidate:
    return Candidate.model_validate({**MODULAR, **overrides})


def other_candidate(**overrides: object) -> Candidate:
    return candidate(
        params={"astar": {"heuristic": "manhattan"}, "dwa": {"sim_time": 1.5}}, **overrides
    )


def anchors():  # type: ignore[no-untyped-def]
    return load_anchors().resolve(make_profile())


def context(seed: int) -> EpisodeContext:
    return EpisodeContext.model_validate(
        {"task_profile_id": "warehouse_a_v1", "mission_id": "m1", "seed": seed}
    )


CONTEXTS = tuple(context(seed) for seed in range(N_EPISODES))


def episode(owner: Candidate, ctx: EpisodeContext, **overrides: object) -> EpisodeMetricSet:
    payload: dict[str, object] = {
        "episode_context_id": ctx.episode_context_id,
        "candidate_id": owner.candidate_id,
        "success": True,
        "failure_reason": None,
        "collision_count": 0,
        "min_clearance": 0.13,
        "near_miss_rate": 0.05,
        "path_length_m": 44.0,
        "travel_time_s": 60.0,
        "l_ref_m": 40.0,
        "path_efficiency": 0.90,
        "t_ideal_s": 50.0,
        "time_efficiency": 0.80,
        "smoothness": 1.2,
        "stop_and_go_count": 2,
        "p99_latency_ms": 25.0,
        "peak_search_nodes": 412_000,
        "peak_tree_nodes": 0,
        "costmap_cells": 400_000,
        "memory_estimate_mb": 19.0,
        "peak_rss_mb": 340.0,
        "cpu_time_per_mission_s": 2.0,
    }
    payload.update(overrides)
    return EpisodeMetricSet.model_validate(payload)


def field(
    a_traits: dict[str, object], b_traits: dict[str, object], *, jitter: bool = True
) -> ScoredField:
    """Two candidates over the same contexts, differing only as told.

    A small per-episode jitter is added by default so the paired
    bootstrap has some spread to work with; without it every difference
    is identical and the effect size is undefined, which is a different
    test's subject.
    """
    a, b = candidate(), other_candidate()
    metrics: dict[str, list[EpisodeMetricSet]] = {a.candidate_id: [], b.candidate_id: []}
    for index, ctx in enumerate(CONTEXTS):
        wobble = (index % 3) * 0.001 if jitter else 0.0
        metrics[a.candidate_id].append(
            episode(a, ctx, **{**a_traits, "path_efficiency": 0.90 + wobble})
        )
        metrics[b.candidate_id].append(
            episode(b, ctx, **{**b_traits, "path_efficiency": 0.90 + wobble})
        )
    return ScoredField.from_survivors(
        [a, b], metrics, CONTEXTS, {a.candidate_id: True, b.candidate_id: True}
    )


#: A wins on cost (fast, cheap to run); B wins on safety (keeps its
#: distance). Which one the platform recommends is then a question about
#: the weights, which is exactly what the sweep is for.
SAFE_VS_FAST = {
    "a": {"p99_latency_ms": 8.0, "min_clearance": 0.05},
    "b": {"p99_latency_ms": 45.0, "min_clearance": 0.26},
}

#: The same trade-off tuned until the two nearly cancel: B's extra
#: clearance is worth almost exactly what its extra latency costs. The
#: numbers were found by measuring, not by guessing — a fixture asserted
#: to be a knife edge has to actually be one.
KNIFE_EDGE = {
    "a": {"p99_latency_ms": 25.0, "min_clearance": 0.13},
    "b": {"p99_latency_ms": 33.0, "min_clearance": 0.26},
}

#: Tuned to sit on the boundary where the *anchor* choice decides it —
#: 34.5 ms is where the two candidates change places, so a 10% shift of
#: either scale involved tips the recommendation. Also measured, not
#: guessed.
ANCHOR_KNIFE = {
    "a": {"p99_latency_ms": 25.0, "min_clearance": 0.13},
    "b": {"p99_latency_ms": 34.5, "min_clearance": 0.26},
}


class TestWeightShifting:
    """The arithmetic underneath: one weight moves, the vector stays a
    valid preference, and nothing else is quietly changed."""

    def test_zero_shift_is_the_declared_vector(self) -> None:
        """Up to the float noise of dividing by the others' sum and
        multiplying back — 0.30 comes home as 0.30000000000000004."""
        declared = PREFERENCE_PROFILES["kho_ban_dem"]
        moved = _shifted_weights(declared, "w_s", "down", 0.0)
        assert (moved.w_r, moved.w_s, moved.w_e, moved.w_c) == pytest.approx(
            (declared.w_r, declared.w_s, declared.w_e, declared.w_c)
        )

    @pytest.mark.parametrize("name", WEIGHT_NAMES)
    @pytest.mark.parametrize("direction", ["down", "up"])
    @pytest.mark.parametrize("shift", [0.25, 0.5, 1.0])
    def test_the_four_always_sum_to_one(self, name: str, direction: str, shift: float) -> None:
        moved = _shifted_weights(PREFERENCE_PROFILES["kho_ban_dem"], name, direction, shift)
        assert moved.w_r + moved.w_s + moved.w_e + moved.w_c == pytest.approx(1.0)

    def test_full_shift_reaches_the_extreme(self) -> None:
        declared = PREFERENCE_PROFILES["kho_ban_dem"]
        assert _shifted_weights(declared, "w_s", "down", 1.0).w_s == pytest.approx(0.0)
        assert _shifted_weights(declared, "w_s", "up", 1.0).w_s == pytest.approx(1.0)

    def test_the_others_keep_their_proportions(self) -> None:
        """Only one assumption moves per sweep direction. If the other
        three re-ordered themselves, a flip could not be attributed to
        the weight that was swept."""
        declared = PREFERENCE_PROFILES["kho_ban_dem"]
        moved = _shifted_weights(declared, "w_s", "down", 0.6)
        assert moved.w_r / moved.w_e == pytest.approx(declared.w_r / declared.w_e)
        assert moved.w_c / moved.w_e == pytest.approx(declared.w_c / declared.w_e)

    def test_beta_is_carried_through_untouched(self) -> None:
        """β splits U_C internally and is not one of the four being
        swept; regenerating it from the default would silently undo a
        ``measured_only`` renormalisation."""
        declared = PREFERENCE_PROFILES["measured_only"]
        assert _shifted_weights(declared, "w_r", "up", 0.4).beta == declared.beta

    def test_a_degenerate_vector_spreads_the_rest_evenly(self) -> None:
        """All weight on one objective, then swept away from it: there is
        no proportion left to preserve, and inventing one would be
        inventing a preference the user never stated."""
        everything_on_r = PreferenceWeights(w_r=1.0, w_s=0.0, w_e=0.0, w_c=0.0)
        moved = _shifted_weights(everything_on_r, "w_r", "down", 1.0)
        assert (moved.w_s, moved.w_e, moved.w_c) == pytest.approx((1 / 3, 1 / 3, 1 / 3))

    @pytest.mark.parametrize("bad", [-0.1, 1.1])
    def test_a_shift_outside_the_walk_is_refused(self, bad: float) -> None:
        with pytest.raises(SensitivityError, match=r"\[0, 1\]"):
            _shifted_weights(PREFERENCE_PROFILES["kho_ban_dem"], "w_s", "down", bad)


class TestWeightStability:
    def test_it_finds_the_flip_and_names_it_in_the_users_terms(self) -> None:
        """N1's whole point: the answer a reader can act on is "safety
        would have to matter this much more", not a bare margin."""
        sweep = weight_stability(field(SAFE_VS_FAST["a"], SAFE_VS_FAST["b"]), anchors())

        assert sweep.nearest_flip is not None
        flip = sweep.nearest_flip
        assert flip.weight == "w_s"
        assert flip.direction == "up"
        assert flip.original_value == pytest.approx(0.10)
        assert flip.flip_value > flip.original_value
        assert sweep.margin == pytest.approx(flip.shift)
        assert "w_s" in flip.sentence and "tăng" in flip.sentence

    def test_the_flip_point_is_the_real_boundary(self) -> None:
        """Just under the reported shift the advice still stands; just
        over it, it does not. Without this the margin is a number from a
        search, not a property of the data."""
        scored = field(SAFE_VS_FAST["a"], SAFE_VS_FAST["b"])
        resolved, settings = anchors(), DecisionSettings()
        sweep = weight_stability(scored, resolved, settings)
        assert sweep.nearest_flip is not None
        flip = sweep.nearest_flip

        def recommended_at(shift: float) -> str:
            moved = _shifted_weights(settings.weights, flip.weight, flip.direction, shift)
            return scored.recommend_under(
                resolved, settings.with_weights(moved), seed=0
            ).recommended_id

        assert recommended_at(max(flip.shift - 0.02, 0.0)) == sweep.recommended_id
        assert recommended_at(min(flip.shift + 0.02, 1.0)) == flip.new_recommended_id

    def test_an_unbeatable_candidate_has_no_flip_at_all(self) -> None:
        """Better on every objective, so no non-negative weighting can
        promote the other one. Margin 1.0 says exactly that, and it is a
        claim about the whole simplex rather than a search that gave up."""
        sweep = weight_stability(
            field(
                {"p99_latency_ms": 8.0, "min_clearance": 0.26, "time_efficiency": 0.95},
                {"p99_latency_ms": 45.0, "min_clearance": 0.05, "time_efficiency": 0.40},
            ),
            anchors(),
        )
        assert sweep.margin == 1.0
        assert sweep.nearest_flip is None
        assert sweep.flips == ()
        assert sweep.label is None

    def test_a_knife_edge_run_gets_the_contract_label(self) -> None:
        """HĐ-11.5: a recommendation that flips under a shift smaller
        than 10% is labelled rather than reported as a plain number."""
        sweep = weight_stability(field(KNIFE_EDGE["a"], KNIFE_EDGE["b"]), anchors())
        assert sweep.margin < SENSITIVE_MARGIN
        assert sweep.label == "SENSITIVE_TO_PREFERENCES"
        assert sweep.is_sensitive

    def test_it_reports_every_direction_that_flips_not_only_the_nearest(self) -> None:
        """A UI showing only the closest edge cannot draw the picture; a
        margin is the minimum, and the rest is still evidence."""
        sweep = weight_stability(field(SAFE_VS_FAST["a"], SAFE_VS_FAST["b"]), anchors())
        assert len(sweep.flips) >= 1
        assert sweep.flips[0] == sweep.nearest_flip
        assert all(flip.shift >= sweep.margin for flip in sweep.flips)

    def test_it_is_reproducible(self) -> None:
        """HĐ-13: the margin ends up on a card somebody else rebuilds."""
        scored = field(SAFE_VS_FAST["a"], SAFE_VS_FAST["b"])
        first = weight_stability(scored, anchors(), seed=11)
        second = weight_stability(scored, anchors(), seed=11)
        assert first.margin == second.margin
        assert first.nearest_flip == second.nearest_flip


class TestPerturbedSettingsSaySoThemselves:
    """A run under moved weights must not be storable as a run under the
    declared ones — the same rule ``ResolvedAnchors.scaled`` follows for
    the anchor version string."""

    def test_the_declared_profile_labels_itself_plainly(self) -> None:
        assert DecisionSettings(preference_profile="pilot_demo").profile_label == "pilot_demo"

    def test_a_swept_profile_is_marked(self) -> None:
        swept = DecisionSettings(preference_profile="pilot_demo").with_weights(
            PreferenceWeights(w_r=0.25, w_s=0.25, w_e=0.25, w_c=0.25)
        )
        assert swept.profile_label == "pilot_demo (perturbed)"
        assert swept.weights.w_s == 0.25

    def test_the_override_is_what_scoring_uses(self) -> None:
        swept = DecisionSettings().with_weights(
            PreferenceWeights(w_r=1.0, w_s=0.0, w_e=0.0, w_c=0.0)
        )
        assert swept.weights.w_r == 1.0
        assert PREFERENCE_PROFILES["kho_ban_dem"].w_r != 1.0


class TestAnchorStability:
    def test_a_robust_run_reports_the_contract_string(self) -> None:
        sweep = anchor_stability(
            field(
                {"p99_latency_ms": 8.0, "min_clearance": 0.26, "time_efficiency": 0.95},
                {"p99_latency_ms": 45.0, "min_clearance": 0.05, "time_efficiency": 0.40},
            ),
            anchors(),
        )
        assert sweep.changed_at == ()
        assert sweep.verdict == "unchanged_at_±10%"

    def test_a_flip_names_the_anchor_and_the_direction(self) -> None:
        """ "Our own scale choice decided this" is only actionable if the
        report says *which* scale and which way.

        A reader can argue with "the recommendation turns on where we
        drew the line for latency". They can do nothing at all with
        "changed at -10%".
        """
        sweep = anchor_stability(field(ANCHOR_KNIFE["a"], ANCHOR_KNIFE["b"]), anchors())
        assert sweep.changed_at
        assert any(label.startswith("p99_latency_ms") for label in sweep.changed_at)
        assert sweep.verdict.startswith("changed_at_")
        assert all(label.endswith(("+10%", "-10%")) for label in sweep.changed_at)

    def test_a_uniform_sweep_is_provably_unable_to_flip_anything(self) -> None:
        """Why this check sweeps one metric at a time.

        HĐ-8.3 law 3 reads "shift every anchor ±10%", and taken literally
        that check cannot fail. Widening every scale by the same factor
        maps every ``u`` by one affine function — ``u ↦ 1 - (1-u)/f`` —
        and the decision utility, being a convex combination of ``u``
        values, maps the same way. A strictly increasing map applied to
        every candidate alike cannot reorder them.

        Asserted on the field that *does* flip under a per-metric sweep,
        so the two cannot both pass by accident.
        """
        scored = field(ANCHOR_KNIFE["a"], ANCHOR_KNIFE["b"])
        resolved, settings = anchors(), DecisionSettings()
        baseline = scored.recommend_under(resolved, settings, seed=0).recommended_id
        for factor in (1.10, 0.90, 1.50, 0.50):
            everything = resolved.scaled(factor)
            assert (
                scored.recommend_under(everything, settings, seed=0).recommended_id == baseline
            ), f"a uniform sweep at {factor} should be order-preserving"
        # ...while the per-metric sweep on the same field does find flips.
        assert anchor_stability(scored, resolved).changed_at

    def test_the_verdict_never_misreports_its_own_sweep(self) -> None:
        """A card field that says ``±10%`` about a 30% shift describes an
        experiment that was not run."""
        scored = field(
            {"p99_latency_ms": 8.0, "min_clearance": 0.26, "time_efficiency": 0.95},
            {"p99_latency_ms": 45.0, "min_clearance": 0.05, "time_efficiency": 0.40},
        )
        assert anchor_stability(scored, anchors()).verdict == "unchanged_at_±10%"
        assert anchor_stability(scored, anchors(), sweep=0.30).verdict == "unchanged_at_±30%"

    def test_no_metric_is_swept_off_its_own_domain(self) -> None:
        """The invariant that makes an "unchanged" verdict mean anything.

        The first version of the sweep scaled *both* ends, which for a
        metric bounded at 1.0 by definition moved the whole scale past
        the domain: ``success_rate`` at ``{1.00, 0.95}`` became
        ``{1.10, 1.045}``, every real success rate clipped to 0, and
        ``U_R`` went dead for every candidate. The sweep then reported
        "recommendation unchanged" — unchanged because the metric had
        stopped existing.

        Holding ``good`` still and moving only ``bad`` makes that
        impossible: the perturbed scale always shares an endpoint with
        the declared one, so a measurement that used to score inside
        [0, 1] still does. Asserted on the shipped anchors rather than
        argued, because the failure was invisible in exactly this file's
        output.
        """
        resolved = load_anchors().resolve(
            make_profile(constraints=constraints(cost_per_mission_max=1.0))
        )
        for factor in (1.10, 0.90):
            for name, (good, bad) in resolved.scaled(factor).anchors.items():
                was_good, was_bad = resolved.anchors[name]
                assert good == pytest.approx(was_good), f"{name} moved its reference point"
                # Same direction, so the metric still reads the same way.
                assert (bad > good) == (was_bad > was_good), f"{name} inverted"
                # And the value that used to sit mid-scale still does.
                midpoint = (was_good + was_bad) / 2
                assert 0.0 < resolved.scaled(factor).u(name, midpoint) < 1.0, name

    def test_success_rate_survives_the_sweep(self) -> None:
        """The specific metric the old rule killed, named so a regression
        is legible rather than showing up as a distant assertion."""
        resolved = load_anchors().resolve(make_profile())
        for factor in (1.10, 0.90):
            good, bad = resolved.scaled(factor).anchors["success_rate"]
            assert good == 1.0
            assert 0.9 < bad < 1.0
            assert resolved.scaled(factor).u("success_rate", 0.967) > 0.0


class TestRefusals:
    def test_a_field_of_one_survivor_cannot_be_swept(self) -> None:
        """With nothing to flip to, a margin of 1.0 would assert
        stability that was never tested."""
        a, b = candidate(), other_candidate()
        metrics = {
            a.candidate_id: [episode(a, ctx) for ctx in CONTEXTS],
            b.candidate_id: [episode(b, ctx) for ctx in CONTEXTS],
        }
        with pytest.raises(SensitivityError, match="at least two candidates"):
            ScoredField.from_survivors(
                [a, b], metrics, CONTEXTS, {a.candidate_id: True, b.candidate_id: False}
            )

    def test_gate_failures_never_enter_the_sweep(self) -> None:
        """A candidate eliminated at a gate does not come back when the
        weights move: gates are not a matter of preference (HĐ-7)."""
        a = candidate()
        b = other_candidate()
        c = candidate(observation_requirements=["lidar_2d", "human_state_estimates"])
        metrics = {
            item.candidate_id: [episode(item, ctx) for ctx in CONTEXTS] for item in (a, b, c)
        }
        scored = ScoredField.from_survivors(
            [a, b, c],
            metrics,
            CONTEXTS,
            {a.candidate_id: True, b.candidate_id: True, c.candidate_id: False},
        )
        assert [item.candidate_id for item in scored.candidates] == [a.candidate_id, b.candidate_id]

    def test_missing_metrics_are_refused_rather_than_skipped(self) -> None:
        a, b = candidate(), other_candidate()
        with pytest.raises(SensitivityError, match="no metrics"):
            ScoredField.from_survivors(
                [a, b],
                {a.candidate_id: [episode(a, ctx) for ctx in CONTEXTS]},
                CONTEXTS,
                {a.candidate_id: True, b.candidate_id: True},
            )


class TestItRunsOnTheDeploymentsOwnThresholds:
    def test_a_stricter_site_can_get_a_different_margin(self) -> None:
        """The sweep moves preferences, but it scores through anchors
        bound to this deployment — so a site demanding 99% success is
        being asked a different question, and may get a different answer.
        """
        scored = field(SAFE_VS_FAST["a"], SAFE_VS_FAST["b"])
        lenient = weight_stability(scored, anchors())
        strict = weight_stability(
            scored,
            load_anchors().resolve(make_profile(constraints=constraints(success_rate_min=0.99))),
        )
        assert lenient.margin >= 0.0 and strict.margin >= 0.0
        assert lenient.recommended_id == strict.recommended_id
