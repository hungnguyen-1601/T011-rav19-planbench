"""P5 — what the tracker costs against the oracle that cannot be wrong.

Three arms on identical seeds: ``dwa`` (no prediction), the P4 oracle
(prediction with **zero** estimation error), and ``dwa_predictive`` with
the real LiDAR tracker. The oracle is the ceiling; the gap between it and
the tracker is the price of having to estimate, which is the number this
phase exists to produce.

Committed rather than left in a report so the comparison is reproducible
— an earlier version of these figures existed only as pasted output,
which is a result nobody else can re-run.

**Read the discordant counts, not the rates.** The oracle changes the
outcome on a small minority of seeds; on the rest all three arms drive
identically. A rate difference over the whole set dilutes those few
seeds into noise, which is exactly the mistake decision gate 2 made the
first time.

Usage::

    python scripts/diagnose_tracker.py --seeds 120
"""

from __future__ import annotations

import argparse
import math

from planbench_benchmark.candidates import LOCAL_CONTROLLER_CONFIGS
from planbench_benchmark.registry import build_global_planner, build_local_planner
from planbench_benchmark.scenarios import build_scenario
from planbench_planning.dwa_predictive import DWAPredictiveConfig, DWAPredictivePlanner
from planbench_planning.dwa_predictive.oracle import build_oracle
from planbench_schemas.dynamic import position_at
from planbench_simulator.nav_stack import run_stack

#: The gate scene of P4: near-constant motion, non-zero baseline success.
SCENE = "intersection"

#: Matches decision gate 2 so the two are directly comparable.
DEFAULT_SEEDS = 120

#: Worst to best. Ties inside a rank are concordant — the robot failed to
#: arrive either way, and preferring one failure over another would be
#: inventing a judgement.
OUTCOME_RANK = {
    "collision": 0,
    "timeout": 1,
    "stuck": 1,
    "no_progress": 1,
    "stopped": 1,
    "no_global_path": 1,
    "success": 2,
}


def _run(seed: int, arm: str) -> tuple[str, dict[str, int]]:
    map_data, scenario = build_scenario(SCENE)
    scenario = scenario.model_copy(update={"random_seed": seed})
    shared = LOCAL_CONTROLLER_CONFIGS["dwa_balanced"]
    if arm == "dwa":
        planner = build_local_planner("astar+dwa", shared)
    elif arm == "oracle":
        planner = build_oracle(scenario, DWAPredictiveConfig(**shared))
    else:
        planner = DWAPredictivePlanner(DWAPredictiveConfig(**shared))
    run = run_stack(
        map_data,
        scenario,
        planner,
        build_global_planner("astar+dwa", episode_seed=seed),
    )
    counters = planner.diagnostics if hasattr(planner, "diagnostics") else {}
    return run.result.status.value, counters


def _perception_report(seed: int) -> None:
    """How often the tracker even has an opinion about the real obstacle.

    The aggregate above says whether the tracker helped; this says why.
    Reads what each control step actually believed rather than asking the
    tracker again, which would consume the frame twice.
    """
    map_data, scenario = build_scenario(SCENE)
    scenario = scenario.model_copy(update={"random_seed": seed})
    obstacle = scenario.dynamic_obstacles[0]
    seen: list[tuple[float, float, float]] = []

    class Spy(DWAPredictivePlanner):
        def compute(self, state, observation):  # noqa: ANN001
            result = super().compute(state, observation)
            truth = position_at(obstacle, observation.time, scenario.random_seed)
            earlier = position_at(obstacle, max(observation.time - 0.05, 0.0), scenario.random_seed)
            true_speed = math.hypot(truth.x - earlier.x, truth.y - earlier.y) / 0.05
            reach = math.hypot(truth.x - observation.pose.x, truth.y - observation.pose.y)
            on_target = [
                math.hypot(track.velocity.x, track.velocity.y)
                for track in self.last_tracks
                if math.hypot(track.center.x - truth.x, track.center.y - truth.y) < 0.8
            ]
            seen.append((reach, true_speed, max(on_target, default=-1.0)))
            return result

    shared = LOCAL_CONTROLLER_CONFIGS["dwa_balanced"]
    run_stack(
        map_data,
        scenario,
        Spy(DWAPredictiveConfig(**shared)),
        build_global_planner("astar+dwa", episode_seed=seed),
    )
    in_range = [row for row in seen if row[0] < 6.0]
    tracked = [row for row in in_range if row[2] >= 0.0]
    speaking = [row for row in tracked if row[2] > 1e-9]
    print(f"\n--- perception on seed {seed} ---")
    print(f"  steps with the obstacle in LiDAR range : {len(in_range)}")
    print(f"  ...with a track on it                  : {len(tracked)}")
    print(f"  ...reporting a non-zero velocity       : {len(speaking)}")
    if speaking:
        errors = sorted(abs(row[2] - row[1]) for row in speaking)
        print(f"  median |estimate - truth| when speaking: {errors[len(errors) // 2]:.3f} m/s")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=DEFAULT_SEEDS)
    parser.add_argument("--perception-seed", type=int, default=0)
    arguments = parser.parse_args()
    seeds = arguments.seeds

    results = {arm: [] for arm in ("dwa", "oracle", "tracker")}
    counters: dict[str, int] = {}
    for seed in range(seeds):
        for arm in results:
            status, found = _run(seed, arm)
            results[arm].append(status)
            if arm == "tracker":
                for key, value in found.items():
                    counters[key] = counters.get(key, 0) + value

    print(f"=== {SCENE}, {seeds} paired seeds ===")
    for arm, statuses in results.items():
        collisions = sum(1 for s in statuses if s == "collision")
        successes = sum(1 for s in statuses if s == "success")
        print(f"  {arm:<9} collisions {collisions:>4}/{seeds}   successes {successes:>4}/{seeds}")

    print("\n=== discordant pairs against dwa ===")
    for arm in ("oracle", "tracker"):
        better = sum(
            1
            for a, b in zip(results["dwa"], results[arm], strict=True)
            if OUTCOME_RANK[b] > OUTCOME_RANK[a]
        )
        worse = sum(
            1
            for a, b in zip(results["dwa"], results[arm], strict=True)
            if OUTCOME_RANK[b] < OUTCOME_RANK[a]
        )
        print(f"  {arm:<9} better {better:>3}   worse {worse:>3}")

    opportunities = sum(
        1
        for a, b in zip(results["dwa"], results["oracle"], strict=True)
        if OUTCOME_RANK[b] > OUTCOME_RANK[a]
    )
    recovered = sum(
        1
        for a, o, t in zip(results["dwa"], results["oracle"], results["tracker"], strict=True)
        if OUTCOME_RANK[o] > OUTCOME_RANK[a] and OUTCOME_RANK[t] > OUTCOME_RANK[a]
    )
    print(f"\n  seeds where prediction could help (oracle beat dwa) : {opportunities}")
    print(f"  ...of which the tracker also took                   : {recovered}")
    print("  ** the price of perception is the gap between those two **")
    if opportunities < 10:
        print(
            f"  NOTE: {opportunities} opportunities is a thin basis for any rate. "
            "Read this as a count, not a percentage."
        )

    print("\n=== tracker counters, summed over every episode ===")
    for key in sorted(counters):
        print(f"  {key:<18} {counters[key]}")

    _perception_report(arguments.perception_seed)


if __name__ == "__main__":
    main()
