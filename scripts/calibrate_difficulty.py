#!/usr/bin/env python3
"""Measure scenario difficulty against a pinned baseline (P03).

    difficulty(scenario) = 1 - success_rate(baseline, fixed seeds)

Dry run (a few seeds, prints, writes nothing):

    python scripts/calibrate_difficulty.py --dry-run

Real calibration (30 fixed seeds over the whole library, writes the cache):

    python scripts/calibrate_difficulty.py --calibration-version 1.0.0 --write

The output is
``packages/benchmark/planbench_benchmark/difficulty_calibration.json``
and it is meant to be reproducible: same code, same baseline, same seeds
gives byte-identical content. Nothing here is time-stamped for that
reason — the commit identifies the code, and a timestamp would only make
two identical calibrations look different.

Editing the cache by hand defeats the entire measurement. Re-run this.
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for relative in (
    "packages/schemas",
    "packages/planning",
    "packages/metrics",
    "packages/benchmark",
    "services/simulator",
    "services/tracking",
):
    sys.path.insert(0, str(REPO_ROOT / relative))

from planbench_benchmark.difficulty import (  # noqa: E402
    CALIBRATION_FILE,
    DEFAULT_CALIBRATION_SEEDS,
    MIDRANGE_DIFFICULTY,
    MIN_CALIBRATION_SEEDS,
    MIN_MIDRANGE_SCENARIOS,
    BaselineSpec,
    DifficultyCalibration,
    ScenarioCalibration,
    difficulty_band,
)
from planbench_benchmark.runner import run_benchmark  # noqa: E402
from planbench_benchmark.scenario_protocol import (  # noqa: E402
    protocol_version,
    scenario_protocol_metadata,
)
from planbench_benchmark.scenarios import CURRICULUM_ORDER, build_scenario  # noqa: E402
from planbench_benchmark.spec import (  # noqa: E402
    BENCHMARK_SPEC_VERSION,
    AlgorithmSpec,
    BenchmarkSpec,
)
from planbench_metrics.statistics import proportion_ci  # noqa: E402
from planbench_schemas.episode import EpisodeStatus  # noqa: E402

logger = logging.getLogger("planbench.calibrate")

#: The reference stack the difficulty scale is defined against. A*+DWA is
#: deterministic given the scenario seed, which is what makes the scale
#: reproducible; a sampling planner would put its own variance into every
#: scenario's number.
DEFAULT_BASELINE = "astar+dwa"


def git_sha() -> str:
    """Commit the calibration is running at, or ``"unknown"``.

    Never guesses. A calibration run from a tarball is still a valid
    measurement; it just cannot claim to be reproducible from a commit,
    and saying ``unknown`` is how it admits that.
    """
    try:
        result = subprocess.run(  # noqa: S603 - fixed argv, no shell
            ["git", "rev-parse", "HEAD"],  # noqa: S607
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    sha = result.stdout.strip()
    return sha if result.returncode == 0 and sha else "unknown"


def calibrate_scenario(
    scenario_name: str,
    *,
    algorithm: str,
    algorithm_config: dict,
    seeds: tuple[int, ...],
) -> tuple[ScenarioCalibration, dict]:
    """Run the baseline over one scenario and turn it into a difficulty.

    Returns the cache entry plus a small dict of run facts for printing
    (wall-clock seconds, the robot profile the scenario actually used).

    The run goes through :func:`run_benchmark` rather than a private loop
    on purpose: difficulty has to be measured by the same machinery that
    produces benchmark results, or the scale would describe a code path
    nobody is scored on.
    """
    map_data, scenario = build_scenario(scenario_name)
    spec = BenchmarkSpec(
        name=f"difficulty-calibration:{scenario_name}",
        description="Difficulty calibration run (P03); not a leaderboard benchmark.",
        algorithms=(AlgorithmSpec(id=algorithm, config=algorithm_config),),
        seeds=seeds,
    )
    started = time.monotonic()
    report = run_benchmark(map_data, scenario, spec)
    elapsed = time.monotonic() - started

    aggregate = report.aggregates[0]
    successes = sum(1 for run in report.runs if run.status is EpisodeStatus.SUCCESS)
    episodes = aggregate.episodes
    success_low, success_high = proportion_ci(successes, episodes)
    status_counts: dict[str, int] = {}
    for run in report.runs:
        status_counts[run.status.value] = status_counts.get(run.status.value, 0) + 1

    entry = ScenarioCalibration(
        difficulty=1.0 - aggregate.success_rate,
        # Mirrored, not recomputed: the difficulty interval is the success
        # interval reflected, so the bounds stay exact and stay consistent
        # with the success rate shown next to them.
        ci95=(1.0 - success_high, 1.0 - success_low),
        success_rate=aggregate.success_rate,
        episodes=episodes,
        status_counts=dict(sorted(status_counts.items())),
        map_checksum=report.fairness.map_checksum,
        scenario_checksum=report.fairness.scenario_checksum,
        scenario_split=report.scenario_split,
    )
    facts = {
        "seconds": elapsed,
        "robot_profile": scenario.robot.model_dump(mode="json"),
    }
    return entry, facts


def build_calibration(
    scenario_names: tuple[str, ...],
    *,
    algorithm: str,
    algorithm_config: dict,
    seeds: tuple[int, ...],
    version: str,
    notes: str | None,
    on_scenario=None,
) -> DifficultyCalibration:
    """Calibrate every scenario and assemble the cache.

    Every scenario must use the same robot. Difficulties measured on
    robots of different size are not points on one scale, and a cache that
    mixed them would rank scenarios by how big the robot was.
    """
    entries: dict[str, ScenarioCalibration] = {}
    robot_profile: dict | None = None
    for name in scenario_names:
        entry, facts = calibrate_scenario(
            name, algorithm=algorithm, algorithm_config=algorithm_config, seeds=seeds
        )
        if robot_profile is None:
            robot_profile = facts["robot_profile"]
        elif facts["robot_profile"] != robot_profile:
            raise ValueError(
                f"{name!r} uses a different robot from the earlier scenarios; one "
                "calibration cache describes one robot, so calibrate them separately"
            )
        entries[name] = entry
        if on_scenario is not None:
            on_scenario(name, entry, facts)

    assert robot_profile is not None  # noqa: S101 - scenario_names is non-empty
    baseline = BaselineSpec(
        algorithm=algorithm,
        algorithm_config=algorithm_config,
        replanning_enabled=False,
        seeds=seeds,
        robot_profile=robot_profile,
        benchmark_spec_version=BENCHMARK_SPEC_VERSION,
        protocol_version=protocol_version(),
        git_sha=git_sha(),
    )
    return DifficultyCalibration(
        calibration_version=version,
        baseline=baseline,
        scenarios=dict(sorted(entries.items())),
        notes=notes,
    )


def serialise(calibration: DifficultyCalibration) -> str:
    """Cache JSON: sorted keys, stable indent, trailing newline."""
    payload = calibration.model_dump(mode="json")
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _print_table(calibration: DifficultyCalibration, timings: dict[str, float]) -> None:
    print()
    print(f"{'scenario':<24} {'split':<11} {'difficulty':>10} {'ci95':>16} {'band':<9} {'sec':>7}")
    print("-" * 82)
    for name, entry in calibration.scenarios.items():
        low, high = entry.ci95
        print(
            f"{name:<24} {entry.scenario_split:<11} {entry.difficulty:>10.3f} "
            f"{f'({low:.2f}, {high:.2f})':>16} {difficulty_band(entry.difficulty):<9} "
            f"{timings.get(name, 0.0):>7.1f}"
        )


def _print_coverage(calibration: DifficultyCalibration) -> None:
    """Range report: does this set of scenarios span a useful range?

    Computed from the calibration in hand rather than from the installed
    cache, so a dry run reports on what it just measured.
    """
    values = [entry.difficulty for entry in calibration.scenarios.values()]
    if not values:
        return
    low, high = min(values), max(values)
    bands: dict[str, int] = {}
    for value in values:
        band = difficulty_band(value)
        bands[band] = bands.get(band, 0) + 1
    midrange_low, midrange_high = MIDRANGE_DIFFICULTY
    midrange = sum(1 for value in values if midrange_low < value < midrange_high)
    print()
    print(f"difficulty range: {low:.3f} .. {high:.3f}  (spread {high - low:.3f})")
    print("bands: " + ", ".join(f"{band}={count}" for band, count in sorted(bands.items())))
    print(f"scenarios between {midrange_low:.1f} and {midrange_high:.1f}: {midrange}")
    if midrange < MIN_MIDRANGE_SCENARIOS:
        print(
            "WARNING: almost nothing sits in the middle of the scale. The set spans "
            "the range and still separates nothing: outside the middle the baseline "
            "either always succeeds or always fails. Author scenarios there."
        )
    if high - low < 0.3:
        print(
            "WARNING: the range is too narrow to separate stacks. Author scenarios "
            "to fill the gap; do not edit the cache."
        )
    if bands.get("unsolved"):
        print(
            f"WARNING: {bands['unsolved']} scenario(s) the baseline never solved; their "
            "difficulty is pinned at 1.0 and cannot be ordered against each other."
        )
    if len(calibration.baseline.seeds) < MIN_CALIBRATION_SEEDS:
        print(
            f"WARNING: {len(calibration.baseline.seeds)} seed(s) is below "
            f"{MIN_CALIBRATION_SEEDS}; these numbers are provisional."
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Calibrate scenario difficulty (P03)")
    parser.add_argument(
        "--scenarios",
        default="",
        help="Comma-separated scenario names. Default: the whole built-in library.",
    )
    parser.add_argument("--algorithm", default=DEFAULT_BASELINE, help="Baseline stack id.")
    parser.add_argument(
        "--algorithm-config",
        default="",
        help="JSON object of local-planner overrides for the baseline.",
    )
    parser.add_argument(
        "--seeds",
        default="",
        help=(
            "Comma-separated seed list. Default: 0..29, the fixed calibration set. "
            "A different list is a different measurement."
        ),
    )
    parser.add_argument("--calibration-version", default="1.0.0")
    parser.add_argument("--notes", default="")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Few seeds, no write. Checks the pipeline, not the difficulty.",
    )
    parser.add_argument(
        "--dry-run-seeds", type=int, default=3, help="How many seeds a dry run uses."
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write the cache. Without it the JSON is printed and nothing is touched.",
    )
    parser.add_argument("--output", default=str(CALIBRATION_FILE))
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.WARNING, format="%(message)s")

    names = tuple(part.strip() for part in args.scenarios.split(",") if part.strip())
    scenario_names = names or CURRICULUM_ORDER
    unknown = [name for name in scenario_names if name not in CURRICULUM_ORDER]
    if unknown:
        parser.error(f"unknown scenario(s): {', '.join(unknown)}")

    if args.seeds:
        seeds = tuple(int(part) for part in args.seeds.split(",") if part.strip())
    elif args.dry_run:
        seeds = tuple(range(args.dry_run_seeds))
    else:
        seeds = DEFAULT_CALIBRATION_SEEDS
    if not seeds:
        parser.error("no seeds")

    try:
        algorithm_config = json.loads(args.algorithm_config) if args.algorithm_config else {}
    except json.JSONDecodeError as exc:
        parser.error(f"--algorithm-config is not valid JSON: {exc}")

    version = args.calibration_version
    if args.dry_run:
        # A dry run must never be mistaken for the real scale, including
        # when someone copies its output into the cache by hand.
        version = f"{version}-dryrun"

    print(
        f"baseline {args.algorithm}  seeds {len(seeds)}  scenarios {len(scenario_names)}  "
        f"git {git_sha()[:12]}"
    )
    if args.dry_run:
        print("DRY RUN: too few seeds to calibrate anything; checking the pipeline only.")

    timings: dict[str, float] = {}

    def progress(name, entry, facts) -> None:
        timings[name] = facts["seconds"]
        print(
            f"  {name:<24} difficulty={entry.difficulty:.3f} "
            f"success={entry.success_rate:.3f} ({facts['seconds']:.1f}s)"
        )

    calibration = build_calibration(
        scenario_names,
        algorithm=args.algorithm,
        algorithm_config=algorithm_config,
        seeds=seeds,
        version=version,
        notes=args.notes or None,
        on_scenario=progress,
    )

    _print_table(calibration, timings)
    _print_coverage(calibration)

    if args.dry_run or not args.write:
        if not args.dry_run:
            print("\n(not written; pass --write to install the cache)")
        return 0

    output = Path(args.output)
    output.write_text(serialise(calibration), encoding="utf-8")
    print(f"\nwrote {output}")
    for name in scenario_names:
        split = scenario_protocol_metadata(name).split
        if split == "holdout":
            print(f"note: {name} is a held-out scenario; this calibration run counts as a look.")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
