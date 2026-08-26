"""PostgreSQL persistence (M10).

Selected by ``PLANBENCH_DATABASE_URL``. Empty keeps the in-memory
backend, so development and the test suite need no database at all.

Both backends return the same ``Stored*`` dataclasses and satisfy the
same ports (`planbench_api.repository_ports`), so nothing above the
repository layer knows which one is running.
"""

from planbench_api.db.models import (
    ApprovalRow,
    Base,
    BenchmarkRow,
    EpisodeRow,
    MapRow,
    ScenarioRow,
    SimulationRow,
)
from planbench_api.db.repositories import SqlRepositoryHub
from planbench_api.db.session import (
    DatabaseUnavailable,
    SessionFactory,
    create_all,
    create_db_engine,
    normalise_url,
)

__all__ = [
    "ApprovalRow",
    "Base",
    "BenchmarkRow",
    "DatabaseUnavailable",
    "EpisodeRow",
    "MapRow",
    "ScenarioRow",
    "SessionFactory",
    "SimulationRow",
    "SqlRepositoryHub",
    "create_all",
    "create_db_engine",
    "normalise_url",
]
