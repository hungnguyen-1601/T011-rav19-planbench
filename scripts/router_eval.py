"""E10 — five router arms, scored off runs that already happened.

A cascade is cheap because of **where it sends a case**, and a router
that sends too much to the floor is cheap and misses exactly the cases a
model was bought for. So the routing decision is a component with its own
failure, measured on its own, and never inferred from a Pareto plot of
two models.

Nothing here calls a model. It reads the artifacts
``run_analyst_experiments.py`` wrote and answers five questions:

``floor_only``
    the model-free reference analyst on every case — the thing any
    cascade has to beat before it is worth its wiring.

``always_default``
    the cheaper model on every case.

``always_strong``
    the dearer model on every case. **The arm that makes the second tier
    honest**: without it, the gain of escalating cannot be separated from
    the gain of simply using the better model.

``oracle_router``
    per case, whichever arm has the highest utility. Not achievable —
    it is the ceiling regret is measured against.

``frozen_cascade``
    a rule designed on one fold and scored on the other. Designing and
    scoring a router on the same cases is how E10 flatters itself, so
    the folds are by case and the rule is fixed before it is read.

Utility is the preregistered one, and the weights were fixed at W0.8:

    U = 1.0 · quality − 0.02 · cost_k_tokens − 0.005 · latency_s

``quality`` is case-level mechanism correctness — every repeat correct,
the same rule the primary endpoint uses. A run whose per-case latency was
not recorded reports the latency term as **absent** rather than as zero:
zero would price a slow arm as a fast one.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for package in ("schemas", "planning", "metrics", "benchmark", "decision", "explanation"):
    sys.path.insert(0, str(ROOT / "packages" / package))
sys.path.insert(0, str(ROOT / "services" / "simulator"))
sys.path.insert(0, str(ROOT / "services" / "agent_service"))
sys.path.insert(0, str(ROOT / "services" / "analyst_service"))

from planbench_analyst.preregistration import PREREGISTRATION  # noqa: E402

ARTIFACTS = ROOT / "artifacts" / "analyst-experiments"

WEIGHTS = dict(PREREGISTRATION.utility_weights)


@dataclass(frozen=True)
class ArmCase:
    """One arm's result on one case, as the utility reads it."""

    arm: str
    case_id: str
    quality: float
    cost_k_tokens: float
    latency_s: float | None

    @property
    def utility(self) -> float:
        value = WEIGHTS["quality"] * self.quality - WEIGHTS["cost_k_tokens"] * self.cost_k_tokens
        if self.latency_s is not None:
            value -= WEIGHTS["latency_s"] * self.latency_s
        return value


def load(label: str, arm: str) -> dict[str, ArmCase]:
    """One arm's cases from whatever file that run was written to."""
    found: dict[str, ArmCase] = {}
    for path in sorted((ARTIFACTS / label).glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for run in payload["runs"]:
            if run["arm"] != arm:
                continue
            for case in run["cases"]:
                repeats = case["repeats"]
                latencies = [
                    item["latency_s"] for item in repeats if item.get("latency_s") is not None
                ]
                found[case["case_id"]] = ArmCase(
                    arm=f"{label}:{arm}",
                    case_id=case["case_id"],
                    quality=1.0 if case["mechanism_correct"] else 0.0,
                    cost_k_tokens=case["median_tokens"] / 1000.0,
                    latency_s=statistics.median(latencies) if latencies else None,
                )
    return found


def floor_from(label: str, arm: str) -> dict[str, ArmCase]:
    """The model-free reference, read off the same artifacts.

    It costs no tokens and no model calls, which is the whole of its
    case: a cascade that cannot beat it on utility is wiring nobody
    needs.
    """
    found: dict[str, ArmCase] = {}
    for path in sorted((ARTIFACTS / label).glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for run in payload["runs"]:
            if run["arm"] != arm:
                continue
            for case in run["cases"]:
                found[case["case_id"]] = ArmCase(
                    arm="floor_only",
                    case_id=case["case_id"],
                    quality=1.0 if case["floor_mechanism_correct"] else 0.0,
                    cost_k_tokens=0.0,
                    latency_s=0.0,
                )
    return found


def cascade_rule(
    train: list[str], default: dict[str, ArmCase], strong: dict[str, ArmCase]
) -> set[str]:
    """Which cases the frozen rule escalates, learned on the train fold.

    Deliberately blunt: escalate a case when the dearer arm was right on
    the training fold and the cheaper one was not. A rule with more
    knobs than a six-case fold can support is a rule fitted to noise.
    """
    return {
        case_id
        for case_id in train
        if strong.get(case_id)
        and default.get(case_id)
        and strong[case_id].quality > default[case_id].quality
    }


def summarise(name: str, chosen: dict[str, ArmCase]) -> dict[str, float]:
    return {
        "cases": len(chosen),
        "quality": sum(item.quality for item in chosen.values()),
        "cost_k_tokens": round(sum(item.cost_k_tokens for item in chosen.values()), 2),
        "utility": round(sum(item.utility for item in chosen.values()), 4),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--default-label", required=True, help="the cheaper model's run")
    parser.add_argument("--strong-label", required=True, help="the dearer model's run")
    parser.add_argument("--arm", default="e8_model")
    args = parser.parse_args()

    default = load(args.default_label, args.arm)
    strong = load(args.strong_label, args.arm)
    floor = floor_from(args.default_label, args.arm)
    shared = sorted(set(default) & set(strong) & set(floor))
    if not shared:
        print("no case is present in all three arms; nothing to compare")
        return 1

    arms: dict[str, dict[str, ArmCase]] = {
        "floor_only": {case: floor[case] for case in shared},
        "always_default": {case: default[case] for case in shared},
        "always_strong": {case: strong[case] for case in shared},
    }
    # The ceiling. Not achievable: it is what regret is measured against.
    arms["oracle_router"] = {
        case: max((floor[case], default[case], strong[case]), key=lambda item: item.utility)
        for case in shared
    }

    # Cross-fitting by case. With six cases the folds are three and
    # three, which is small — and stated rather than hidden, because a
    # router scored on the cases that designed it reports its own
    # training set.
    half = max(1, len(shared) // 2)
    folds = [(shared[:half], shared[half:]), (shared[half:], shared[:half])]
    frozen: dict[str, ArmCase] = {}
    escalated: set[str] = set()
    for train, test in folds:
        rule = cascade_rule(train, default, strong)
        # The rule is a set of case ids from the *training* fold, so on
        # the test fold it can only generalise through what those cases
        # had in common — here, nothing but their names. A six-case fold
        # cannot support more, and pretending otherwise is the failure
        # this arm exists to expose.
        for case in test:
            escalate = case in rule
            frozen[case] = strong[case] if escalate else default[case]
            if escalate:
                escalated.add(case)
    arms["frozen_cascade"] = frozen

    print(f"cases: {len(shared)}  ({', '.join(shared)})")
    print(
        f"utility weights (preregistered): quality {WEIGHTS['quality']}, "
        f"cost {WEIGHTS['cost_k_tokens']}/1k tok, latency {WEIGHTS['latency_s']}/s"
    )
    missing_latency = [
        name
        for name, chosen in arms.items()
        if any(item.latency_s is None for item in chosen.values())
    ]
    if missing_latency:
        print(
            f"latency term ABSENT for {sorted(missing_latency)}: those runs recorded no "
            "per-case wall time, and pricing them at zero would call a slow arm fast"
        )
    print()
    print(f"{'arm':18} {'cases':>5} {'quality':>8} {'cost_k':>8} {'utility':>9}")
    for name, chosen in arms.items():
        row = summarise(name, chosen)
        print(
            f"{name:18} {row['cases']:>5} {row['quality']:>8.0f} "
            f"{row['cost_k_tokens']:>8.1f} {row['utility']:>9.4f}"
        )

    oracle = summarise("oracle_router", arms["oracle_router"])["utility"]
    print()
    for name in ("floor_only", "always_default", "always_strong", "frozen_cascade"):
        regret = round(oracle - summarise(name, arms[name])["utility"], 4)
        print(f"regret vs oracle · {name:18} {regret:+.4f}")

    # Router recall and false non-escalation, on the cases where
    # escalating was the right call.
    needed = {case for case in shared if strong[case].quality > default[case].quality}
    caught = needed & escalated
    print()
    print(f"cases where escalating helps: {len(needed)}")
    if needed:
        print(f"router recall: {len(caught)}/{len(needed)}")
        print(f"false non-escalation: {len(needed - escalated)}/{len(needed)}")
    else:
        print(
            "router recall: not defined — the dearer model was never right where the "
            "cheaper one was wrong, so there is nothing for a router to catch"
        )
    second_tier = round(
        summarise("frozen_cascade", arms["frozen_cascade"])["utility"]
        - summarise("always_strong", arms["always_strong"])["utility"],
        4,
    )
    print(f"second tier vs always_strong: {second_tier:+.4f}")
    print()
    print(
        "Exploratory. Six cases, one per family, no holdout — the preregistration "
        "reports counts rather than rates below twelve, and a router scored on folds "
        "this small is a direction, not a decision."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
