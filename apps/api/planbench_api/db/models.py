"""SQLAlchemy tables.

Two choices worth stating, because both look odd until you know why.

**Timestamps are ISO-8601 strings, not DATETIME.** The API contract
returns ISO strings, and the in-memory backend stores exactly what it
returns. Storing a native timestamp would mean a format round-trip
(``+00:00`` vs ``Z``, microsecond truncation) that makes the two
backends disagree on a value a client can see. UTC ISO-8601 sorts
lexicographically in chronological order, so ``ORDER BY created_at``
still works. The cost is that SQL date functions need a cast — worth it
for two backends that cannot drift.

**Payloads are JSON columns holding the Pydantic dump.** The domain
models in ``packages/schemas`` are the single source of truth
(contract-first); shredding a Scenario into columns would fork that
definition into a second, silently divergent one. JSONB on PostgreSQL
keeps them queryable.

Large payloads — trajectories, reports — are *not* here. They live in
the artifact store; these tables keep the URI, checksum and size
(decision D15).
"""

from __future__ import annotations

from sqlalchemy import JSON, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

#: JSONB where available, plain JSON elsewhere (SQLite in tests).
JsonColumn = JSON().with_variant(JSONB, "postgresql")

ID_LENGTH = 32
TIMESTAMP_LENGTH = 40


class Base(DeclarativeBase):
    pass


class MapRow(Base):
    __tablename__ = "maps"

    id: Mapped[str] = mapped_column(String(ID_LENGTH), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    resolution: Mapped[float] = mapped_column(Float, nullable=False)
    #: SHA-256 over the map content; two maps with the same checksum are
    #: interchangeable for fairness purposes.
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[str] = mapped_column(String(TIMESTAMP_LENGTH), nullable=False)
    payload: Mapped[dict] = mapped_column(JsonColumn, nullable=False)

    __table_args__ = (Index("ix_maps_checksum", "checksum"),)


class ScenarioRow(Base):
    __tablename__ = "scenarios"

    id: Mapped[str] = mapped_column(String(ID_LENGTH), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # No FK: a scenario must survive its map being deleted, otherwise
    # deleting a map would silently erase benchmark provenance.
    map_id: Mapped[str] = mapped_column(String(ID_LENGTH), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[str] = mapped_column(String(TIMESTAMP_LENGTH), nullable=False)
    payload: Mapped[dict] = mapped_column(JsonColumn, nullable=False)

    __table_args__ = (Index("ix_scenarios_map_id", "map_id"),)


class SimulationRow(Base):
    __tablename__ = "simulations"

    id: Mapped[str] = mapped_column(String(ID_LENGTH), primary_key=True)
    map_id: Mapped[str] = mapped_column(String(ID_LENGTH), nullable=False)
    scenario_id: Mapped[str] = mapped_column(String(ID_LENGTH), nullable=False)
    algorithm: Mapped[str] = mapped_column(String(100), nullable=False)
    config: Mapped[dict] = mapped_column(JsonColumn, nullable=False, default=dict)
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="created")
    created_at: Mapped[str] = mapped_column(String(TIMESTAMP_LENGTH), nullable=False)
    #: Full StackRun dump. Single simulations are one-off and small
    #: enough to keep inline; benchmark episodes are not (see EpisodeRow).
    run: Mapped[dict | None] = mapped_column(JsonColumn, nullable=True)


class BenchmarkRow(Base):
    __tablename__ = "benchmarks"

    id: Mapped[str] = mapped_column(String(ID_LENGTH), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    map_id: Mapped[str] = mapped_column(String(ID_LENGTH), nullable=False)
    scenario_id: Mapped[str] = mapped_column(String(ID_LENGTH), nullable=False)
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[str] = mapped_column(String(TIMESTAMP_LENGTH), nullable=False)
    started_at: Mapped[str | None] = mapped_column(String(TIMESTAMP_LENGTH), nullable=True)
    finished_at: Mapped[str | None] = mapped_column(String(TIMESTAMP_LENGTH), nullable=True)
    spec: Mapped[dict] = mapped_column(JsonColumn, nullable=False)
    #: Metrics-only report. Trajectories are in the artifact store.
    report: Mapped[dict | None] = mapped_column(JsonColumn, nullable=True)
    report_artifact_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Denormalised from the report so the leaderboard can group without
    #: parsing every report body.
    conditions_checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)

    approvals: Mapped[list[ApprovalRow]] = relationship(
        back_populates="benchmark",
        cascade="all, delete-orphan",
        order_by="ApprovalRow.sequence",
    )

    __table_args__ = (
        Index("ix_benchmarks_state", "state"),
        Index("ix_benchmarks_conditions_checksum", "conditions_checksum"),
    )


class ApprovalRow(Base):
    """One human decision. Append-only: the audit trail is the point."""

    __tablename__ = "approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    benchmark_id: Mapped[str] = mapped_column(
        String(ID_LENGTH), ForeignKey("benchmarks.id", ondelete="CASCADE"), nullable=False
    )
    #: Explicit order, because two decisions can share a timestamp at
    #: whatever resolution the clock happens to have.
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    previous_state: Mapped[str] = mapped_column(String(30), nullable=False)
    new_state: Mapped[str] = mapped_column(String(30), nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False, default="")
    timestamp: Mapped[str] = mapped_column(String(TIMESTAMP_LENGTH), nullable=False)

    benchmark: Mapped[BenchmarkRow] = relationship(back_populates="approvals")

    __table_args__ = (Index("ix_approvals_benchmark_id", "benchmark_id"),)


class EpisodeRow(Base):
    """Episode metadata. The trajectory itself lives in artifact storage."""

    __tablename__ = "episodes"

    id: Mapped[str] = mapped_column(String(ID_LENGTH), primary_key=True)
    benchmark_id: Mapped[str] = mapped_column(
        String(ID_LENGTH), ForeignKey("benchmarks.id", ondelete="CASCADE"), nullable=False
    )
    algorithm: Mapped[str] = mapped_column(String(100), nullable=False)
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    episode_index: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[str] = mapped_column(String(TIMESTAMP_LENGTH), nullable=False)
    #: The RunRecord dump: status, reason, metrics, counts.
    record: Mapped[dict] = mapped_column(JsonColumn, nullable=False)
    artifact_uri: Mapped[str] = mapped_column(Text, nullable=False)
    artifact_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        Index("ix_episodes_benchmark_id", "benchmark_id"),
        Index("ix_episodes_benchmark_order", "benchmark_id", "episode_index"),
    )


__all__ = [
    "ApprovalRow",
    "Base",
    "BenchmarkRow",
    "EpisodeRow",
    "JsonColumn",
    "MapRow",
    "ScenarioRow",
    "SimulationRow",
]
