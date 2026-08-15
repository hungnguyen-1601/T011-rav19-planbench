"""The arithmetic behind retiring a candidate mid-sweep.

These tests are deliberately about *numbers*, not about simulation. The
whole safety argument of early stopping is that it never guesses: a
candidate leaves the run only when the gate's own expression, evaluated
at that candidate's best possible future, still fails. So the tests do
what the rules do — count episodes and compare against thresholds — and
each one names the boundary it is standing on.

The integration side (a real sweep actually stopping, the report saying
so, the paired invariant surviving) lives in ``test_compare.py``.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml
from test_vertical_slice import write_profile

from planbench_decision.early_stop import GATES_WITHOUT_A_RULE, check_early_stop
from planbench_metrics.definitions import EpisodeMetricSet
from planbench_schemas.task_profile import TaskProfile


def _profile(tmp_path: Path, **constraints: float) -> TaskProfile:
    payload = yaml.safe_load(write_profile(tmp_path).read_text(encoding="utf-8"))
    payload["constraints"].update(constraints)
    return TaskProfile.model_validate(payload)


def _episode(
    index: int,
    *,
    success: bool = True,
    collisions: int = 0,
    failure_reason: str | None = None,
    memory_mb: float = 1.0,
) -> EpisodeMetricSet:
    """One row, with every field the model needs and only ``index`` unique.

    Values are deliberately bland: any rule that reacted to path length
    or smoothness would be a rule that stopped guessing arithmetic and
    started guessing quality.
    """
    return EpisodeMetricSet(
        episode_context_id=f"ctx{index:04d}",
        candidate_id="cand",
        success=success,
        failure_reason=failure_reason,  # type: ignore[arg-type]
        collision_count=collisions,
        min_clearance=0.5,
        near_miss_rate=0.0,
        path_length_m=10.0,
        travel_time_s=10.0,
        l_ref_m=10.0,
        path_efficiency=1.0,
        t_ideal_s=10.0,
        time_efficiency=1.0,
        smoothness=1.0,
        stop_and_go_count=0,
        p99_latency_ms=1.0,
        peak_search_nodes=10,
        peak_tree_nodes=0,
        costmap_cells=1000,
        memory_estimate_mb=memory_mb,
        peak_rss_mb=100.0,
        cpu_time_per_mission_s=1.0,
    )


class TestG2IsAbsorbing:
    """G2 demands exactly zero collisions, so it has no allowance to spend."""

    def test_one_collision_retires_the_candidate(self, tmp_path: Path) -> None:
        rows = [_episode(0), _episode(1, success=False, collisions=1, failure_reason="collision")]
        verdict = check_early_stop(rows, _profile(tmp_path), planned_episodes=300)
        assert verdict is not None
        assert verdict.gate == "G2"
        assert verdict.evidence["observed_collisions"] == 1
        assert verdict.evidence["first_collision_episode_context_id"] == "ctx0001"

    def test_a_clean_run_is_not_retired(self, tmp_path: Path) -> None:
        rows = [_episode(i) for i in range(50)]
        assert check_early_stop(rows, _profile(tmp_path), planned_episodes=300) is None

    def test_no_episodes_yet_is_not_a_verdict(self, tmp_path: Path) -> None:
        """Nothing measured is not evidence of anything — the mistake the
        whole platform exists to prevent, in miniature."""
        assert check_early_stop([], _profile(tmp_path), planned_episodes=300) is None


class TestG3CountsAgainstTheBestPossibleFuture:
    """``failures > floor(N(1 - min))``, checked on both sides of the line."""

    @staticmethod
    def _rows(failures: int, total: int) -> list[EpisodeMetricSet]:
        # Timeouts, not collisions: this class is about G3 and a
        # collision would retire the candidate at G2 first.
        return [
            _episode(i, success=i >= failures, failure_reason="timeout" if i < failures else None)
            for i in range(total)
        ]

    def test_exactly_the_allowance_keeps_running(self, tmp_path: Path) -> None:
        """15 failures of 300 at 0.95 leaves 285/300 = exactly the
        threshold. Still reachable, so still running."""
        profile = _profile(tmp_path, success_rate_min=0.95, collision_probability_max=0.01)
        assert check_early_stop(self._rows(15, 20), profile, planned_episodes=300) is None

    def test_one_more_than_the_allowance_retires(self, tmp_path: Path) -> None:
        profile = _profile(tmp_path, success_rate_min=0.95, collision_probability_max=0.01)
        verdict = check_early_stop(self._rows(16, 20), profile, planned_episodes=300)
        assert verdict is not None
        assert verdict.gate == "G3"
        assert verdict.evidence["failures"] == 16
        assert verdict.evidence["max_failures_allowed"] == 15
        assert verdict.evidence["best_possible_success_rate"] == pytest.approx(284 / 300)

    def test_the_verdict_still_holds_if_the_run_ends_early(self, tmp_path: Path) -> None:
        """The rule is stated for N, but a run can stop at any n <= N.

        ``failures > N(1-thr) >= n(1-thr)`` gives ``(n-failures)/n < thr``,
        so a candidate retired on the N-rule also fails the gate on the
        shorter sample it actually has. Without this, an interrupted run
        could contain a retired candidate that its own gate table says
        passed."""
        profile = _profile(tmp_path, success_rate_min=0.95, collision_probability_max=0.01)
        rows = self._rows(16, 20)
        assert check_early_stop(rows, profile, planned_episodes=300) is not None
        observed_rate = sum(1 for m in rows if m.success) / len(rows)
        assert observed_rate < 0.95


class TestG1AndG5:
    def test_too_many_no_path_episodes_retire(self, tmp_path: Path) -> None:
        profile = _profile(tmp_path, no_path_rate_max=0.02, collision_probability_max=0.01)
        rows = [_episode(i, success=False, failure_reason="no_path") for i in range(7)]
        verdict = check_early_stop(rows, profile, planned_episodes=300)
        assert verdict is not None
        assert verdict.gate == "G1"  # 7/300 = 0.0233 > 0.02, and it can only grow

    def test_six_no_path_episodes_are_still_within_reach(self, tmp_path: Path) -> None:
        profile = _profile(tmp_path, no_path_rate_max=0.02, collision_probability_max=0.01)
        rows = [_episode(i, success=False, failure_reason="no_path") for i in range(6)]
        assert check_early_stop(rows, profile, planned_episodes=300) is None  # 6/300 = 0.02

    def test_a_memory_estimate_over_budget_retires(self, tmp_path: Path) -> None:
        """G5 takes the worst episode, so the maximum only ever grows."""
        profile = _profile(tmp_path)
        rows = [_episode(0), _episode(1, memory_mb=1e9)]
        verdict = check_early_stop(rows, profile, planned_episodes=300)
        assert verdict is not None
        assert verdict.gate == "G5"

    def test_a_missing_memory_estimate_is_skipped_not_raised(self, tmp_path: Path) -> None:
        """G5 itself refuses that input loudly at scoring time. A stopping
        rule is the wrong place to discover it — turning a diagnosable
        error into an early exit hides it."""
        rows = [_episode(0), _episode(1).model_copy(update={"memory_estimate_mb": None})]
        assert check_early_stop(rows, _profile(tmp_path), planned_episodes=300) is None


class TestGatesThatMustNeverRetire:
    """A safety clause, not a regression test.

    G4 pools a p99 over every control step and that percentile is *not*
    monotone: slow steps early on can sink below p99 once the total grows.
    A rule reading "p99 is over budget right now" would retire a candidate
    for starting slowly.
    """

    def test_g4_and_g6_are_declared_ruleless_with_reasons(self) -> None:
        assert set(GATES_WITHOUT_A_RULE) == {"G4", "G6"}
        assert "không đơn điệu" in GATES_WITHOUT_A_RULE["G4"]

    def test_a_slow_candidate_is_never_retired(self, tmp_path: Path) -> None:
        rows = [_episode(i).model_copy(update={"p99_latency_ms": 5_000.0}) for i in range(50)]
        assert check_early_stop(rows, _profile(tmp_path), planned_episodes=300) is None


class TestGateOrder:
    def test_the_earliest_gate_is_the_one_reported(self, tmp_path: Path) -> None:
        """A candidate can be doomed at several gates at once. Reporting
        the contract-first one keeps the reason stable across runs instead
        of depending on which check happened to be written first."""
        profile = _profile(tmp_path, success_rate_min=0.95, collision_probability_max=0.01)
        rows = [
            _episode(i, success=False, failure_reason="no_path", collisions=1) for i in range(20)
        ]
        verdict = check_early_stop(rows, profile, planned_episodes=300)
        assert verdict is not None
        assert verdict.gate == "G1"


class TestTheVerdictIsReadable:
    def test_it_serialises_with_gate_rule_and_evidence(self, tmp_path: Path) -> None:
        """The report carries this verbatim, so a reader has to be able to
        re-check the arithmetic without the code in front of them."""
        rows = [_episode(0, success=False, collisions=1, failure_reason="collision")]
        verdict = check_early_stop(rows, _profile(tmp_path), planned_episodes=300)
        assert verdict is not None
        payload = verdict.to_json_dict()
        assert set(payload) == {"gate", "rule", "evidence"}
        assert payload["evidence"]["episodes_measured"] == 1
        assert copy.deepcopy(payload) == payload  # plain JSON-able data, no model objects
