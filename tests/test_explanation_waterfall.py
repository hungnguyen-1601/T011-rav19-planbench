"""E1 — the waterfall decomposes the number the card printed.

Everything here guards one of three ways a decomposition lies: bars that
do not add up to their total, a total built through a statistic the
decomposition identity does not survive (the median), and two
aggregation levels quietly swapped for one another so the reader adds
the bars and lands somewhere else.
"""

from __future__ import annotations

import numpy as np
import pytest
from pydantic import ValidationError
from task_profile_fakes import make_profile

from planbench_decision.anchors import load_anchors
from planbench_decision.candidate import Candidate
from planbench_decision.objectives import (
    PREFERENCE_PROFILES,
    DecisionSettings,
    PreferenceWeights,
)
from planbench_decision.pairing import PairingViolation
from planbench_decision.stats import CandidateEvidence, build_evidence, compare_pair
from planbench_explanation.waterfall import (
    SUM_TOLERANCE,
    ObjectiveLevels,
    UtilityDrillDown,
    Waterfall,
    WaterfallBar,
    WaterfallProfile,
    WaterfallRefusal,
    build_waterfall,
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

SETTINGS = DecisionSettings()


def candidate(**overrides: object) -> Candidate:
    return Candidate.model_validate({**MODULAR, **overrides})


A = candidate()
B = candidate(params={"astar": {"heuristic": "manhattan"}, "dwa": {"sim_time": 1.5}})


def anchors():  # type: ignore[no-untyped-def]
    return load_anchors().resolve(make_profile())


def context(seed: int) -> EpisodeContext:
    return EpisodeContext.model_validate(
        {"task_profile_id": "warehouse_a_v1", "mission_id": "m1", "seed": seed}
    )


def episode(owner: Candidate, ctx: EpisodeContext, **overrides: object) -> EpisodeMetricSet:
    payload: dict[str, object] = {
        "episode_context_id": ctx.episode_context_id,
        "candidate_id": owner.candidate_id,
        "success": True,
        "failure_reason": None,
        "collision_count": 0,
        "min_clearance": 0.45,
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


def evidence(
    owner: Candidate,
    n: int = 30,
    *,
    per_episode: dict[int, dict[str, object]] | None = None,
    common: dict[str, object] | None = None,
    seeds: range | None = None,
    settings: DecisionSettings | None = None,
) -> CandidateEvidence:
    per_episode = per_episode or {}
    contexts = [context(seed) for seed in (seeds or range(n))]
    metrics = [
        episode(owner, ctx, **{**(common or {}), **per_episode.get(i, {})})
        for i, ctx in enumerate(contexts)
    ]
    return build_evidence(owner, metrics, contexts, anchors(), settings or SETTINGS)


def _arm(i: int) -> dict[str, object]:
    """Three unequal arms whose objectives move against each other.

    Deliberately not two symmetric halves: with two equally sized arms
    every median lands on the midpoint of the same pair, the median
    decomposition accidentally holds, and the test that is supposed to
    catch a median waterfall passes on arithmetic that will not
    generalise. Six-twelve-twelve puts the median episode of ΔU in a
    different arm than the median episode of each objective.
    """
    if i % 5 == 0:  # 6 episodes: fast and close to things
        return {"time_efficiency": 0.95, "near_miss_rate": 0.30, "min_clearance": 0.20}
    if i % 5 in (1, 2):  # 12 episodes: slow and careful
        return {"time_efficiency": 0.45, "near_miss_rate": 0.00, "min_clearance": 0.80}
    return {"time_efficiency": 0.30, "near_miss_rate": 0.20, "min_clearance": 0.35}


#: Episodes where A's advantage moves between objectives rather than
#: sitting on one. Two bars that swing in opposite directions is what
#: makes the median non-linear and the marginal intervals wider than the
#: total's — with a single objective moving, both facts hide.
ANTICORRELATED: dict[int, dict[str, object]] = {i: _arm(i) for i in range(30)}


def bar(waterfall, objective: str):  # type: ignore[no-untyped-def]
    (found,) = [b for b in waterfall.bars if b.objective == objective]
    return found


# --------------------------------------------------------------------------
# The identity the whole module rests on
# --------------------------------------------------------------------------


def test_the_bars_reconstitute_the_paired_delta_u() -> None:
    """``mean(ΔU) = Σ w_j · mean(Δu_j)``, to float drift."""
    faster = evidence(A, common={"time_efficiency": 0.90, "travel_time_s": 55.0})
    slower = evidence(B, common={"time_efficiency": 0.70, "travel_time_s": 70.0})

    waterfall = build_waterfall(faster, slower, settings=SETTINGS)

    assert waterfall.bar_sum == pytest.approx(waterfall.delta_utility_mean, abs=SUM_TOLERANCE)
    assert len(waterfall.bars) == 4


def test_a_tampered_bar_makes_the_waterfall_refuse_to_exist() -> None:
    """The check is structural, not a warning printed beside the chart."""
    waterfall = build_waterfall(
        evidence(A, common={"time_efficiency": 0.90}),
        evidence(B, common={"time_efficiency": 0.70}),
        settings=SETTINGS,
    )
    payload = waterfall.model_dump()
    payload["bars"][2]["contribution"] = 0.5

    # A refusal raised inside a validator reaches the caller wrapped,
    # the same way ``StatisticsRefusal`` does in the decision layer.
    with pytest.raises(ValidationError, match="weight × difference"):
        Waterfall.model_validate(payload)


def test_a_bar_whose_height_is_not_its_own_arithmetic_is_refused() -> None:
    """Height and printed numbers cannot tell two different stories."""
    with pytest.raises(ValidationError, match="weight × difference"):
        WaterfallBar(
            objective="U_E",
            weight=0.25,
            delta_objective_mean=0.40,
            contribution=0.02,  # 0.25 × 0.40 is 0.10
            ci95=(0.0, 0.05),
        )


def test_numbers_no_utility_could_produce_are_refused() -> None:
    """Utilities are on [0, 1], so their differences are on [-1, 1].

    ``delta_objective_mean = 999`` is not an extreme measurement, it is
    an impossible one — and impossible numbers are exactly what can be
    chosen in pairs that cancel, so every sum still balances.
    """
    with pytest.raises(ValidationError):  # ΔU_j outside [-1, 1]
        WaterfallBar(
            objective="U_E",
            weight=0.25,
            delta_objective_mean=999.0,
            contribution=0.25 * 999.0,
            ci95=(0.0, 0.05),
        )

    with pytest.raises(ValidationError, match="outside"):  # interval beyond ±weight
        WaterfallBar(
            objective="U_E",
            weight=0.25,
            delta_objective_mean=0.40,
            contribution=0.10,
            ci95=(-0.9, 0.9),
        )

    with pytest.raises(ValidationError):  # a utility level outside [0, 1]
        ObjectiveLevels(objective="U_R", set_level=99.0, episode_mean=0.5)


def test_a_waterfall_missing_an_objective_is_refused() -> None:
    waterfall = build_waterfall(evidence(A), evidence(B), settings=SETTINGS)
    payload = waterfall.model_dump()
    payload["bars"] = payload["bars"][:3]

    with pytest.raises(ValidationError, match="exactly once"):
        Waterfall.model_validate(payload)


def test_a_duplicated_objective_cannot_stand_in_for_a_missing_one() -> None:
    """Four bars whose total is right and whose story is wrong.

    ``U_R, U_S, U_E, U_E`` passes a count, passes the sum — and U_C has
    disappeared, so the explanation credits the win to an objective that
    was never decomposed.
    """
    waterfall = build_waterfall(
        evidence(A, common={"time_efficiency": 0.90}),
        evidence(B, common={"time_efficiency": 0.70}),
        settings=SETTINGS,
    )
    payload = waterfall.model_dump()
    bars = [dict(entry) for entry in payload["bars"]]
    # Same total: U_C contributes nothing here, so relabelling it U_E
    # leaves every number in place.
    bars[3] = {**bars[3], "objective": "U_E", "weight": bars[2]["weight"]}
    bars[3]["contribution"] = 0.0
    bars[3]["delta_objective_mean"] = 0.0
    payload["bars"] = bars

    with pytest.raises(ValidationError, match="exactly once"):
        Waterfall.model_validate(payload)


def test_the_total_agrees_with_the_number_on_the_card() -> None:
    """Same episodes, same seed: the card's ΔU and CI, not a near miss."""
    faster = evidence(A, common={"time_efficiency": 0.90})
    slower = evidence(B, common={"time_efficiency": 0.70})

    waterfall = build_waterfall(faster, slower, settings=SETTINGS, seed=7, n_resamples=500)
    card = compare_pair(faster, slower, seed=7, n_resamples=500)

    assert waterfall.delta_utility_mean == pytest.approx(card.delta_mean)
    assert waterfall.delta_utility_median == pytest.approx(card.delta_median)
    assert waterfall.total_ci95 == pytest.approx(card.ci95)


def test_only_the_objective_that_moved_carries_a_bar() -> None:
    faster = evidence(A, common={"time_efficiency": 0.90})
    slower = evidence(B, common={"time_efficiency": 0.70})

    waterfall = build_waterfall(faster, slower, settings=SETTINGS)

    assert bar(waterfall, "U_E").contribution > 0
    for objective in ("U_R", "U_S", "U_C"):
        assert bar(waterfall, objective).contribution == pytest.approx(0.0, abs=1e-12)


def test_a_bar_is_weight_times_difference() -> None:
    faster = evidence(A, common={"time_efficiency": 0.90})
    slower = evidence(B, common={"time_efficiency": 0.70})

    efficiency = bar(build_waterfall(faster, slower, settings=SETTINGS), "U_E")

    assert efficiency.weight == pytest.approx(SETTINGS.weights.w_e)
    assert efficiency.contribution == pytest.approx(
        efficiency.weight * efficiency.delta_objective_mean
    )


# --------------------------------------------------------------------------
# Mean, not median
# --------------------------------------------------------------------------


def test_the_median_travels_as_description_and_never_as_a_bar() -> None:
    """A median is not linear, so a median waterfall would not add up.

    The skewed advantage below is built so the two statistics genuinely
    disagree: were the bars drawn from per-objective medians, their sum
    would miss ``median(ΔU)`` — which is the picture this test exists to
    keep off the screen.
    """
    faster = evidence(A, per_episode=ANTICORRELATED)
    slower = evidence(B, common={"time_efficiency": 0.70, "near_miss_rate": 0.15})

    waterfall = build_waterfall(faster, slower, settings=SETTINGS)

    median_bars = sum(
        b.weight
        * float(
            np.median(
                [
                    faster.objective_series(b.objective)[c]
                    - slower.objective_series(b.objective)[c]
                    for c in faster.contexts
                ]
            )
        )
        for b in waterfall.bars
    )
    assert waterfall.delta_utility_median != pytest.approx(median_bars, abs=SUM_TOLERANCE)
    # And the mean decomposition still holds on the same data.
    assert waterfall.bar_sum == pytest.approx(waterfall.delta_utility_mean, abs=SUM_TOLERANCE)


# --------------------------------------------------------------------------
# The intervals are marginal
# --------------------------------------------------------------------------


def test_bar_intervals_are_marginal_and_do_not_sum_to_the_total_interval() -> None:
    """Four per-objective statements, not one simultaneous band.

    Adding the bounds is the mistake this locks: it produces a wider
    interval than the total's, because the objectives' differences are
    correlated across episodes and the total was resampled as one
    quantity.
    """
    faster = evidence(A, per_episode=ANTICORRELATED)
    slower = evidence(B, common={"time_efficiency": 0.70, "near_miss_rate": 0.15})

    waterfall = build_waterfall(faster, slower, settings=SETTINGS, seed=3)

    summed_low = sum(b.ci95[0] for b in waterfall.bars)
    summed_high = sum(b.ci95[1] for b in waterfall.bars)
    assert (summed_low, summed_high) != pytest.approx(waterfall.total_ci95)
    assert summed_high - summed_low > waterfall.total_ci95[1] - waterfall.total_ci95[0]


def test_a_bar_that_settles_nothing_says_so() -> None:
    """Identical candidates: every interval contains zero."""
    left = evidence(A)
    right = evidence(B)

    waterfall = build_waterfall(left, right, settings=SETTINGS)

    assert all(b.crosses_zero for b in waterfall.bars)
    assert waterfall.delta_utility_mean == pytest.approx(0.0, abs=1e-12)


def test_a_consistent_advantage_produces_a_bar_clear_of_zero() -> None:
    faster = evidence(A, common={"time_efficiency": 0.95})
    slower = evidence(B, common={"time_efficiency": 0.60})

    efficiency = bar(build_waterfall(faster, slower, settings=SETTINGS), "U_E")

    assert not efficiency.crosses_zero
    assert efficiency.ci95[0] > 0.0


# --------------------------------------------------------------------------
# Two utility levels, said out loud
# --------------------------------------------------------------------------


def test_the_drill_down_shows_where_the_card_and_the_bars_part_company() -> None:
    """U_R is clipped in every episode, so the two levels diverge there.

    A reader adding the bars will not land on the card's ΔU. That is
    correct, and the drill-down is where it is stated rather than
    discovered.
    """
    failing = evidence(A, per_episode={0: {"success": False, "failure_reason": "timeout"}})
    clean = evidence(B)

    drill = build_waterfall(failing, clean, settings=SETTINGS).drill_down

    assert drill.diverging_objectives == ("U_R",)
    assert drill.set_delta != pytest.approx(drill.episode_mean_delta)
    (reliability,) = [level for level in drill.levels_a if level.objective == "U_R"]
    assert reliability.episode_mean == pytest.approx(29 / 30)
    assert reliability.set_level != pytest.approx(reliability.episode_mean)


def test_the_bars_still_sum_to_the_episode_level_delta_when_the_levels_diverge() -> None:
    failing = evidence(A, per_episode={0: {"success": False, "failure_reason": "timeout"}})
    clean = evidence(B)

    waterfall = build_waterfall(failing, clean, settings=SETTINGS)

    assert waterfall.bar_sum == pytest.approx(waterfall.delta_utility_mean, abs=SUM_TOLERANCE)
    assert waterfall.bar_sum == pytest.approx(
        waterfall.drill_down.episode_mean_delta, abs=SUM_TOLERANCE
    )


# --------------------------------------------------------------------------
# What it refuses
# --------------------------------------------------------------------------


def test_the_profile_that_drew_the_bars_must_be_the_one_that_scored_them() -> None:
    faster = evidence(A, common={"time_efficiency": 0.90})
    slower = evidence(B, common={"time_efficiency": 0.70})

    with pytest.raises(WaterfallRefusal) as excinfo:
        build_waterfall(faster, slower, settings=DecisionSettings(preference_profile="pilot_demo"))
    assert "decompose" in str(excinfo.value)


def test_a_candidate_cannot_be_decomposed_against_itself() -> None:
    only = evidence(A)
    with pytest.raises(WaterfallRefusal):
        build_waterfall(only, only, settings=SETTINGS)


def test_unshared_contexts_are_refused_before_any_bar_is_drawn() -> None:
    left = evidence(A, seeds=range(0, 30))
    right = evidence(B, seeds=range(1, 31))

    with pytest.raises(PairingViolation):
        build_waterfall(left, right, settings=SETTINGS)


def test_the_profile_is_recorded_on_the_waterfall() -> None:
    waterfall = build_waterfall(evidence(A), evidence(B), settings=SETTINGS)
    assert waterfall.profile.label == SETTINGS.profile_label


def test_the_same_seed_draws_the_same_waterfall() -> None:
    faster = evidence(A, per_episode=ANTICORRELATED)
    slower = evidence(B, common={"time_efficiency": 0.70, "near_miss_rate": 0.15})

    first = build_waterfall(faster, slower, settings=SETTINGS, seed=11)
    second = build_waterfall(faster, slower, settings=SETTINGS, seed=11)
    other = build_waterfall(faster, slower, settings=SETTINGS, seed=12)

    assert first.model_dump() == second.model_dump()
    assert first.bars[2].ci95 != other.bars[2].ci95


# --------------------------------------------------------------------------
# What survives serialisation, and what an artifact may not claim
# --------------------------------------------------------------------------


def test_the_flags_the_ui_reads_survive_a_round_trip() -> None:
    """E4 writes these objects to an artifact and serves them as JSON.

    A property does not survive ``model_dump()``, so the flag that says
    "this bar settles nothing" and the list that says "do not add the
    bars up to the card's number" would be missing from exactly the
    place a reader looks.
    """
    waterfall = build_waterfall(
        evidence(A, per_episode=ANTICORRELATED),
        evidence(B, common={"time_efficiency": 0.70, "near_miss_rate": 0.15}),
        settings=SETTINGS,
    )
    payload = waterfall.model_dump()

    assert all("crosses_zero" in entry for entry in payload["bars"])
    assert "diverging_objectives" in payload["drill_down"]
    assert Waterfall.model_validate(payload).model_dump() == payload

    as_json = Waterfall.model_validate_json(waterfall.model_dump_json())
    assert as_json.model_dump() == payload


def test_a_dimming_flag_cannot_disagree_with_its_interval() -> None:
    with pytest.raises(ValidationError, match="crosses_zero"):
        WaterfallBar(
            objective="U_E",
            weight=0.25,
            delta_objective_mean=0.40,
            contribution=0.10,
            ci95=(0.05, 0.20),
            crosses_zero=True,
        )


def test_an_inside_out_interval_is_refused_on_a_bar_and_on_the_total() -> None:
    """``(2.0, -2.0)`` tests as containing everything and draws backwards."""
    with pytest.raises(ValidationError, match="bounds reversed"):
        WaterfallBar(
            objective="U_E",
            weight=0.25,
            delta_objective_mean=0.40,
            contribution=0.10,
            ci95=(2.0, -2.0),
        )

    waterfall = build_waterfall(evidence(A), evidence(B), settings=SETTINGS)
    payload = waterfall.model_dump()
    payload["total_ci95"] = (2.0, -2.0)
    with pytest.raises(ValidationError, match="bounds reversed"):
        Waterfall.model_validate(payload)


def test_a_drill_down_missing_an_objective_is_refused() -> None:
    waterfall = build_waterfall(evidence(A), evidence(B), settings=SETTINGS)
    payload = waterfall.model_dump()
    payload["drill_down"] = {**payload["drill_down"], "levels_a": ()}

    with pytest.raises(ValidationError, match="exactly once"):
        Waterfall.model_validate(payload)


def test_a_drill_down_about_other_candidates_is_refused() -> None:
    waterfall = build_waterfall(evidence(A), evidence(B), settings=SETTINGS)
    payload = waterfall.model_dump()
    payload["drill_down"] = {**payload["drill_down"], "candidate_a": "somebody_else"}

    with pytest.raises(ValidationError, match="drill-down compares"):
        Waterfall.model_validate(payload)


def test_a_drill_down_reporting_another_delta_is_refused() -> None:
    """Two halves of one panel cannot disagree about what was measured."""
    waterfall = build_waterfall(
        evidence(A, common={"time_efficiency": 0.90}),
        evidence(B, common={"time_efficiency": 0.70}),
        settings=SETTINGS,
    )
    payload = waterfall.model_dump()
    drill = dict(payload["drill_down"])
    # Stays inside [0, 1] — the point is the disagreement, not the range.
    drill["episode_mean_utility_a"] = drill["episode_mean_utility_a"] - 0.2
    payload["drill_down"] = drill

    with pytest.raises(ValidationError, match="episode-level"):
        Waterfall.model_validate(payload)


def test_a_set_level_objective_moved_under_a_standing_total_is_refused() -> None:
    """The same identity at the level the card prints."""
    waterfall = build_waterfall(
        evidence(A, common={"time_efficiency": 0.90}),
        evidence(B, common={"time_efficiency": 0.70}),
        settings=SETTINGS,
    )
    payload = waterfall.model_dump()
    drill = dict(payload["drill_down"])
    levels = [dict(level) for level in drill["levels_a"]]
    levels[2] = {**levels[2], "set_level": levels[2]["set_level"] * 0.5}
    drill["levels_a"] = levels
    # Keep the divergence list honest, so the fold check is what fires
    # rather than the narrower one about that list.
    drill["diverging_objectives"] = ("U_E",)
    payload["drill_down"] = drill

    with pytest.raises(ValidationError, match="set_level objectives fold to"):
        Waterfall.model_validate(payload)


def test_a_divergence_list_that_drifts_from_the_levels_is_refused() -> None:
    levels = tuple(
        ObjectiveLevels(objective=name, set_level=0.5, episode_mean=0.5)
        for name in ("U_R", "U_S", "U_E", "U_C")
    )
    with pytest.raises(ValidationError, match="diverge"):
        UtilityDrillDown(
            candidate_a="a",
            candidate_b="b",
            set_utility_a=0.5,
            set_utility_b=0.5,
            episode_mean_utility_a=0.5,
            episode_mean_utility_b=0.5,
            levels_a=levels,
            levels_b=levels,
            diverging_objectives=("U_R",),
        )


def test_an_impossible_artifact_whose_sums_all_balance_is_refused() -> None:
    """The attack the sum checks alone cannot see.

    Every invariant of the previous round passes: the bars name each
    objective once, each height is its own weight × difference, they sum
    to ΔU, the drill-down agrees with the total. Every number is
    fabricated, and they were chosen in cancelling pairs precisely so
    that the arithmetic would balance. Only the value domain catches it.
    """
    waterfall = build_waterfall(evidence(A), evidence(B), settings=SETTINGS)
    payload = waterfall.model_dump()

    bars = [dict(entry) for entry in payload["bars"]]
    for entry, delta in zip(bars, (100.0, -100.0, 0.0, 0.0), strict=True):
        entry["delta_objective_mean"] = delta
        entry["contribution"] = entry["weight"] * delta
        entry["ci95"] = (min(0.0, entry["contribution"]), max(0.0, entry["contribution"]))
        entry["crosses_zero"] = True
    # w_R × 100 + w_S × (−100) = 30 − 10 = 20, so ΔU has to follow the
    # fiction for the sum to close.
    payload["bars"] = bars
    payload["delta_utility_mean"] = sum(entry["contribution"] for entry in bars)
    payload["delta_utility_median"] = 999.0
    payload["total_ci95"] = (-999.0, 999.0)

    with pytest.raises(ValidationError):
        Waterfall.model_validate(payload)

    drill = dict(payload["drill_down"])
    drill["set_utility_a"] = 99.0
    drill["set_utility_b"] = -99.0
    with pytest.raises(ValidationError):
        UtilityDrillDown.model_validate(drill)


def test_weights_that_are_not_one_profile_are_refused() -> None:
    """Four bars from two different preference profiles do not add up
    to a decomposition of anything a deployment declared."""
    waterfall = build_waterfall(evidence(A), evidence(B), settings=SETTINGS)
    payload = waterfall.model_dump()
    bars = [dict(entry) for entry in payload["bars"]]
    bars[0] = {**bars[0], "weight": bars[0]["weight"] / 2, "contribution": 0.0}
    bars[0]["delta_objective_mean"] = 0.0
    payload["bars"] = bars

    with pytest.raises(ValidationError, match="sum to"):
        Waterfall.model_validate(payload)


def test_malformed_input_is_a_validation_error_not_a_typeerror() -> None:
    """A broken artifact reaching an API is a 422, never a 500.

    The derived fields are filled *after* parsing for this reason: a
    before-validator doing arithmetic on raw JSON raises ``TypeError``
    from inside the request handler.
    """
    with pytest.raises(ValidationError):
        WaterfallBar(
            objective="U_E",
            weight=0.25,
            delta_objective_mean=0.40,
            contribution=0.10,
            ci95=("x", "y"),  # type: ignore[arg-type]
        )

    with pytest.raises(ValidationError):
        ObjectiveLevels(objective="U_R", set_level="x", episode_mean=0.5)  # type: ignore[arg-type]


def test_an_artifact_comparing_a_candidate_with_itself_is_refused() -> None:
    """The builder refuses this; so must the model that is read back."""
    waterfall = build_waterfall(evidence(A), evidence(B), settings=SETTINGS)
    payload = waterfall.model_dump()
    payload["candidate_b"] = payload["candidate_a"]
    payload["drill_down"] = {**payload["drill_down"], "candidate_b": payload["candidate_a"]}

    with pytest.raises(ValidationError, match="itself"):
        Waterfall.model_validate(payload)


def test_bars_must_decompose_the_differences_the_drill_down_measured() -> None:
    """Per-objective errors that cancel: right total, wrong attribution.

    Bars saying (+0.1, −0.1) against a drill-down measuring (+0.2, −0.2)
    reconstitute the same ΔU, and every earlier invariant passes. What
    changes is which objective the win is credited to — which is the
    only thing the panel is for.
    """
    waterfall = build_waterfall(
        evidence(A, per_episode=ANTICORRELATED),
        evidence(B, common={"time_efficiency": 0.70, "near_miss_rate": 0.15}),
        settings=SETTINGS,
    )
    payload = waterfall.model_dump()
    bars = [dict(entry) for entry in payload["bars"]]

    safety, efficiency = bars[1], bars[2]
    shift = 0.05
    # Move the two bars in opposite directions by amounts whose weighted
    # contributions cancel exactly, so the total is untouched.
    counter_shift = shift * safety["weight"] / efficiency["weight"]
    for entry, delta in ((safety, shift), (efficiency, -counter_shift)):
        entry["delta_objective_mean"] += delta
        entry["contribution"] = entry["weight"] * entry["delta_objective_mean"]
        entry["ci95"] = (
            min(entry["contribution"], entry["ci95"][0]),
            max(entry["contribution"], entry["ci95"][1]),
        )
        entry["crosses_zero"] = entry["ci95"][0] <= 0.0 <= entry["ci95"][1]
    payload["bars"] = bars

    assert sum(entry["contribution"] for entry in bars) == pytest.approx(
        payload["delta_utility_mean"], abs=SUM_TOLERANCE
    )
    with pytest.raises(ValidationError, match="drill-down measured"):
        Waterfall.model_validate(payload)


def test_the_profile_label_cannot_disagree_with_the_weights_that_drew_the_bars() -> None:
    """A label is checkable against nothing; the snapshot is."""
    waterfall = build_waterfall(
        evidence(A, common={"time_efficiency": 0.90}),
        evidence(B, common={"time_efficiency": 0.70}),
        settings=SETTINGS,
    )
    payload = waterfall.model_dump()
    bars = [dict(entry) for entry in payload["bars"]]
    for entry, weight in zip(bars, (0.5, 0.5, 0.0, 0.0), strict=True):
        entry["weight"] = weight
        entry["contribution"] = weight * entry["delta_objective_mean"]
        entry["ci95"] = (
            min(0.0, entry["contribution"]),
            max(0.0, entry["contribution"]),
        )
        entry["crosses_zero"] = True
    payload["bars"] = bars
    payload["delta_utility_mean"] = sum(entry["contribution"] for entry in bars)

    with pytest.raises(ValidationError, match="profile snapshot"):
        Waterfall.model_validate(payload)


def test_a_perturbed_profile_is_representable_and_says_so() -> None:
    """The HĐ-11.5 sweep moves the weights on purpose.

    Checking bars against ``PREFERENCE_PROFILES`` by label would make
    this case unrepresentable; checking them against a snapshot keeps it
    honest instead — the label records that the weights were moved, and
    the snapshot records where to.
    """
    swept = DecisionSettings(
        weights_override=PreferenceWeights(w_r=0.10, w_s=0.10, w_e=0.60, w_c=0.20)
    )
    faster = evidence(A, common={"time_efficiency": 0.90}, settings=swept)
    slower = evidence(B, common={"time_efficiency": 0.70}, settings=swept)

    waterfall = build_waterfall(faster, slower, settings=swept)

    assert waterfall.profile.weights.w_e == pytest.approx(0.60)
    assert waterfall.profile.kind == "perturbed"
    assert waterfall.profile.base_profile == "kho_ban_dem"
    assert bar(waterfall, "U_E").weight == pytest.approx(0.60)
    assert waterfall.profile.label == swept.profile_label
    assert waterfall.profile.label != DecisionSettings().profile_label
    assert waterfall.bar_sum == pytest.approx(waterfall.delta_utility_mean, abs=SUM_TOLERANCE)


def test_relabelling_an_artifact_without_touching_a_number_is_refused() -> None:
    """The last place a free-text name could still lie.

    Weights snapshotted, bars checked against them, every sum intact —
    and the profile name swapped for another deployment's. The
    arithmetic stays right while the panel claims to describe a
    preference it does not describe.
    """
    waterfall = build_waterfall(
        evidence(A, common={"time_efficiency": 0.90}),
        evidence(B, common={"time_efficiency": 0.70}),
        settings=SETTINGS,
    )
    payload = waterfall.model_dump()
    payload["profile"] = {**payload["profile"], "label": "pilot_demo"}

    with pytest.raises(ValidationError, match="does not follow from"):
        Waterfall.model_validate(payload)


def test_swapping_the_base_profile_under_unchanged_weights_is_refused() -> None:
    """Renaming the origin does not make the weights that profile's."""
    waterfall = build_waterfall(
        evidence(A, common={"time_efficiency": 0.90}),
        evidence(B, common={"time_efficiency": 0.70}),
        settings=SETTINGS,
    )
    payload = waterfall.model_dump()
    payload["profile"] = {
        **payload["profile"],
        "base_profile": "pilot_demo",
        "label": "pilot_demo",
    }

    with pytest.raises(ValidationError, match="declared canonical"):
        Waterfall.model_validate(payload)


def test_a_sweep_may_not_be_filed_under_the_plain_profile_name() -> None:
    swept = PreferenceWeights(w_r=0.10, w_s=0.10, w_e=0.60, w_c=0.20)

    with pytest.raises(ValidationError, match="declared canonical"):
        WaterfallProfile(kind="canonical", base_profile="kho_ban_dem", weights=swept)

    # ...and the reverse: an unmoved profile marked as a sweep hides a
    # headline result behind a caveat.
    with pytest.raises(ValidationError, match="declared perturbed"):
        WaterfallProfile(
            kind="perturbed",
            base_profile="kho_ban_dem",
            weights=PREFERENCE_PROFILES["kho_ban_dem"],
        )


def test_weights_with_no_named_origin_are_refused() -> None:
    """A sweep names what it moved away from; anything else is an
    unexplained preference wearing a profile's clothes."""
    with pytest.raises(ValidationError, match="unknown base profile"):
        WaterfallProfile(
            kind="perturbed",
            base_profile="whatever_we_felt_like",
            weights=PreferenceWeights(w_r=0.10, w_s=0.10, w_e=0.60, w_c=0.20),
        )


def test_the_label_is_derived_and_survives_serialisation() -> None:
    profile = WaterfallProfile(
        kind="canonical",
        base_profile="pilot_demo",
        weights=PREFERENCE_PROFILES["pilot_demo"],
    )
    assert profile.label == "pilot_demo"
    assert WaterfallProfile.model_validate(profile.model_dump()).label == "pilot_demo"

    swept = WaterfallProfile(
        kind="perturbed",
        base_profile="pilot_demo",
        weights=PreferenceWeights(w_r=0.10, w_s=0.10, w_e=0.60, w_c=0.20),
    )
    assert swept.label == "pilot_demo (perturbed)"
    assert (
        swept.label
        == DecisionSettings(
            preference_profile="pilot_demo",
            weights_override=PreferenceWeights(w_r=0.10, w_s=0.10, w_e=0.60, w_c=0.20),
        ).profile_label
    )


def test_canonical_means_the_whole_profile_including_the_cost_split() -> None:
    """``beta`` decides what "cost" means, so it is part of the profile.

    Keeping the four top-level weights at the table's values while
    splitting U_C as (1, 0, 0, 0) is a different preference — and with
    beta left out of the comparison it was certifiable as canonical
    *and* unfilable as perturbed, because the same check called it a
    match either way.
    """
    canonical = PREFERENCE_PROFILES["kho_ban_dem"]
    beta_only = canonical.model_copy(update={"beta": (1.0, 0.0, 0.0, 0.0)})
    assert (beta_only.w_r, beta_only.w_s, beta_only.w_e, beta_only.w_c) == (
        canonical.w_r,
        canonical.w_s,
        canonical.w_e,
        canonical.w_c,
    )

    with pytest.raises(ValidationError, match="declared canonical"):
        WaterfallProfile(kind="canonical", base_profile="kho_ban_dem", weights=beta_only)

    swept = WaterfallProfile(kind="perturbed", base_profile="kho_ban_dem", weights=beta_only)
    assert swept.label == "kho_ban_dem (perturbed)"


def test_a_beta_only_override_builds_a_perturbed_waterfall() -> None:
    canonical = PREFERENCE_PROFILES["kho_ban_dem"]
    settings = DecisionSettings(
        weights_override=canonical.model_copy(update={"beta": (0.4, 0.3, 0.3, 0.0)})
    )
    faster = evidence(A, common={"time_efficiency": 0.90}, settings=settings)
    slower = evidence(B, common={"time_efficiency": 0.70}, settings=settings)

    waterfall = build_waterfall(faster, slower, settings=settings)

    assert waterfall.profile.kind == "perturbed"
    assert waterfall.profile.weights.beta == (0.4, 0.3, 0.3, 0.0)
    assert waterfall.profile.label == "kho_ban_dem (perturbed)"
