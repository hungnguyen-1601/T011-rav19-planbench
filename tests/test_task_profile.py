"""TaskProfile schema (CONTRACTS HĐ-2): validation and claim levels."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from task_profile_fakes import (
    TRAFFIC,
    constraints,
    environment,
    hardware,
    make_profile,
    three_missions,
)

from planbench_schemas.task_profile import (
    HardwareSpec,
    Mission,
    TaskConstraints,
    TaskRobotSpec,
)


class TestParsing:
    def test_contract_example_parses(self) -> None:
        profile = make_profile()
        assert profile.robot.control_period == 0.05
        assert profile.missions[0].start.x == 2.0
        assert profile.missions[0].goal.theta == 1.57

    def test_pose_accepts_mapping_form_too(self) -> None:
        profile = make_profile(
            missions=[{"id": "m1", "start": {"x": 1, "y": 2, "theta": 0}, "goal": [3, 4, 0]}]
        )
        assert profile.missions[0].start.y == 2.0

    def test_frozen(self) -> None:
        profile = make_profile()
        with pytest.raises(ValidationError):
            profile.id = "other"  # type: ignore[misc]

    def test_hardware_is_required(self) -> None:
        with pytest.raises(ValidationError, match="hardware"):
            make_profile(hardware=None)

    def test_observations_are_canonicalised(self) -> None:
        profile = make_profile(
            available_observations=["lidar_2d", "human_state_estimates", "lidar_2d "]
        )
        assert profile.available_observations == ("human_state_estimates", "lidar_2d")

    def test_unknown_observation_rejected(self) -> None:
        """G6 compares tokens literally, so a typo must not parse — see
        planbench_schemas.observations."""
        with pytest.raises(ValidationError, match="unknown observation"):
            make_profile(available_observations=["lidar_2d", "camera"])

    def test_blank_observation_rejected(self) -> None:
        with pytest.raises(ValidationError, match="unknown observation"):
            make_profile(available_observations=["lidar_2d", "  "])


class TestEnvironmentTraffic:
    def test_traffic_is_declared_by_the_deployment(self) -> None:
        """HĐ-3.3 draws an obstacle realisation per episode, so the
        population has to come from somewhere — and it is the site's
        property, not the candidate's."""
        profile = make_profile()
        assert len(profile.environment.dynamic_obstacles) == 1
        assert profile.environment.dynamic_obstacles[0].name == "forklift"

    def test_static_only_environment_is_legal(self) -> None:
        profile = make_profile(environment=environment(dynamic_obstacles=[]))
        assert profile.environment.dynamic_obstacles == ()

    def test_deterministic_motion_without_seed_offset_rejected(self) -> None:
        """Otherwise 300 seeds replay one episode and G2's rule-of-three
        bound has an effective sample size of 1."""
        frozen = [{**dict(TRAFFIC[0]), "seed_time_offset": 0.0}]
        with pytest.raises(ValidationError, match="effective sample size of 1"):
            make_profile(environment=environment(dynamic_obstacles=frozen))

    @pytest.mark.parametrize("kind", ["waypoint", "sudden_stop"])
    def test_every_time_deterministic_motion_is_covered(self, kind: str) -> None:
        motions: dict[str, dict[str, object]] = {
            "waypoint": {
                "kind": "waypoint",
                "waypoints": [{"x": 1.0, "y": 1.0}, {"x": 5.0, "y": 1.0}],
                "speed": 0.9,
            },
            "sudden_stop": {
                "kind": "sudden_stop",
                "start": {"x": 2.0, "y": 2.0},
                "heading": 0.0,
                "speed": 0.7,
                "stop_time": 4.0,
            },
        }
        obstacle: dict[str, object] = {
            "name": "walker",
            "radius": 0.3,
            "motion": motions[kind],
            "seed_time_offset": 0.0,
        }
        with pytest.raises(ValidationError, match="effective sample size of 1"):
            make_profile(environment=environment(dynamic_obstacles=[obstacle]))
        obstacle["seed_time_offset"] = 5.0
        assert make_profile(environment=environment(dynamic_obstacles=[obstacle]))

    def test_random_walk_needs_no_offset(self) -> None:
        """It draws its heading from the episode seed already."""
        obstacle = {
            "name": "wanderer",
            "radius": 0.3,
            "motion": {
                "kind": "random_walk",
                "origin": {"x": 8.0, "y": 8.0},
                "speed": 0.6,
                "change_interval": 2.0,
                "max_radius": 4.0,
            },
        }
        profile = make_profile(environment=environment(dynamic_obstacles=[obstacle]))
        assert profile.environment.dynamic_obstacles[0].seed_time_offset == 0.0

    def test_duplicate_obstacle_names_rejected(self) -> None:
        """The name is mixed into the seed hash; two obstacles sharing one
        would move in lockstep."""
        pair = [dict(TRAFFIC[0]), dict(TRAFFIC[0])]
        with pytest.raises(ValidationError, match="unique"):
            make_profile(environment=environment(dynamic_obstacles=pair))


class TestMissions:
    def test_probabilities_must_sum_to_one(self) -> None:
        missions = three_missions()
        missions[0]["probability"] = 0.50
        with pytest.raises(ValidationError, match="sum to 1.0"):
            make_profile(missions=missions)

    def test_decimal_sum_noise_tolerated(self) -> None:
        # 0.40 + 0.35 + 0.25 is not exactly 1.0 in binary floating point.
        profile = make_profile(missions=three_missions())
        assert len(profile.missions) == 3

    def test_duplicate_ids_rejected(self) -> None:
        missions = three_missions()
        missions[1]["id"] = "m1"
        with pytest.raises(ValidationError, match="unique"):
            make_profile(missions=missions)

    def test_empty_missions_rejected(self) -> None:
        with pytest.raises(ValidationError):
            make_profile(missions=[])


class TestClaimLevel:
    def test_single_mission_caps_at_mission_even_if_more_desired(self) -> None:
        profile = make_profile(claim_level="robust_deployment")
        assert profile.effective_claim_level() == "mission"
        assert profile.effective_claim_level(neighborhood_evaluated=True) == "mission"

    def test_several_missions_support_deployment(self) -> None:
        profile = make_profile(claim_level="deployment", missions=three_missions())
        assert profile.effective_claim_level() == "deployment"

    def test_robust_needs_neighborhood_run(self) -> None:
        profile = make_profile(claim_level="robust_deployment", missions=three_missions())
        assert profile.effective_claim_level() == "deployment"
        assert profile.effective_claim_level(neighborhood_evaluated=True) == "robust_deployment"

    def test_author_may_claim_less_than_data_supports(self) -> None:
        profile = make_profile(claim_level="mission", missions=three_missions())
        assert profile.effective_claim_level(neighborhood_evaluated=True) == "mission"


class TestDerivedThresholds:
    @pytest.mark.parametrize(
        ("risk", "expected"),
        [(0.01, 300), (0.005, 600), (0.003, 1000), (0.1, 30), (1.0, 3)],
    )
    def test_n_min_rule_of_three(self, risk: float, expected: int) -> None:
        profile = make_profile(constraints=constraints(collision_probability_max=risk))
        assert profile.constraints.n_min_evaluation_episodes == expected

    def test_t_cycle_ms(self) -> None:
        assert make_profile().robot.t_cycle_ms == 50.0

    def test_control_period_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            TaskRobotSpec(
                radius=0.26,
                max_linear_velocity=0.8,
                max_angular_velocity=1.2,
                max_linear_acceleration=0.5,
                max_angular_acceleration=1.0,
                control_period=0.0,
            )

    def test_no_path_rate_default_matches_contract(self) -> None:
        # HĐ-7 G1 default: no_path_rate <= 0.02.
        assert make_profile().constraints.no_path_rate_max == 0.02


class TestScenarioChecksumUntouched:
    def test_robot_config_has_no_new_fields(self) -> None:
        """Adding fields to RobotConfig would change _scenario_checksum
        for every stored scenario; TaskRobotSpec must carry the new
        fields instead (see module docstring)."""
        from planbench_schemas.robot import RobotConfig

        assert set(RobotConfig.model_fields) == {
            "radius",
            "max_linear_velocity",
            "max_angular_velocity",
            "max_linear_acceleration",
            "max_angular_acceleration",
        }

    def test_task_robot_spec_extends_without_touching_base(self) -> None:
        assert {"control_period", "type"} <= set(TaskRobotSpec.model_fields)


class TestSubSchemas:
    def test_mission_probability_bounds(self) -> None:
        with pytest.raises(ValidationError):
            Mission(id="m", start=[0, 0, 0], goal=[1, 1, 0], probability=0.0)
        with pytest.raises(ValidationError):
            Mission(id="m", start=[0, 0, 0], goal=[1, 1, 0], probability=1.1)

    def test_constraints_bounds(self) -> None:
        with pytest.raises(ValidationError):
            TaskConstraints(
                success_rate_min=0.0,
                collision_probability_max=0.01,
                goal_tolerance_m=0.2,
                goal_tolerance_rad=0.35,
                episode_timeout_s=180,
                stuck_threshold_s=10,
                clearance_warning_m=0.35,
            )

    def test_hardware_bounds(self) -> None:
        with pytest.raises(ValidationError):
            HardwareSpec.model_validate(hardware(available_ram_mb=0))


class TestRamBudget:
    """HĐ-2.4: ``available_ram_mb`` is an allocation decision and must be
    explained, because G5 compares every candidate against it."""

    def test_contract_budget_adds_up(self) -> None:
        spec = HardwareSpec.model_validate(hardware())
        assert spec.total_ram_mb - spec.ram_budget_breakdown.total_mb == spec.available_ram_mb

    def test_breakdown_is_required(self) -> None:
        payload = {k: v for k, v in hardware().items() if k != "ram_budget_breakdown"}
        with pytest.raises(ValidationError):
            HardwareSpec.model_validate(payload)

    def test_budget_that_does_not_add_up_is_refused(self) -> None:
        """The failure this rule exists for: perception grows, nobody
        edits the line that says what is left, and G5 keeps judging
        against a budget the board no longer has."""
        with pytest.raises(ValidationError, match="does not add up"):
            HardwareSpec.model_validate(hardware(available_ram_mb=6000))

    def test_rounding_slack_is_tolerated(self) -> None:
        """Within 1% of total: a hand-written budget in round megabytes."""
        HardwareSpec.model_validate(hardware(available_ram_mb=3277 - 40))

    def test_unknown_breakdown_item_refused(self) -> None:
        """A typo would silently drop a claimant and inflate what
        navigation appears to be allowed."""
        breakdown = dict(hardware()["ram_budget_breakdown"])  # type: ignore[arg-type]
        breakdown["perceptionstack_mb"] = breakdown.pop("perception_stack_mb")
        with pytest.raises(ValidationError):
            HardwareSpec.model_validate(hardware(ram_budget_breakdown=breakdown))
