"""FastAPI application factory.

Run locally (core packages are resolved from source via PYTHONPATH):

    PYTHONPATH="packages/schemas:packages/planning:packages/metrics:\
packages/benchmark:services/simulator:apps/api" \
        .venv/bin/uvicorn planbench_api.main:app --port 8000
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from planbench_api.artifacts import FileSystemArtifactStore
from planbench_api.auth import UserDirectory
from planbench_api.config import get_settings
from planbench_api.errors import register_error_handlers
from planbench_api.logging_config import configure_logging
from planbench_api.repositories import RepositoryHub
from planbench_api.routers import (
    algorithms,
    auth,
    benchmarks,
    episodes,
    health,
    library,
    maps,
    scenarios,
    simulations,
    ws,
)
from planbench_api.worker import JobQueue
from planbench_tracking import build_tracker

API_PREFIX = "/api/v1"


def create_app(artifact_dir: str | None = None) -> FastAPI:
    settings = get_settings()
    configure_logging(settings.debug)
    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )
    artifacts = FileSystemArtifactStore(artifact_dir or settings.artifact_dir)
    app.state.artifacts = artifacts
    app.state.repos = RepositoryHub(artifacts)
    app.state.users = UserDirectory(settings)
    app.state.jobs = JobQueue(settings.worker_concurrency)
    app.state.tracker = build_tracker(settings.mlflow_tracking_uri, settings.mlflow_experiment)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)
    app.include_router(health.router, prefix=API_PREFIX)
    app.include_router(auth.router, prefix=API_PREFIX)
    app.include_router(maps.router, prefix=API_PREFIX)
    app.include_router(scenarios.router, prefix=API_PREFIX)
    app.include_router(algorithms.router, prefix=API_PREFIX)
    app.include_router(simulations.router, prefix=API_PREFIX)
    app.include_router(benchmarks.router, prefix=API_PREFIX)
    app.include_router(episodes.router, prefix=API_PREFIX)
    app.include_router(library.router, prefix=API_PREFIX)
    app.include_router(ws.router)  # websockets are not under /api/v1
    return app


app = create_app()
