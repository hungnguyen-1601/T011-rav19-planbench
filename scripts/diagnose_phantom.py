"""R1 — where the tracker's phantom velocities actually come from.

Q0 measured that raising LiDAR resolution buys a fivefold gain in real
detection and a sevenfold gain in **false** motion: on a completely
static warehouse the tracker reports something moving on 14% of frames
at 72 rays and on 99% at 360. The velocity floor exists to stop exactly
that, and one column explains why it does not::

    phantom p90 (m/s):  1.868   1.515   1.820   2.023     <- flat

The magnitude of the phantoms does not change with ray spacing, while
the floor built to suppress them shrinks linearly with it — the floor's
third term is ``reach · Δθ``. So the floor models phantom magnitude as a
function of angular resolution, and the measurement says it is not one.
The floor happens to be about the right size at 72 rays. That is a
coincidence of scale, not a model.

**This script does not run the planner.** Ego-motion is scripted and the
engine is stepped directly, because the question is about perception and
a DWA rollout would only add cost and confounds. That also makes the
matrix affordable: a run here is a LiDAR scan plus a tracker update.

**What it records, and why it is more than Q0 recorded.** Q0 could only
see velocity *after* the zero-gates, so a frame reporting nothing was
indistinguishable from a frame whose estimate was fine and got floored.
R1 records the raw least-squares fit **before** any gate, the floor that
frame, and the value that survived — plus the ego-motion, the sensor,
and the geometry of the cluster the track was built from. The causal
question needs all three: what the estimator produced, what the gate
asked of it, and what the world looked like at that moment.

**Distributions, not maxima.** Q0 reported one number per frame (the
fastest phantom). That is a summary of a summary and it cannot answer
where a threshold should sit. Here the raw speeds are kept and reported
as percentiles and as exceedance rates across the band the floor lives
in, because "what fraction of estimates would a floor of X remove"
is the question a redesign has to answer.

Usage::

    python scripts/diagnose_phantom.py                 # the full matrix
    python scripts/diagnose_phantom.py --rays 72,360 --seconds 10
    python scripts/diagnose_phantom.py --geometries straight_wall
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

for _variable in (
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ.setdefault(_variable, "1")

REPO_ROOT = Path(__file__).resolve().parents[1]
for _package in (
    "packages/schemas",
    "packages/benchmark",
    "packages/decision",
    "packages/explanation",
    "packages/plugin_sdk",
    "packages/metrics",
    "packages/planning",
    "services/simulator",
    "ml",
    "services/tracking",
    "services/agent_service",
    "services/analyst_service",
    "apps/api",
    "apps/desktop",
):
    sys.path.insert(0, str(REPO_ROOT / _package))


from planbench_benchmark.candidates import controller_version  # noqa: E402
from planbench_planning.dwa_predictive.planner import DWAPredictiveConfig  # noqa: E402
from planbench_planning.dwa_predictive.tracking import LidarTracker  # noqa: E402
from planbench_schemas.geometry import EPS, Pose2D  # noqa: E402
from planbench_schemas.map import CellState, MapData  # noqa: E402
from planbench_schemas.robot import RobotConfig, SimAction  # noqa: E402
from planbench_schemas.scenario import Scenario  # noqa: E402
from planbench_schemas.sensor import LidarConfig, SensorNoise  # noqa: E402
from planbench_simulator.engine import SimulationEngine  # noqa: E402

DEFAULT_OUT = REPO_ROOT / "artifacts" / "r1_phantom" / "records.json"

DEFAULT_RESOLUTIONS = (72, 144, 271, 360)

#: Metres per cell for the synthetic geometries. Matches the warehouse.
CELL = 0.05

#: The robot every row drives. Same vehicle as every deployment, so the
#: ego-motion magnitudes are the ones the tracker actually meets.
ROBOT = RobotConfig(
    radius=0.26,
    max_linear_velocity=0.8,
    max_angular_velocity=1.2,
    max_linear_acceleration=0.5,
    max_angular_acceleration=1.0,
)

#: The control period the deployments declare. Not on ``RobotConfig`` —
#: it is a property of the stack's timing, and the scenario carries it as
#: ``simulation_dt``.
CONTROL_PERIOD = 0.05

#: The experiment matrix. Each row isolates one contribution; read the
#: rows in order and each new one adds exactly one source.
#:
#:   still + quiet   -> the ideal floor. Anything here is a tracker bug,
#:                      not a perception limit: nothing moved and nothing
#:                      was measured wrongly.
#:   still + noise   -> the contribution of sigma_range alone.
#:   straight+quiet  -> viewpoint / ray-set sliding from translation.
#:   spin + quiet    -> the same from rotation, which sweeps the ray set
#:                      across every surface without changing range.
#:   both + quiet    -> their interaction, which is what driving is.
#:   both + noise    -> the whole thing, and the row Q0 measured.
MATRIX = (
    ("still", False),
    ("still", True),
    ("straight", False),
    ("spin", False),
    ("straight_spin", False),
    ("straight_spin", True),
)

#: Ego-motion programs, as (linear m/s, angular rad/s).
MOTIONS = {
    "still": (0.0, 0.0),
    "straight": (0.5, 0.0),
    "spin": (0.0, 0.6),
    "straight_spin": (0.5, 0.6),
}

#: Range noise used by the "noise on" rows — the value both shipped
#: warehouse profiles declare.
RANGE_SIGMA = 0.02

#: Thresholds the exceedance table reports, spanning the band the floor
#: lives in today (0.19 m/s at 360 rays to 0.71 m/s at 72, at 4-5 m).
EXCEEDANCE = (0.1, 0.2, 0.3, 0.4, 0.6, 0.8, 1.2)

PERCENTILES = (10, 25, 50, 75, 90, 99)


# -- synthetic geometry ------------------------------------------------


def _blank(width_m: float, height_m: float) -> list[int]:
    cols = int(round(width_m / CELL))
    rows = int(round(height_m / CELL))
    return [CellState.FREE.value] * (cols * rows), cols, rows


def _grid(name: str, width_m: float, height_m: float, fill) -> MapData:
    cells, cols, rows = _blank(width_m, height_m)
    for row in range(rows):
        for col in range(cols):
            x = (col + 0.5) * CELL
            y = (row + 0.5) * CELL
            if fill(x, y):
                cells[row * cols + col] = CellState.OCCUPIED.value
    return MapData(
        name=name,
        width=cols,
        height=rows,
        resolution=CELL,
        origin=Pose2D(x=0.0, y=0.0, theta=0.0),
        cells=tuple(cells),
    )


def _border(x: float, y: float, w: float, h: float) -> bool:
    return x < 0.2 or y < 0.2 or x > w - 0.2 or y > h - 0.2


def straight_wall() -> tuple[MapData, Pose2D, Pose2D]:
    """One long flat surface. The cleanest case for centroid sliding:
    a wall has no features, so any velocity read off it is invented."""
    w, h = 12.0, 8.0
    return (
        _grid("r1_straight_wall", w, h, lambda x, y: _border(x, y, w, h)),
        Pose2D(x=2.0, y=4.0, theta=0.0),
        Pose2D(x=2.0, y=7.0, theta=0.0),
    )


def corner() -> tuple[MapData, Pose2D]:
    """Shelf faces meeting at right angles — the warehouse's actual
    feature, and the case where a cluster's ends are genuine corners
    rather than artefacts of where the scan was cut."""
    w, h = 12.0, 8.0

    def fill(x: float, y: float) -> bool:
        if _border(x, y, w, h):
            return True
        if 4.0 <= x <= 8.0 and 5.0 <= y <= 5.4:
            return True
        return 7.6 <= x <= 8.0 and 2.0 <= y <= 5.4

    return (
        _grid("r1_corner", w, h, fill),
        Pose2D(x=2.0, y=3.0, theta=0.0),
        Pose2D(x=2.0, y=7.0, theta=0.0),
    )


def isolated_object() -> tuple[MapData, Pose2D]:
    """A single compact static block in the open. Separates *object
    shaped* clusters from *long surface* clusters: if phantoms cling to
    surfaces and spare this, the fault is in `_is_free_standing` rather
    than in the floor."""
    w, h = 12.0, 8.0

    def fill(x: float, y: float) -> bool:
        if _border(x, y, w, h):
            return True
        return math.hypot(x - 6.0, y - 4.0) <= 0.4

    return (
        _grid("r1_isolated_object", w, h, fill),
        Pose2D(x=2.0, y=4.0, theta=0.0),
        Pose2D(x=2.0, y=7.0, theta=0.0),
    )


def warehouse() -> tuple[MapData, Pose2D, Pose2D]:
    """The real map, so the synthetic rows can be checked against the
    geometry the measurement is actually about. Start and goal are the
    deployment's own mission, which is the one pair guaranteed to be free
    of obstacles on this map."""
    from planbench_benchmark.selection import load_profile, load_task_map

    profile = load_profile(REPO_ROOT / "profiles" / "warehouse_crossing_v1.yaml")
    mission = profile.missions[0]
    return load_task_map(profile, base_dir=REPO_ROOT), mission.start, mission.goal


GEOMETRIES = {
    "straight_wall": straight_wall,
    "corner": corner,
    "isolated_object": isolated_object,
    "warehouse": warehouse,
}


# -- instrumentation ---------------------------------------------------


@dataclass
class Recorder:
    """One run's per-(track, frame) records.

    Kept as raw rows rather than accumulated statistics: the whole point
    of R1 is that Q0's summaries hid the thing that mattered, and a
    summary chosen now would hide the next one.
    """

    rows: list[dict] = field(default_factory=list)
    frames: int = 0
    #: identity -> time first seen, so a track can report its age.
    born: dict[int, float] = field(default_factory=dict)
    pending: list[dict] = field(default_factory=list)
    #: R1b: when on, surviving phantoms carry the **actual scan points**
    #: of the cluster they were built from. Three summary numbers
    #: (width, straightness, count) were enough to prove the cluster is
    #: not a single flat surface and **not** enough to say what it is —
    #: two mechanisms were proposed from them and the data refuted both.
    #: The shape has to be looked at rather than inferred.
    dump: bool = False
    dumped: list[dict] = field(default_factory=list)
    #: centroid tuple -> the scan points that produced it, this frame.
    geometry: dict = field(default_factory=dict)


def _raw_fit(history: list[tuple[float, float, float]]) -> tuple[float, float]:
    """The least-squares velocity, computed exactly as the tracker does
    but **without** any of its gates. This is the number the floor is
    asked to judge, and Q0 could never see it."""
    if len(history) < 2:
        return 0.0, 0.0
    times = [sample[0] for sample in history]
    mean_t = sum(times) / len(times)
    spread = sum((t - mean_t) ** 2 for t in times)
    if spread <= EPS:
        return 0.0, 0.0
    vx = sum((s[0] - mean_t) * s[1] for s in history) / spread
    vy = sum((s[0] - mean_t) * s[2] for s in history) / spread
    return vx, vy


def _install(recorder: Recorder, engine: SimulationEngine, rays: int, sigma: float):
    """Wrap the tracker so every velocity decision leaves a record.

    Class-level and restored by the caller: ``reset`` builds a fresh
    tracker, so an instance wrapper is discarded before the first scan —
    a failure this project has already paid for once.
    """
    real_velocity = LidarTracker._velocity_of
    real_update = LidarTracker.update
    real_describe = LidarTracker._describe
    spacing = 2.0 * math.pi / rays

    def describe(self, points, run, rays_count, ranges, limit):
        cluster = real_describe(self, points, run, rays_count, ranges, limit)
        if recorder.dump:
            # `Cluster` keeps only summary numbers, so the points are
            # captured here — this is the one place they exist.
            recorder.geometry[(round(cluster.centroid.x, 6), round(cluster.centroid.y, 6))] = (
                [(round(x, 4), round(y, 4)) for x, y in points],
                [run[0], run[-1]],
            )
        return cluster

    def velocity_of(self, track, floor):
        raw_x, raw_y = _raw_fit(track.history)
        out, confidence = real_velocity(self, track, floor)
        state = engine.get_state()
        recorder.pending.append(
            {
                "identity": track.identity,
                "raw_speed": math.hypot(raw_x, raw_y),
                "raw_vx": raw_x,
                "raw_vy": raw_y,
                "floor": floor,
                "out_speed": math.hypot(out.x, out.y),
                "confidence": confidence,
                "misses": track.misses,
                "history": len(track.history),
                "history_points": (
                    [(round(s[0], 4), round(s[1], 4), round(s[2], 4)) for s in track.history]
                    if recorder.dump
                    else None
                ),
                "age_s": 0.0,
                "track_x": track.center.x,
                "track_y": track.center.y,
                "track_radius": track.radius,
                "robot_v": state.linear_velocity,
                "robot_omega": state.angular_velocity,
                "rays": rays,
                "delta_theta": spacing,
                "sigma_range": sigma,
            }
        )
        return out, confidence

    def update(self, observation):
        recorder.frames += 1
        recorder.pending = []
        clusters = self.cluster(observation)
        tracks = real_update(self, observation)
        here_x, here_y = observation.pose.x, observation.pose.y
        for row in recorder.pending:
            born = recorder.born.setdefault(row["identity"], observation.time)
            row["age_s"] = observation.time - born
            row["time"] = observation.time
            row["reach"] = math.hypot(row["track_x"] - here_x, row["track_y"] - here_y)
            # The cluster this track sits on, matched by centroid. When
            # the track was associated this frame its centre *is* that
            # centroid, so the join is exact; when it was not, the
            # nearest cluster is the honest best guess and `misses`
            # already says the estimate is not being trusted.
            best, best_distance = None, float("inf")
            for cluster in clusters:
                distance = math.hypot(
                    cluster.centroid.x - row["track_x"], cluster.centroid.y - row["track_y"]
                )
                if distance < best_distance:
                    best, best_distance = cluster, distance
            if best is not None:
                row["cluster_offset"] = best_distance
                row["cluster_points"] = best.points
                row["cluster_width"] = best.width
                row["cluster_straightness"] = best.straightness
                row["cluster_clipped"] = best.clipped
                if recorder.dump and row["out_speed"] > 1e-9:
                    key = (round(best.centroid.x, 6), round(best.centroid.y, 6))
                    scan, run = recorder.geometry.get(key, ([], [0, 0]))
                    recorder.dumped.append(
                        {
                            **row,
                            "scan_points": scan,
                            "ray_span": run,
                            "robot_pose": [
                                observation.pose.x,
                                observation.pose.y,
                                observation.pose.theta,
                            ],
                            "neighbours": [
                                {
                                    "cx": round(c.centroid.x, 3),
                                    "cy": round(c.centroid.y, 3),
                                    "width": round(c.width, 3),
                                    "points": c.points,
                                    "straightness": round(c.straightness, 3),
                                    "clipped": c.clipped,
                                }
                                for c in clusters
                                if 0.0
                                < math.hypot(
                                    c.centroid.x - best.centroid.x, c.centroid.y - best.centroid.y
                                )
                                < 2.5
                            ],
                        }
                    )
            recorder.rows.append(row)
        recorder.pending = []
        recorder.geometry = {}
        return tracks

    LidarTracker._velocity_of = velocity_of
    LidarTracker.update = update
    LidarTracker._describe = describe
    return real_velocity, real_update, real_describe


# -- one run -----------------------------------------------------------


def run(
    geometry: str,
    motion: str,
    noisy: bool,
    rays: int,
    seconds: float,
    seed: int,
    dump: bool = False,
) -> Recorder:
    map_data, start, goal = GEOMETRIES[geometry]()
    sigma = RANGE_SIGMA if noisy else 0.0
    linear, angular = MOTIONS[motion]

    scenario = Scenario(
        name=f"r1_{geometry}",
        robot=ROBOT,
        start_pose=start,
        # **The run must end when this script stops stepping, not when
        # the world decides the episode is over.** Three separate guards
        # would otherwise truncate it, and each would do so silently:
        # the goal (placed far from every scripted path), the stuck
        # window (five seconds, which the `still` row trips by design),
        # and the progress window. A truncated run is not a shorter
        # measurement — it is a measurement whose length depends on the
        # thing being measured.
        goal_pose=goal,
        goal_tolerance=0.05,
        timeout_seconds=seconds * 10.0,
        stuck_time_window=seconds * 10.0,
        progress_time_window=seconds * 10.0,
        simulation_dt=CONTROL_PERIOD,
        lidar=LidarConfig(num_rays=rays, max_range=5.0),
        sensor_noise=SensorNoise(lidar_range_sigma_m=sigma),
        random_seed=seed,
    )

    engine = SimulationEngine()
    engine.load_map(map_data)
    engine.load_scenario(scenario)
    engine.reset()

    recorder = Recorder(dump=dump)
    saved_velocity, saved_update, saved_describe = _install(recorder, engine, rays, sigma)
    tracker = LidarTracker(DWAPredictiveConfig(), None, scenario.sensor_noise)
    try:
        steps = int(round(seconds / scenario.simulation_dt))
        for _ in range(steps):
            tracker.update(engine.get_observation())
            try:
                engine.step(SimAction(linear_velocity=linear, angular_velocity=angular))
            except RuntimeError:
                # The engine stopped the episode (a wall, most likely).
                # Whatever was recorded up to here is still evidence.
                break
    finally:
        LidarTracker._velocity_of = saved_velocity
        LidarTracker.update = saved_update
        LidarTracker._describe = saved_describe
    return recorder


def _shape(points: list) -> dict:
    """Reduce a cluster's scan points to the few numbers that tell one
    shape from another: how far the worst point sits off the chord, and
    **where along the chord** it sits. A corner peaks in the middle; a
    curve peaks broadly; a straight run with one outlier peaks at an end.
    ``width`` and ``straightness`` alone cannot separate these, which is
    why two mechanisms were proposed from them and both were wrong."""
    if len(points) < 3:
        return {"chord": 0.0, "residual": 0.0, "peak_at": 0.0, "span_ratio": 0.0}
    (x0, y0), (x1, y1) = points[0], points[-1]
    chord = math.hypot(x1 - x0, y1 - y0)
    if chord <= EPS:
        return {"chord": 0.0, "residual": 0.0, "peak_at": 0.0, "span_ratio": 0.0}
    dx, dy = (x1 - x0) / chord, (y1 - y0) / chord
    best, best_at = 0.0, 0.0
    for index, (x, y) in enumerate(points):
        offset = abs((x - x0) * dy - (y - y0) * dx)
        if offset > best:
            best, best_at = offset, index / (len(points) - 1)
    # Path length along the points against the straight chord: 1.0 is a
    # straight run, well above 1.0 means the run doubles back.
    path = sum(
        math.hypot(points[i + 1][0] - points[i][0], points[i + 1][1] - points[i][1])
        for i in range(len(points) - 1)
    )
    return {
        "chord": chord,
        "residual": best,
        "peak_at": best_at,
        "span_ratio": path / chord,
    }


# -- reporting ---------------------------------------------------------


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round(fraction * (len(ordered) - 1))))
    return ordered[index]


def summarise(rows: list[dict]) -> dict:
    # Every velocity here is false by construction: the world is static.
    raw = [row["raw_speed"] for row in rows]
    surviving = [row for row in rows if row["out_speed"] > 1e-9]
    floors = [row["floor"] for row in rows]

    # **Why the gate breakdown is reported rather than just the survival
    # rate.** A record can be zeroed for three different reasons and they
    # call for opposite fixes: unobserved this frame (the track is
    # coasting and the contract says stay quiet), too little history
    # (warm-up, correct), or below the floor (the gate did its job). A
    # single "5% survived" hides which of the three is carrying the load,
    # and the redesign in R2 turns entirely on that.
    coasting = sum(1 for row in rows if row["misses"] > 0)
    warmup = sum(1 for row in rows if row["misses"] == 0 and row["history"] < 3)
    floored = sum(
        1 for row in rows if row["misses"] == 0 and row["history"] >= 3 and row["out_speed"] <= 1e-9
    )
    return {
        "records": len(rows),
        "reported": len(surviving),
        "reported_share": len(surviving) / max(len(rows), 1),
        "raw_percentiles": {p: _percentile(raw, p / 100.0) for p in PERCENTILES},
        "floor_median": _percentile(floors, 0.5),
        "exceedance": {t: sum(1 for v in raw if v > t) / max(len(raw), 1) for t in EXCEEDANCE},
        "robot_v_median": _percentile([row["robot_v"] for row in rows], 0.5),
        "zeroed_coasting": coasting / max(len(rows), 1),
        "zeroed_warmup": warmup / max(len(rows), 1),
        "zeroed_by_floor": floored / max(len(rows), 1),
        # Geometry of the clusters whose phantoms actually reached the
        # cost function. If these are wide and straight, the fault is a
        # surface being followed as an object and belongs to
        # `_is_free_standing`; if they are compact, the floor is the
        # thing that has to change.
        "survivor_speed_median": _percentile([r["out_speed"] for r in surviving], 0.5),
        "survivor_width_median": _percentile(
            [r.get("cluster_width", float("nan")) for r in surviving], 0.5
        ),
        "survivor_straightness_median": _percentile(
            [r.get("cluster_straightness", float("nan")) for r in surviving], 0.5
        ),
        "survivor_points_median": _percentile(
            [float(r.get("cluster_points", 0)) for r in surviving], 0.5
        ),
        "survivor_history_median": _percentile([float(r["history"]) for r in surviving], 0.5),
    }


def _dump(args) -> int:
    """R1b — look at the clusters instead of inferring from summaries."""
    resolutions = tuple(int(v) for v in args.rays.split(","))
    geometries = tuple(g.strip() for g in args.geometries.split(","))
    everything: list[dict] = []

    print("R1b — the actual shape of the clusters that produce surviving phantoms")
    print(f"controller {controller_version('dwa_predictive')}   seed {args.seed}")
    print(f"motion {args.motion}   noise {'on' if args.noise else 'off'}   static world")
    print()

    for geometry in geometries:
        for rays in resolutions:
            recorder = run(
                geometry, args.motion, args.noise, rays, args.seconds, args.seed, dump=True
            )
            worst = sorted(recorder.dumped, key=lambda r: -r["out_speed"])[: args.dump]
            print(f"=== {geometry}, {rays} rays — {len(recorder.dumped)} surviving phantoms ===")
            if not worst:
                print("  none\n")
                continue
            print(
                f"  {'speed':>7}{'reach':>7}{'pts':>5}{'chord':>7}{'resid':>7}"
                f"{'peak@':>7}{'path/chord':>11}{'rays':>10}{'nbrs':>6}"
            )
            for record in worst:
                shape = _shape(record["scan_points"])
                span = record["ray_span"]
                print(
                    f"  {record['out_speed']:7.3f}{record['reach']:7.2f}"
                    f"{len(record['scan_points']):5d}{shape['chord']:7.2f}"
                    f"{shape['residual']:7.3f}{shape['peak_at']:7.2f}"
                    f"{shape['span_ratio']:11.2f}"
                    f"{span[0]:>5}-{span[1]:<4}{len(record['neighbours']):6d}"
                )
                everything.append({"geometry": geometry, "rays": rays, "shape": shape, **record})
            print()

    print("how to read it:")
    print("  path/chord ~ 1.0 and small resid  -> one flat surface")
    print("  resid peaking near 0.5            -> a corner: two surfaces in one cluster")
    print("  path/chord >> 1.0                 -> the run doubles back on itself")
    print("  resid peaking near 0.0 or 1.0     -> a straight run with one stray end")

    out = args.out.with_name("dump.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(everything, indent=1), encoding="utf-8")
    print(f"\nfull point sets -> {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rays", type=str, default=",".join(map(str, DEFAULT_RESOLUTIONS)))
    parser.add_argument("--geometries", type=str, default=",".join(GEOMETRIES))
    parser.add_argument("--seconds", type=float, default=12.0)
    parser.add_argument("--seed", type=int, default=1000)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--dump",
        type=int,
        default=0,
        help="R1b: dump the N worst surviving phantoms with their real scan points",
    )
    parser.add_argument("--motion", type=str, default="straight", help="--dump only")
    parser.add_argument("--noise", action="store_true", help="--dump only")
    args = parser.parse_args(argv)

    if args.dump:
        return _dump(args)

    resolutions = tuple(int(v) for v in args.rays.split(","))
    geometries = tuple(g.strip() for g in args.geometries.split(","))

    print("R1 — where the phantom velocities come from")
    print(f"controller {controller_version('dwa_predictive')}   seed {args.seed}")
    print("every scene is STATIC: every velocity below is false by construction")
    print("no planner runs; ego-motion is scripted so each row isolates one source")
    print()

    results: list[dict] = []
    for geometry in geometries:
        print(f"=== {geometry} ===")
        header = f"{'motion':<14} {'noise':<6} {'rays':>5} {'recs':>6} {'reported':>9} "
        header += "".join(f"{'p' + str(p):>7}" for p in PERCENTILES) + f" {'floor':>7}"
        print(header)
        for motion, noisy in MATRIX:
            for rays in resolutions:
                recorder = run(geometry, motion, noisy, rays, args.seconds, args.seed)
                stats = summarise(recorder.rows)
                results.append(
                    {
                        "geometry": geometry,
                        "motion": motion,
                        "noise": noisy,
                        "rays": rays,
                        "frames": recorder.frames,
                        **stats,
                    }
                )
                line = f"{motion:<14} {'on' if noisy else 'off':<6} {rays:>5} "
                line += f"{stats['records']:>6} {100 * stats['reported_share']:8.2f}% "
                line += "".join(f"{stats['raw_percentiles'][p]:7.3f}" for p in PERCENTILES)
                line += f" {stats['floor_median']:7.3f}"
                print(line, flush=True)
        print()

    print("why each record was zeroed, and what the survivors look like")
    head = f"{'geometry':<18}{'motion':<14}{'noise':<6}{'rays':>5}"
    head += f"{'coast':>8}{'warmup':>8}{'floored':>8}{'kept':>8}"
    head += f"{'kept m/s':>10}{'width':>8}{'straight':>9}{'pts':>6}"
    print(head)
    for entry in results:
        if not entry["records"]:
            continue
        line = f"{entry['geometry']:<18}{entry['motion']:<14}"
        line += f"{'on' if entry['noise'] else 'off':<6}{entry['rays']:>5}"
        line += f"{100 * entry['zeroed_coasting']:7.1f}%{100 * entry['zeroed_warmup']:7.1f}%"
        line += f"{100 * entry['zeroed_by_floor']:7.1f}%{100 * entry['reported_share']:7.1f}%"
        line += f"{entry['survivor_speed_median']:10.3f}{entry['survivor_width_median']:8.2f}"
        line += f"{entry['survivor_straightness_median']:9.3f}"
        line += f"{entry['survivor_points_median']:6.0f}"
        print(line)

    print()
    print("exceedance of the RAW fit — the share a floor at each value would remove")
    print(
        f"{'geometry':<18}{'motion':<14}{'noise':<6}{'rays':>5} "
        + "".join(f"{t:>8}" for t in EXCEEDANCE)
    )
    for entry in results:
        if not entry["records"]:
            continue
        line = f"{entry['geometry']:<18}{entry['motion']:<14}"
        line += f"{'on' if entry['noise'] else 'off':<6}{entry['rays']:>5} "
        line += "".join(f"{100 * entry['exceedance'][t]:7.1f}%" for t in EXCEEDANCE)
        print(line)

    empty = [e for e in results if not e["records"]]
    if empty:
        print()
        print("rows with NO tracks at all — the tracker built nothing to be wrong about:")
        for entry in empty:
            print(
                f"  {entry['geometry']:<18}{entry['motion']:<14}"
                f"{'on' if entry['noise'] else 'off':<6}{entry['rays']:>5} rays"
            )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            {
                "controller_version": controller_version("dwa_predictive"),
                "seed": args.seed,
                "seconds": args.seconds,
                "matrix": [list(row) for row in MATRIX],
                "results": results,
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"\nsummaries -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
