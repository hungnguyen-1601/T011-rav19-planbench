"""Q0 — what angular resolution costs and buys the LiDAR tracker.

**Why this script exists, and why it is committed rather than pasted.**
The survey that produced the 2026-08-16 plan ran on **one seed** with
medians over two to seventeen frames. It found something worth acting on
— that detection improves up to ~144 rays and then *degrades* — but a
non-monotonicity read off one seed is a hypothesis, not a measurement.
`diagnose_tracker.py` was committed for exactly this reason once before:
*"an earlier version of these figures existed only as pasted output,
which is a result nobody else can re-run."* Same discipline here.

**The static column is not optional.** Measuring only a scene with
traffic makes every change that renders the tracker *more sensitive*
look like an improvement — including the changes that simply let noise
through. So each resolution is measured twice: once on the deployment as
declared, and once on the same deployment with the traffic removed,
where **every** reported velocity is by construction a phantom. A
configuration that reports more real velocities and more phantoms has
not been shown to be better.

**Seed discipline, declared here and printed at every run.** The
calibration set and the evaluation set are disjoint, and this script may
only touch the calibration one. Seeds ``{0..119}`` are burnt: the
one-seed survey ran on seed 0 and phases P4/P5 read that whole range
while designing against it. Recording that contamination in a report
does not turn a seed anybody has looked at back into held-out data, so
the gate in Q4 uses a third range that nothing has touched.

**This script does not measure latency.** It runs episodes in parallel
across processes, which is precisely what G4's measurement forbids — a
p99 read off a loaded box is not the p99 the gate means. Latency belongs
to Q5, on a pinned host, one episode at a time.

**A sweep is measured in instalments.** Four resolutions at twenty seeds
is over an hour of simulation, which is longer than a working machine is
usually free — so every episode is appended to a sidecar log the instant
it finishes, and ``--resume`` simulates only what is missing. Stop it
whenever; run it again with the same ``--out``; the table fills up. Rows
carry the controller checksum they were measured under and rows from
other versions are refused rather than merged, so re-running this after
changing the tracker starts a clean table instead of averaging two
controllers together.

Usage::

    # start, or carry on from whatever is already recorded
    python scripts/diagnose_resolution.py --resume

    # a first pass wide enough to see the shape, before committing an hour
    python scripts/diagnose_resolution.py --seeds 8 --resume

    # top the same table up to twenty seeds later; only the gap is run
    python scripts/diagnose_resolution.py --seeds 20 --resume

    python scripts/diagnose_resolution.py --rays 72,144 --workers 4 --resume
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

# **One BLAS thread per process, set before numpy is imported.** The
# rollout is numpy, and its threads are already using the cores this
# script wants for episodes: eight workers left in the default
# configuration ran roughly as slowly as one, each episode taking about
# eight times its solo wall clock while the box stayed busy. Threads
# fighting over the same cores is not parallelism. Measured, not
# assumed — an earlier run of this script is where the number came from.
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
    "packages/metrics",
    "packages/planning",
    "services/simulator",
    "ml",
):
    sys.path.insert(0, str(REPO_ROOT / _package))


from planbench_benchmark.candidates import (  # noqa: E402
    LOCAL_CONTROLLER_CONFIGS,
    controller_version,
)
from planbench_benchmark.contexts import build_evaluation_contexts  # noqa: E402
from planbench_benchmark.episode import scenario_for  # noqa: E402
from planbench_benchmark.registry import (  # noqa: E402
    build_global_planner,
    build_local_planner,
)
from planbench_benchmark.selection import load_profile, load_task_map  # noqa: E402
from planbench_planning.dwa_predictive.tracking import LidarTracker  # noqa: E402
from planbench_schemas.dynamic import position_at  # noqa: E402
from planbench_schemas.sensor import LidarConfig  # noqa: E402
from planbench_simulator.nav_stack import run_stack  # noqa: E402

#: The deployment measured. Constant-velocity crossing traffic — the
#: domain `dwa_predictive`'s model actually claims, which is where a
#: perception limit should be measured before anyone asks how it behaves
#: outside it.
PROFILE = REPO_ROOT / "profiles" / "warehouse_crossing_v1.yaml"

STACK = "astar+dwa_predictive"
CONTROLLER_CONFIG = "dwa_predictive_balanced"

#: Calibration seeds. **Every number this script prints comes from here**,
#: and every threshold Q2 calibrates is chosen from here.
CALIBRATION_FIRST_SEED = 1000

#: Written down so the split is auditable from the output rather than
#: from somebody's memory of a plan.
SEED_POLICY = {
    "calibration (this script, and every Q2 threshold)": "1000..1119",
    "evaluation (the Q4 gate; expansion 2000..2359)": "2000..2119",
    "burnt — never an evaluation set again": "0..119",
}

#: The rule for reading the table, fixed **before** the table exists.
#: Without it, "measured at Q0" degrades into picking by eye whichever
#: configuration produced the prettiest number.
OBJECTIVE = (
    "hard constraint : phantom_rate (static scene) <= the 72-ray baseline",
    "maximise        : velocity_report_rate (scene with traffic)",
    "tie-break       : the more conservative margin, then the simpler configuration",
)

DEFAULT_RESOLUTIONS = (72, 144, 271, 360)

#: Where episodes accumulate across runs. Under ``artifacts/``, which is
#: git-ignored and — unlike a session scratchpad — is still there
#: tomorrow. The default is not a convenience: a sweep is measured in
#: whatever quiet the machine has, so ``--resume`` has to find yesterday's
#: episodes without anybody having written the path down.
DEFAULT_OUT = REPO_ROOT / "artifacts" / "q0_resolution" / "sweep.json"

#: How close to the obstacle's true centre a cluster or track has to be
#: before it counts as *that* obstacle. Its radius plus a margin: wide
#: enough to survive centroid noise, tight enough that a wall fragment a
#: metre away is not credited as a detection.
MATCH_MARGIN_M = 0.35

#: A ray counts as hitting the obstacle when its endpoint lands inside
#: the obstacle's disc plus this. Covers grid rasterisation of the disc
#: in the simulator without swallowing the wall behind it.
RAY_HIT_MARGIN_M = 0.12

#: Seconds used to difference the obstacle's true position into a true
#: velocity, for the estimation-error column.
TRUTH_DT = 0.1


@dataclass
class Tally:
    """One episode's counters. Deliberately not metrics — see HĐ-5."""

    frames: int = 0
    in_range: int = 0
    scanned: int = 0
    hit_rays: int = 0
    clustered: int = 0
    passed: int = 0
    tracked: int = 0
    velocity_reported: int = 0
    velocity_errors: list[float] = field(default_factory=list)
    #: Static scene only: frames on which *any* track carried a velocity.
    phantom_frames: int = 0
    phantom_speeds: list[float] = field(default_factory=list)
    #: Static scene only, and the pair that keeps ``phantom_frames``
    #: honest. A finer scan produces many more tracks, so "a frame with
    #: at least one phantom" rises even if each track is exactly as
    #: trustworthy as before. ``phantom_tracks / tracks_seen`` is the
    #: per-track rate that separates *more tracks* from *worse tracks*;
    #: the frame rate is still the decision-relevant one, because one
    #: false mover is enough to change the command that gets chosen.
    tracks_seen: int = 0
    phantom_tracks: int = 0
    status: str = ""
    wall_seconds: float = 0.0

    def as_dict(self) -> dict:
        return {
            "frames": self.frames,
            "in_range": self.in_range,
            "scanned": self.scanned,
            "hit_rays": self.hit_rays,
            "clustered": self.clustered,
            "passed": self.passed,
            "tracked": self.tracked,
            "velocity_reported": self.velocity_reported,
            "velocity_errors": self.velocity_errors,
            "phantom_frames": self.phantom_frames,
            "phantom_speeds": self.phantom_speeds,
            "tracks_seen": self.tracks_seen,
            "phantom_tracks": self.phantom_tracks,
            "status": self.status,
            "wall_seconds": self.wall_seconds,
        }


_LOADED: dict = {}


def _deployment(static: bool):
    """Profile and map, loaded once per worker process.

    The static arm is *the same deployment with the traffic taken out* —
    same map, same missions, same robot, same noise — so the only thing
    separating the two columns is whether anything is moving. Building it
    from a different scene would compare two worlds and call the
    difference a phantom rate.
    """
    key = "static" if static else "traffic"
    if key not in _LOADED:
        profile = load_profile(PROFILE)
        if static:
            environment = profile.environment.model_copy(update={"dynamic_obstacles": ()})
            profile = profile.model_copy(update={"environment": environment})
        _LOADED[key] = (profile, load_task_map(profile, base_dir=REPO_ROOT))
    return _LOADED[key]


def _observer(tally: Tally, spec, seed: int, max_range: float):
    """Build the wrapper that counts what one episode's tracker saw.

    **Wrapped on the class, not on the instance**, and the reason is a
    property of the controller rather than a convenience:
    ``DWAPredictivePlanner.reset`` builds a *fresh* ``LidarTracker`` —
    deliberately, so that two episodes on one planner equal two planners
    — and ``run_stack`` calls ``reset`` after this function returns. An
    instance-level wrapper is therefore thrown away before the first
    scan, and the episode reports zero frames while completing normally,
    which is the quietest possible way for a diagnostic to lie. The
    caller restores the original method in a ``finally``.
    """
    inner = LidarTracker.update

    def observed(tracker, observation):
        tally.frames += 1
        truth = position_at(spec, observation.time, seed) if spec is not None else None
        px, py, theta = observation.pose.x, observation.pose.y, observation.pose.theta

        in_range = False
        if truth is not None:
            distance = math.hypot(truth.x - px, truth.y - py)
            in_range = distance <= max_range + spec.radius
            if in_range:
                tally.in_range += 1
                ranges = observation.lidar_ranges
                rays = len(ranges)
                spacing = 2.0 * math.pi / rays
                start = theta - math.pi
                limit = max(ranges)
                hits = 0
                for index, reading in enumerate(ranges):
                    if reading >= limit - 1e-9:
                        continue
                    ex = px + reading * math.cos(start + index * spacing)
                    ey = py + reading * math.sin(start + index * spacing)
                    if math.hypot(ex - truth.x, ey - truth.y) <= spec.radius + RAY_HIT_MARGIN_M:
                        hits += 1
                tally.hit_rays += hits
                if hits:
                    tally.scanned += 1
                reach = spec.radius + MATCH_MARGIN_M
                near = [
                    cluster
                    for cluster in tracker.cluster(observation)
                    if math.hypot(cluster.centroid.x - truth.x, cluster.centroid.y - truth.y)
                    < reach
                ]
                if near:
                    tally.clustered += 1
                    if any(tracker._is_free_standing(cluster) for cluster in near):
                        tally.passed += 1

        tracks = inner(tracker, observation)

        if truth is not None and in_range:
            reach = spec.radius + MATCH_MARGIN_M
            for track in tracks:
                if math.hypot(track.center.x - truth.x, track.center.y - truth.y) >= reach:
                    continue
                tally.tracked += 1
                speed = math.hypot(track.velocity.x, track.velocity.y)
                if speed > 1e-9:
                    tally.velocity_reported += 1
                    ahead = position_at(spec, observation.time + TRUTH_DT, seed)
                    tvx = (ahead.x - truth.x) / TRUTH_DT
                    tvy = (ahead.y - truth.y) / TRUTH_DT
                    tally.velocity_errors.append(
                        math.hypot(track.velocity.x - tvx, track.velocity.y - tvy)
                    )
                break

        if spec is None:
            # Static scene: nothing moves, so every reported velocity is
            # a phantom by construction. No matching needed and none
            # possible — there is no true object to match against.
            speeds = [
                math.hypot(track.velocity.x, track.velocity.y)
                for track in tracks
                if math.hypot(track.velocity.x, track.velocity.y) > 1e-9
            ]
            tally.tracks_seen += len(tracks)
            tally.phantom_tracks += len(speeds)
            if speeds:
                tally.phantom_frames += 1
                tally.phantom_speeds.append(max(speeds))

        return tracks

    return observed


def measure(rays: int, seed: int, static: bool) -> dict:
    """One episode at one resolution. Returns counters, never a verdict."""
    profile, map_data = _deployment(static)
    context = build_evaluation_contexts(profile, seed_count=1, first_seed=seed)[0]
    scenario = scenario_for(profile, context).model_copy(
        update={"lidar": LidarConfig(num_rays=rays, max_range=5.0)}
    )
    spec = scenario.dynamic_obstacles[0] if scenario.dynamic_obstacles else None

    global_planner = build_global_planner(STACK, episode_seed=context.seed)
    local_planner = build_local_planner(STACK, LOCAL_CONTROLLER_CONFIGS[CONTROLLER_CONFIG])

    tally = Tally()
    original = LidarTracker.update
    LidarTracker.update = _observer(tally, spec, context.seed, scenario.lidar.max_range)
    started = time.perf_counter()
    try:
        run = run_stack(
            map_data,
            scenario,
            local_planner,
            global_planner,
            profile.replanning,
            recovery=profile.recovery,
            legacy_metrics=False,
            obstacle_speed=profile.environment.v_obstacle_max,
        )
    finally:
        LidarTracker.update = original
    tally.wall_seconds = time.perf_counter() - started
    tally.status = run.result.status

    if tally.frames == 0:
        # The failure this script has already had once: the episode
        # completes, every counter reads zero, and the table says the
        # tracker saw nothing rather than that nobody was watching.
        raise RuntimeError(
            f"instrumentation never fired (rays={rays}, seed={seed}, static={static}) — "
            "the tracker's update was not routed through the observer"
        )
    return {
        "rays": rays,
        "seed": seed,
        "static": static,
        "controller_version": controller_version("dwa_predictive"),
        **tally.as_dict(),
    }


def _job(payload: tuple[int, int, bool]) -> dict:
    rays, seed, static = payload
    return measure(rays, seed, static)


def _median(values: list[float]) -> float:
    return statistics.median(values) if values else float("nan")


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round(fraction * (len(ordered) - 1))))
    return ordered[index]


def summarise(rows: list[dict], rays: int) -> dict:
    traffic = [row for row in rows if row["rays"] == rays and not row["static"]]
    static = [row for row in rows if row["rays"] == rays and row["static"]]

    in_range = sum(row["in_range"] for row in traffic)
    denominator = max(in_range, 1)
    errors = [value for row in traffic for value in row["velocity_errors"]]
    phantom_frames = sum(row["phantom_frames"] for row in static)
    static_frames = sum(row["frames"] for row in static)
    phantom_speeds = [value for row in static for value in row["phantom_speeds"]]

    return {
        "rays": rays,
        "degrees": 360.0 / rays,
        "episodes_traffic": len(traffic),
        "episodes_static": len(static),
        # **The real sample size of the traffic columns.** A seed whose
        # robot never comes within sensor range of the crosser
        # contributes nothing to either the numerator or the denominator
        # — correctly, but it also means "20 seeds" can be a handful of
        # actual encounters. Reported so nobody reads the seed count as
        # the sample.
        "episodes_with_encounter": sum(1 for row in traffic if row["in_range"] > 0),
        "in_range_frames": in_range,
        "scanned_frames": sum(row["scanned"] for row in traffic),
        "rays_per_frame": sum(row["hit_rays"] for row in traffic) / denominator,
        "clustered_rate": sum(row["clustered"] for row in traffic) / denominator,
        "passed_rate": sum(row["passed"] for row in traffic) / denominator,
        "velocity_report_rate": sum(row["velocity_reported"] for row in traffic) / denominator,
        "velocity_error_median": _median(errors),
        "velocity_error_n": len(errors),
        "phantom_rate": phantom_frames / max(static_frames, 1),
        "phantom_speed_p90": _percentile(phantom_speeds, 0.90),
        "tracks_per_frame": sum(row.get("tracks_seen", 0) for row in static)
        / max(static_frames, 1),
        "phantom_per_track": (
            sum(row.get("phantom_tracks", 0) for row in static)
            / max(sum(row.get("tracks_seen", 0) for row in static), 1)
        ),
        "statuses": dict(Counter(row["status"] for row in traffic)),
        "wall_seconds": sum(row["wall_seconds"] for row in rows if row["rays"] == rays),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=20, help="calibration seeds per resolution")
    parser.add_argument(
        "--rays",
        type=str,
        default=",".join(str(value) for value in DEFAULT_RESOLUTIONS),
        help="comma-separated ray counts",
    )
    parser.add_argument("--workers", type=int, default=0, help="0 = auto")
    parser.add_argument(
        "--arms",
        choices=("both", "traffic", "static"),
        default="both",
        help="which scene to simulate; 'static' alone re-measures the phantom columns",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"where rows accumulate (default: {DEFAULT_OUT.relative_to(REPO_ROOT)})",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="reuse episodes already recorded in the sidecar log beside --out",
    )
    args = parser.parse_args(argv)

    resolutions = tuple(int(value) for value in args.rays.split(","))
    seeds = tuple(CALIBRATION_FIRST_SEED + offset for offset in range(args.seeds))

    workers = args.workers or max(1, min(10, (os.cpu_count() or 4) - 2))

    print("Q0 — LiDAR angular resolution against the tracker")
    print(f"profile      {PROFILE.name}   candidate {STACK}:{CONTROLLER_CONFIG}")
    print()
    print("seed policy (calibration and evaluation are disjoint, and stay that way):")
    for label, value in SEED_POLICY.items():
        print(f"  {value:<12} {label}")
    print(f"  this run    seeds {seeds[0]}..{seeds[-1]} ({len(seeds)} per resolution)")
    print()
    print("objective for choosing a configuration, fixed before the table exists:")
    for line in OBJECTIVE:
        print(f"  {line}")
    print()
    print("NOT measured here: latency. Episodes run in parallel, so a p99 from")
    print("this run would be meaningless. G4 belongs to Q5, on a pinned host.")
    print()

    # **Every episode is written the moment it finishes.** A full sweep
    # is over an hour of simulation, and the first version of this script
    # held every row in memory until the end — so a machine somebody
    # needed back, or a stopped run, threw away the entire measurement.
    # The sidecar is append-only JSON Lines: interrupt it whenever, run
    # it again with --resume, and only the episodes nobody has measured
    # yet are simulated. That makes N >= 20 reachable in whatever length
    # of quiet the box actually has, instead of demanding one long block.
    log_path = args.out.with_suffix(".jsonl") if args.out else None
    if log_path is not None:
        # Before the first episode, not after the last: the sidecar is
        # opened for append while the sweep runs, and a run that dies on
        # a missing directory an hour in has thrown away the hour.
        log_path.parent.mkdir(parents=True, exist_ok=True)
    done_keys: set[tuple[int, int, bool]] = set()
    rows: list[dict] = []
    version = controller_version("dwa_predictive")
    if args.resume and log_path and log_path.is_file():
        stale = 0
        for line in log_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            # **Episodes measured by different code may not share a
            # table.** Q2 changes this tracker and then re-runs this
            # script; a resume that merged before-and-after rows would
            # produce one table describing two controllers, which is the
            # same defect as a run journal holding two worlds under one
            # id. Rows from other versions are ignored and counted, never
            # silently folded in.
            if row.get("controller_version") != version:
                stale += 1
                continue
            key = (row["rays"], row["seed"], row["static"])
            if key in done_keys:
                continue
            done_keys.add(key)
            rows.append(row)
        print(f"resumed {len(rows)} episodes recorded in {log_path.name} at {version}")
        if stale:
            print(
                f"  ignored {stale} episode(s) measured by different controller code — "
                "they will be re-simulated rather than mixed into this table"
            )

    arms = {"both": (False, True), "traffic": (False,), "static": (True,)}[args.arms]
    jobs = [
        (rays, seed, static)
        for rays in resolutions
        for seed in seeds
        for static in arms
        if (rays, seed, static) not in done_keys
    ]
    if not jobs:
        print("nothing left to simulate — every requested episode is already recorded")
    else:
        print(f"{len(jobs)} episodes on {workers} workers…", flush=True)

    started = time.perf_counter()
    if jobs:
        sink = log_path.open("a", encoding="utf-8") if log_path else None
        try:
            with ProcessPoolExecutor(max_workers=workers) as pool:
                # ``chunksize=1`` deliberately. The default batches jobs
                # per worker and hands back a chunk's results only once
                # the whole chunk is done, so ten workers on a chunk of
                # four can have thirty finished episodes that the sidecar
                # has never seen — and a stop loses every one of them.
                # The scheduling overhead is microseconds against
                # episodes measured in tens of seconds.
                for done, row in enumerate(pool.map(_job, jobs, chunksize=1), start=1):
                    rows.append(row)
                    if sink is not None:
                        sink.write(json.dumps(row) + "\n")
                        sink.flush()
                    if done % 10 == 0 or done == len(jobs):
                        print(f"  {done}/{len(jobs)}", flush=True)
        finally:
            if sink is not None:
                sink.close()
    elapsed = time.perf_counter() - started

    # Summaries are computed over whatever is on hand, resumed or fresh,
    # so a partial sweep still prints a table for the resolutions it
    # actually covered rather than nothing at all.
    resolutions = tuple(value for value in resolutions if any(r["rays"] == value for r in rows))

    summaries = [summarise(rows, rays) for rays in resolutions]

    have_traffic = any(row["episodes_traffic"] for row in summaries)
    have_static = any(row["episodes_static"] for row in summaries)

    if have_traffic:
        print()
        print("scene with traffic — measured against the obstacle's true position")
        print(" rays   deg  enc/eps  in_range  rays/f  clustered  passed  vel_out   err_med    n")
        for row in summaries:
            encounters = f"{row['episodes_with_encounter']}/{row['episodes_traffic']}"
            print(
                f"{row['rays']:>5} {row['degrees']:5.2f} {encounters:>8}"
                f" {row['in_range_frames']:>9}"
                f" {row['rays_per_frame']:7.2f} {100 * row['clustered_rate']:9.1f}%"
                f" {100 * row['passed_rate']:6.1f}% {100 * row['velocity_report_rate']:7.1f}%"
                f" {row['velocity_error_median']:9.3f} {row['velocity_error_n']:>4}"
            )
        print("  enc/eps = seeds where the crosser came within sensor range at all")

    if have_static:
        print()
        print("static scene — same deployment, traffic removed; every velocity is a phantom")
        print(" rays   phantom_rate   phantom_p90   tracks/f   per-track")
        for row in summaries:
            print(
                f"{row['rays']:>5} {100 * row['phantom_rate']:13.2f}%"
                f" {row['phantom_speed_p90']:13.3f}"
                f" {row['tracks_per_frame']:10.2f} {100 * row['phantom_per_track']:10.2f}%"
            )
        print("  phantom_rate = frames carrying at least one false mover (what reaches the cost)")
        print("  per-track    = share of individual tracks that are false movers")

    baseline = next((row for row in summaries if row["rays"] == 72), None)
    print()
    print("objective applied:")
    if baseline is None:
        print("  no 72-ray baseline in this run — hard constraint cannot be evaluated")
    else:
        eligible = [
            row for row in summaries if row["phantom_rate"] <= baseline["phantom_rate"] + 1e-12
        ]
        for row in summaries:
            verdict = "eligible" if row in eligible else "REJECTED by hard constraint"
            print(
                f"  {row['rays']:>4} rays  phantom {100 * row['phantom_rate']:6.2f}%"
                f"  vs baseline {100 * baseline['phantom_rate']:6.2f}%   {verdict}"
            )
        if not eligible:
            print("  -> no configuration satisfies the hard constraint")
        elif not have_traffic:
            # Half the objective needs the traffic arm, and this run did
            # not simulate it. Printing "best at 0.0%" would announce a
            # verdict derived from a column nobody measured — the same
            # class of quiet lie as a diagnostic that reports zero
            # because nothing was watching.
            print(
                f"  -> {len(eligible)} configuration(s) pass the hard constraint; the"
                " maximisation step needs the traffic arm, which this run did not simulate"
            )
        else:
            best = max(eligible, key=lambda row: row["velocity_report_rate"])
            print(
                f"  -> maximum velocity_report_rate among eligible: {best['rays']} rays"
                f" at {100 * best['velocity_report_rate']:.1f}%"
            )

    print()
    print(f"wall clock {elapsed / 60:.1f} min across {workers} workers")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(
                {
                    "profile": PROFILE.name,
                    "stack": STACK,
                    "controller_config": CONTROLLER_CONFIG,
                    "seed_policy": SEED_POLICY,
                    "seeds": list(seeds),
                    "objective": list(OBJECTIVE),
                    "summaries": summaries,
                    "rows": rows,
                },
                indent=1,
            ),
            encoding="utf-8",
        )
        print(f"raw rows -> {args.out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
