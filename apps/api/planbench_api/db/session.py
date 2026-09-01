"""Engine and session management.

The engine is created once per application and handed to the
repositories; nothing here is global state, so two apps in one process
(as the test suite does) never share a connection pool.

Driver imports stay lazy: a checkout without ``psycopg`` still runs
every test against SQLite, and only a request for a ``postgresql://``
URL surfaces the missing driver — with the install command in the
message rather than a bare ``ModuleNotFoundError``.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from planbench_api.db.models import Base

logger = logging.getLogger("planbench.api.db")

POSTGRES_DRIVER_HINT = (
    "PostgreSQL support needs the psycopg driver: `.venv/bin/pip install "
    "'psycopg[binary]'` (the Docker image installs it already)."
)


class DatabaseUnavailable(RuntimeError):
    """The configured database cannot be reached or its driver is missing."""


def normalise_url(url: str) -> str:
    """Accept the common ``postgres://`` alias and pin the v3 driver.

    Managed providers hand out ``postgres://`` URLs, which SQLAlchemy
    rejects. Rewriting here means an operator can paste the URL they
    were given.
    """
    if url.startswith("postgres://"):
        url = "postgresql://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url


def create_db_engine(url: str, *, echo: bool = False) -> Engine:
    """Build an engine for ``url``, with sane defaults per backend."""
    url = normalise_url(url)
    if url.startswith("postgresql"):
        try:
            import psycopg  # noqa: F401
        except ImportError as exc:
            raise DatabaseUnavailable(POSTGRES_DRIVER_HINT) from exc
        engine = create_engine(
            url,
            echo=echo,
            pool_pre_ping=True,  # a recycled connection killed server-side fails fast
            pool_size=5,
            max_overflow=5,
        )
    else:
        engine = create_engine(url, echo=echo)
        if url.startswith("sqlite"):
            _enable_sqlite_foreign_keys(engine)
    return engine


def _enable_sqlite_foreign_keys(engine: Engine) -> None:
    """SQLite ignores foreign keys unless asked, per connection.

    Without this the cascade on ``approvals``/``episodes`` would appear
    to work in tests and only be enforced in production — the worst
    possible split between the two backends.
    """

    @event.listens_for(engine, "connect")
    def _set_pragma(connection, _record) -> None:  # noqa: ANN001 - DBAPI object
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def create_all(engine: Engine) -> None:
    """Create the schema directly.

    For tests and throwaway SQLite files. A deployment uses Alembic, so
    that schema changes are reviewable and reversible — see
    ``docs/reference/DEPLOYMENT.md``.
    """
    Base.metadata.create_all(engine)


class SessionFactory:
    """Hands out short-lived sessions, one transaction each."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._maker = sessionmaker(bind=engine, expire_on_commit=False)

    @property
    def engine(self) -> Engine:
        return self._engine

    @contextmanager
    def begin(self) -> Iterator[Session]:
        """A session wrapped in one transaction: commit or roll back.

        Repository methods use one of these each, so a failed write can
        never leave a half-updated benchmark behind.
        """
        session = self._maker()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def dispose(self) -> None:
        self._engine.dispose()


__all__ = [
    "POSTGRES_DRIVER_HINT",
    "DatabaseUnavailable",
    "SessionFactory",
    "create_all",
    "create_db_engine",
    "normalise_url",
]
