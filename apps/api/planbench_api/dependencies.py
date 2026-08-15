"""FastAPI dependency wiring (services over the app-scoped repositories)."""

from __future__ import annotations

from pathlib import Path
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
    TestBenchService,
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
from planbench_api.worker import JobQueue


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


def get_map_root(request: Request) -> Path:
    """Where a task profile's relative paths resolve.

    Every profile names its map as ``maps/<name>.pgm`` relative to the
    repository root, and storing the profile in a database did not move
    the ``.pgm`` — so anything writing a map for a profile to name has to
    be told where those files live rather than guess.
    """
    return request.app.state.decision_map_root


def get_task_profile_service(request: Request) -> TaskProfileService:
    """Deployments, plus the one place a drawn map becomes one.

    It gets the map repository and the map root because deriving a
    deployment from a custom map writes that map to disk: profiles name
    their map by path (HĐ-2) and the editor stores grids in the database,
    so something has to cross between them.
    """
    state = request.app.state
    return TaskProfileService(
        state.repos.task_profiles,
        maps=state.repos.maps,
        map_root=get_map_root(request),
        runs=state.repos.decision_runs,
    )


def get_test_bench_service(request: Request) -> TestBenchService:
    """One episode of a deployment, watched live.

    It gets the whole repository hub because staging crosses three
    stores — the deployment it reads, the map and scenario it
    materialises, and the simulation the WebSocket then streams.
    """
    return TestBenchService(request.app.state.repos, map_root=get_map_root(request))


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


def get_decision_jobs(request: Request) -> JobQueue:
    """The single-slot queue selection sweeps run in.

    Separate from ``app.state.jobs``, which benchmark runs share and
    which is sized for throughput. This one holds **one** job because
    HĐ-7.4 forbids two evaluation runs on a machine at once: they pin the
    same cores, each becomes the other's background load, and G4 — which
    reads wall-clock latency — then measures a machine that does not
    exist. The bound is a correctness property, not a capacity choice.
    """
    return request.app.state.decision_jobs
