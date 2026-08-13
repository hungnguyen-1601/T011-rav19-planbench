"""Task Neighborhood (N5): the variants, and what they must never do.

``robustness_margin`` has been ``null`` on every Decision Card this
project has produced. These tests cover the half that can be checked
without hours of wall clock: the *generator*. Running twenty sweeps and
counting how often the recommendation holds is the other half, and it is
expensive by construction.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest
import yaml

from planbench_benchmark.neighborhood import (
    AXES,
    neighborhood_variants,
    recommendation_robustness,
)
from planbench_schemas.task_profile import TaskProfile

REPO_ROOT = Path(__file__).resolve().parents[1]


def load(name: str) -> TaskProfile:
    path = REPO_ROOT / "profiles" / f"{name}.yaml"
    return TaskProfile.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


@pytest.fixture(params=["open_hall_v2", "warehouse_a_v2"])
def profile(request: pytest.FixtureRequest) -> TaskProfile:
    """Both shipped deployments. They differ in the ways that matter
    here: the hall declares noise and has no traffic, the warehouse has
    traffic and declares none."""
    return load(request.param)


class TestAVariantIsNamedByWhatItDoes:
    def test_the_id_is_a_hash_of_the_perturbation(self, profile: TaskProfile) -> None:
        """Not a position in a list. "Variant 3" from two generator
        versions would otherwise be two different worlds under one name —
        invisible, because both runs would look complete."""
        variants = neighborhood_variants(profile, count=20, seed=0)
        assert len({v.variant_id for v in variants}) == 20

    def test_the_same_deployment_and_seed_give_the_same_neighbourhood(
        self, profile: TaskProfile
    ) -> None:
        """Two people asking for the neighbourhood of one deployment must
        get the same one, or ``robustness_margin`` is not a number
        anybody can check."""
        first = neighborhood_variants(profile, count=8, seed=3)
        again = neighborhood_variants(profile, count=8, seed=3)
        assert [v.variant_id for v in first] == [v.variant_id for v in again]
        assert [v.perturbation for v in first] == [v.perturbation for v in again]

    def test_a_different_seed_gives_a_different_neighbourhood(self, profile: TaskProfile) -> None:
        first = neighborhood_variants(profile, count=8, seed=0)
        other = neighborhood_variants(profile, count=8, seed=1)
        assert [v.variant_id for v in first] != [v.variant_id for v in other]


class TestAVariantIsNotANewDeployment:
    def test_the_task_profile_id_is_left_alone(self, profile: TaskProfile) -> None:
        """A variant is the same deployment asked a what-if. Giving it a
        new id would file a deployment nobody deployed, and its runs
        would then read as evidence about a real site. Episodes are told
        apart by ``environment_variant`` in the context hash (HĐ-3.1)."""
        for variant in neighborhood_variants(profile, count=5, seed=0):
            assert variant.profile.id == profile.id

    def test_every_variant_is_a_valid_profile(self, profile: TaskProfile) -> None:
        """A generator that emits a profile the contract refuses turns
        "this deployment is fragile" into "this generator is broken", and
        the two look identical from the outside."""
        variants = neighborhood_variants(profile, count=20, seed=7)
        assert all(isinstance(v.profile, TaskProfile) for v in variants)


class TestTheAxesAreTheOnesTheTopicDocumentNamed:
    def test_the_poses_move_within_the_declared_amplitude(self, profile: TaskProfile) -> None:
        limit = AXES["start_goal_shift_m"]
        for variant in neighborhood_variants(profile, count=20, seed=0):
            for nominal, moved in zip(profile.missions, variant.profile.missions, strict=True):
                assert abs(moved.start.x - nominal.start.x) <= limit + 1e-9
                assert abs(moved.goal.y - nominal.goal.y) <= limit + 1e-9
                assert (
                    abs(moved.start.theta - nominal.start.theta)
                    <= AXES["start_goal_heading_rad"] + 1e-9
                )

    def test_top_speed_moves_within_ten_percent(self, profile: TaskProfile) -> None:
        nominal = profile.robot.max_linear_velocity
        for variant in neighborhood_variants(profile, count=20, seed=0):
            ratio = variant.profile.robot.max_linear_velocity / nominal
            assert abs(ratio - 1.0) <= AXES["v_max_scale"] + 1e-9

    def test_a_periodic_obstacle_is_perturbed_too(self) -> None:
        """The reference warehouse's forklift is ``periodic``, which
        carries a ``period`` and no ``speed``. A generator that touched
        only ``speed`` would leave it completely unperturbed while the
        report claimed the traffic axis was covered."""
        warehouse = load("warehouse_a_v2")
        assert warehouse.environment.dynamic_obstacles, (
            "fixture assumption: the warehouse has traffic"
        )
        changed = {
            variant.profile.environment.dynamic_obstacles[0].motion.period
            for variant in neighborhood_variants(warehouse, count=10, seed=0)
        }
        assert len(changed) == 10
        assert warehouse.environment.dynamic_obstacles[0].motion.period not in changed

    def test_the_seed_offset_follows_the_period(self) -> None:
        """HĐ-2 makes a periodic obstacle's offset clear a full cycle, or
        every seed meets it at the same phase and a hundred episodes
        collapse into one distinct episode. A lengthened period would
        otherwise overtake a fixed offset and the variant would be
        refused at load."""
        warehouse = load("warehouse_a_v2")
        for variant in neighborhood_variants(warehouse, count=20, seed=0):
            obstacle = variant.profile.environment.dynamic_obstacles[0]
            assert obstacle.seed_time_offset >= obstacle.motion.period - 1e-9

    def test_noise_is_scaled_never_introduced(self) -> None:
        """A deployment that declared no noise is one nobody
        characterised. Inventing an amplitude here would answer a
        question about a world the author did not describe."""
        warehouse = load("warehouse_a_v2")
        assert warehouse.environment.sensor_noise.lidar_range_sigma_m == 0.0
        for variant in neighborhood_variants(warehouse, count=10, seed=0):
            assert variant.profile.environment.sensor_noise.lidar_range_sigma_m == 0.0

    def test_declared_noise_does_move(self) -> None:
        hall = load("open_hall_v2")
        assert hall.environment.sensor_noise.lidar_range_sigma_m > 0.0
        moved = {
            variant.profile.environment.sensor_noise.lidar_range_sigma_m
            for variant in neighborhood_variants(hall, count=10, seed=0)
        }
        assert len(moved) == 10

    def test_the_amplitude_table_matches_the_topic_document(self) -> None:
        """The numbers N5 names, kept as data so the table and the
        generator cannot drift apart."""
        assert AXES["start_goal_shift_m"] == 1.0
        assert AXES["start_goal_heading_rad"] == pytest.approx(math.radians(15.0))
        assert AXES["traffic_speed_scale"] == 0.2
        assert AXES["v_max_scale"] == 0.1


class TestTheMarginItself:
    def test_full_agreement_is_one(self) -> None:
        assert recommendation_robustness("c1", {"a": "c1", "b": "c1"}) == 1.0

    def test_a_disagreeing_variant_lowers_it(self) -> None:
        assert recommendation_robustness("c1", {"a": "c1", "b": "c2"}) == 0.5

    def test_a_variant_that_could_not_rank_counts_against_it(self) -> None:
        """ "Under this much input error the field stops being rankable at
        all" is exactly the fragility this number is asked about.
        Dropping those would report the stability of the variants that
        happened to stay easy."""
        assert recommendation_robustness("c1", {"a": "c1", "b": None}) == 0.5

    def test_nothing_measured_is_null_and_never_one(self) -> None:
        """HĐ-12 reads null as "not measured". Returning 1.0 for an empty
        neighbourhood would report perfect robustness from no evidence —
        and it is the direction a safety claim must never round."""
        assert recommendation_robustness("c1", {}) is None
        assert recommendation_robustness(None, {"a": "c1"}) is None
