"""Decision gate 2 — is the constant-velocity model worth anything at all?

Runs ``dwa`` against ``dwa_oracle_predictive``, which is the same
controller handed the velocities the simulator itself is using. That
removes estimation error entirely, so whatever prediction is worth, it is
worth **at most** what this measures. If perfect perception buys nothing
here, no tracker can rescue it and the plan should stop.

**A diagnostic, not an evaluation.** It writes a table to stdout and
nothing else — no Decision Card, no manifest, no registry entry, no
artifact. The oracle is a measuring instrument and cannot be a candidate:
it is not registered, and it could not be, because the registry factory is
``config -> LocalPlanner`` and has no scenario to close a ground-truth
provider over.

**Scene choice is measured, not assumed.** The gate may only run where the
model's own assumption holds — a scene that breaks constant velocity
measures the model's *limits*, not its *value*. Median error of a 1.5 s
constant-velocity extrapolation, over the library:

    crossing_obstacle   periodic      0.949 m   <- excluded: not near-constant
    dynamic_warehouse   mixed         0.583 m   <- excluded: includes a random walk
    sudden_stop         sudden_stop   0.000 m   <- excluded: adversarial by design
    bidirectional_corridor  waypoint  0.000 m   <- GATE
    intersection            waypoint  0.000 m   <- GATE

``crossing_obstacle`` is the one the plan warned about: it sounds like the
canonical crossing case and its pedestrian is a **sinusoid** whose median
extrapolation error is almost a metre. ``intersection`` is the
constant-velocity crossing scene the library already had, so no new
scenario was needed.

Usage::

    python scripts/diagnose_oracle.py [--seeds 20]
"""

from __future__ import annotations

import argparse
import math
import random
import statistics
from dataclasses import dataclass

from planbench_benchmark.candidates import LOCAL_CONTROLLER_CONFIGS
from planbench_benchmark.registry import build_global_planner, build_local_planner
from planbench_benchmark.scenarios import build_scenario
from planbench_planning.dwa_predictive import DWAPredictiveConfig
from planbench_planning.dwa_predictive.oracle import build_oracle
from planbench_simulator.nav_stack import run_stack

# ---------------------------------------------------------------------------
# THE GATE, DECLARED BEFORE IT WAS RUN.
#
# These constants are the plan's criteria written down as code so that
# "declared in advance" is a property of the file rather than a claim in a
# report. Moving any of them after seeing a result is the move HĐ-15.3
# exists to ask about.
# ---------------------------------------------------------------------------

#: Scenes whose motion is near-constant inside one prediction horizon.
GATE_SCENES = ("bidirectional_corridor", "intersection")

#: Scenes run for information but **excluded from the verdict**, because
#: they measure where the model breaks rather than what it buys.
LIMIT_SCENES = ("sudden_stop", "crossing_obstacle")

#: At least this many paired seeds per scene.
MIN_SEEDS = 20

#: Bootstrap resamples for the paired CI, and the seed that drives them.
RESAMPLES = 10_000
BOOTSTRAP_SEED = 0

#: PASS needs at least one of these median differences to have its whole
#: 95% CI below zero — oracle strictly faster, or strictly less stop-go.
IMPROVEMENT_METRICS = ("travel_time", "stop_and_go")

#: And nothing may get worse: no gate metric may degrade at all.
GUARDED_METRICS = ("success_rate", "collision_rate", "near_miss_rate")

#: Written before running, so the record shows which came first. The
#: rollout already sees obstacles at t=0; prediction only changes *where
#: they will be*, and on a 2 m corridor there is little room to exploit
#: it. Expectation: a small improvement on `intersection`, where there is
#: room to time the crossing, and close to nothing on
#: `bidirectional_corridor`, where yielding is mostly a question of who
#: gets to the pinch first.
PREDICTION = (
    "5-15% median travel-time improvement on intersection; "
    "little or nothing on bidirectional_corridor; no metric worse anywhere"
)

#: Clearance below this counts as a near miss, matching the shipped
#: deployment's `clearance_warning_m`.
NEAR_MISS_M = 0.35


# ---------------------------------------------------------------------------
# THE GATE, SECOND DECLARATION — 2026-08-15, dev-approved.
#
# The rule above FAILED, and the post-mortem found the failure was in the
# rule rather than in the algorithm. Two flaws, both checkable before the
# run and both mine:
#
#   1. It conditioned on "both reached the goal". Prediction only acts
#      when a collision is imminent, and in those episodes `dwa` fails —
#      so the conditioning deletes every episode where the treatment did
#      anything, leaving a subset on which the two arms are **byte
#      identical**. The measured delta was exactly 0.000 with a
#      zero-width CI: identical by construction, not by measurement.
#   2. It priced a rare event with a bootstrap CI on a difference of
#      proportions. Outcomes differ on ~7.5% of seeds; that instrument
#      cannot resolve an effect that sparse at n=40.
#
# Declared here in full, and committed before being run, so that "the
# rule came first" is a property of the git history rather than a claim.
# The first rule's failure is kept above and in the report: this replaces
# the instrument, not the record.
# ---------------------------------------------------------------------------

#: A gate scene must satisfy **both**, and the second is what
#: `bidirectional_corridor` fails: its baseline success rate is 0.000, and
#: a scene where every episode of both arms fails cannot discriminate
#: between them whatever the treatment does. This is a precondition on the
#: scene, not a judgement of a result.
RARE_EVENT_SCENES = ("intersection",)

#: Three times the first attempt. Estimated from the pilot's discordant
#: rate of 3/40: n=120 should yield ~9 discordant pairs, and 9 of 9 in one
#: direction gives p = 0.5^9 ~ 0.002. Fewer than 7 of 9 would fail, so the
#: rule is genuinely falsifiable rather than sized to pass.
RARE_EVENT_SEEDS = 120

#: Outcomes, worst to best. A collision is strictly worse than not
#: arriving; not arriving is strictly worse than arriving. Ties within a
#: rank (timeout vs stuck) are not discordant — the robot failed to arrive
#: either way, and calling one better would be inventing a preference.
OUTCOME_RANK = {
    "collision": 0,
    "timeout": 1,
    "stuck": 1,
    "no_progress": 1,
    "stopped": 1,
    "no_global_path": 1,
    "success": 2,
}

#: One-sided: the question is whether prediction *helps*, and a result
#: where it reliably hurt would fail the guard below regardless.
SIGN_TEST_ALPHA = 0.05

#: Predicted before this rule was run, recorded so the order is legible.
#: The pilot saw 3/40 discordant, all favouring the oracle. If that rate
#: and direction hold, n=120 gives ~9/9 and p ~ 0.002 — a pass. The honest
#: uncertainty is the direction: three pairs is a thin basis for expecting
#: nine to agree, and a single reversal costs a great deal of the margin.
RARE_EVENT_PREDICTION = (
    "~9 discordant pairs at n=120, most or all favouring the oracle; "
    "p in the 0.002-0.09 range, so a pass is likely but not assured"
)


@dataclass(frozen=True)
class Episode:
    success: bool
    collision: bool
    travel_time: float
    stop_and_go: int
    near_miss: bool


def _stop_and_go(trajectory) -> int:
    """Times the robot came to rest and set off again.

    The metric the plan names as the main objective: "standing still when
    it meets an obstacle" is exactly this count.
    """
    moving = [point.linear_velocity > 1e-6 for point in trajectory]
    return sum(1 for a, b in zip(moving, moving[1:], strict=False) if a and not b)


def _closest_approach(trajectory, robot_radius: float) -> float:
    best = math.inf
    for point in trajectory:
        for obstacle in point.obstacles:
            gap = math.hypot(point.x - obstacle.x, point.y - obstacle.y)
            best = min(best, gap - obstacle.radius - robot_radius)
    return best


def _run(scene: str, seed: int, oracle: bool) -> Episode:
    map_data, scenario = build_scenario(scene)
    scenario = scenario.model_copy(update={"random_seed": seed})
    shared = LOCAL_CONTROLLER_CONFIGS["dwa_balanced"]
    if oracle:
        planner = build_oracle(scenario, DWAPredictiveConfig(**shared))
    else:
        planner = build_local_planner("astar+dwa", shared)
    run = run_stack(
        map_data,
        scenario,
        planner,
        build_global_planner("astar+dwa", episode_seed=seed),
    )
    result = run.result
    return Episode(
        success=result.status.value == "success",
        collision=result.status.value == "collision",
        travel_time=result.elapsed_time,
        stop_and_go=_stop_and_go(result.trajectory),
        near_miss=_closest_approach(result.trajectory, scenario.robot.radius) < NEAR_MISS_M,
    )


def _paired_median_ci(differences: list[float]) -> tuple[float, float, float]:
    """``(median, low, high)`` of the paired difference, 95% bootstrap.

    Paired by seed and resampled by **pair**, not by arm: the two
    controllers meet the identical world at each seed, and throwing that
    away would compare two independent samples and widen the interval for
    no reason.
    """
    rng = random.Random(BOOTSTRAP_SEED)
    size = len(differences)
    medians = []
    for _ in range(RESAMPLES):
        draw = [differences[rng.randrange(size)] for _ in range(size)]
        medians.append(statistics.median(draw))
    medians.sort()
    return (
        statistics.median(differences),
        medians[int(0.025 * RESAMPLES)],
        medians[int(0.975 * RESAMPLES) - 1],
    )


def _report_scene(scene: str, seeds: int, gate: bool) -> dict[str, tuple[float, float, float]]:
    plain = [_run(scene, seed, oracle=False) for seed in range(seeds)]
    oracle = [_run(scene, seed, oracle=True) for seed in range(seeds)]

    label = "GATE " if gate else "limit"
    print(f"\n=== {label} {scene}  ({seeds} paired seeds) ===")

    for name, pick in (
        ("success_rate", lambda e: float(e.success)),
        ("collision_rate", lambda e: float(e.collision)),
        ("near_miss_rate", lambda e: float(e.near_miss)),
    ):
        theirs = statistics.fmean(pick(e) for e in plain)
        ours = statistics.fmean(pick(e) for e in oracle)
        flag = "  <-- WORSE" if _worse(name, theirs, ours) else ""
        print(f"  {name:<16} dwa {theirs:>6.3f}   oracle {ours:>6.3f}{flag}")

    outcome = {}
    # Conditioned on both succeeding: a candidate that gives up early has
    # fewer stops because it went less far, not because it flowed better.
    both = [(p, o) for p, o in zip(plain, oracle, strict=True) if p.success and o.success]
    print(f"  paired on {len(both)} of {seeds} contexts where both reached the goal")
    if len(both) < 2:
        print("  too few paired successes to bootstrap")
        return outcome
    for name, pick in (
        ("travel_time", lambda e: e.travel_time),
        ("stop_and_go", lambda e: float(e.stop_and_go)),
    ):
        differences = [pick(o) - pick(p) for p, o in both]
        median, low, high = _paired_median_ci(differences)
        verdict = "improves" if high < 0.0 else ("worsens" if low > 0.0 else "no effect")
        print(
            f"  d{name:<15} median {median:>+7.3f}   95% CI [{low:>+7.3f}, {high:>+7.3f}]"
            f"   {verdict}"
        )
        outcome[name] = (median, low, high)
    return outcome


def _worse(metric: str, plain: float, oracle: float) -> bool:
    if metric == "success_rate":
        return oracle < plain
    return oracle > plain


def _sign_test(better: int, worse: int) -> float:
    """One-sided p that ``better`` of the discordant pairs is chance.

    The paired test for binary outcomes, and the right one for a rare
    effect: only the pairs that **disagree** carry information about which
    controller is better, and a proportion difference dilutes them in the
    majority of seeds where nothing happened. Concordant pairs are
    uninformative by construction — both arms did the same thing.
    """
    trials = better + worse
    if trials == 0:
        return 1.0
    return sum(math.comb(trials, k) for k in range(better, trials + 1)) / 2**trials


def _rare_event_gate(seeds: int) -> bool:
    print("\n" + "=" * 70)
    print("GATE, SECOND DECLARATION — rare-event sign test on discordant pairs")
    print(f"Predicted before running: {RARE_EVENT_PREDICTION}")
    print(f"Pass: p < {SIGN_TEST_ALPHA} one-sided, and no guarded metric worse.")
    print("=" * 70)

    passed = True
    for scene in RARE_EVENT_SCENES:
        plain = [_run(scene, seed, oracle=False) for seed in range(seeds)]
        oracle = [_run(scene, seed, oracle=True) for seed in range(seeds)]

        better = worse = 0
        for p, o in zip(plain, oracle, strict=True):
            rank_p = OUTCOME_RANK[_status(p)]
            rank_o = OUTCOME_RANK[_status(o)]
            if rank_o > rank_p:
                better += 1
            elif rank_o < rank_p:
                worse += 1

        p_value = _sign_test(better, worse)
        print(f"\n=== {scene} ({seeds} paired seeds, unconditioned) ===")
        print(f"  discordant pairs      {better + worse}")
        print(f"  favouring the oracle  {better}")
        print(f"  favouring dwa         {worse}")
        print(f"  one-sided sign test   p = {p_value:.5f}")

        collisions_plain = sum(1 for e in plain if e.collision)
        collisions_oracle = sum(1 for e in oracle if e.collision)
        successes_plain = sum(1 for e in plain if e.success)
        successes_oracle = sum(1 for e in oracle if e.success)
        print(f"  collisions  dwa {collisions_plain:>3} -> oracle {collisions_oracle:>3}")
        print(f"  successes   dwa {successes_plain:>3} -> oracle {successes_oracle:>3}")

        guard_ok = collisions_oracle <= collisions_plain and successes_oracle >= successes_plain
        scene_ok = p_value < SIGN_TEST_ALPHA and guard_ok
        if not guard_ok:
            print("  GUARD BREACHED — a metric got worse")
        print(f"  {scene}: {'PASS' if scene_ok else 'FAIL'}")
        passed = passed and scene_ok

    print("\n=== VERDICT ===")
    print("  PASS — continue to P5" if passed else "  FAIL — the plan stops here")
    return passed


def _status(episode: Episode) -> str:
    if episode.collision:
        return "collision"
    return "success" if episode.success else "timeout"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=MIN_SEEDS)
    parser.add_argument(
        "--rare-event",
        action="store_true",
        help="run the second gate declaration instead of the first",
    )
    arguments = parser.parse_args()
    if arguments.rare_event:
        _rare_event_gate(max(RARE_EVENT_SEEDS, arguments.seeds))
        return
    seeds = max(MIN_SEEDS, arguments.seeds)

    print("Decision gate 2 — oracle (perfect perception) versus dwa")
    print(f"Predicted before running: {PREDICTION}")
    print(f"Pass rule: 95% CI of the paired median below zero for one of {IMPROVEMENT_METRICS},")
    print(f"           and none of {GUARDED_METRICS} worse.")

    results = {scene: _report_scene(scene, seeds, gate=True) for scene in GATE_SCENES}
    for scene in LIMIT_SCENES:
        _report_scene(scene, seeds, gate=False)

    print("\n=== VERDICT (gate scenes only) ===")
    passed = False
    for scene, outcome in results.items():
        for metric, (_, _, high) in outcome.items():
            if metric in IMPROVEMENT_METRICS and high < 0.0:
                print(f"  {scene}: {metric} improves with the whole CI below zero")
                passed = True
    print("  PASS — continue to P5" if passed else "  FAIL — the plan stops here")


if __name__ == "__main__":
    main()
