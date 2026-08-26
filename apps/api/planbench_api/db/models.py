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

from sqlalchemy import (
    JSON,
    Boolean,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

#: JSONB where available, plain JSON elsewhere (SQLite in tests).
JsonColumn = JSON().with_variant(JSONB, "postgresql")

ID_LENGTH = 32
TIMESTAMP_LENGTH = 40


class Base(DeclarativeBase):
    pass


class UserRow(Base):
    """A member account.

    ``nickname_key`` is the case-folded form and carries the unique
    index; ``nickname`` keeps the capitalisation the person chose. A
    functional index on ``lower(nickname)`` would work on PostgreSQL and
    not on SQLite, so the key is a real column instead.

    It is nullable because an account created by OAuth exists before its
    owner has picked a nickname, and several such accounts can be
    part-way through onboarding at once — a unique index treats multiple
    NULLs as distinct on both backends, which is exactly what is needed.
    """

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(ID_LENGTH), primary_key=True)
    nickname: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    nickname_key: Mapped[str | None] = mapped_column(String(30), nullable=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, default="")
    display_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    avatar_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    #: Only set for accounts usable with the development password login.
    password_hash: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[str] = mapped_column(String(TIMESTAMP_LENGTH), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(TIMESTAMP_LENGTH), nullable=False)

    __table_args__ = (UniqueConstraint("nickname_key", name="uq_users_nickname_key"),)


class OAuthAccountRow(Base):
    """A provider identity bound to one account.

    The unique constraint on (provider, provider_account_id) is the
    guarantee that one Google or GitHub identity cannot be attached to
    two PlanBench accounts.
    """

    __tablename__ = "oauth_accounts"

    id: Mapped[str] = mapped_column(String(ID_LENGTH), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(ID_LENGTH), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_account_id: Mapped[str] = mapped_column(String(200), nullable=False)
    provider_email: Mapped[str] = mapped_column(String(320), nullable=False, default="")
    created_at: Mapped[str] = mapped_column(String(TIMESTAMP_LENGTH), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(TIMESTAMP_LENGTH), nullable=False)

    __table_args__ = (
        UniqueConstraint("provider", "provider_account_id", name="uq_oauth_provider_account"),
        Index("ix_oauth_accounts_user_id", "user_id"),
    )


class ReviewRequestRow(Base):
    """One request for a second opinion on a benchmark."""

    __tablename__ = "review_requests"

    id: Mapped[str] = mapped_column(String(ID_LENGTH), primary_key=True)
    benchmark_id: Mapped[str] = mapped_column(
        String(ID_LENGTH), ForeignKey("benchmarks.id", ondelete="CASCADE"), nullable=False
    )
    stage: Mapped[str] = mapped_column(String(10), nullable=False)
    requested_by_user_id: Mapped[str] = mapped_column(String(ID_LENGTH), nullable=False)
    reviewer_user_id: Mapped[str] = mapped_column(String(ID_LENGTH), nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False)
    request_comment: Mapped[str] = mapped_column(Text, nullable=False, default="")
    review_comment: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[str] = mapped_column(String(TIMESTAMP_LENGTH), nullable=False)
    reviewed_at: Mapped[str | None] = mapped_column(String(TIMESTAMP_LENGTH), nullable=True)
    cancelled_at: Mapped[str | None] = mapped_column(String(TIMESTAMP_LENGTH), nullable=True)

    __table_args__ = (
        Index("ix_review_requests_benchmark_id", "benchmark_id"),
        # The inbox query: my pending requests, newest first.
        Index("ix_review_requests_reviewer", "reviewer_user_id", "status"),
        Index("ix_review_requests_requester", "requested_by_user_id"),
    )


class RobotProfileRow(Base):
    """The robot a model was trained for, and a benchmark runs.

    Exists so swapping robots is a form, not a code edit — the PPO
    adapter reads limits from here rather than from constants.
    """

    __tablename__ = "robot_profiles"

    id: Mapped[str] = mapped_column(String(ID_LENGTH), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[str] = mapped_column(String(40), nullable=False, default="1")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    radius: Mapped[float] = mapped_column(Float, nullable=False)
    footprint: Mapped[str] = mapped_column(String(40), nullable=False, default="circle")
    max_linear_velocity: Mapped[float] = mapped_column(Float, nullable=False)
    max_angular_velocity: Mapped[float] = mapped_column(Float, nullable=False)
    # Nullable because a profile written before these existed never
    # declared them, and NULL is the recorded truth rather than a value
    # waiting to be backfilled — the same reasoning as 0004's replanning
    # column. Substituting a number would put a physical claim about
    # somebody's vehicle into the database with nobody's name on it.
    max_linear_acceleration: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_angular_acceleration: Mapped[float | None] = mapped_column(Float, nullable=True)
    lidar_beams: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    lidar_range: Mapped[float] = mapped_column(Float, nullable=False, default=6.0)
    observation_type: Mapped[str] = mapped_column(String(60), nullable=False)
    action_type: Mapped[str] = mapped_column(String(60), nullable=False)
    created_by_user_id: Mapped[str] = mapped_column(String(ID_LENGTH), nullable=False, default="")
    created_at: Mapped[str] = mapped_column(String(TIMESTAMP_LENGTH), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(TIMESTAMP_LENGTH), nullable=False)

    __table_args__ = (Index("ix_robot_profiles_owner", "created_by_user_id"),)


class ModelRow(Base):
    """One uploaded, trained policy.

    The binary never lands here — only `storage_key` plus the checksum,
    so "which model produced these numbers?" has an answer that survives
    the file being replaced (decision D15 again).
    """

    __tablename__ = "models"

    id: Mapped[str] = mapped_column(String(ID_LENGTH), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[str] = mapped_column(String(40), nullable=False, default="1")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    algorithm_type: Mapped[str] = mapped_column(String(40), nullable=False, default="ppo")
    framework: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    framework_version: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    storage_key: Mapped[str] = mapped_column(Text, nullable=False, default="")
    original_filename: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    uploaded_by_user_id: Mapped[str] = mapped_column(String(ID_LENGTH), nullable=False, default="")
    robot_profile_id: Mapped[str] = mapped_column(String(ID_LENGTH), nullable=False, default="")
    observation_schema: Mapped[dict] = mapped_column(JsonColumn, nullable=False)
    action_schema: Mapped[dict] = mapped_column(JsonColumn, nullable=False)
    training_environment: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    training_steps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    validation_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    validation_message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[str] = mapped_column(String(TIMESTAMP_LENGTH), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(TIMESTAMP_LENGTH), nullable=False)

    __table_args__ = (
        Index("ix_models_owner", "uploaded_by_user_id"),
        Index("ix_models_status", "status", "validation_status"),
        # Two models may share a name only if their versions differ.
        UniqueConstraint("uploaded_by_user_id", "name", "version", name="uq_models_name_version"),
    )


class ModelDocumentRow(Base):
    """A metadata sidecar or a PDF attached to a model.

    Separate from the model row because these are *not* the model: a PDF
    is documentation and a JSON is a description. Keeping them in their
    own table makes it structurally impossible to run one.
    """

    __tablename__ = "model_documents"

    id: Mapped[str] = mapped_column(String(ID_LENGTH), primary_key=True)
    model_id: Mapped[str] = mapped_column(
        String(ID_LENGTH), ForeignKey("models.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(200), nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    created_at: Mapped[str] = mapped_column(String(TIMESTAMP_LENGTH), nullable=False)

    __table_args__ = (Index("ix_model_documents_model", "model_id"),)


class ModelUsageRow(Base):
    """Which benchmark used which model, at which checksum.

    Written when a benchmark runs. Answers "can I delete this model?"
    without a scan, and "exactly what ran?" after the fact — the
    checksum is recorded at use time, so a later re-upload cannot
    rewrite history.
    """

    __tablename__ = "model_usages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_id: Mapped[str] = mapped_column(String(ID_LENGTH), nullable=False)
    benchmark_id: Mapped[str] = mapped_column(String(ID_LENGTH), nullable=False)
    model_version: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    model_checksum: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    created_at: Mapped[str] = mapped_column(String(TIMESTAMP_LENGTH), nullable=False)

    __table_args__ = (
        Index("ix_model_usages_model", "model_id"),
        Index("ix_model_usages_benchmark", "benchmark_id"),
    )


class ConversationRow(Base):
    """One chat with the assistant."""

    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(ID_LENGTH), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(ID_LENGTH), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    locale: Mapped[str] = mapped_column(String(8), nullable=False, default="en")
    created_at: Mapped[str] = mapped_column(String(TIMESTAMP_LENGTH), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(TIMESTAMP_LENGTH), nullable=False)

    messages: Mapped[list[ConversationMessageRow]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ConversationMessageRow.sequence",
    )

    __table_args__ = (Index("ix_conversations_user", "user_id", "updated_at"),)


class ConversationMessageRow(Base):
    """One turn. Append-only: a transcript that can be edited is not one."""

    __tablename__ = "conversation_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(
        String(ID_LENGTH), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    #: A benchmark proposal or a result card, when the turn produced one.
    payload: Mapped[dict | None] = mapped_column(JsonColumn, nullable=True)
    created_at: Mapped[str] = mapped_column(String(TIMESTAMP_LENGTH), nullable=False)

    conversation: Mapped[ConversationRow] = relationship(back_populates="messages")

    __table_args__ = (Index("ix_conversation_messages_conversation", "conversation_id"),)


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
    #: ``ReplanningConfig`` dump, or NULL on rows written before the rule
    #: could be set here. NULL reads back as disabled, which is what
    #: those runs actually did — a default of "enabled" would rewrite
    #: history, and NOT NULL would break the upgrade.
    replanning: Mapped[dict | None] = mapped_column(JsonColumn, nullable=True)


class BenchmarkRow(Base):
    __tablename__ = "benchmarks"

    id: Mapped[str] = mapped_column(String(ID_LENGTH), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    map_id: Mapped[str] = mapped_column(String(ID_LENGTH), nullable=False)
    scenario_id: Mapped[str] = mapped_column(String(ID_LENGTH), nullable=False)
    #: Display name of the creator, kept for rows written before
    #: accounts existed.
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    #: The identity authorization actually uses. NULL on benchmarks
    #: created before the accounts refactor — see approval.py.
    owner_user_id: Mapped[str | None] = mapped_column(String(ID_LENGTH), nullable=True)
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
        Index("ix_benchmarks_owner", "owner_user_id"),
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
    #: Nickname at the time of the decision — readable after a rename.
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    #: The identity that acted. NULL on rows written before accounts
    #: existed, which is why nothing keys off it retroactively.
    user_id: Mapped[str | None] = mapped_column(String(ID_LENGTH), nullable=True)
    #: Set when the decision answered a review request.
    review_request_id: Mapped[str | None] = mapped_column(String(ID_LENGTH), nullable=True)
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


class TaskProfileRow(Base):
    """One deployment as declared (HĐ-2).

    The whole profile is stored as JSON rather than as columns. It is a
    frozen Pydantic model that the decision layer validates on the way
    in, and shredding it into columns would create a second definition of
    HĐ-2 that drifts from the first — the failure §16 exists to prevent.
    What *is* promoted to columns is what queries need: the id, the
    environment, and who owns it.
    """

    __tablename__ = "task_profiles"

    id: Mapped[str] = mapped_column(String(ID_LENGTH), primary_key=True)
    environment: Mapped[str] = mapped_column(String(200), nullable=False)
    owner_user_id: Mapped[str | None] = mapped_column(String(ID_LENGTH), nullable=True)
    created_at: Mapped[str] = mapped_column(String(TIMESTAMP_LENGTH), nullable=False)
    profile: Mapped[dict] = mapped_column(JsonColumn, nullable=False)

    __table_args__ = (Index("ix_task_profiles_owner", "owner_user_id"),)


class CandidateRow(Base):
    """One registered candidate, keyed by its own content hash (HĐ-1.3).

    ``candidate_id`` is the primary key, not a surrogate: it is a hash of
    the planner, the controller, the parameters, the code version and the
    observation requirements, so two rows with the same id are the same
    configuration by construction and an autoincrement key would let the
    same stack be registered twice under two names.

    ``tuning`` is nullable because HĐ-1.6 lets a candidate decline to
    declare its tuning cost — and the objectives layer charges it for
    that (a profile weighting engineering cost refuses to score it),
    which is the honest handling and not something the schema should
    pre-empt.
    """

    __tablename__ = "candidates"

    candidate_id: Mapped[str] = mapped_column(String(ID_LENGTH), primary_key=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    stack_label: Mapped[str] = mapped_column(String(200), nullable=False)
    registered_by: Mapped[str | None] = mapped_column(String(ID_LENGTH), nullable=True)
    created_at: Mapped[str] = mapped_column(String(TIMESTAMP_LENGTH), nullable=False)
    spec: Mapped[dict] = mapped_column(JsonColumn, nullable=False)
    #: HĐ-1.6's declaration, with its evidence log. NULL means undeclared.
    tuning: Mapped[dict | None] = mapped_column(JsonColumn, nullable=True)

    __table_args__ = (Index("ix_candidates_stack_label", "stack_label"),)


class DecisionRunRow(Base):
    """One evaluation run — and the card is something a run *sometimes*
    produces (HĐ-12/13).

    ``0005`` modelled this the other way round: a ``decision_cards`` table
    whose ``card`` and ``recommended_candidate_id`` were NOT NULL. That
    encodes the assumption the decision layer exists to refuse — that
    every evaluation ends in a ranking — and the first MVP run disproved
    it within a day: three comparisons out of three produced no card,
    because a card needs *two* candidates through all six gates and only
    one of four got there.

    Those runs are results, not failures. Each carries a full gate table
    answering "who was eliminated where, after how many runs", which is
    the question HĐ-12 puts on a card in the first place. So:

    * ``report`` is NOT NULL — a run always produces evidence;
    * ``card``, ``manifest``, ``recommended_candidate_id`` and ``status``
      are nullable — a run sometimes produces a recommendation.

    Reading it the other way is what puts pressure on every run to be
    rankable, and that pressure is what produced a card bounding a
    collision probability off a single episode.

    **The bodies stay JSON** for the same reason as ``TaskProfileRow``:
    they are frozen Pydantic models the decision layer already validates,
    and a second definition in DDL would drift from the first. Only what
    a query needs is promoted — including ``artifact_kind``, because
    "show me the runs that could not be ranked" is a question asked on
    day one and it should not be a JSON scan.

    ``approval_id`` is deliberately absent. HĐ-14's approvals are an
    append-only trail keyed the other way round, and a single "approved
    by" column would quietly reduce that trail to its last row.
    """

    __tablename__ = "decision_runs"

    id: Mapped[str] = mapped_column(String(ID_LENGTH), primary_key=True)
    task_profile_id: Mapped[str] = mapped_column(
        String(ID_LENGTH), ForeignKey("task_profiles.id", ondelete="RESTRICT"), nullable=False
    )
    #: ``decision_card`` | ``comparison`` | ``measurement``.
    artifact_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    #: HĐ-1.4. NULL for a measurement: one candidate licenses no
    #: layer-scoped claim, so there is no scope to declare.
    experiment_scope: Mapped[str | None] = mapped_column(String(40), nullable=True)
    contracts_version: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[str] = mapped_column(String(TIMESTAMP_LENGTH), nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(ID_LENGTH), nullable=True)
    #: The evidence, whatever the verdict.
    report: Mapped[dict] = mapped_column(JsonColumn, nullable=False)
    #: The recommendation, when the run supported one.
    card: Mapped[dict | None] = mapped_column(JsonColumn, nullable=True)
    manifest: Mapped[dict | None] = mapped_column(JsonColumn, nullable=True)
    recommended_candidate_id: Mapped[str | None] = mapped_column(String(ID_LENGTH), nullable=True)
    status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    #: Where the traces of this run live, and a checksum over them (D15).
    run_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # --- the two human acts, kept apart on purpose (HĐ-14) -------------
    #
    # One column would have been shorter and wrong. "Somebody read this"
    # applies to every run; "this recommendation is the config we deploy"
    # only exists where there *is* a recommendation. Collapsing them
    # forces one of two bad answers: either an unranked run can be
    # approved — turning "measured" into "endorsed" — or it cannot be
    # marked read at all, which is how a run that eliminated four
    # candidates becomes an artifact nobody ever looked at again.
    #
    # ``unreviewed`` | ``reviewed``.
    review_state: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="unreviewed"
    )
    reviewed_by: Mapped[str | None] = mapped_column(String(ID_LENGTH), nullable=True)
    reviewed_at: Mapped[str | None] = mapped_column(String(TIMESTAMP_LENGTH), nullable=True)
    #: ``not_applicable`` | ``pending`` | ``approved`` | ``rejected``.
    #: NOT NULL with the safe default, so a row written by a path that
    #: does not know about this column cannot land in an approvable state.
    config_state: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="not_applicable"
    )
    config_decided_by: Mapped[str | None] = mapped_column(String(ID_LENGTH), nullable=True)
    config_decided_at: Mapped[str | None] = mapped_column(String(TIMESTAMP_LENGTH), nullable=True)

    __table_args__ = (
        Index("ix_decision_runs_task_profile", "task_profile_id"),
        Index("ix_decision_runs_kind", "artifact_kind"),
        Index("ix_decision_runs_recommended", "recommended_candidate_id"),
        Index("ix_decision_runs_status", "status"),
        # "Which runs is nobody watching?" and "what is cleared to
        # deploy?" are both list screens, so neither should be a scan.
        Index("ix_decision_runs_review_state", "review_state"),
        Index("ix_decision_runs_config_state", "config_state"),
    )


class DecisionRunReviewRow(Base):
    """One human act on one decision run. Append-only (HĐ-14).

    A separate table from ``approvals`` rather than a widened one:
    ``approvals.benchmark_id`` is a NOT NULL foreign key into
    ``benchmarks``, and a decision run is not a benchmark. Making that
    column nullable to fit both would leave every existing audit row
    unable to say which of the two kinds it described.
    """

    __tablename__ = "decision_run_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        String(ID_LENGTH), ForeignKey("decision_runs.id", ondelete="CASCADE"), nullable=False
    )
    #: Explicit order: two events can share a timestamp at whatever
    #: resolution the clock has.
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    #: ``review`` | ``approve_config`` | ``reject_config``.
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(String(ID_LENGTH), nullable=True)
    #: Nickname at the time of the act — readable after a rename.
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    #: Both ends, because "approved" alone does not say what it replaced.
    previous_state: Mapped[str] = mapped_column(String(20), nullable=False)
    new_state: Mapped[str] = mapped_column(String(20), nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[str] = mapped_column(String(TIMESTAMP_LENGTH), nullable=False)

    __table_args__ = (Index("ix_decision_run_reviews_run", "run_id", "sequence"),)


__all__ = [
    "ApprovalRow",
    "CandidateRow",
    "DecisionRunReviewRow",
    "DecisionRunRow",
    "TaskProfileRow",
    "ConversationMessageRow",
    "ConversationRow",
    "ModelDocumentRow",
    "ModelRow",
    "ModelUsageRow",
    "RobotProfileRow",
    "OAuthAccountRow",
    "ReviewRequestRow",
    "UserRow",
    "Base",
    "BenchmarkRow",
    "EpisodeRow",
    "JsonColumn",
    "MapRow",
    "ScenarioRow",
    "SimulationRow",
]
