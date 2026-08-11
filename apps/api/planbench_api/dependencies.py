"""FastAPI dependency wiring (services over the app-scoped repositories)."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from planbench_agent import AgentService
from planbench_agent.tools import ToolPolicy
from planbench_api.agent_gateway import ApiAgentGateway
from planbench_api.auth import CurrentUser
from planbench_api.chat_service import ChatService
from planbench_api.decision_service import (
    CandidateService,
    DecisionRunService,
    TaskProfileService,
)
from planbench_api.registry_service import ModelRegistryService, RobotProfileService
from planbench_api.repositories import RepositoryHub
from planbench_api.review_service import ReviewService
from planbench_api.services import (
    BenchmarkJobService,
    BenchmarkService,
    EpisodeService,
    MapService,
    ScenarioService,
    SimulationService,
)


def get_repos(request: Request) -> RepositoryHub:
    return request.app.state.repos


def get_map_service(request: Request) -> MapService:
    return MapService(get_repos(request))


def get_scenario_service(request: Request) -> ScenarioService:
    return ScenarioService(get_repos(request))


def get_simulation_service(request: Request) -> SimulationService:
    return SimulationService(get_repos(request))


def get_profile_service(request: Request) -> RobotProfileService:
    return RobotProfileService(get_repos(request).robot_profiles)


def get_model_service(request: Request) -> ModelRegistryService:
    repos = get_repos(request)
    return ModelRegistryService(repos.models, repos.robot_profiles, request.app.state.model_storage)


def get_review_service(request: Request) -> ReviewService:
    repos = get_repos(request)
    return ReviewService(repos.reviews, repos.users, repos.benchmarks)


def get_benchmark_service(request: Request) -> BenchmarkService:
    """The benchmark service, wired to reviews.

    It needs them: whether the owner may run or accept depends on
    whether a review is pending, and that question is only answerable
    from stored requests.
    """
    return BenchmarkService(
        get_repos(request),
        request.app.state.tracker,
        request.app.state.jobs,
        reviews=get_review_service(request),
        models=get_model_service(request),
    )


def get_benchmark_job_service(request: Request) -> BenchmarkJobService:
    return BenchmarkJobService(get_benchmark_service(request), request.app.state.jobs)


def get_chat_service(request: Request) -> ChatService:
    repos = get_repos(request)
    return ChatService(
        repos,
        get_model_service(request),
        get_profile_service(request),
        get_benchmark_service(request),
    )


def get_episode_service(request: Request) -> EpisodeService:
    return EpisodeService(get_repos(request))


def get_agent_service(request: Request, user: CurrentUser) -> AgentService:
    """An agent bound to the calling user.

    Constructed per request so the gateway acts as that user: benchmarks
    the agent creates are attributed to a real person, and separation of
    duties still applies to whoever approves them. The provider and the
    knowledge index are app-scoped and shared.
    """
    gateway = ApiAgentGateway(
        repos=get_repos(request),
        benchmarks=get_benchmark_service(request),
        maps=get_map_service(request),
        scenarios=get_scenario_service(request),
        user=user,
    )
    return AgentService(
        provider=request.app.state.agent_provider,
        gateway=gateway,
        knowledge=request.app.state.agent_knowledge,
        policy=ToolPolicy(max_episodes=request.app.state.agent_max_episodes),
    )


AgentDependency = Annotated[AgentService, Depends(get_agent_service)]


def get_task_profile_service(request: Request) -> TaskProfileService:
    return TaskProfileService(request.app.state.repos.task_profiles)


def get_candidate_service(request: Request) -> CandidateService:
    return CandidateService(request.app.state.repos.candidates)


def get_decision_run_service(request: Request) -> DecisionRunService:
    """The selection runner, pointed at this instance's directories.

    ``repo_root`` is where maps live: every path inside a task profile is
    relative to it, and storing the profile in a database did not move
    its ``.pgm``.
    """
    state = request.app.state
    return DecisionRunService(
        state.repos.decision_runs,
        get_task_profile_service(request),
        repo_root=state.decision_map_root,
        trace_root=state.decision_trace_dir,
        run_root=state.decision_run_dir,
    )
