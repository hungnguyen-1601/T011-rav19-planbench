"""Is the platform fair? (CONTRACTS HĐ-3.2, HĐ-7.4, HĐ-9, HĐ-11)

Every other suite asks whether a number is computed correctly. This one
asks something the project cannot function without and which no single
module owns: **when two candidates come out different, is that difference
coming from the candidates?**

The question is answered by symmetry, not by accuracy. If the platform is
fair then it must be blind to everything except what a candidate actually
did — so feeding it two things that are the same must produce "the same",
and feeding it the same things in a different order must produce the same
answer. Those are checkable without knowing what the right answer is,
which is what makes them worth having.

Five kinds of symmetry are checked here:

1. **Identity** — two candidates that behaved identically must be reported
   as indistinguishable. A platform that names a winner between two equal
   things is biased, and nothing downstream can repair that.
2. **Order** — the answer must not depend on which candidate was passed
   first.
3. **Label** — renaming a candidate must not move its score.
4. **Reference** — the yardstick (``L_ref``) belongs to the deployment.
   Grading each candidate against its own optimum would flatter whoever
   optimises the thing being measured.
5. **Geometry** — the fairness map is mirror-symmetric, so neither way
   around the obstacle is shorter.

What is deliberately *not* here: any assertion that a candidate succeeds.
Fairness is not success. A stack that fails on an easy map has told us
something true, and a suite that treated failure as its own bug would be
the first step toward tuning the simulator until the algorithms pass.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import yaml
from task_profile_fakes import constraints, make_profile

from planbench_decision.anchors import load_anchors
from planbench_decision.candidate import Candidate
from planbench_decision.objectives import DecisionSettings, set_objectives
from planbench_decision.pareto import label_field
from planbench_decision.stats import build_evidence, compare_pair, recommend
from planbench_metrics.definitions import EpisodeMetricSet
from planbench_schemas.episode_context import EpisodeContext
from planbench_schemas.map import CellState
from planbench_schemas.map_io import load_map_server
from planbench_schemas.task_profile import TaskProfile

REPO_ROOT = Path(__file__).resolve().parents[1]
FAIRNESS_PROFILE = REPO_ROOT / "profiles" / "open_hall_v1.yaml"

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
    "tuning_trials_used": 0,
    "tuning_wall_clock_h": 0.0,
    "n_tunable_params": 4,
    "evidence_log": "tests/test_fairness.py (no tuning)",
}

BASE: dict[str, object] = {
    "type": "modular",
    "global_planner": {"name": "astar", "version": "v1"},
    "local_controller": {"name": "dwa", "version": "v1"},
    "params": {"astar": {"heuristic": "euclidean"}, "dwa": {"sim_time": 1.5}},
    "observation_requirements": ["lidar_2d"],
    "resource_profile": dict(STRUCTURAL),
    "tuning": dict(TUNING),
}

#: 10% accepted risk => N_min = 30, so a 30-episode fixture can clear G2.
FAST = constraints(collision_probability_max=0.1)

N = 30


def twin(version: str) -> Candidate:
    """A candidate identical in behaviour, distinguishable only by name.

    ``candidate_id`` is a hash of the configuration (HĐ-1.3), so the same
    stack registered twice *is* one candidate and cannot be compared with
    itself. Varying the version string alone gives two ids over one
    behaviour — which is exactly the probe an identity test needs.
    """
    return Candidate.model_validate(
        {**BASE, "global_planner": {"name": "astar", "version": version}}
    )


def profile():  # type: ignore[no-untyped-def]
    return make_profile(constraints=dict(FAST))


def anchors():  # type: ignore[no-untyped-def]
    return load_anchors().resolve(profile())


def context(seed: int) -> EpisodeContext:
    return EpisodeContext.model_validate(
        {"task_profile_id": "warehouse_a_v1", "mission_id": "m1", "seed": seed}
    )


CONTEXTS = [context(seed) for seed in range(N)]


def episode(owner: Candidate, ctx: EpisodeContext, index: int, **over: object) -> EpisodeMetricSet:
    """One episode. ``index`` varies it, so a set of them is not a replay."""
    payload: dict[str, object] = {
        "episode_context_id": ctx.episode_context_id,
        "candidate_id": owner.candidate_id,
        "success": True,
        "failure_reason": None,
        "collision_count": 0,
        "min_clearance": 0.20 + (index % 7) * 0.004,
        "near_miss_rate": 0.05,
        "path_length_m": 44.0 + (index % 5) * 0.03,
        "travel_time_s": 60.0 + (index % 3) * 0.05,
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
    payload.update(over)
    return EpisodeMetricSet.model_validate(payload)


def evidence_for(owner: Candidate, **over: object):  # type: ignore[no-untyped-def]
    metrics = [episode(owner, ctx, i, **over) for i, ctx in enumerate(CONTEXTS)]
    return build_evidence(owner, metrics, CONTEXTS, anchors(), DecisionSettings())


class TestIdenticalCandidatesAreCalledIdentical:
    """The null test: two candidates that did the same thing.

    If the platform can pick a winner here, it is picking on something
    other than behaviour — an id, an ordering, leaked state — and every
    verdict it has ever issued is suspect by the same amount.
    """

    def test_paired_difference_is_exactly_zero(self) -> None:
        left, right = evidence_for(twin("a")), evidence_for(twin("b"))
        comparison = compare_pair(left, right, seed=0)
        assert comparison.delta_median == 0.0
        assert comparison.delta_mean == 0.0
        assert comparison.ci95 == (0.0, 0.0)

    def test_the_verdict_is_near_equivalent_not_a_winner(self) -> None:
        recommendation = recommend([evidence_for(twin("a")), evidence_for(twin("b"))], seed=0)
        assert recommendation.status == "NEAR_EQUIVALENT"

    def test_effect_size_is_undefined_rather_than_infinite(self) -> None:
        """Zero difference over zero spread. Reporting a number here is
        how a platform manufactures confidence out of nothing."""
        comparison = compare_pair(evidence_for(twin("a")), evidence_for(twin("b")), seed=0)
        assert comparison.effect_size is None

    def test_neither_dominates_the_other(self) -> None:
        report = label_field([evidence_for(twin("a")), evidence_for(twin("b"))], seed=0)
        assert set(report.labels.values()) == {"PARETO_FRONTIER"}
        assert len(report.frontier) == 2

    def test_the_four_objectives_agree_to_the_last_float(self) -> None:
        left = evidence_for(twin("a")).set_objectives
        right = evidence_for(twin("b")).set_objectives
        assert (left.u_r, left.u_s, left.u_e, left.u_c) == (
            right.u_r,
            right.u_s,
            right.u_e,
            right.u_c,
        )
        assert left.decision_utility == right.decision_utility


class TestTheAnswerDoesNotDependOnOrder:
    """Whoever was passed first must not be advantaged."""

    def test_recommendation_is_the_same_either_way(self) -> None:
        better = evidence_for(twin("a"), p99_latency_ms=10.0)
        worse = evidence_for(twin("b"), p99_latency_ms=40.0)
        forward = recommend([better, worse], seed=5)
        backward = recommend([worse, better], seed=5)
        assert forward.recommended_id == backward.recommended_id
        assert forward.status == backward.status

    def test_delta_only_changes_sign(self) -> None:
        better = evidence_for(twin("a"), p99_latency_ms=10.0)
        worse = evidence_for(twin("b"), p99_latency_ms=40.0)
        forward = compare_pair(better, worse, seed=5)
        backward = compare_pair(worse, better, seed=5)
        assert forward.delta_median == pytest.approx(-backward.delta_median)
        assert forward.delta_mean == pytest.approx(-backward.delta_mean)

    def test_pareto_labels_do_not_depend_on_order(self) -> None:
        better = evidence_for(twin("a"), p99_latency_ms=10.0)
        worse = evidence_for(twin("b"), p99_latency_ms=40.0)
        assert label_field([better, worse], seed=5).labels == (
            label_field([worse, better], seed=5).labels
        )


class TestScoringIgnoresWhoIsBeingScored:
    """A score must be a function of the episodes, not of the name on them."""

    def test_renaming_a_candidate_does_not_move_its_score(self) -> None:
        first, second = twin("a"), twin("zzz-renamed")
        assert first.candidate_id != second.candidate_id
        assert (
            evidence_for(first).set_objectives.decision_utility
            == evidence_for(second).set_objectives.decision_utility
        )

    def test_a_global_planner_name_carries_no_weight_of_its_own(self) -> None:
        """Nothing in the scoring may prefer "astar" to "rrtstar" as a
        word. Same episodes, different declared planner, same number."""
        astar = twin("a")
        rrtstar = Candidate.model_validate(
            {
                **BASE,
                "global_planner": {"name": "rrtstar", "version": "v1"},
                # The params block is keyed by layer name, so it moves with
                # the planner. Same contents, same shape, different label.
                "params": {"rrtstar": {"heuristic": "euclidean"}, "dwa": {"sim_time": 1.5}},
            }
        )
        assert (
            evidence_for(astar).set_objectives.decision_utility
            == evidence_for(rrtstar).set_objectives.decision_utility
        )

    def test_the_declared_tuning_cost_is_the_only_candidate_input(self) -> None:
        """HĐ-1.6 lets engineering effort count against a candidate, and
        that is the *only* candidate-side field allowed to move a score.
        If any other one did, a stack could be advantaged by paperwork."""
        cheap = twin("a")
        expensive = Candidate.model_validate(
            {**BASE, "tuning": {**TUNING, "tuning_wall_clock_h": 40.0}}
        )
        assert (
            evidence_for(cheap).set_objectives.decision_utility
            > evidence_for(expensive).set_objectives.decision_utility
        )


class TestTheYardstickBelongsToTheDeployment:
    """``L_ref`` grades a route against the deployment's optimum.

    Computing it per candidate would grade each stack against its own
    best effort, which flatters whoever is being measured and makes the
    efficiency objective meaningless as a comparison.
    """

    def test_l_ref_is_an_input_to_scoring_not_an_output_of_a_candidate(self) -> None:
        from planbench_metrics import definitions

        source = Path(definitions.__file__).read_text(encoding="utf-8")
        # The reference path is computed from the context and the map.
        assert "reference_path_length" in source
        # ...and compute_metrics takes no planner, only a resource profile
        # (which feeds the memory estimate and nothing else).
        assert "def compute_metrics(" in source
        signature = source[source.index("def compute_metrics(") :].split(")")[0]
        assert "candidate" not in signature
        assert "planner" not in signature

    def test_two_candidates_on_one_context_share_one_reference(self) -> None:
        left = episode(twin("a"), CONTEXTS[0], 0)
        right = episode(twin("b"), CONTEXTS[0], 0)
        assert left.l_ref_m == right.l_ref_m


class TestTheFairnessMapIsSymmetric:
    """The map's own bias, measured rather than assumed.

    A hall 5 cm wider on one side would favour whichever planner prefers
    that side, and the finding would read as a property of the planner.
    The first generated version had exactly that defect — a float
    truncation made the top wall one cell thicker than the bottom.
    """

    @staticmethod
    @pytest.fixture(scope="class")
    def grid() -> np.ndarray:
        image = REPO_ROOT / "maps" / "open_hall.pgm"
        meta = REPO_ROOT / "maps" / "open_hall.yaml"
        if not image.is_file():
            pytest.skip("run scripts/make_fairness_map.py to generate the fairness map")
        map_data = load_map_server(image.read_bytes(), meta.read_text(encoding="utf-8"), "hall")
        cells = np.asarray(map_data.cells, dtype=np.int16).reshape(map_data.height, map_data.width)
        return cells == CellState.FREE.value

    def test_mirror_symmetric_about_the_mission_line(self, grid: np.ndarray) -> None:
        middle = grid.shape[0] // 2
        assert np.array_equal(grid[middle:], grid[:middle][::-1])

    def test_mirror_symmetric_left_to_right(self, grid: np.ndarray) -> None:
        middle = grid.shape[1] // 2
        assert np.array_equal(grid[:, middle:], grid[:, :middle][:, ::-1])

    def test_both_ways_round_the_block_are_equally_wide(self, grid: np.ndarray) -> None:
        column = grid[:, grid.shape[1] // 2]
        middle = grid.shape[0] // 2

        def widest(band: np.ndarray) -> int:
            best = run = 0
            for free in band:
                run = run + 1 if free else 0
                best = max(best, run)
            return best

        assert widest(column[:middle]) == widest(column[middle:])

    def test_the_hall_is_easy_enough_that_geometry_defeats_nobody(self, grid: np.ndarray) -> None:
        """6.2 m of clear width against a 0.52 m robot. A map that fails a
        candidate cannot be used to judge candidates."""
        column = grid[:, grid.shape[1] // 2]
        run = best = 0
        for free in column:
            run = run + 1 if free else 0
            best = max(best, run)
        assert best * 0.05 > 4.0


class TestTheFairnessProfileSaysWhatItIs:
    def test_it_loads_and_targets_the_symmetric_hall(self) -> None:
        profile_data = TaskProfile.model_validate(
            yaml.safe_load(FAIRNESS_PROFILE.read_text(encoding="utf-8"))
        )
        assert profile_data.environment.map.endswith("open_hall.pgm")
        mission = profile_data.missions[0]
        # Start, goal and the block's centre all sit on y = 8.0.
        assert mission.start.y == 8.0
        assert mission.goal.y == 8.0

    def test_it_declares_no_traffic_on_purpose(self) -> None:
        """With no moving obstacles a deterministic stack replays one
        episode, and G2 will refuse to bound anything. That is correct
        and it is not a defect of this profile: fairness is a question
        about symmetry, answerable on a single episode."""
        profile_data = TaskProfile.model_validate(
            yaml.safe_load(FAIRNESS_PROFILE.read_text(encoding="utf-8"))
        )
        assert profile_data.environment.dynamic_obstacles == ()

    def test_the_robot_matches_the_warehouse_robot(self) -> None:
        """The deployment changes between profiles; the vehicle does not,
        or results from the two cannot be read against each other."""
        hall = TaskProfile.model_validate(
            yaml.safe_load(FAIRNESS_PROFILE.read_text(encoding="utf-8"))
        )
        warehouse = TaskProfile.model_validate(
            yaml.safe_load(
                (REPO_ROOT / "profiles" / "warehouse_a_v2.yaml").read_text(encoding="utf-8")
            )
        )
        assert hall.robot.radius == warehouse.robot.radius
        assert hall.robot.max_linear_velocity == warehouse.robot.max_linear_velocity
        assert hall.robot.control_period == warehouse.robot.control_period


class TestSettingsApplyToEveryCandidateAlike:
    def test_one_preference_profile_scores_the_whole_field(self) -> None:
        """Weights are a property of the deployment, so two candidates in
        one run cannot be scored under different ones."""
        settings = DecisionSettings(preference_profile="benh_vien_gio_cao_diem")
        left, right = twin("a"), twin("b")
        metrics_l = [episode(left, ctx, i) for i, ctx in enumerate(CONTEXTS)]
        metrics_r = [episode(right, ctx, i) for i, ctx in enumerate(CONTEXTS)]
        scored_l = set_objectives(metrics_l, anchors(), left, settings)
        scored_r = set_objectives(metrics_r, anchors(), right, settings)
        assert scored_l.preference_profile == scored_r.preference_profile
        assert scored_l.decision_utility == scored_r.decision_utility

    def test_one_anchor_set_scores_the_whole_field(self) -> None:
        """Anchors are exogenous (HĐ-8.3 law 1). Two candidates measured
        on two scales are not being compared at all."""
        resolved = anchors()
        left, right = twin("a"), twin("b")
        assert (
            set_objectives(
                [episode(left, c, i) for i, c in enumerate(CONTEXTS)], resolved, left
            ).decision_utility
            == set_objectives(
                [episode(right, c, i) for i, c in enumerate(CONTEXTS)], resolved, right
            ).decision_utility
        )
