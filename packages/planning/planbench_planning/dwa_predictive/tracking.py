"""Estimating obstacle velocity from the robot's own LiDAR.

This is the half of ``dwa_predictive`` that makes it a candidate rather
than a thought experiment. P4's oracle proved the constant-velocity model
is worth something *given perfect perception*; this module has to earn
some of that back from two consecutive scans, and **the estimation error
it carries is part of the algorithm, not something it is excused from**.

**Why it may not simply read the answer.** ``dwa`` declares
``local_observation_class = "lidar_only"``. A predictive controller that
took velocities from ``engine.dynamic_obstacles_now()`` would become a
``lidar+human_states`` candidate, and the platform's ranking refuses to
compare across observation classes by default — because a candidate that
knows where everything is will beat one that has to look, and that
victory says nothing about prediction. So the velocities are estimated
here, from ``Observation`` alone, and the estimator's failures are the
candidate's failures.

The pipeline, and the classification step is the one people skip::

    scan  ->  [1] cluster        adjacent rays, split on a range jump
              [2] classify       wall / edge-clipped / free-standing
              [3] associate      nearest centroid inside a gate
              [4] estimate       least squares over a few frames
              [5] floor          below which "moving" is just noise
              [6] lifecycle      warm-up, loss, ambiguity

**Every failure mode falls back to ``dwa``.** A broken tracker must make
this controller behave like the one without prediction, never like one
carrying rubbish velocities. That is why each stage below answers
uncertainty with **zero velocity** rather than a guess: a track with no
velocity contributes nothing to the predictive cost, which is exactly
``dwa``.

**Thresholds come from the sensor, never from the scenario.** An earlier
draft sized the cluster split from the largest ``DynamicObstacle.radius``
the deployment declared. That is ground truth: a ``lidar_only`` candidate
reading it knows *how big the things in this room are* before it has seen
them, and the leak surfaces the moment somebody runs it on an unfamiliar
map. The split is derived from ray spacing and declared range noise
instead — the controller's own specification, which it is entitled to.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from planbench_planning.dwa_predictive.tracks import ObstacleTrack
from planbench_schemas.episode import Observation
from planbench_schemas.feasibility import SafetyEnvelope
from planbench_schemas.geometry import EPS, Point2D
from planbench_schemas.sensor import SensorNoise

__all__ = ["Cluster", "LidarTracker", "TrackerDiagnostics"]


@dataclass(frozen=True)
class Cluster:
    """A run of adjacent rays that plausibly hit one object."""

    centroid: Point2D
    width: float
    points: int
    #: Straight-line residual of the points, in metres. Small on a wall.
    straightness: float
    #: True when the run ends because the scan ran out rather than because
    #: the object did — its far side is unknown, so its centre is not a
    #: quantity that can be tracked.
    clipped: bool

    @property
    def radius(self) -> float:
        """Half the width, floored so a one-ray return is not zero-sized."""
        return max(self.width / 2.0, 0.05)


@dataclass
class TrackerDiagnostics:
    """Counters for reading a run afterwards, never for scoring one.

    Deliberately not metrics. The Metrics Engine reads the trace and the
    gates read the metrics; a number produced here would be a second
    source for the same question (HĐ-5). These exist so that when a
    comparison comes out flat somebody can ask *did the tracker even
    work* without re-running anything.
    """

    frames: int = 0
    clusters_seen: int = 0
    clusters_tracked: int = 0
    associations: int = 0
    ambiguous_drops: int = 0
    tracks_started: int = 0
    tracks_timed_out: int = 0
    floored: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "frames": self.frames,
            "clusters_seen": self.clusters_seen,
            "clusters_tracked": self.clusters_tracked,
            "associations": self.associations,
            "ambiguous_drops": self.ambiguous_drops,
            "tracks_started": self.tracks_started,
            "tracks_timed_out": self.tracks_timed_out,
            "floored": self.floored,
        }


@dataclass
class _Track:
    """One followed object and the short history its velocity comes from."""

    identity: int
    #: ``(time, x, y)`` newest last, capped at the estimation window.
    history: list[tuple[float, float, float]] = field(default_factory=list)
    radius: float = 0.2
    last_seen: float = 0.0
    misses: int = 0

    @property
    def center(self) -> Point2D:
        _, x, y = self.history[-1]
        return Point2D(x=x, y=y)


class LidarTracker:
    """Clusters a scan, follows the free-standing parts, estimates velocity.

    Holds state between control steps — the first thing in this
    controller that does — so :meth:`reset` has to clear **all** of it.
    Two episodes on one instance must equal two instances, and that is a
    test rather than an intention.
    """

    def __init__(
        self,
        config,
        envelope: SafetyEnvelope | None = None,
        sensor_noise: SensorNoise | None = None,
    ) -> None:
        self._config = config
        self._envelope = envelope or SafetyEnvelope()
        self._noise = sensor_noise or SensorNoise()
        self._tracks: list[_Track] = []
        self._next_identity = 0
        self.diagnostics = TrackerDiagnostics()

    def reset(self) -> None:
        self._tracks = []
        self._next_identity = 0
        self.diagnostics = TrackerDiagnostics()

    # -- the pipeline ---------------------------------------------------

    def update(self, observation: Observation) -> tuple[ObstacleTrack, ...]:
        """One scan in, the tracks it supports out."""
        self.diagnostics.frames += 1

        clusters = self.cluster(observation)
        self.diagnostics.clusters_seen += len(clusters)
        movable = [c for c in clusters if self._is_free_standing(c)]
        self.diagnostics.clusters_tracked += len(movable)

        self._associate(movable, observation.time)
        self._expire(observation.time)

        here = Point2D(x=observation.pose.x, y=observation.pose.y)
        spacing = 2.0 * math.pi / max(len(observation.lidar_ranges), 1)
        out: list[ObstacleTrack] = []
        for track in self._tracks:
            reach = math.hypot(track.center.x - here.x, track.center.y - here.y)
            floor = self.velocity_floor(reach, spacing)
            velocity, confidence = self._velocity_of(track, floor)
            out.append(
                ObstacleTrack(
                    center=track.center,
                    radius=track.radius,
                    velocity=velocity,
                    confidence=confidence,
                )
            )
        # Sorted by identity so the order a controller sees is a function
        # of when things were first seen, not of list churn. Determinism
        # is a contract here, not a nicety.
        return tuple(out)

    def cluster(self, observation: Observation) -> tuple[Cluster, ...]:
        """Split the scan into runs of adjacent rays on one surface.

        Two neighbouring rays that hit the same flat surface at range
        ``r`` land about ``r · Δθ`` apart, so a gap much larger than that
        means the surface ended. The threshold is that quantity times a
        declared factor, plus a margin for the declared range noise — both
        from the sensor's own specification.

        Rays that returned nothing are not obstacles at maximum range;
        they are the absence of an obstacle, and they end a run.
        """
        ranges = observation.lidar_ranges
        if not ranges:
            return ()
        config = self._config
        rays = len(ranges)
        spacing = 2.0 * math.pi / rays
        start_angle = observation.pose.theta - math.pi
        limit = max(ranges)

        runs: list[list[int]] = []
        current: list[int] = []
        for index, distance in enumerate(ranges):
            if distance >= limit - EPS:
                if current:
                    runs.append(current)
                    current = []
                continue
            if current:
                previous = ranges[current[-1]]
                threshold = (
                    config.cluster_gap_factor * distance * spacing
                    + config.cluster_range_margin * max(self._noise.lidar_range_sigma_m, 1e-6)
                )
                if abs(distance - previous) > threshold or index != current[-1] + 1:
                    runs.append(current)
                    current = []
            current.append(index)
        if current:
            runs.append(current)

        # The scan wraps: a run touching ray 0 and one touching the last
        # ray are one object seen across the seam. Joining them is what
        # stops an obstacle directly behind the robot being read as two.
        if len(runs) > 1 and runs[0][0] == 0 and runs[-1][-1] == rays - 1:
            runs[0] = runs[-1] + runs[0]
            runs.pop()

        clusters = []
        for run in runs:
            points = [
                (
                    observation.pose.x + ranges[i] * math.cos(start_angle + i * spacing),
                    observation.pose.y + ranges[i] * math.sin(start_angle + i * spacing),
                )
                for i in run
            ]
            clusters.append(self._describe(points, run, rays, ranges, limit))
        return tuple(clusters)

    def _describe(self, points, run, rays, ranges, limit) -> Cluster:
        count = len(points)
        cx = sum(p[0] for p in points) / count
        cy = sum(p[1] for p in points) / count
        first, last = points[0], points[-1]
        width = math.hypot(last[0] - first[0], last[1] - first[1])

        # Residual of the points about the chord: near zero on a flat
        # surface, larger on something curved like a person or a cart.
        straightness = 0.0
        if count > 2 and width > EPS:
            dx, dy = (last[0] - first[0]) / width, (last[1] - first[1]) / width
            for x, y in points:
                straightness = max(straightness, abs((x - first[0]) * dy - (y - first[1]) * dx))

        # **Bounded on both sides by free space is the good case**, and
        # getting this polarity backwards silently disables the tracker:
        # an isolated object in an open room is *always* flanked by rays
        # that returned nothing, so reading "no return beside it" as
        # clipped rejects exactly the objects worth following.
        #
        # A run is clipped when a neighbouring ray **did** return
        # something that the gap threshold split off — the surface carries
        # on past the break, so this run is a slice of a larger structure
        # and its centroid is a property of where the split fell rather
        # than of any object.
        before = ranges[(run[0] - 1) % rays]
        after = ranges[(run[-1] + 1) % rays]
        clipped = before < limit - EPS or after < limit - EPS
        return Cluster(
            centroid=Point2D(x=cx, y=cy),
            width=width,
            points=count,
            straightness=straightness,
            clipped=clipped,
        )

    def _is_free_standing(self, cluster: Cluster) -> bool:
        """Whether this cluster has a centre worth following.

        **Not a size test.** Sizing the decision from the obstacles the
        scenario declares would be reading ground truth. The three signals
        below are all properties of the scan itself:

        * **clipped** — the run ended because the scan did, so the far
          side is unknown and the centroid moves when the *view* changes
          rather than when the object does;
        * **long and straight** — a wall or a shelf face. It has a
          centroid, and that centroid slides along the wall as the robot
          drives past, which is a velocity that does not exist;
        * **too few points** — one or two returns give a centroid
          dominated by range noise.
        """
        config = self._config
        if cluster.clipped:
            return False
        if cluster.points < config.cluster_min_points:
            return False
        if cluster.width > config.cluster_max_width:
            return False
        return not (
            cluster.width > config.cluster_wall_width
            and cluster.straightness < config.cluster_straightness
        )

    def _associate(self, clusters: list[Cluster], time: float) -> None:
        """Match clusters to existing tracks, nearest centroid in a gate.

        The gate is ``association_speed_limit · Δt`` plus a margin, and
        that limit is **candidate-owned** — deliberately not
        ``v_obstacle_max``. The two fail in different ways: a wrong
        ``v_obstacle_max`` breaks a braking guarantee and ends in a
        collision, while a wrong association limit only breaks matching,
        and a tracker that stops matching falls back to ``dwa``. Two
        different failure modes may not share one field.
        """
        config = self._config
        unmatched = list(clusters)
        for track in self._tracks:
            elapsed = max(time - track.last_seen, config.control_period)
            gate = config.association_speed_limit * elapsed + config.association_margin
            inside = [
                cluster
                for cluster in unmatched
                if math.hypot(
                    cluster.centroid.x - track.center.x,
                    cluster.centroid.y - track.center.y,
                )
                <= gate
            ]
            if len(inside) > 1:
                # **Ambiguous, so take neither.** Two objects passing each
                # other is the case this protects against: matching across
                # them produces two velocities pointing the wrong way,
                # which is worse than no velocity at all.
                self.diagnostics.ambiguous_drops += 1
                track.misses += 1
                continue
            if not inside:
                track.misses += 1
                continue
            chosen = inside[0]
            unmatched.remove(chosen)
            track.history.append((time, chosen.centroid.x, chosen.centroid.y))
            del track.history[: -config.velocity_window]
            track.radius = chosen.radius
            track.last_seen = time
            track.misses = 0
            self.diagnostics.associations += 1

        for cluster in unmatched:
            self._tracks.append(
                _Track(
                    identity=self._next_identity,
                    history=[(time, cluster.centroid.x, cluster.centroid.y)],
                    radius=cluster.radius,
                    last_seen=time,
                )
            )
            self._next_identity += 1
            self.diagnostics.tracks_started += 1

    def _expire(self, time: float) -> None:
        """Drop tracks nothing has matched for a while.

        Kept for a few frames first, because partial occlusion is
        ordinary: deleting on the first miss would restart the estimate
        every time something passed behind a shelf, and the velocity would
        be zero exactly when it mattered. An object that reappears after
        the timeout becomes a **new** track — re-identification across a
        long gap is a different problem and not one this MVP claims.
        """
        keep = []
        for track in self._tracks:
            if time - track.last_seen > self._config.track_timeout:
                self.diagnostics.tracks_timed_out += 1
                continue
            keep.append(track)
        self._tracks = keep

    def velocity_floor(self, reach: float, ray_spacing: float) -> float:
        """Speed below which "moving" is indistinguishable from not moving.

        **Derived, not chosen** — the same discipline as ``SafetyEnvelope``
        and ``N_min``. Three sources, and the third is the one an earlier
        draft of this module left out:

        * **localisation** — a robot wrong about its own pose puts that
          error into every world-frame point it computes, so a wall
          acquires a velocity;
        * **range noise** — straight into the centroid;
        * **the scan itself.** A cluster is sampled by discrete rays, so
          its centroid moves when the *set of rays hitting it* changes,
          which happens whenever the robot moves. One ray spacing at that
          object's range, ``reach · Δθ``, is the scale of that shift, and
          it exists with a **perfect** sensor.

        The third term is not theoretical. Measured on three fully static
        scenes with every noise stream **off**, the tracker reported
        phantom speeds with a median of 0.28–0.41 m/s and peaks at
        1.27 m/s — the same magnitude as the real traffic in this library.
        With only the first two terms the floor is exactly zero there, and
        every one of those phantoms reaches the cost function.

        This is the single most important line in the module. Without it
        ``dwa_predictive`` is **worse** than ``dwa`` on every static
        scene, and worse precisely where the deployment declares
        localisation noise — which is where the project wants to measure.
        """
        window = max(self._window_seconds(), EPS)
        return (
            2.0 * self._envelope.position_uncertainty_m
            + self._config.cluster_range_margin * self._noise.lidar_range_sigma_m
            + max(reach, 0.0) * ray_spacing
        ) / window

    def _window_seconds(self) -> float:
        return max(self._config.velocity_window - 1, 1) * self._config.control_period

    def _velocity_of(self, track: _Track, floor: float) -> tuple[Point2D, float]:
        """Least squares over the history, then the noise floor.

        Least squares over several frames rather than a difference of two:
        range noise goes straight into a two-frame derivative, and the
        derivative is the quantity the whole prediction rests on.
        """
        samples = track.history
        if len(samples) < self._config.velocity_min_samples:
            # **Warm-up: no history, no guess.** Behaving exactly like
            # ``dwa`` for the first few frames of a track is the correct
            # answer, not a limitation.
            return Point2D(x=0.0, y=0.0), 0.0

        times = [s[0] for s in samples]
        mean_t = sum(times) / len(times)
        spread = sum((t - mean_t) ** 2 for t in times)
        if spread <= EPS:
            return Point2D(x=0.0, y=0.0), 0.0

        vx = sum((s[0] - mean_t) * s[1] for s in samples) / spread
        vy = sum((s[0] - mean_t) * s[2] for s in samples) / spread

        if math.hypot(vx, vy) < floor:
            self.diagnostics.floored += 1
            return Point2D(x=0.0, y=0.0), 1.0

        # Confidence falls while a track is coasting through a gap in the
        # scan. It does not gate anything yet — it is carried so P6 and
        # any later cost term can price a stale estimate.
        confidence = 1.0 / (1.0 + track.misses)
        return Point2D(x=vx, y=vy), confidence
