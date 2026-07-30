"""FastAPI dependency wiring (services over the app-scoped repositories)."""

from __future__ import annotations

from fastapi import Request

from planbench_api.repositories import RepositoryHub
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


def get_benchmark_service(request: Request) -> BenchmarkService:
    return BenchmarkService(get_repos(request), request.app.state.tracker, request.app.state.jobs)


def get_benchmark_job_service(request: Request) -> BenchmarkJobService:
    return BenchmarkJobService(get_benchmark_service(request), request.app.state.jobs)


def get_episode_service(request: Request) -> EpisodeService:
    return EpisodeService(get_repos(request))
