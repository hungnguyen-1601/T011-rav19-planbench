"""Episode endpoints: per-run metrics, trajectory, events, replay."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from planbench_api.approval import Role
from planbench_api.auth import User, require_roles
from planbench_api.dependencies import get_episode_service
from planbench_api.repositories import StoredEpisode
from planbench_api.services import EpisodeService
from planbench_benchmark import FailureReport, RunRecord, analyse_episode
from planbench_metrics import EpisodeMetrics
from planbench_planning import PlanResult
from planbench_schemas.episode import EpisodeEvent, EpisodeResult, TrajectoryPoint

router = APIRouter(tags=["episodes"])

Service = Annotated[EpisodeService, Depends(get_episode_service)]
AnyUser = Annotated[User, Depends(require_roles(Role.OPERATOR, Role.REVIEWER))]


class EpisodeSummary(BaseModel):
    id: str
    benchmark_id: str
    algorithm: str
    seed: int
    created_at: str
    record: RunRecord
    artifact_uri: str
    artifact_checksum: str
    artifact_bytes: int


class EpisodeReplay(BaseModel):
    """Everything needed to replay an episode in the UI."""

    id: str
    algorithm: str
    seed: int
    plan_path: tuple[dict, ...]
    trajectory: tuple[TrajectoryPoint, ...]
    events: tuple[EpisodeEvent, ...]
    metrics: EpisodeMetrics


def _summary(stored: StoredEpisode) -> EpisodeSummary:
    return EpisodeSummary(
        id=stored.id,
        benchmark_id=stored.benchmark_id,
        algorithm=stored.algorithm,
        seed=stored.seed,
        created_at=stored.created_at,
        record=stored.record,
        artifact_uri=stored.artifact_uri,
        artifact_checksum=stored.artifact_checksum,
        artifact_bytes=stored.artifact_bytes,
    )


@router.get("/benchmarks/{benchmark_id}/episodes", response_model=list[EpisodeSummary])
def list_episodes(benchmark_id: str, service: Service, _: AnyUser) -> list[EpisodeSummary]:
    return [_summary(stored) for stored in service.list_for_benchmark(benchmark_id)]


@router.get("/episodes/{episode_id}", response_model=EpisodeSummary)
def get_episode(episode_id: str, service: Service, _: AnyUser) -> EpisodeSummary:
    return _summary(service.get(episode_id))


@router.get("/episodes/{episode_id}/result", response_model=EpisodeResult)
def get_episode_result(episode_id: str, service: Service, _: AnyUser) -> EpisodeResult:
    return service.get(episode_id).run.result


@router.get("/episodes/{episode_id}/plan", response_model=PlanResult)
def get_episode_plan(episode_id: str, service: Service, _: AnyUser) -> PlanResult:
    return service.get(episode_id).run.plan


@router.get("/episodes/{episode_id}/failures", response_model=FailureReport)
def analyse_failure(
    episode_id: str, service: Service, request: Request, _: AnyUser
) -> FailureReport:
    """Evidence-based diagnosis of how this episode ended.

    Every finding cites recorded data; nothing is inferred beyond what
    the episode actually contains.
    """
    stored = service.get(episode_id)
    scenario = request.app.state.repos.scenarios.get(
        request.app.state.repos.benchmarks.get(stored.benchmark_id).scenario_id
    ).scenario
    return analyse_episode(
        stored.run.result, scenario, min_clearance=stored.run.metrics.min_clearance
    )


@router.get("/episodes/{episode_id}/replay", response_model=EpisodeReplay)
def replay_episode(episode_id: str, service: Service, _: AnyUser) -> EpisodeReplay:
    stored = service.get(episode_id)
    return EpisodeReplay(
        id=stored.id,
        algorithm=stored.algorithm,
        seed=stored.seed,
        plan_path=tuple({"x": point.x, "y": point.y} for point in stored.run.plan.path),
        trajectory=stored.run.result.trajectory,
        events=stored.run.result.events,
        metrics=stored.run.metrics,
    )
