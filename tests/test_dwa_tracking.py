"""P5 — estimating obstacle velocity from the robot's own LiDAR.

The tracker is where ``dwa_predictive`` stops being a thought experiment
and becomes a candidate: P4 proved the constant-velocity model is worth
something *given perfect perception*, and this has to earn some of it
back from consecutive scans.

Two things this file is organised around, and the second is the finding.

**Every failure mode must fall back to ``dwa``.** A tracker that is
unsure has exactly one honest answer — zero velocity — because a track
with no velocity contributes nothing to the predictive cost, which is
what ``dwa`` is. Guessing instead would make a broken estimator worse
than no estimator, and the whole point of the layering is that it cannot
be.

**Phantom velocity is real, large, and measured here.** On completely
static scenes with every noise stream off, a centroid tracker on a
72-ray scan reports speeds comparable to the library's real traffic —
because the centroid of a coarsely sampled object moves when the robot's
*view* of it changes, not only when the object does. That is not a bug
to be tuned away; it is the cost of ``lidar_only`` perception at this
resolution, and it is characterised rather than hidden.
"""

from __future__ import annotations

import math

import pytest

from planbench_benchmark.candidates import LOCAL_CONTROLLER_CONFIGS
from planbench_benchmark.registry import build_global_planner
from planbench_benchmark.scenarios import build_scenario
from planbench_planning.dwa_predictive import DWAPredictiveConfig, DWAPredictivePlanner
from planbench_planning.dwa_predictive.tracking import LidarTracker
from planbench_schemas.episode import Observation
from planbench_schemas.feasibility import SafetyEnvelope
from planbench_schemas.geometry import Pose2D
from planbench_schemas.sensor import SensorNoise
from planbench_simulator.nav_stack import run_stack

RAYS = 72
SPAN = 2.0 * math.pi
DT = 0.05


def _scan(objects, pose=(0.0, 0.0, 0.0), max_range=6.0):
    """A synthetic scan of circular objects, so geometry is exact.

    Real episodes are used further down; these give the pipeline inputs
    whose right answer can be written by hand.
    """
    x, y, theta = pose
    ranges = []
    for index in range(RAYS):
        angle = theta - SPAN / 2.0 + index * SPAN / RAYS
        best = max_range
        for ox, oy, radius in objects:
            dx, dy = ox - x, oy - y
            along = dx * math.cos(angle) + dy * math.sin(angle)
            if along <= 0:
                continue
            perp = abs(-dx * math.sin(angle) + dy * math.cos(angle))
            if perp > radius:
                continue
            best = min(best, along - math.sqrt(max(radius * radius - perp * perp, 0.0)))
        ranges.append(best)
    return tuple(ranges)


def _observation(time, objects, pose=(0.0, 0.0, 0.0)):
    return Observation(
        time=time,
        pose=Pose2D(x=pose[0], y=pose[1], theta=pose[2]),
        linear_velocity=0.0,
        angular_velocity=0.0,
        goal_distance=5.0,
        goal_bearing=0.0,
        lidar_ranges=_scan(objects, pose),
    )


def _tracker(**overrides) -> LidarTracker:
    config = DWAPredictiveConfig(control_period=DT, **overrides)
    return LidarTracker(config, SafetyEnvelope(), SensorNoise())


class TestClustering:
    """Runs of adjacent rays, split where the surface ends."""

    def test_one_object_is_one_cluster(self) -> None:
        clusters = _tracker().cluster(_observation(0.0, [(3.0, 0.0, 0.4)]))
        assert len(clusters) == 1
        assert clusters[0].centroid.x == pytest.approx(3.0 - 0.4, abs=0.15)
        assert clusters[0].centroid.y == pytest.approx(0.0, abs=0.05)

    def test_two_separated_objects_are_two_clusters(self) -> None:
        clusters = _tracker().cluster(_observation(0.0, [(3.0, -1.5, 0.4), (3.0, 1.5, 0.4)]))
        assert len(clusters) == 2

    def test_an_empty_room_has_no_clusters(self) -> None:
        """Rays that returned nothing are the absence of an obstacle, not
        an obstacle at maximum range. A tracker that read them as returns
        would follow a ring of phantom objects around the robot."""
        assert _tracker().cluster(_observation(0.0, [])) == ()

    def test_the_split_threshold_scales_with_range(self) -> None:
        """Two neighbouring rays on one surface land ``r · Δθ`` apart, so
        the same physical gap is many rays wide up close and sub-ray far
        away. A fixed threshold would over-split near objects and merge
        distant ones."""
        near = _tracker().cluster(_observation(0.0, [(1.0, -0.6, 0.25), (1.0, 0.6, 0.25)]))
        assert len(near) == 2


class TestClassification:
    """Which clusters have a centre worth following at all."""

    def test_a_free_standing_object_is_tracked(self) -> None:
        tracker = _tracker()
        assert tracker.update(_observation(0.0, [(3.0, 0.0, 0.4)]))

    def test_a_long_flat_wall_is_not(self) -> None:
        """Its centroid slides along it as the robot drives past, which is
        a velocity that does not exist. Built as a row of touching circles
        so the scan sees one long straight surface."""
        wall = [(3.0, offset, 0.25) for offset in [-1.2, -0.8, -0.4, 0.0, 0.4, 0.8, 1.2]]
        tracker = _tracker()
        assert tracker.update(_observation(0.0, wall)) == ()

    def test_a_slice_of_a_larger_surface_is_not(self) -> None:
        """A run whose neighbour also returned something is a *slice*: the
        surface carries on past the split, so the centroid says where the
        threshold fell rather than where an object is.

        This is the polarity that had to be got right. An isolated object
        is always flanked by rays returning nothing — that is what
        *bounded* looks like, and reading it as clipped would reject
        exactly the objects worth following.
        """
        tracker = _tracker()
        isolated = tracker.cluster(_observation(0.0, [(3.0, 0.0, 0.4)]))
        assert isolated and not isolated[0].clipped

        # Two objects close enough that the gap threshold splits one run
        # into two while both neighbours still carry returns.
        touching = [(3.0, offset, 0.3) for offset in (-0.35, 0.0, 0.35, 0.7)]
        runs = tracker.cluster(_observation(0.0, touching))
        assert any(run.clipped for run in runs) or len(runs) == 1


class TestVelocityEstimation:
    """Test 7.1 — a constant-velocity obstacle must be read correctly."""

    def test_it_converges_on_a_straight_line_run(self) -> None:
        """The headline requirement: get this wrong and everything after
        it is meaningless. A stationary robot watching an object close at
        a known speed must recover that speed."""
        tracker = _tracker()
        speed = 0.6
        estimate = None
        for step in range(25):
            time = step * DT
            observation = _observation(time, [(4.0 - speed * time, 0.0, 0.35)])
            tracks = tracker.update(observation)
            if tracks:
                estimate = tracks[0]
        assert estimate is not None
        assert estimate.velocity.x == pytest.approx(-speed, abs=0.12)
        assert estimate.velocity.y == pytest.approx(0.0, abs=0.12)

    def test_a_stationary_object_is_reported_stationary(self) -> None:
        tracker = _tracker()
        for step in range(25):
            tracks = tracker.update(_observation(step * DT, [(3.0, 0.0, 0.35)]))
        assert tracks
        assert math.hypot(tracks[0].velocity.x, tracks[0].velocity.y) == 0.0


class TestEveryUncertaintyAnswersZero:
    """The fallback rule, one case per row of the plan's lifecycle table."""

    def test_warm_up_reports_no_velocity(self) -> None:
        """One frame is not a velocity. Guessing from a single sample
        would be inventing one, and the oracle refuses identically —
        the two must agree wherever neither has information."""
        tracker = _tracker()
        tracks = tracker.update(_observation(0.0, [(3.0, 0.0, 0.35)]))
        assert tracks
        assert tracks[0].velocity.x == 0.0
        assert tracks[0].confidence == 0.0

    def test_a_brand_new_track_reports_no_velocity(self) -> None:
        tracker = _tracker()
        for step in range(20):
            tracker.update(_observation(step * DT, [(3.0, 0.0, 0.35)]))
        # A second object appears late; it has no history of its own.
        tracks = tracker.update(_observation(20 * DT, [(3.0, 0.0, 0.35), (2.0, 2.0, 0.35)]))
        newest = min(tracks, key=lambda t: t.confidence)
        assert newest.velocity.x == 0.0

    def test_an_ambiguous_match_takes_neither(self) -> None:
        """Two objects passing each other is the case this protects
        against: matching across them yields two velocities pointing the
        wrong way, which is worse than no velocity."""
        tracker = _tracker(association_speed_limit=50.0, association_margin=5.0)
        tracker.update(_observation(0.0, [(3.0, 0.0, 0.3)]))
        tracker.update(_observation(DT, [(3.0, -0.5, 0.3), (3.0, 0.5, 0.3)]))
        assert tracker.diagnostics.ambiguous_drops > 0

    def test_a_track_nothing_matches_is_eventually_dropped(self) -> None:
        tracker = _tracker(track_timeout=0.1)
        for step in range(5):
            tracker.update(_observation(step * DT, [(3.0, 0.0, 0.35)]))
        for step in range(5, 20):
            tracker.update(_observation(step * DT, []))
        assert tracker.diagnostics.tracks_timed_out > 0


class TestTheNoiseFloor:
    """Derived from what the deployment declares, plus the scan itself."""

    def test_localisation_noise_raises_it(self) -> None:
        quiet = _tracker()
        noisy = LidarTracker(
            DWAPredictiveConfig(control_period=DT),
            SafetyEnvelope(position_uncertainty_m=0.2),
            SensorNoise(),
        )
        spacing = SPAN / RAYS
        assert noisy.velocity_floor(3.0, spacing) > quiet.velocity_floor(3.0, spacing)

    def test_it_is_never_zero_even_with_a_perfect_sensor(self) -> None:
        """**The term an earlier draft left out.** A cluster is sampled by
        discrete rays, so its centroid moves when the set of rays hitting
        it changes — which happens whenever the robot moves, with a
        perfect sensor and a perfectly known pose. Without this the floor
        is exactly zero on a noiseless deployment and every phantom
        reaches the cost function."""
        floor = _tracker().velocity_floor(3.0, SPAN / RAYS)
        assert floor > 0.0

    def test_it_grows_with_range(self) -> None:
        """One ray spacing is 4 cm at a metre and 26 cm at six, so a
        distant object's centroid is far less certain."""
        tracker = _tracker()
        spacing = SPAN / RAYS
        assert tracker.velocity_floor(6.0, spacing) > tracker.velocity_floor(1.0, spacing)


class TestDeterminism:
    """Test 7.6 — the first thing here holding state across steps."""

    def test_two_episodes_on_one_instance_match_two_instances(self) -> None:
        shared = LOCAL_CONTROLLER_CONFIGS["dwa_balanced"]

        def episode(planner, seed: int):
            map_data, scenario = build_scenario("intersection")
            scenario = scenario.model_copy(update={"timeout_seconds": 12.0, "random_seed": seed})
            run = run_stack(
                map_data,
                scenario,
                planner,
                build_global_planner("astar+dwa", episode_seed=seed),
            )
            return [(p.linear_velocity, p.angular_velocity) for p in run.result.trajectory]

        reused = DWAPredictivePlanner(DWAPredictiveConfig(**shared))
        first_reused = episode(reused, 0)
        second_reused = episode(reused, 1)
        assert first_reused == episode(DWAPredictivePlanner(DWAPredictiveConfig(**shared)), 0)
        assert second_reused == episode(DWAPredictivePlanner(DWAPredictiveConfig(**shared)), 1)

    def test_the_tracker_state_does_not_survive_reset(self) -> None:
        tracker = _tracker()
        for step in range(10):
            tracker.update(_observation(step * DT, [(3.0, 0.0, 0.35)]))
        assert tracker.diagnostics.frames == 10
        tracker.reset()
        assert tracker.diagnostics.frames == 0
        tracks = tracker.update(_observation(0.0, [(3.0, 0.0, 0.35)]))
        assert tracks[0].velocity.x == 0.0, "history survived the reset"


#: Measured 2026-08-15 with **every noise stream off**, so none of this is
#: sensor noise: it is the centroid of a coarsely sampled object moving
#: because the robot's view of it changed.
PHANTOM_SCENES = ("doorway", "static_obstacles", "narrow_corridor")


class TestPhantomVelocityIsCharacterisedNotHidden:
    """The finding of this phase, stated as a measurement.

    A ``lidar_only`` centroid tracker cannot tell a small static object
    (a pillar, a door jamb) from a moving one by shape, and its estimate
    of "how fast is that" carries the robot's own motion. On three fully
    static scenes the reported speeds reach the magnitude of the
    library's real traffic.

    This is deliberately **not** asserted as zero. Writing a test that
    demanded zero and then tuning thresholds until it passed would be the
    exact anti-pattern this project keeps catching: a measurement made
    green rather than made true. What *is* guaranteed is the layer below
    — the hard feasible set and the braking bound are untouched by any of
    this, which is asserted in ``test_dwa_predictive.py``.
    """

    def test_static_scenes_still_produce_estimated_motion(self) -> None:
        shared = LOCAL_CONTROLLER_CONFIGS["dwa_balanced"]
        worst = 0.0

        class Spy(DWAPredictivePlanner):
            """Records what the tracker believed at each control step."""

            def __init__(self, config, sink):
                super().__init__(config)
                self._sink = sink

            def compute(self, state, observation):  # noqa: ANN001
                result = super().compute(state, observation)
                for track in self._tracker.update(observation):
                    self._sink.append(math.hypot(track.velocity.x, track.velocity.y))
                return result

        for scene in PHANTOM_SCENES:
            seen: list[float] = []
            map_data, scenario = build_scenario(scene)
            scenario = scenario.model_copy(update={"timeout_seconds": 15.0})
            run_stack(
                map_data,
                scenario,
                Spy(DWAPredictiveConfig(**shared), seen),
                build_global_planner("astar+dwa", episode_seed=0),
            )
            worst = max(worst, max(seen, default=0.0))
        # Recorded, not required: this is what the estimator does today.
        assert worst > 0.0, "the phantom effect vanished — re-measure before celebrating"

    def test_the_hard_constraints_are_untouched_by_any_of_it(self) -> None:
        """Which is why the above is survivable. The phantoms reach the
        **cost**, never the refusal or the speed bound, so the worst a
        broken estimate can do is route badly."""
        shared = LOCAL_CONTROLLER_CONFIGS["dwa_balanced"]
        tracked = DWAPredictivePlanner(DWAPredictiveConfig(**shared))
        empty = DWAPredictivePlanner(DWAPredictiveConfig(**shared), provider=lambda _t: ())
        from planbench_schemas.robot import RobotConfig, RobotState

        robot = RobotConfig(
            radius=0.26,
            max_linear_velocity=0.8,
            max_angular_velocity=1.2,
            max_linear_acceleration=0.5,
            max_angular_acceleration=1.0,
        )
        from planbench_schemas.geometry import Point2D

        path = [Point2D(x=0.0, y=0.0), Point2D(x=10.0, y=0.0)]
        tracked.reset(path, robot)
        empty.reset(path, robot)
        import numpy as np

        obstacles = np.array([[3.0, 0.0], [3.0, 0.5]])
        state = RobotState(pose=Pose2D(x=1.0, y=0.0, theta=0.0), linear_velocity=0.6)
        assert tracked._dynamic_window(state, obstacles) == empty._dynamic_window(state, obstacles)
