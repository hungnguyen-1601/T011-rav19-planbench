"""TaskProfile schema (CONTRACTS HĐ-2): validation and claim levels."""

from __future__ import annotations

import math
import pathlib

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

from planbench_schemas.dynamic import DynamicObstacle, clock_key, position_at
from planbench_schemas.task_profile import (
    HardwareSpec,
    Mission,
    TaskConstraints,
    TaskProfile,
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

    def test_periodic_motion_must_shift_by_a_whole_period(self) -> None:
        """The quiet version of the zero-offset bug, and the one that
        actually shipped.

        The reference warehouse shifted a 24-second patrol by 6 seconds.
        The seeds explored a quarter of the cycle, the robot crossed that
        lane in a two-second window, and across 100 seeds it never came
        within 2 m of the forklift — closest approach 2.53 m against a
        0.66 m contact distance. A deterministic stack therefore drove
        one identical episode a hundred times while G2 reported a 3%
        collision bound.
        """
        partial = [{**dict(TRAFFIC[0]), "seed_time_offset": 6.0}]
        with pytest.raises(ValidationError, match="less than one period"):
            make_profile(environment=environment(dynamic_obstacles=partial))

    def test_a_full_period_offset_is_accepted(self) -> None:
        exact = [{**dict(TRAFFIC[0]), "seed_time_offset": 24.0}]
        assert make_profile(environment=environment(dynamic_obstacles=exact))

    def test_a_longer_offset_is_accepted(self) -> None:
        """More than a cycle is redundant, not wrong — the phase simply
        wraps, which is still the whole phase space."""
        generous = [{**dict(TRAFFIC[0]), "seed_time_offset": 48.0}]
        assert make_profile(environment=environment(dynamic_obstacles=generous))

    def test_the_rule_only_applies_to_periodic_motion(self) -> None:
        """Waypoint and sudden-stop motions have no period to compare
        against; any positive offset varies them."""
        obstacle: dict[str, object] = {
            "name": "walker",
            "radius": 0.3,
            "motion": {
                "kind": "waypoint",
                "waypoints": [{"x": 1.0, "y": 1.0}, {"x": 5.0, "y": 1.0}],
                "speed": 0.9,
            },
            "seed_time_offset": 0.5,
        }
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
        """A trace, a snapshot and a refusal all name the obstacle they
        mean; two answering to one name makes every such record
        ambiguous."""
        pair = [dict(TRAFFIC[0]), dict(TRAFFIC[0])]
        with pytest.raises(ValidationError, match="unique"):
            make_profile(environment=environment(dynamic_obstacles=pair))


class TestTwoObstaclesMustNotShareAClock:
    """Unique names were never enough, and the old message said they were.

    The head start is hashed from ``seed_offset + len(name)``. Two names
    of the same length therefore collide, and the collision is total: not
    a similar head start, the *same* one, at every seed. ``cart`` and
    ``rack`` pass the uniqueness rule and move as one object.

    Found while writing the deployment form's traffic editor, which is
    the first thing that lets anybody declare a second obstacle without
    hand-editing YAML — so the trap had never been reachable by the
    people most likely to fall into it.
    """

    @staticmethod
    def crosser(name: str, **overrides: object) -> dict[str, object]:
        obstacle: dict[str, object] = {
            "name": name,
            "radius": 0.4,
            "seed_time_offset": 20.0,
            "motion": {
                "kind": "waypoint",
                "waypoints": [{"x": 4.0, "y": 2.0}, {"x": 4.0, "y": 16.0}],
                "speed": 0.7,
                "loop": False,
                "ping_pong": True,
            },
        }
        obstacle.update(overrides)
        return obstacle

    def test_the_collision_is_real_before_it_is_refused(self) -> None:
        """The defect itself, pinned. Without this the rule below looks
        like a rule about spelling."""
        cart = DynamicObstacle.model_validate(self.crosser("cart"))
        rack = DynamicObstacle.model_validate(self.crosser("rack"))
        assert clock_key(cart) == clock_key(rack)
        for seed in (0, 1, 7, 42):
            assert position_at(cart, 3.0, seed) == position_at(rack, 3.0, seed)

    def test_same_length_names_are_refused(self) -> None:
        with pytest.raises(ValidationError, match="clock key"):
            make_profile(
                environment=environment(
                    dynamic_obstacles=[self.crosser("cart"), self.crosser("rack")]
                )
            )

    def test_a_different_seed_offset_is_the_fix(self) -> None:
        """What the refusal tells the author to do has to actually work."""
        profile = make_profile(
            environment=environment(
                dynamic_obstacles=[self.crosser("cart"), self.crosser("rack", seed_offset=1)]
            )
        )
        first, second = profile.environment.dynamic_obstacles
        assert clock_key(first) != clock_key(second)
        assert position_at(first, 3.0, 7) != position_at(second, 3.0, 7)

    def test_different_lengths_pass_untouched(self) -> None:
        """The common case stays legal without anybody thinking about it."""
        profile = make_profile(
            environment=environment(
                dynamic_obstacles=[self.crosser("cart"), self.crosser("forklift")]
            )
        )
        assert len(profile.environment.dynamic_obstacles) == 2

    def test_obstacles_with_no_head_start_are_not_compared(self) -> None:
        """At offset zero the shift is zero for everyone, so a shared key
        means nothing — and ``random_walk``, the one motion allowed to sit
        there, still reads the seed through its headings."""
        walk: dict[str, object] = {
            "radius": 0.3,
            "seed_time_offset": 0.0,
            "motion": {
                "kind": "random_walk",
                "origin": {"x": 8.0, "y": 8.0},
                "speed": 0.6,
                "change_interval": 2.0,
                "max_radius": 4.0,
            },
        }
        profile = make_profile(
            environment=environment(
                dynamic_obstacles=[
                    {**walk, "name": "cart"},
                    {**walk, "name": "rack", "motion": {**walk["motion"], "seed_offset": 3}},  # type: ignore[dict-item]
                ]
            )
        )
        assert len(profile.environment.dynamic_obstacles) == 2

    def test_every_shipped_profile_still_loads(self) -> None:
        """The rule was chosen to cost no re-measurement. This is that
        claim, checked rather than asserted in a report.

        Every profile in the directory rather than the two named further
        down this file: a rule about *pairs* of obstacles is exactly the
        kind a two-deployment sample can pass while a third fails.
        """
        import yaml

        root = pathlib.Path(__file__).resolve().parents[1] / "profiles"
        paths = sorted(root.glob("*.yaml"))
        assert paths, "no shipped profiles found; this test would pass vacuously"
        for path in paths:
            TaskProfile.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


#: One obstacle per motion law, each with a **known** top speed, so the
#: validator is exercised against every branch of ``max_speed`` rather
#: than against the one law the fixture happens to use.
#:
#: The periodic entry is the only one where the bound is not the declared
#: ``speed``: a 14 m chord over 24 s peaks at ``π·14/24`` = 1.833 m/s at
#: the midpoint, which is both faster than the average and exactly where
#: a crossing obstacle is most likely to be in front of a robot.
SPEED_CASES: list[tuple[str, dict[str, object], float]] = [
    (
        "waypoint",
        {
            "kind": "waypoint",
            "waypoints": [{"x": 1.0, "y": 1.0}, {"x": 5.0, "y": 1.0}],
            "speed": 1.2,
        },
        1.2,
    ),
    (
        "random_walk",
        {
            "kind": "random_walk",
            "origin": {"x": 8.0, "y": 8.0},
            "speed": 0.6,
            "change_interval": 2.0,
            "max_radius": 4.0,
        },
        0.6,
    ),
    (
        "periodic",
        {
            "kind": "periodic",
            "start": {"x": 12.0, "y": 4.0},
            "end": {"x": 12.0, "y": 18.0},
            "period": 24.0,
        },
        math.pi * 14.0 / 24.0,
    ),
    (
        "sudden_stop",
        {
            "kind": "sudden_stop",
            "start": {"x": 2.0, "y": 2.0},
            "heading": 0.0,
            "speed": 0.7,
            "stop_time": 4.0,
        },
        0.7,
    ),
]


def _traffic(motion: dict[str, object]) -> list[dict[str, object]]:
    """One obstacle running ``motion``, with the seed offset the other
    rules demand so this class only ever fails for its own reason."""
    return [
        {
            "name": "mover",
            "radius": 0.35,
            "motion": motion,
            "seed_time_offset": float(motion.get("period", 5.0)),
        }
    ]


class TestTheDeclaredObstacleSpeedIsVerified:
    """``v_obstacle_max`` is a safety claim, so it is checked at load.

    A number declared and never checked is a sentence, not a guarantee. A
    profile stating 1.0 m/s beside a 1.5 m/s cart makes the robot size its
    braking distance for traffic slower than the traffic it meets, and
    nothing reports it — the failure is a robot that brakes too late, not
    an exception. Refusing it while the deployment is still loading is the
    HĐ-1.4 shape: a wrong profile found after 300 episodes is 300 episodes
    answering a different question.

    All four motion laws have a closed-form bound, so the check is
    **total**: there is no "cannot prove it" branch for a reader to worry
    about.
    """

    @pytest.mark.parametrize(
        ("kind", "motion", "bound"), SPEED_CASES, ids=[c[0] for c in SPEED_CASES]
    )
    def test_a_bound_below_the_traffic_is_refused(
        self, kind: str, motion: dict[str, object], bound: float
    ) -> None:
        with pytest.raises(ValidationError, match="declares faster traffic"):
            make_profile(
                environment=environment(
                    dynamic_obstacles=_traffic(motion), v_obstacle_max=bound * 0.5
                )
            )

    @pytest.mark.parametrize(
        ("kind", "motion", "bound"), SPEED_CASES, ids=[c[0] for c in SPEED_CASES]
    )
    def test_a_bound_at_the_traffic_is_accepted(
        self, kind: str, motion: dict[str, object], bound: float
    ) -> None:
        """Exactly at the bound, not merely above it. A validator with an
        accidental strict comparison would reject the one declaration that
        is precisely right."""
        profile = make_profile(
            environment=environment(dynamic_obstacles=_traffic(motion), v_obstacle_max=bound)
        )
        assert profile.environment.v_obstacle_max == pytest.approx(bound)

    def test_the_message_names_the_obstacle_and_a_number_that_works(self) -> None:
        """Written for the person choosing, not for a stack trace — the
        same standard ``PPOStackConfig._require_a_model`` set."""
        with pytest.raises(ValidationError) as raised:
            make_profile(environment=environment(v_obstacle_max=0.5))
        message = str(raised.value)
        assert "forklift" in message
        assert "1.83" in message

    def test_undeclared_is_the_default_and_validates_nothing(self) -> None:
        """The backward-compatibility promise. Every profile written
        before this field existed declares traffic, so a ``0.0`` default
        would fail its own validator on load — which is why the default is
        ``None`` and why ``None`` means *no claim* rather than *no
        traffic*."""
        profile = make_profile()
        assert profile.environment.v_obstacle_max is None
        assert profile.environment.dynamic_obstacles  # and it still loaded

    def test_zero_is_a_claim_and_a_false_one_is_refused(self) -> None:
        """The third meaning. ``0.0`` asserts that nothing at this site
        moves; beside declared traffic that assertion is false, and a
        false claim is worse than an absent one."""
        with pytest.raises(ValidationError, match="declares faster traffic"):
            make_profile(environment=environment(v_obstacle_max=0.0))

    def test_zero_is_accepted_where_it_is_true(self) -> None:
        """And the same value is correct on a site with no traffic. Note
        what would happen without ``default=0.0`` on the ``max``: the
        validator would raise on an empty sequence and the honest
        declaration would be the one case that crashed."""
        profile = make_profile(environment=environment(dynamic_obstacles=[], v_obstacle_max=0.0))
        assert profile.environment.v_obstacle_max == 0.0

    def test_a_negative_bound_is_not_a_direction(self) -> None:
        with pytest.raises(ValidationError):
            make_profile(environment=environment(dynamic_obstacles=[], v_obstacle_max=-1.0))

    def test_every_motion_law_has_a_bound(self) -> None:
        """All four laws are covered, and a fifth added later reaches the
        explicit ``NotImplementedError`` at the bottom of ``max_speed``
        rather than silently receiving a generous number."""
        from planbench_schemas.dynamic import Motion, max_speed

        covered = {case[0] for case in SPEED_CASES}
        declared = {option.model_fields["kind"].default for option in Motion.__origin__.__args__}
        assert covered == declared
        for _, motion, bound in SPEED_CASES:
            parsed = make_profile(
                environment=environment(dynamic_obstacles=_traffic(motion), v_obstacle_max=bound)
            ).environment.dynamic_obstacles[0]
            assert max_speed(parsed.motion) == pytest.approx(bound)

    def test_a_law_that_cannot_be_bounded_costs_the_claim_not_a_traceback(self) -> None:
        """The refusal path, checked without needing an unboundable law.

        ``max_speed`` raises ``NotImplementedError`` for a motion it
        cannot bound, and pydantic does **not** convert that into a
        validation error — it would escape as a raw traceback to whoever
        filed the deployment. The validator translates it into a load
        rejection, and this pins that translation while the branch has no
        real occupant.
        """
        from unittest.mock import patch

        with patch(
            "planbench_schemas.task_profile.max_speed",
            side_effect=NotImplementedError("no bound for this law"),
        ), pytest.raises(ValidationError, match="no provable speed bound"):
            make_profile(environment=environment(v_obstacle_max=1.0))


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


class TestHeadingReservation:
    """CONTRACTS HĐ-6: this platform has no final-orientation controller,
    so it cannot evaluate a heading requirement — and says so at load.

    Both reference profiles used to carry a paragraph explaining why they
    write π here. A paragraph protects the profiles whose author read it;
    the next profile is written by someone who did not.
    """

    def test_a_heading_requirement_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="constrains the arrival heading"):
            make_profile(constraints=constraints(goal_tolerance_rad=0.35))

    def test_the_message_points_at_the_reservation(self) -> None:
        """A refusal that does not say where the rule lives sends the
        reader to guess at the schema."""
        with pytest.raises(ValidationError) as excinfo:
            make_profile(constraints=constraints(goal_tolerance_rad=1.0))
        assert "HĐ-6" in str(excinfo.value)
        assert "final-orientation controller" in str(excinfo.value)

    @pytest.mark.parametrize("tolerance", [math.pi, 3.1416, 4.0])
    def test_unconstrained_headings_are_accepted(self, tolerance: float) -> None:
        make_profile(constraints=constraints(goal_tolerance_rad=tolerance))


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


class TestADeclarationIsNeverSilentlyDiscarded:
    """A profile that says something the model does not know is refused.

    Pydantic ignores unknown fields by default, and until this was closed
    a deployment could declare one and be accepted with the declaration
    dropped — the document said one thing and the measurement did
    another, with nothing anywhere saying so.

    Two ways it bites, and both are real rather than theoretical:

    * **a typo.** ``replaning: {enabled: true}`` parsed, stored, and ran
      with replanning off. The author had no way to find out short of
      reading the stored JSON.
    * **a server behind the document.** A profile naming a field the
      running code does not have yet is what a half-deployed upgrade
      looks like from the outside. Dropping it turns "my new setting does
      nothing" into an unfindable bug instead of a 422 naming the field.

    HĐ-2 makes this model the single statement of a deployment. One that
    discards part of what it was told is not a single statement.
    """

    @staticmethod
    def _hall() -> dict:
        import yaml

        path = pathlib.Path(__file__).resolve().parents[1] / "profiles" / "open_hall_v2.yaml"
        return yaml.safe_load(path.read_text(encoding="utf-8"))

    def test_a_mistyped_field_is_refused_by_name(self) -> None:
        profile = self._hall()
        profile["replaning"] = {"enabled": True}
        with pytest.raises(ValidationError, match="replaning"):
            TaskProfile.model_validate(profile)

    def test_an_unknown_field_is_refused(self) -> None:
        profile = self._hall()
        profile["measured_on_a_tuesday"] = True
        with pytest.raises(ValidationError, match="measured_on_a_tuesday"):
            TaskProfile.model_validate(profile)

    def test_the_shipped_profiles_still_load(self) -> None:
        """The refusal must not have been bought by breaking the two
        deployments this project measures itself with."""
        import yaml

        root = pathlib.Path(__file__).resolve().parents[1] / "profiles"
        for name in ("open_hall_v2", "warehouse_a_v2"):
            path = root / f"{name}.yaml"
            TaskProfile.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))

    def test_the_correctly_spelled_field_is_kept(self) -> None:
        """The other half: refusing the unknown is only useful if the
        known survives."""
        profile = self._hall()
        profile["replanning"] = {"enabled": True}
        parsed = TaskProfile.model_validate(profile)
        assert parsed.replanning.enabled
        assert parsed.replanning.max_replans is None
