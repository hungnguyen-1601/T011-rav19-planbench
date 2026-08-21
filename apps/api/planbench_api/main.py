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
from planbench_api.auth import AuthService
from planbench_api.config import get_settings
from planbench_api.db import (
    SessionFactory,
    SqlRepositoryHub,
    create_all,
    create_db_engine,
)
from planbench_api.errors import register_error_handlers
from planbench_api.logging_config import configure_logging
from planbench_api.model_storage import LocalModelStorage
from planbench_api.oauth import ExchangeCodes, OAuthClient
from planbench_api.repositories import RepositoryHub
from planbench_api.routers import (
    agent,
    algorithms,
    auth,
    benchmarks,
    chat,
    decisions,
    episodes,
    health,
    library,
    maps,
    models,
    reviews,
    scenarios,
    simulations,
    tuning,
    users,
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
    # Uploaded checkpoints. Separate from the artifact store because the
    # lifecycles differ: artifacts belong to a run, models outlive many.
    app.state.model_storage = LocalModelStorage(settings.model_dir)
    # Decision layer (Phase 6.2). The roots follow `artifact_dir` when a
    # caller overrides it — a test passing its own artifact root must not
    # have selection runs land in the developer's checkout — but an
    # explicit PLANBENCH_DECISION_TRACE_DIR wins over both.
    #
    # That last clause was missing until 2026-08-12, and the setting was
    # dead: `config.py` declares both fields and documents their default,
    # and this line then overwrote whatever they said, on every call. A
    # configuration knob that silently does nothing is worse than one
    # that does not exist, because somebody sets it and believes it.
    #
    # It also has a cost the tests pay. Trace paths are content hashes
    # (HĐ-1.3, HĐ-3.1), so a shared trace root is exactly what makes
    # `--reuse-traces` safe — but with the root pinned to a per-test
    # temporary directory, every test re-simulated episodes another test
    # had already run.
    decision_root = Path(artifact_dir) if artifact_dir else Path(settings.artifact_dir)
    app.state.decision_map_root = Path(settings.map_root)
    app.state.decision_trace_dir = (
        Path(settings.decision_trace_dir)
        if settings.decision_trace_dir
        else decision_root / "traces"
    )
    app.state.decision_run_dir = (
        Path(settings.decision_run_dir) if settings.decision_run_dir else decision_root / "runs"
    )
    app.state.repos = _build_repositories(settings, artifacts, app)
    app.state.auth = AuthService(settings, app.state.repos.users)
    # One-time codes and the provider HTTP client are app-scoped: the
    # codes must outlive a request, and the client is replaced wholesale
    # in tests so no OAuth test ever reaches the network.
    app.state.oauth_codes = ExchangeCodes()
    app.state.oauth_client = OAuthClient()
    app.state.jobs = JobQueue(settings.worker_concurrency)
    # A separate queue for selection runs, and it holds exactly one job.
    #
    # **One, because the contract says so.** HĐ-7.4 forbids two
    # evaluation runs on one machine at once: both pin the same cores, so
    # each becomes the other's background load and G4 — which reads
    # wall-clock latency — measures a machine that does not exist. The
    # same stack has been measured at 59.30 ms unpinned and 16.10 ms
    # pinned to two cores. A second slot here would let the API produce
    # exactly the corruption the pinning exists to prevent.
    #
    # Separate from `jobs`, because that queue is shared with benchmark
    # runs and sized for throughput. Parking a three-hour selection in it
    # would starve them, and shrinking it to one would starve everything
    # else. Two queues, two different jobs, two different bounds.
    app.state.decision_jobs = JobQueue(1)
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
        # Without this the browser hides `Content-Disposition` from
        # JavaScript on any cross-origin read — and the web app is on a
        # different port from the API in every local setup. The download
        # helper then cannot see the filename the server chose and falls
        # back to one it guessed, which is how the Excel export came to
        # save itself as `.md`.
        expose_headers=["Content-Disposition"],
    )
    register_error_handlers(app)
    app.include_router(health.router, prefix=API_PREFIX)
    app.include_router(auth.router, prefix=API_PREFIX)
    app.include_router(users.router, prefix=API_PREFIX)
    app.include_router(reviews.router, prefix=API_PREFIX)
    app.include_router(maps.router, prefix=API_PREFIX)
    app.include_router(scenarios.router, prefix=API_PREFIX)
    app.include_router(algorithms.router, prefix=API_PREFIX)
    app.include_router(tuning.router, prefix=API_PREFIX)
    app.include_router(simulations.router, prefix=API_PREFIX)
    app.include_router(benchmarks.router, prefix=API_PREFIX)
    app.include_router(episodes.router, prefix=API_PREFIX)
    app.include_router(library.router, prefix=API_PREFIX)
    app.include_router(models.router, prefix=API_PREFIX)
    app.include_router(decisions.router, prefix=API_PREFIX)
    app.include_router(chat.router, prefix=API_PREFIX)
    app.include_router(agent.router, prefix=API_PREFIX)
    app.include_router(ws.router)  # websockets are not under /api/v1
    return app


app = create_app()
