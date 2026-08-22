"""The narrow port between the agent and the rest of PlanBench.

The agent service must not import the FastAPI application: that would
invert the dependency (core-first) and make every agent test require an
HTTP app. Instead it declares the operations it needs as a Protocol, and
``planbench_api.agent_gateway`` supplies the adapter.

Two consequences worth stating:

- The tool surface is exactly this protocol. There is deliberately no
  method for driving the robot, writing ``/cmd_vel``, editing a map,
  approving a run or accepting a result — the agent physically cannot
  reach them.
- Tests substitute a fake gateway and exercise the whole agent, tool
  policy included, without a server.

**This port is read-only.** Every write the previous version offered
created a benchmark in a UI that no longer exists, so removing them cost
nothing and closed the gap between what the agent could do and what a
person could see it do. Proposing an experiment is a person's job on the
decisions page; the agent's job is to read what came back and argue with
it.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict


class ScenarioSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    curriculum_index: int
    dynamic_obstacles: int
    timeout_seconds: float


class CandidateSummary(BaseModel):
    """One configuration a comparison may choose between (HĐ-1).

    ``candidate_id`` is a hash of the configuration, not a name somebody
    picked, which is why it is safe to quote in a finding: two runs
    naming the same id ran the same thing.
    """

    model_config = ConfigDict(frozen=True)

    candidate_id: str
    stack_label: str
    local_controller_config: str | None = None
    observation_requirements: tuple[str, ...] = ()


class DeploymentSummary(BaseModel):
    """A world the platform is asked to measure something in (HĐ-2)."""

    model_config = ConfigDict(frozen=True)

    task_profile_id: str
    environment: str
    missions: int = 0
    n_min_episodes: int | None = None
    created_at: str = ""


class DecisionRunSummary(BaseModel):
    """One comparison. ``ranked`` false is a result, not an error.

    Fewer than two candidates through the gates means no ΔU and no card;
    the gate table is then the whole deliverable. A summary that hid that
    case would make an honest outcome look like a missing one.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    task_profile_id: str
    experiment_scope: str | None = None
    created_at: str = ""
    created_by: str | None = None
    ranked: bool = False
    recommended_candidate_id: str | None = None
    status: str | None = None
    review_state: str = "unreviewed"
    config_state: str = "not_applicable"


class GatewayError(Exception):
    """The platform refused. Carries a message meant for the transcript."""


@runtime_checkable
class AgentGateway(Protocol):
    """Everything the agent is allowed to do to PlanBench.

    Read-only by construction: there is no write method to gate, so
    there is no write path to get wrong.
    """

    # -- what can be compared, and in which world ------------------------
    def list_deployments(self) -> list[DeploymentSummary]: ...

    def get_deployment(self, task_profile_id: str) -> dict[str, Any]:
        """The full profile: constraints, hardware, sensor noise, missions.

        Returned raw rather than as a model because the agent quotes
        fields from it by path, and a lossy summary would let it cite a
        field this layer had dropped.
        """
        ...

    def list_candidates(self) -> list[CandidateSummary]: ...

    def list_scenarios(self) -> list[ScenarioSummary]: ...

    # -- what came back ---------------------------------------------------
    def list_decision_runs(
        self, task_profile_id: str | None = None
    ) -> list[DecisionRunSummary]: ...

    def get_decision_run(self, run_id: str) -> dict[str, Any]:
        """The stored ``comparison_report``, whole.

        Whole for the same reason as the profile: every objection the
        agent raises has to cite a path that resolves in this dict, and
        a trimmed copy would make honest citations unresolvable.
        """
        ...

    def get_decision_card(self, run_id: str) -> dict[str, Any] | None:
        """The recommendation, or None when the run ranked nobody."""
        ...

    def get_gate_table(self, run_id: str) -> list[dict[str, Any]]:
        """Per-candidate G1–G6, including who was eliminated where.

        Separate from the report because it is the one part of an
        unranked run that still answers a question, and asking for it
        should not mean paging in every episode row.
        """
        ...

    def get_critique(self, run_id: str) -> list[dict[str, Any]]:
        """What the deterministic rules already object to (self_check).

        The agent reads this so it can say something *else*. Handing a
        model the rules' output is what keeps its own findings additive
        rather than a paraphrase of work already done.
        """
        ...

    def get_outcome(self, run_id: str) -> list[dict[str, Any]]:
        """Why the run ended as it did: numbers joined to algorithm natures.

        Deterministic rules produce this (outcome_advice); the agent
        reads it so its own narrative starts from grounded findings —
        which metric separated the field, who was eliminated rather than
        beaten — instead of from the model's recollection of what A* is.
        """
        ...

    def get_recommendation(self, task_profile_id: str | None = None) -> dict[str, Any]:
        """Which algorithm this deployment should use, from stored runs.

        The deterministic recommendation rules — feasibility on this
        profile first, then the stored cards, then the per-mission
        split. The agent reads this so "which should I pick" is answered
        by the same floor a person sees on the deployment page, never by
        the model's own weighing of the evidence.

        ``task_profile_id`` may be omitted when exactly one deployment
        exists; with several, the gateway refuses and names them, which
        is an answer the model can relay rather than a guess it must
        make.
        """
        ...


__all__ = [
    "AgentGateway",
    "CandidateSummary",
    "DecisionRunSummary",
    "DeploymentSummary",
    "GatewayError",
    "ScenarioSummary",
]
