"""One run, fully populated, shared by every export test that needs a whole document.

**Why a shared fixture and not one per test file.** The golden snapshots
exist to prove the English Markdown never changes by accident. A snapshot
is only worth what its input is worth: a fixture missing the gate
payloads, the episodes or the card would render a document with most of
its sections absent, and the snapshot would then guard the parts nobody
was going to break anyway.

So this one carries every branch the renderers have: two candidates that
both cleared, gate payloads with the numbers the comparison reads, two
episodes each (one passing, one failing), a card with its interval and
its objectives, a manifest naming the preference profile, and a review
that happened while the configuration decision has not.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any


def _episodes(prefix: str, clearance: float, latency: float) -> list[dict[str, Any]]:
    return [
        {
            "episode_context_id": f"{prefix}00",
            "success": True,
            "failure_reason": None,
            "collision_count": 0,
            "min_clearance": clearance,
            "travel_time_s": 22.8,
            "p99_latency_ms": latency,
            "replan_count": 1,
            "episode_decision_utility": 0.88,
        },
        {
            "episode_context_id": f"{prefix}01",
            "success": False,
            "failure_reason": "timeout",
            "collision_count": 0,
            "min_clearance": 0.113,
            "travel_time_s": 60.0,
            "p99_latency_ms": latency * 2,
            "replan_count": 17,
            "episode_decision_utility": 0.31,
        },
    ]


def _candidate(
    *,
    candidate_id: str,
    stack_label: str,
    config: str,
    success_rate: float,
    p99: float,
    memory: float,
    clearance: float,
    median_travel: float,
    replans: int,
    utility: float,
    objectives: dict[str, float],
) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "stack_label": stack_label,
        "local_controller_config": config,
        "local_observation_class": "lidar_only",
        "n_episodes": 30,
        "n_distinct_episodes": 30,
        "success_rate": success_rate,
        "pooled_p99_latency_ms": p99,
        "worst_clearance_m": clearance,
        "median_travel_time_s": median_travel,
        "replan_count": replans,
        "cleared_gates": True,
        "blocking_gates": [],
        "gates": {
            "G1": {"no_path_rate": 0.0, "threshold": 0.05},
            "G2": {"observed": 0, "upper_bound_95": 0.1, "n_distinct_episodes": 30},
            "G3": {"threshold": 0.95},
            "G4": {"threshold_ms": 50.0},
            "G5": {"memory_estimate_mb": memory, "available_ram_mb": 3277.0},
        },
        "objectives": objectives,
        "decision_utility": utility,
        "recommendation_eligible": True,
        "episodes": _episodes(candidate_id, clearance, p99),
    }


CARD: dict[str, Any] = {
    "recommended": {"stack": "astar+dwa", "candidate_id": "c1"},
    "alternative": {"stack": "rrtstar+dwa", "candidate_id": "c2"},
    "status": "CLEAR_RECOMMENDATION",
    "contracts_version": "6.9.0",
    "recommendation_scope": "warehouse_a_v2",
    # **The arithmetic is real.** 0.30·1.0 + 0.10·0.912 + 0.25·0.568 +
    # 0.35·0.958 under `kho_ban_dem` — the profile the manifest below
    # names. A fixture whose utility did not equal its own weighted sum
    # would make the one assertion worth most here (the Contribution
    # column adding up to the card) unwritable.
    "decision_utility": 0.8685,
    "pareto_label": "DOMINANT",
    "decision_mode": "technical",
    "objectives": {"U_R": 1.0, "U_S": 0.912, "U_E": 0.568, "U_C": 0.958},
    "evidence": {
        "delta_u_mean": 0.22735,
        "delta_u_vs_second": 0.22735,
        "ci95": [0.181, 0.274],
        "effect_size": 0.74,
        "n_episodes": 30,
        "weight_stability_margin": 1.0,
        "anchor_stability": "unchanged",
        "robustness_margin": None,
    },
}

MANIFEST: dict[str, Any] = {
    "contracts_version": "6.9.0",
    "git_sha": "abc1234",
    "task_profile_id": "warehouse_a_v2",
    "anchor_config_version": "v1.2",
    "preference_profile": "kho_ban_dem",
    "decision_mode": "technical",
    "travel_time_accounting": "efficiency",
}


def report() -> dict[str, Any]:
    return {
        "artifact": "comparison_report",
        "identity": {
            "task_profile_id": "warehouse_a_v2",
            "experiment_scope": "global_planner_selection",
            "git_sha": "abc1234",
            "anchor_config_version": "v1.2",
            "created_at": "2026-08-21T14:30:00+00:00",
        },
        "sample": {"n_episodes": 30, "n_episodes_requested": 30, "n_min_required": 6},
        "candidates": [
            _candidate(
                candidate_id="c1",
                stack_label="astar+dwa",
                config="dwa_coarse",
                success_rate=1.0,
                p99=7.3479,
                memory=412.5,
                clearance=0.494,
                median_travel=22.8,
                replans=30,
                utility=0.8685,
                objectives={"U_R": 1.0, "U_S": 0.912, "U_E": 0.568, "U_C": 0.958},
            ),
            _candidate(
                candidate_id="c2",
                stack_label="rrtstar+dwa",
                config="dwa_balanced",
                success_rate=0.9667,
                p99=16.1043,
                memory=688.25,
                clearance=0.331,
                median_travel=25.4,
                replans=44,
                utility=0.64115,
                objectives={"U_R": 0.34, "U_S": 0.771, "U_E": 0.612, "U_C": 0.883},
            ),
        ],
        "measurement_environment": {"benchmark_host": {}, "warning": None},
        "decision_card": CARD,
        "manifest": MANIFEST,
    }


def golden_run(**overrides: Any) -> SimpleNamespace:
    """The run both golden snapshots are rendered from."""
    base: dict[str, Any] = {
        "id": "run_golden",
        "task_profile_id": "warehouse_a_v2",
        "experiment_scope": "global_planner_selection",
        "contracts_version": "6.9.0",
        "created_at": "2026-08-21T14:30:00+00:00",
        "report": report(),
        "card": CARD,
        "manifest": MANIFEST,
        "review_state": "reviewed",
        "reviewed_by": "an",
        "reviewed_at": "2026-08-21T16:00:00+00:00",
        "config_state": "pending",
        "config_decided_by": None,
        "config_decided_at": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def unranked_run(**overrides: Any) -> SimpleNamespace:
    """The other branch: gates ran, nobody was ranked, no card and no manifest.

    Snapshotted alongside the ranked one because the two take different
    paths through every renderer — `no_card_reason`, the missing
    objectives, the absent margin — and a snapshot of only the happy
    path would leave the branch most runs actually take unguarded.
    """
    thin = report()
    thin["decision_card"] = None
    thin["manifest"] = None
    thin["why_no_card"] = "only one candidate cleared the gates"
    blocked = thin["candidates"][1]
    blocked["cleared_gates"] = False
    blocked["blocking_gates"] = ["G4"]
    blocked["recommendation_eligible"] = False
    blocked["decision_utility"] = None
    blocked["objectives"] = {}
    return golden_run(report=thin, card=None, manifest=None, **overrides)
