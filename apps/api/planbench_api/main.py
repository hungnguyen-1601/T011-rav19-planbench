"""FastAPI application factory.

Run locally (core packages are resolved from source via PYTHONPATH):

    PYTHONPATH="packages/schemas:packages/planning:packages/metrics:\
packages/benchmark:services/simulator:apps/api" \
        .venv/bin/uvicorn planbench_api.main:app --port 8000
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from planbench_agent import KnowledgeBase, build_provider, load_markdown_directory
from planbench_api.artifacts import FileSystemArtifactStore
from planbench_api.auth import UserDirectory
from planbench_api.config import get_settings
from planbench_api.db import (
    SessionFactory,
    SqlRepositoryHub,
    create_all,
    create_db_engine,
)
from planbench_api.errors import register_error_handlers
from planbench_api.logging_config import configure_logging
from planbench_api.repositories import RepositoryHub
from planbench_api.routers import (
    agent,
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
REPO_ROOT = Path(__file__).resolve().parents[3]


def _build_repositories(settings, artifacts, app: FastAPI):
    """In-memory unless a database URL is configured.

    In-memory stays the default on purpose: a checkout with no database
    still runs the whole API and the whole test suite, so an unreachable
    database can never masquerade as an unrelated regression.
    """
    if not settings.database_url:
        app.state.sessions = None
        return RepositoryHub(artifacts)

    engine = create_db_engine(settings.database_url, echo=settings.db_echo)
    sessions = SessionFactory(engine)
    if settings.db_create_all:
        create_all(engine)
    app.state.sessions = sessions
    logging.getLogger("planbench.api").info(
        "persistence: SQL", extra={"context": {"dialect": engine.dialect.name}}
    )
    return SqlRepositoryHub(sessions, artifacts)


def _build_knowledge(settings) -> KnowledgeBase | None:
    """Index the configured documentation directories once, at startup.

    Indexing is not on the request path: the corpus is static for the
    process, and rebuilding it per request would make retrieval results
    depend on timing.
    """
    directories = [
        part.strip() for part in settings.agent_knowledge_dirs.split(",") if part.strip()
    ]
    if not directories:
        return None
    chunks: list = []
    for directory in directories:
        path = Path(directory)
        chunks.extend(load_markdown_directory(path if path.is_absolute() else REPO_ROOT / path))
    return KnowledgeBase(chunks) if chunks else None


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
    app.state.repos = _build_repositories(settings, artifacts, app)
    app.state.users = UserDirectory(settings)
    app.state.jobs = JobQueue(settings.worker_concurrency)
    app.state.tracker = build_tracker(settings.mlflow_tracking_uri, settings.mlflow_experiment)
    app.state.agent_provider = build_provider(
        settings.agent_provider,
        model=settings.agent_model or None,
        base_url=settings.agent_base_url or None,
    )
    app.state.agent_knowledge = _build_knowledge(settings)
    app.state.agent_max_episodes = settings.agent_max_episodes
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
    app.include_router(agent.router, prefix=API_PREFIX)
    app.include_router(ws.router)  # websockets are not under /api/v1
    return app


app = create_app()
