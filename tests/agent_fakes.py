"""A gateway the agent tests can drive, with no server behind it.

The point of the Protocol in :mod:`planbench_agent.gateway` is that the
whole agent — tool policy, loop bounds, refusal paths — can be exercised
without FastAPI, a database or a model. This is the other half of that
bargain.

It stores dictionaries rather than domain objects on purpose. The real
gateway hands the agent stored JSON, and a fake that handed back
perfectly-shaped Pydantic models would hide exactly the class of bug
worth catching: a tool that reads a field the stored report does not
actually have.
"""

from __future__ import annotations

from typing import Any

from planbench_agent.gateway import (
    CandidateSummary,
    DecisionRunSummary,
    DeploymentSummary,
    GatewayError,
    ScenarioSummary,
)
from planbench_decision.self_check import critique

SCENARIOS: tuple[tuple[str, str, int, float], ...] = (
    ("open_space", "Empty room, one goal.", 0, 30.0),
    ("doorway", "A gap one robot wide.", 1, 45.0),
    ("dynamic_warehouse", "Aisles with moving traffic.", 4, 60.0),
)


def sample_report(
    *,
    n_episodes: int = 30,
    n_min: int = 30,
    distinct: int = 30,
    ranked: bool = True,
) -> dict[str, Any]:
    """A stored comparison report, shaped like the real thing.

    Defaults describe a run with nothing wrong with it, so a test that
    wants a defect injects exactly one and the rules' answer is
    unambiguous.
    """
    report: dict[str, Any] = {
        "artifact": "comparison_report",
        "identity": {
            "task_profile_id": "hall_v1",
            "experiment_scope": "local_controller_selection",
            "sensor_noise": {"lidar_range_sigma_m": 0.02, "wheel_slip_fraction": 0.01},
            "git_sha": "abc123def456",
        },
        "sample": {
            "n_episodes": n_episodes,
            "n_episodes_requested": n_episodes,
            "interrupted": False,
            "n_min_required": n_min,
        },
        "early_stop": {"stopped": []},
        "candidates": [
            _candidate("aaa111", "astar+dwa", distinct=distinct, success=0.93),
            _candidate("bbb222", "rrtstar+dwa", distinct=distinct, success=0.87),
        ],
        "measurement_environment": {"warning": None},
        "why_no_card": None if ranked else "only 1 of 2 candidates cleared all six gates",
    }
    report["decision_card"] = (
        {
            "status": "CLEAR_RECOMMENDATION",
            "tie_break_reason": None,
            "evidence": {
                "delta_u_vs_second": 0.041,
                "ci95": [0.033, 0.048],
                "n_episodes": n_episodes,
                "effect_size": 3.9,
            },
        }
        if ranked
        else None
    )
    return report


def _candidate(candidate_id: str, label: str, *, distinct: int, success: float) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "stack_label": label,
        "local_controller_config": "dwa_coarse",
        "n_episodes": 30,
        "cleared_gates": True,
        "blocking_gates": [],
        "n_distinct_episodes": distinct,
        "success_rate": success,
        "pooled_p99_latency_ms": 7.4,
        "gates": {
            "candidate_id": candidate_id,
            "G1": "pass",
            "G2": {
                "result": "pass",
                "observed": 0,
                "n_runs": 30,
                "n_distinct_episodes": distinct,
                "upper_bound_95": 0.1,
                "n_min": 30,
            },
            "G3": "pass",
            "G4": {
                "result": "pass",
                "status": "confirmed_on_target",
                "p99_ms": 7.4,
                "threshold_ms": 50.0,
            },
            "G5": {"result": "pass", "status": "estimated_from_structure"},
            "G6": "pass",
        },
    }


class FakeGateway:
    """Implements :class:`planbench_agent.gateway.AgentGateway`, in memory."""

    def __init__(self) -> None:
        self.deployments: dict[str, dict[str, Any]] = {}
        self.runs: dict[str, dict[str, Any]] = {}
        self.candidates: list[CandidateSummary] = []
        #: Every method call, so a test can assert what the model reached
        #: for rather than only what it said.
        self.calls: list[str] = []

    # -- fixture helpers --------------------------------------------------

    def add_deployment(self, task_profile_id: str = "hall_v1", **overrides: Any) -> str:
        profile: dict[str, Any] = {
            "id": task_profile_id,
            "environment": {"map": "maps/open_hall.pgm", "map_yaml": "maps/open_hall.yaml"},
            "missions": [{"id": "m1", "start": [1.0, 1.0, 0.0], "goal": [8.0, 6.0, 0.0]}],
            "robot": {"radius": 0.26, "control_period": 0.05},
            "constraints": {"collision_probability_max": 0.1, "success_rate_min": 0.9},
            "hardware": {"available_ram_mb": 2048},
        }
        profile.update(overrides)
        self.deployments[task_profile_id] = profile
        return task_profile_id

    def add_run(self, run_id: str = "run001", **kwargs: Any) -> str:
        self.runs[run_id] = sample_report(**kwargs)
        return run_id

    def add_candidate(self, candidate_id: str = "aaa111", label: str = "astar+dwa") -> None:
        self.candidates.append(
            CandidateSummary(
                candidate_id=candidate_id,
                stack_label=label,
                local_controller_config="dwa_coarse",
                observation_requirements=("full_static_map", "lidar_only"),
            )
        )

    # -- AgentGateway -----------------------------------------------------

    def list_deployments(self) -> list[DeploymentSummary]:
        self.calls.append("list_deployments")
        return [
            DeploymentSummary(
                task_profile_id=key,
                environment=str((profile.get("environment") or {}).get("map", "")),
                missions=len(profile.get("missions") or []),
                n_min_episodes=30,
                created_at="2026-08-16T00:00:00Z",
            )
            for key, profile in self.deployments.items()
        ]

    def get_deployment(self, task_profile_id: str) -> dict[str, Any]:
        self.calls.append("get_deployment")
        if task_profile_id not in self.deployments:
            raise GatewayError(f"deployment {task_profile_id!r} not found")
        return self.deployments[task_profile_id]

    def list_candidates(self) -> list[CandidateSummary]:
        self.calls.append("list_candidates")
        return list(self.candidates)

    def list_scenarios(self) -> list[ScenarioSummary]:
        self.calls.append("list_scenarios")
        return [
            ScenarioSummary(
                name=name,
                description=description,
                curriculum_index=index,
                dynamic_obstacles=obstacles,
                timeout_seconds=timeout,
            )
            for index, (name, description, obstacles, timeout) in enumerate(SCENARIOS)
        ]

    def list_decision_runs(self, task_profile_id: str | None = None) -> list[DecisionRunSummary]:
        self.calls.append("list_decision_runs")
        return [
            DecisionRunSummary(
                id=run_id,
                task_profile_id=report["identity"]["task_profile_id"],
                experiment_scope=report["identity"].get("experiment_scope"),
                ranked=report.get("decision_card") is not None,
                status=(report.get("decision_card") or {}).get("status"),
            )
            for run_id, report in self.runs.items()
            if task_profile_id is None or report["identity"]["task_profile_id"] == task_profile_id
        ]

    def get_decision_run(self, run_id: str) -> dict[str, Any]:
        self.calls.append("get_decision_run")
        return self._require(run_id)

    def get_decision_card(self, run_id: str) -> dict[str, Any] | None:
        self.calls.append("get_decision_card")
        return self._require(run_id).get("decision_card")

    def get_gate_table(self, run_id: str) -> list[dict[str, Any]]:
        self.calls.append("get_gate_table")
        return [
            {
                "candidate_id": candidate["candidate_id"],
                "stack_label": candidate["stack_label"],
                "cleared_gates": candidate["cleared_gates"],
                "blocking_gates": candidate["blocking_gates"],
                "gates": candidate["gates"],
            }
            for candidate in self._require(run_id)["candidates"]
        ]

    def get_critique(self, run_id: str) -> list[dict[str, Any]]:
        self.calls.append("get_critique")
        return [finding.model_dump(mode="json") for finding in critique(self._require(run_id))]

    def get_outcome(self, run_id: str) -> list[dict[str, Any]]:
        self.calls.append("get_outcome")
        from planbench_benchmark.outcome import build_outcome, outcome_advice

        return [
            a.model_dump(mode="json") for a in outcome_advice(build_outcome(self._require(run_id)))
        ]

    def _require(self, run_id: str) -> dict[str, Any]:
        if run_id not in self.runs:
            raise GatewayError(f"decision run {run_id!r} not found")
        return self.runs[run_id]


def populated_gateway() -> FakeGateway:
    """A gateway with one deployment, one run and two candidates."""
    gateway = FakeGateway()
    gateway.add_deployment()
    gateway.add_run()
    gateway.add_candidate("aaa111", "astar+dwa")
    gateway.add_candidate("bbb222", "rrtstar+dwa")
    return gateway
