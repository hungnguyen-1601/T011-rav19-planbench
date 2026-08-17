"""Two holes that let a run describe a world nobody asked about.

**The artefact both of these come from.** Re-running
``warehouse_crossing_v1`` after withdrawing ``v_obstacle_max`` left a
``run_journal.jsonl`` holding **120 records** — sixty ``stuck`` followed
by sixty ``success`` — under the *same* ``episode_context_id``
``b408516ece7f``. Two different worlds, one identity, one file. Nothing
raised, and a reader diffing that journal would conclude the episode was
flaky rather than that two incomparable runs had been stacked.

Three separate mechanisms had to line up for that, and each is pinned
below: the trace store is keyed only by ids that exclude the
environment; the run directory is named from things that do not change
when the world does; and a partial LiDAR sweep would be simulated
correctly and read back wrong, which is the same class of defect waiting
on a field nobody has used yet.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from pydantic import ValidationError

from planbench_benchmark.contexts import build_evaluation_contexts
from planbench_benchmark.episode import scenario_for
from planbench_benchmark.fingerprint import (
    CONDITION_ARGUMENTS,
    execution_conditions_fingerprint,
)
from planbench_benchmark.selection import load_profile, load_task_map
from planbench_schemas.sensor import LidarConfig
from planbench_simulator.nav_stack import run_stack

REPO_ROOT = Path(__file__).resolve().parents[1]
PROFILE = REPO_ROOT / "profiles" / "warehouse_crossing_v1.yaml"


@pytest.fixture(scope="module")
def deployment():
    profile = load_profile(PROFILE)
    return profile, load_task_map(profile, base_dir=REPO_ROOT)


def _fingerprint(profile, map_data, seed: int = 0) -> str:
    context = build_evaluation_contexts(profile, seed_count=1, first_seed=seed)[0]
    return execution_conditions_fingerprint(map_data, scenario_for(profile, context), profile)


class TestTheFingerprintTracksTheWorld:
    def test_it_is_stable_for_the_same_conditions(self, deployment) -> None:
        """An identity that moved between two calls would make every
        reuse check fail and every sweep re-simulate from scratch."""
        profile, map_data = deployment
        assert _fingerprint(profile, map_data) == _fingerprint(profile, map_data)

    def test_withdrawing_the_braking_bound_changes_it(self, deployment) -> None:
        """**The exact edit that produced the 120-record journal.**
        ``v_obstacle_max`` is not in ``episode_context_id``, so before
        this the two runs were indistinguishable to everything that reads
        a trace."""
        profile, map_data = deployment
        environment = profile.environment.model_copy(update={"v_obstacle_max": 0.8})
        louder = profile.model_copy(update={"environment": environment})
        assert _fingerprint(profile, map_data) != _fingerprint(louder, map_data)

    def test_changing_the_traffic_changes_it(self, deployment) -> None:
        profile, map_data = deployment
        obstacle = profile.environment.dynamic_obstacles[0]
        slower = obstacle.model_copy(
            update={"motion": obstacle.motion.model_copy(update={"speed": 0.4})}
        )
        environment = profile.environment.model_copy(update={"dynamic_obstacles": (slower,)})
        assert _fingerprint(
            profile.model_copy(update={"environment": environment}), map_data
        ) != _fingerprint(profile, map_data)

    def test_changing_the_declared_noise_changes_it(self, deployment) -> None:
        profile, map_data = deployment
        noise = profile.environment.sensor_noise.model_copy(update={"lidar_range_sigma_m": 0.05})
        environment = profile.environment.model_copy(update={"sensor_noise": noise})
        assert _fingerprint(
            profile.model_copy(update={"environment": environment}), map_data
        ) != _fingerprint(profile, map_data)

    def test_changing_the_clearance_preference_changes_it(self, deployment) -> None:
        """The field the first hand-written version of this hash forgot.
        It reshapes the planning grid, so it reshapes the trajectory —
        exactly the kind of thing a maintained list drifts away from."""
        profile, map_data = deployment
        louder = profile.model_copy(update={"clearance_preference": 8.0})
        assert _fingerprint(profile, map_data) != _fingerprint(louder, map_data)

    def test_a_gate_threshold_does_not_change_it(self, deployment) -> None:
        """The other half of the rule, and the half that keeps this
        usable: retuning what counts as success re-scores finished traces
        and must not force a re-simulation."""
        profile, map_data = deployment
        constraints = profile.constraints.model_copy(update={"success_rate_min": 0.80})
        stricter = profile.model_copy(update={"constraints": constraints})
        assert _fingerprint(profile, map_data) == _fingerprint(stricter, map_data)

    def test_different_seeds_share_conditions(self, deployment) -> None:
        """The seed is already the ``s`` in ``episode_context_id``. This
        hash answers a narrower question — *were the conditions the
        same?* — so two episodes of one deployment must agree."""
        profile, map_data = deployment
        assert _fingerprint(profile, map_data, seed=0) == _fingerprint(profile, map_data, seed=7)


class TestNothingTheSimulatorReadsIsUnhashed:
    def test_run_stack_has_not_grown_a_condition(self) -> None:
        """**The guard that keeps the hash honest as the code moves.**

        The fingerprint is built from what ``run_contract_episode`` hands
        the simulator. If ``run_stack`` gains a sixth argument describing
        the world, traces become reusable across a change nobody sees —
        which is the whole defect. Adding one is fine; adding one without
        deciding whether it belongs in the hash is not.
        """
        import inspect

        parameters = set(inspect.signature(run_stack).parameters)
        # The candidate, and plumbing that cannot change an outcome.
        not_conditions = {
            "local_planner",
            "global_planner",
            "recorder",
            "legacy_metrics",
            "self",
        }
        conditions = parameters - not_conditions
        assert conditions == set(CONDITION_ARGUMENTS), (
            "run_stack's condition arguments changed; decide whether the new one "
            "belongs in execution_conditions_fingerprint, then update CONDITION_ARGUMENTS"
        )


class TestAPartialSweepIsRefusedAtTheSource:
    """A 180-degree scanner is simulated correctly and read back wrong.

    ``planbench_simulator.lidar.scan`` spaces rays by
    ``angle_span / num_rays``; ``dwa_core.obstacle_points`` and the
    predictive clusterer both rebuild world points assuming a full
    circle. The mismatch places every return at the wrong bearing and
    raises nothing — and it would hit plain ``dwa`` too, not only the
    predictive candidate.
    """

    def test_a_full_circle_is_accepted(self) -> None:
        assert LidarConfig(num_rays=72, max_range=5.0).angle_span == pytest.approx(2 * math.pi)

    @pytest.mark.parametrize("span", [math.pi, math.pi / 2, 4.0])
    def test_a_partial_sweep_is_refused(self, span: float) -> None:
        with pytest.raises(ValidationError, match="full circle"):
            LidarConfig(num_rays=72, max_range=5.0, angle_span=span)

    def test_the_message_says_who_would_be_wrong(self) -> None:
        """A refusal that only said "unsupported" would leave the next
        person to rediscover which consumers assume a full circle."""
        with pytest.raises(ValidationError) as raised:
            LidarConfig(num_rays=72, max_range=5.0, angle_span=math.pi)
        message = str(raised.value)
        assert "obstacle_points" in message
        assert "L20" in message
