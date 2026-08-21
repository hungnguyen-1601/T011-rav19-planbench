"""Adapter implementing :class:`planbench_agent.gateway.AgentGateway`.

The dependency points this way on purpose: the API knows about the agent
package, the agent package knows nothing about FastAPI. Everything the
agent can reach is spelled out here, so widening its authority means
editing this file and nothing else.

Read-only throughout. The gateway still runs as a specific user, because
authorisation and audit are the caller's concern even when nothing is
written — and because the day somebody adds a write method, the identity
it needs should already be in hand rather than retrofitted.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from planbench_agent.gateway import (
    CandidateSummary,
    DecisionRunSummary,
    DeploymentSummary,
    GatewayError,
    ScenarioSummary,
)
from planbench_api.auth import User
from planbench_api.decision_service import (
    CandidateService,
    DecisionRunService,
    TaskProfileService,
)
from planbench_api.errors import NotFoundError
from planbench_benchmark import CURRICULUM_ORDER, build_scenario
from planbench_decision.self_check import critique


class ApiAgentGateway:
    """Everything the agent may read, expressed over the existing services."""

    def __init__(
        self,
        *,
        profiles: TaskProfileService,
        candidates: CandidateService,
        runs: DecisionRunService,
        user: User,
        map_root: Path | None = None,
    ) -> None:
        self._profiles = profiles
        self._candidates = candidates
        self._runs = runs
        self._user = user
        #: Where a profile's relative map paths resolve. Optional because
        #: only the recommendation tool reads it, and a gateway without
        #: it degrades to mapless preflight rather than refusing to exist.
        self._map_root = map_root

    # -- deployments -----------------------------------------------------

    def list_deployments(self) -> list[DeploymentSummary]:
        summaries: list[DeploymentSummary] = []
        for stored in self._profiles.list():
            profile = stored.profile or {}
            environment = profile.get("environment") or {}
            constraints = profile.get("constraints") or {}
            summaries.append(
                DeploymentSummary(
                    task_profile_id=stored.id,
                    environment=str(environment.get("map", "")),
                    missions=len(profile.get("missions") or []),
                    n_min_episodes=_n_min(constraints),
                    created_at=stored.created_at,
                )
            )
        return summaries

    def get_deployment(self, task_profile_id: str) -> dict[str, Any]:
        return dict(self._lookup_profile(task_profile_id).profile or {})

    # -- candidates ------------------------------------------------------

    def list_candidates(self) -> list[CandidateSummary]:
        summaries: list[CandidateSummary] = []
        for stored in self._candidates.list():
            spec = stored.spec or {}
            summaries.append(
                CandidateSummary(
                    candidate_id=stored.candidate_id,
                    stack_label=stored.stack_label,
                    local_controller_config=_local_config(spec),
                    observation_requirements=tuple(spec.get("observation_requirements") or ()),
                )
            )
        return summaries

    def list_scenarios(self) -> list[ScenarioSummary]:
        summaries: list[ScenarioSummary] = []
        for index, name in enumerate(CURRICULUM_ORDER):
            _, scenario = build_scenario(name)
            summaries.append(
                ScenarioSummary(
                    name=name,
                    description=scenario.description or "",
                    curriculum_index=index,
                    dynamic_obstacles=len(scenario.dynamic_obstacles or ()),
                    timeout_seconds=scenario.timeout_seconds,
                )
            )
        return summaries

    # -- runs ------------------------------------------------------------

    def list_decision_runs(self, task_profile_id: str | None = None) -> list[DecisionRunSummary]:
        return [
            DecisionRunSummary(
                id=stored.id,
                task_profile_id=stored.task_profile_id,
                experiment_scope=stored.experiment_scope,
                created_at=stored.created_at,
                created_by=stored.created_by,
                ranked=stored.card is not None,
                recommended_candidate_id=stored.recommended_candidate_id,
                status=stored.status,
                review_state=stored.review_state,
                config_state=stored.config_state,
            )
            for stored in self._runs.list(task_profile_id=task_profile_id)
        ]

    def get_decision_run(self, run_id: str) -> dict[str, Any]:
        return dict(self._lookup_run(run_id).report or {})

    def get_decision_card(self, run_id: str) -> dict[str, Any] | None:
        card = self._lookup_run(run_id).card
        return dict(card) if card else None

    def get_gate_table(self, run_id: str) -> list[dict[str, Any]]:
        """Gates plus the identity of who they applied to.

        The report keys gates under each candidate, so a bare
        ``[c["gates"] ...]`` would hand the model six verdicts with no
        way to say whose they were.
        """
        report = self._lookup_run(run_id).report or {}
        rows: list[dict[str, Any]] = []
        for candidate in report.get("candidates") or []:
            rows.append(
                {
                    "candidate_id": candidate.get("candidate_id"),
                    "stack_label": candidate.get("stack_label"),
                    "cleared_gates": candidate.get("cleared_gates"),
                    "blocking_gates": candidate.get("blocking_gates") or [],
                    "n_episodes": candidate.get("n_episodes"),
                    "n_distinct_episodes": candidate.get("n_distinct_episodes"),
                    "success_rate": candidate.get("success_rate"),
                    "gates": candidate.get("gates") or {},
                }
            )
        return rows

    def get_critique(self, run_id: str) -> list[dict[str, Any]]:
        """The deterministic objections, so the model can add rather than repeat."""
        return [
            finding.model_dump(mode="json") for finding in critique(self._lookup_run(run_id).report)
        ]

    def get_outcome(self, run_id: str) -> list[dict[str, Any]]:
        """Why the run ended as it did, from the deterministic rules.

        The chat model narrates on top of these; it does not get to
        replace them with its own recollection of what the algorithms
        are like.
        """
        from planbench_benchmark.outcome import build_outcome, outcome_advice

        report = self._lookup_run(run_id).report or {}
        return [item.model_dump(mode="json") for item in outcome_advice(build_outcome(report))]

    def get_recommendation(self, task_profile_id: str | None = None) -> dict[str, Any]:
        """Which algorithm this deployment should use, from stored runs.

        Same floor as ``GET /task-profiles/{id}/recommendation``: the
        deterministic rules run here and the model narrates on top in the
        chat — it does not get to weigh the evidence itself.
        """
        from planbench_benchmark.recommendation import (
            recommend_from_history,
            recommendation_source,
        )
        from planbench_schemas.task_profile import TaskProfile

        if task_profile_id is None:
            stored_profiles = self._profiles.list()
            if len(stored_profiles) != 1:
                names = ", ".join(sorted(p.id for p in stored_profiles)) or "none declared"
                raise GatewayError(
                    f"several deployments exist ({names}); name the task_profile_id "
                    "the recommendation is for"
                )
            task_profile_id = stored_profiles[0].id

        stored = self._lookup_profile(task_profile_id)
        try:
            profile = TaskProfile.model_validate(stored.profile or {})
        except Exception as exc:  # noqa: BLE001 — a stored-but-invalid profile is data
            raise GatewayError(
                f"deployment {task_profile_id} no longer validates against the current "
                f"TaskProfile contract: {exc}"
            ) from exc

        source = recommendation_source(
            profile,
            [
                {
                    "run_id": run.id,
                    "status": run.status,
                    "card": run.card,
                    "report": run.report,
                    "created_at": run.created_at,
                    "contracts_version": run.contracts_version,
                }
                for run in self._runs.list(task_profile_id=task_profile_id)
            ],
            map_base_dir=self._map_root,
        )
        found = recommend_from_history(source)
        return {
            "task_profile_id": task_profile_id,
            "evidence_tier": source["evidence_tier"],
            "runs_considered": [row["run_id"] for row in source["runs"]],
            "cases": [
                {"run_id": row["run_id"], **case}
                for row in source["runs"]
                if row.get("case_table") and row["case_table"].get("available")
                for case in row["case_table"]["cases"]
            ],
            "advice": [item.model_dump(mode="json") for item in found],
        }

    # -- lookups ---------------------------------------------------------

    def _lookup_profile(self, task_profile_id: str) -> Any:
        try:
            return self._profiles.get(task_profile_id)
        except NotFoundError as exc:
            raise GatewayError(str(exc)) from exc

    def _lookup_run(self, run_id: str) -> Any:
        try:
            return self._runs.get(run_id)
        except NotFoundError as exc:
            raise GatewayError(str(exc)) from exc


def _n_min(constraints: dict[str, Any]) -> int | None:
    """Episodes the declared collision risk requires (rule of three).

    Recomputed rather than read: the stored profile keeps the risk, and
    deriving the count here means the two can never disagree.
    """
    risk = constraints.get("collision_probability_max")
    if not isinstance(risk, (int, float)) or risk <= 0:
        return None
    from math import ceil

    return ceil(3 / risk)


def _local_config(spec: dict[str, Any]) -> str | None:
    local = spec.get("local_controller")
    if isinstance(local, dict):
        return local.get("config") or local.get("name")
    return None
