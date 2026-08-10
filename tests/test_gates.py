"""Feasibility gates G1–G6 (CONTRACTS HĐ-7).

The arithmetic of a gate is one comparison. What these tests are about is
where the bar came from, what a pass is allowed to mean, and what has to
be printed beside the result — those are the parts that decide whether a
Decision Card tells the truth.
"""

from __future__ import annotations

import pytest
from task_profile_fakes import constraints, hardware, make_profile

from planbench_decision.candidate import Candidate
from planbench_decision.gates import (
    BANNED_PHRASES,
    G4_HOST_ONLY_CAVEAT,
    GATE_IDS,
    BannedLanguageError,
    GateInputError,
    assert_no_banned_language,
    evaluate_gates,
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

ARTIFACT: dict[str, object] = {
    "kind": "artifact",
    "model_artifact_mb": 340.0,
    "runtime_footprint_mb": 2100.0,
    "source": "declared",
}

MODULAR: dict[str, object] = {
    "type": "modular",
    "global_planner": {"name": "astar", "version": "v1"},
    "local_controller": {"name": "dwa", "version": "v1"},
    "params": {"astar": {"heuristic": "euclidean"}, "dwa": {"sim_time": 1.5}},
    "observation_requirements": ["lidar_2d"],
    "resource_profile": dict(STRUCTURAL),
}

MONOLITHIC: dict[str, object] = {
    "type": "monolithic",
    "policy": {"name": "ppo_navigation", "checkpoint": "ckpt_12", "version": "v1"},
    "observation_requirements": ["lidar_2d"],
    "resource_profile": dict(ARTIFACT),
}

#: 10% accepted collision risk ⇒ N_min = 30, small enough to build a
#: passing evaluation set in a test without weakening what is checked.
FAST_CONSTRAINTS = constraints(collision_probability_max=0.1)


def modular(**overrides: object) -> Candidate:
    return Candidate.model_validate({**MODULAR, **overrides})


def monolithic(**overrides: object) -> Candidate:
    return Candidate.model_validate({**MONOLITHIC, **overrides})


def profile(**overrides: object):  # type: ignore[no-untyped-def]
    payload: dict[str, object] = {"constraints": dict(FAST_CONSTRAINTS)}
    payload.update(overrides)
    return make_profile(**payload)


def context(seed: int, **overrides: object) -> EpisodeContext:
    payload: dict[str, object] = {
        "task_profile_id": "warehouse_a_v1",
        "mission_id": "m1",
        "seed": seed,
    }
    payload.update(overrides)
    return EpisodeContext.model_validate(payload)


def episode(candidate: Candidate, ctx: EpisodeContext, **overrides: object) -> EpisodeMetricSet:
    """One passing episode; overrides change exactly what a test is about."""
    payload: dict[str, object] = {
        "episode_context_id": ctx.episode_context_id,
        "candidate_id": candidate.candidate_id,
        "success": True,
        "failure_reason": None,
        "collision_count": 0,
        "min_clearance": 0.6,
        "near_miss_rate": 0.0,
        "path_length_m": 44.0,
        "travel_time_s": 60.0,
        "l_ref_m": 40.0,
        "path_efficiency": 40.0 / 44.0,
        "t_ideal_s": 50.0,
        "time_efficiency": 50.0 / 60.0,
        "smoothness": 1.2,
        "stop_and_go_count": 2,
        "p99_latency_ms": 23.0,
        "peak_search_nodes": 412_000,
        "peak_tree_nodes": 0,
        "costmap_cells": 400_000,
        "memory_estimate_mb": 19.0,
        "peak_rss_mb": 340.0,
        "cpu_time_per_mission_s": 4.0,
    }
    payload.update(overrides)
    return EpisodeMetricSet.model_validate(payload)


def run(
    candidate: Candidate,
    task_profile: object,
    n: int = 30,
    *,
    failures: dict[int, dict[str, object]] | None = None,
    sample_set: str = "evaluation",
):  # type: ignore[no-untyped-def]
    """``n`` paired episodes, with per-index overrides for the failures."""
    failures = failures or {}
    variant: dict[str, object] = (
        {}
        if sample_set == "evaluation"
        else {"sample_set": sample_set, "environment_variant": "v1"}
    )
    contexts = [context(seed, **variant) for seed in range(n)]
    metrics = [episode(candidate, ctx, **failures.get(i, {})) for i, ctx in enumerate(contexts)]
    return evaluate_gates(candidate, task_profile, metrics, contexts)  # type: ignore[arg-type]


class TestThresholdsComeFromTheProfile:
    """HĐ-7: not one bar below belongs to this module (HĐ-15.3)."""

    def test_g3_bar_moves_with_the_deployment(self) -> None:
        """Same episodes, two deployments, two verdicts.

        29 of 30 successes is 0.9667. A site that declared 0.95 accepts
        it; a site that declared 0.99 does not. Neither number appears in
        the gate code — which is the point, because a hardcoded one would
        judge every deployment by the first customer's tolerance.
        """
        candidate = modular()
        failing = {0: {"success": False, "failure_reason": "timeout"}}

        lenient = run(candidate, profile(), failures=failing)
        strict = run(
            candidate,
            profile(constraints=constraints(collision_probability_max=0.1, success_rate_min=0.99)),
            failures=failing,
        )

        assert lenient.g3.success_rate == pytest.approx(29 / 30)
        assert lenient.g3.result == "pass"
        assert strict.g3.result == "fail"
        assert (lenient.g3.threshold, strict.g3.threshold) == (0.95, 0.99)

    def test_g4_bar_is_the_declared_control_period(self) -> None:
        candidate = modular()
        slow_loop = run(candidate, profile())
        fast_loop = run(
            candidate,
            profile(
                robot={
                    "radius": 0.26,
                    "max_linear_velocity": 0.8,
                    "max_angular_velocity": 1.2,
                    "max_linear_acceleration": 0.5,
                    "max_angular_acceleration": 1.0,
                    "control_period": 0.02,
                }
            ),
        )
        assert (slow_loop.g4.threshold_ms, fast_loop.g4.threshold_ms) == (50.0, 20.0)
        assert slow_loop.g4.result == "pass"
        assert fast_loop.g4.result == "fail"

    def test_g5_bar_is_the_boards_navigation_budget(self) -> None:
        candidate = modular()
        roomy = run(candidate, profile())
        cramped = run(
            candidate,
            profile(
                hardware=hardware(
                    total_ram_mb=1024,
                    available_ram_mb=10,
                    ram_budget_breakdown={
                        "os_and_middleware_mb": 512,
                        "perception_stack_mb": 300,
                        "localization_mapping_mb": 102,
                        "logging_and_reserve_mb": 100,
                    },
                )
            ),
        )
        assert roomy.g5.available_ram_mb == 3277
        assert roomy.g5.result == "pass"
        assert cramped.g5.result == "fail"

    def test_g2_run_count_derives_from_the_accepted_risk(self) -> None:
        """``N_min = ceil(3 / p_max)`` — the risk decides N, not the run."""
        clean = run(modular(), profile(), n=30)
        assert clean.g2.n_min == 30
        assert clean.g2.result == "pass"

        stricter = profile(constraints=constraints(collision_probability_max=0.01))
        same_runs = run(modular(), stricter, n=30)
        assert same_runs.g2.n_min == 300
        assert same_runs.g2.result == "fail"


class TestG1NoPath:
    def test_passes_under_the_declared_rate(self) -> None:
        report = run(
            modular(),
            profile(),
            n=100,
            failures={
                0: {"success": False, "failure_reason": "no_path"},
            },
        )
        assert report.g1.no_path_rate == pytest.approx(0.01)
        assert report.g1.result == "pass"

    def test_fails_above_it(self) -> None:
        report = run(
            modular(),
            profile(),
            n=100,
            failures={i: {"success": False, "failure_reason": "no_path"} for i in range(3)},
        )
        assert report.g1.no_path_rate == pytest.approx(0.03)
        assert report.g1.result == "fail"

    def test_other_failures_do_not_count_as_no_path(self) -> None:
        """G1 and G3 measure different jobs (route search vs. execution)."""
        report = run(
            modular(),
            profile(),
            n=30,
            failures={i: {"success": False, "failure_reason": "timeout"} for i in range(5)},
        )
        assert report.g1.no_path_rate == 0.0
        assert report.g1.result == "pass"
        assert report.g3.result == "fail"


class TestG2Collisions:
    def test_zero_collisions_alone_is_not_enough(self) -> None:
        """Zero events in too few runs bounds nothing useful (HĐ-7.1).

        Ten clean runs are consistent with a 26% collision rate. Passing
        on them would let the size of the run decide what may be claimed,
        which is the inversion HĐ-7.1 exists to forbid.
        """
        report = run(modular(), profile(), n=10)
        assert report.g2.observed_collisions == 0
        assert report.g2.n_runs < report.g2.n_min
        assert report.g2.result == "fail"
        assert "N_min" in (report.g2.note or "")

    def test_mandated_sentence_is_emitted_verbatim(self) -> None:
        """HĐ-7.1 fixes this string; it is what keeps "0 collisions" from
        being read as "no collisions happen"."""
        report = run(modular(), profile(), n=30)
        assert report.g2.statement == (
            "0 va chạm quan sát trong 30 lần chạy; cận trên 95% dưới phân phối "
            "kịch bản đã mô phỏng: 10.0%"
        )
        assert report.g2.upper_bound_95 == pytest.approx(0.1)

    def test_bound_matches_the_contracts_own_example(self) -> None:
        """300 runs ⇒ 1.0%, the figure printed in HĐ-12's card."""
        report = run(
            modular(), profile(constraints=constraints(collision_probability_max=0.01)), n=300
        )
        assert report.g2.upper_bound_95 == pytest.approx(0.01)
        assert "1.0%" in report.g2.statement
        assert report.g2.result == "pass"

    def test_one_collision_fails_and_quotes_no_bound(self) -> None:
        """The rule of three applies to zero-event data only."""
        report = run(
            modular(),
            profile(),
            n=30,
            failures={
                7: {"success": False, "failure_reason": "collision", "collision_count": 1},
            },
        )
        assert report.g2.observed_collisions == 1
        assert report.g2.result == "fail"
        assert report.g2.upper_bound_95 is None
        assert "cận trên" in report.g2.statement

    def test_neighborhood_episodes_are_refused(self) -> None:
        """Pooling the sets makes 3/N optimistic (HĐ-11.4, §17 ban 7)."""
        with pytest.raises(ValueError, match="evaluation"):
            run(modular(), profile(), n=30, sample_set="neighborhood")


class TestG4Realtime:
    def test_worst_episode_decides_not_the_mean(self) -> None:
        """A budget is a ceiling. One episode over it is a violation that
        an average across 29 good ones would hide."""
        report = run(modular(), profile(), n=30, failures={11: {"p99_latency_ms": 61.0}})
        assert report.g4.p99_ms == 61.0
        assert report.g4.result == "fail"

    def test_status_is_always_host_screening(self) -> None:
        """Sim-only reservation: no target board exists (§17 ban 12)."""
        report = run(modular(), profile())
        assert report.g4.status == "screened_on_host"
        assert report.g4.caveat == G4_HOST_ONLY_CAVEAT
        assert "verified_on_target" not in str(report.to_card())


class TestG5Memory:
    def test_structural_estimate_and_its_provenance(self) -> None:
        report = run(modular(), profile())
        assert report.g5.status == "estimated_from_structure"
        assert report.g5.memory_estimate_mb == 19.0
        assert report.g5.target_implementation == "cpp_ros2"
        assert report.g5.bytes_per_search_node == 40
        assert report.g5.result == "pass"

    def test_declared_artifact_is_labelled_as_declared(self) -> None:
        """A number the author wrote down may only eliminate (HĐ-7.3)."""
        candidate = monolithic()
        report = run(
            candidate, profile(), failures={i: {"memory_estimate_mb": 2440.0} for i in range(30)}
        )
        assert report.g5.status == "declared_by_author"
        assert "chỉ có giá trị loại bỏ" in report.g5.note
        assert report.g5.target_implementation is None

    def test_rss_never_becomes_the_gate_number(self) -> None:
        """§17 ban 13. RSS of a Python process against a C++ board budget
        is wrong by an order of magnitude, in an unpredictable direction."""
        report = run(modular(), profile(), failures={i: {"peak_rss_mb": 4000.0} for i in range(30)})
        assert report.g5.peak_rss_mb_diagnostic == 4000.0
        assert report.g5.memory_estimate_mb == 19.0
        assert report.g5.result == "pass"

    def test_missing_estimate_raises_rather_than_failing(self) -> None:
        """ "Not measured" and "too big" are different verdicts."""
        with pytest.raises(GateInputError, match="memory_estimate_mb"):
            run(modular(), profile(), failures={3: {"memory_estimate_mb": None}})

    def test_measured_on_target_is_refused_under_the_reservation(self) -> None:
        candidate = monolithic(resource_profile={**ARTIFACT, "source": "measured_on_target"})
        with pytest.raises(GateInputError, match="no target board"):
            run(
                candidate,
                profile(),
                failures={i: {"memory_estimate_mb": 2440.0} for i in range(30)},
            )


class TestG6Observations:
    def test_subset_passes(self) -> None:
        assert run(modular(), profile()).g6.result == "pass"

    def test_missing_sensor_is_named(self) -> None:
        candidate = modular(observation_requirements=["lidar_2d", "human_state_estimates"])
        report = run(candidate, profile())
        assert report.g6.result == "fail"
        assert report.g6.missing == ("human_state_estimates",)

    def test_deployment_that_owns_the_tracker_passes(self) -> None:
        candidate = modular(observation_requirements=["lidar_2d", "human_state_estimates"])
        report = run(
            candidate,
            profile(available_observations=["lidar_2d", "human_state_estimates"]),
        )
        assert report.g6.result == "pass"


class TestReport:
    def test_all_six_gates_run_even_after_a_failure(self) -> None:
        """HĐ-15.1 criterion 3: six gates and their run count, always.

        "Eliminated at G2" without knowing whether G4 also failed is a
        diagnosis nobody can act on.
        """
        candidate = modular(observation_requirements=["lidar_2d", "human_state_estimates"])
        report = run(
            candidate,
            profile(),
            n=10,
            failures={
                0: {"success": False, "failure_reason": "collision", "collision_count": 1},
                1: {"p99_latency_ms": 90.0},
            },
        )
        assert set(report.results) == set(GATE_IDS)
        assert report.blocking_gates == ("G2", "G3", "G4", "G6")
        assert report.passed is False
        assert all(result.n_runs == 10 for result in report.results.values())

    def test_a_clean_candidate_passes_everything(self) -> None:
        report = run(modular(), profile())
        assert report.passed is True
        assert report.blocking_gates == ()

    def test_card_has_the_contract_shape(self) -> None:
        card = run(modular(), profile()).to_card()
        assert [key for key in card if key != "candidate_id"] == list(GATE_IDS)
        assert card["G1"] == "pass" and card["G3"] == "pass" and card["G6"] == "pass"
        assert card["G2"]["observed"] == 0 and card["G2"]["n_runs"] == 30
        assert card["G4"]["status"] == "screened_on_host"
        assert card["G5"]["status"] == "estimated_from_structure"
        assert card["G5"]["peak_rss_mb_diagnostic"] == 340.0


class TestBannedLanguage:
    """§17 ban 10, as a CI test — required by HĐ-7.1."""

    def test_no_gate_card_says_the_banned_words(self) -> None:
        for candidate in (modular(), monolithic()):
            report = run(
                candidate,
                profile(),
                n=30,
                failures={i: {"memory_estimate_mb": 2440.0} for i in range(30)},
            )
            assert_no_banned_language(report.to_card())
            for result in report.results.values():
                assert_no_banned_language(result.model_dump())

    def test_failing_cards_are_clean_too(self) -> None:
        report = run(
            modular(),
            profile(),
            n=10,
            failures={
                0: {"success": False, "failure_reason": "collision", "collision_count": 1},
            },
        )
        assert_no_banned_language(report.to_card())

    @pytest.mark.parametrize(
        "text",
        [
            "candidate is an toàn at 300 runs",
            "không an toàn",
            "AN TOÀN",
            "TCO estimate: 4.2",
            "tco: 4.2",
        ],
    )
    def test_the_guard_actually_catches_them(self, text: str) -> None:
        with pytest.raises(BannedLanguageError):
            assert_no_banned_language(text)

    def test_words_that_merely_contain_the_letters_are_fine(self) -> None:
        assert_no_banned_language("protocol tcod and antoan_id are not the banned words")

    def test_guard_walks_nested_payloads(self) -> None:
        with pytest.raises(BannedLanguageError):
            assert_no_banned_language({"gates": [{"note": "an toàn"}]})

    def test_both_phrases_are_declared(self) -> None:
        assert BANNED_PHRASES == ("an toàn", "TCO")


class TestInputsThatCannotSupportAVerdict:
    def test_no_episodes(self) -> None:
        candidate = modular()
        with pytest.raises(GateInputError, match="no episodes"):
            evaluate_gates(candidate, profile(), [], [])

    def test_metrics_from_another_candidate(self) -> None:
        mine, theirs = modular(), modular(params={"astar": {"heuristic": "manhattan"}})
        contexts = [context(seed) for seed in range(3)]
        metrics = [
            episode(mine, contexts[0]),
            episode(theirs, contexts[1]),
            episode(mine, contexts[2]),
        ]
        with pytest.raises(GateInputError, match="pooled across candidates"):
            evaluate_gates(mine, profile(), metrics, contexts)

    def test_repeated_context_inflates_n(self) -> None:
        candidate = modular()
        contexts = [context(0), context(1)]
        metrics = [episode(candidate, contexts[0]), episode(candidate, contexts[0])]
        with pytest.raises(GateInputError, match="more than once"):
            evaluate_gates(candidate, profile(), metrics, contexts)

    def test_contexts_and_metrics_must_describe_the_same_run(self) -> None:
        candidate = modular()
        contexts = [context(0), context(1)]
        metrics = [episode(candidate, contexts[0])]
        with pytest.raises(GateInputError, match="same run"):
            evaluate_gates(candidate, profile(), metrics, contexts)

    def test_episodes_from_another_deployment(self) -> None:
        """Every threshold comes from the profile, so the runs have to be
        the runs that profile describes."""
        candidate = modular()
        contexts = [context(seed, task_profile_id="other_site_v1") for seed in range(3)]
        metrics = [episode(candidate, ctx) for ctx in contexts]
        with pytest.raises(GateInputError, match="task profile"):
            evaluate_gates(candidate, profile(), metrics, contexts)
