"""SQL repositories for robot profiles, models and conversations.

Same contract as the in-memory versions in `registry_store.py`, same
returned objects — everything above this layer is unchanged by which
backend is configured.

Model *files* are not here. The row keeps a storage key and a checksum;
the bytes live in model storage (decision D15, same split as episode
trajectories). A database is not a filesystem, and a 200 MB BLOB column
would make every "list my models" query pay for weights nobody asked
for.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from planbench_api.accounts import now_iso
from planbench_api.db.models import (
    ConversationMessageRow,
    ConversationRow,
    ModelDocumentRow,
    ModelRow,
    ModelUsageRow,
    RobotProfileRow,
)
from planbench_api.db.session import SessionFactory
from planbench_api.errors import NotFoundError
from planbench_api.model_registry import (
    ActionSchema,
    DocumentKind,
    ModelDocument,
    ModelRecord,
    ModelStatus,
    ObservationSchema,
    RegistryError,
    RobotProfile,
    ValidationStatus,
)
from planbench_api.repositories import new_id


def _require(session: Session, model: type, key: str, label: str):
    row = session.get(model, key)
    if row is None:
        raise NotFoundError(label, key)
    return row


# ---------------------------------------------------------------------
# Robot profiles
# ---------------------------------------------------------------------


class SqlRobotProfileRepository:
    def __init__(self, sessions: SessionFactory) -> None:
        self._sessions = sessions

    def create(self, profile: RobotProfile) -> RobotProfile:
        stamp = now_iso()
        row = RobotProfileRow(
            id=profile.id or new_id(),
            name=profile.name,
            version=profile.version,
            description=profile.description,
            radius=profile.radius,
            footprint=profile.footprint,
            max_linear_velocity=profile.max_linear_velocity,
            max_angular_velocity=profile.max_angular_velocity,
            lidar_beams=profile.lidar_beams,
            lidar_range=profile.lidar_range,
            observation_type=profile.observation_type,
            action_type=profile.action_type,
            created_by_user_id=profile.created_by_user_id,
            created_at=profile.created_at or stamp,
            updated_at=stamp,
        )
        with self._sessions.begin() as session:
            session.add(row)
            session.flush()
            return _to_profile(row)

    def get(self, profile_id: str) -> RobotProfile:
        with self._sessions.begin() as session:
            return _to_profile(_require(session, RobotProfileRow, profile_id, "robot profile"))

    def save(self, profile: RobotProfile) -> RobotProfile:
        with self._sessions.begin() as session:
            row = _require(session, RobotProfileRow, profile.id, "robot profile")
            row.name = profile.name
            row.version = profile.version
            row.description = profile.description
            row.radius = profile.radius
            row.footprint = profile.footprint
            row.max_linear_velocity = profile.max_linear_velocity
            row.max_angular_velocity = profile.max_angular_velocity
            row.lidar_beams = profile.lidar_beams
            row.lidar_range = profile.lidar_range
            row.observation_type = profile.observation_type
            row.action_type = profile.action_type
            row.updated_at = now_iso()
            session.flush()
            return _to_profile(row)

    def list(self) -> list[RobotProfile]:
        with self._sessions.begin() as session:
            rows = session.scalars(
                select(RobotProfileRow).order_by(RobotProfileRow.created_at)
            ).all()
            return [_to_profile(row) for row in rows]

    def delete(self, profile_id: str) -> None:
        with self._sessions.begin() as session:
            session.delete(_require(session, RobotProfileRow, profile_id, "robot profile"))


# ---------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------


class SqlModelRepository:
    def __init__(self, sessions: SessionFactory) -> None:
        self._sessions = sessions

    def _require_unique(self, session: Session, record: ModelRecord) -> None:
        """The readable half of the (owner, name, version) rule.

        The unique index is the guarantee; this is the error message.
        Both exist because only one of them is a good explanation.
        """
        clash = session.scalars(
            select(ModelRow).where(
                ModelRow.uploaded_by_user_id == record.uploaded_by_user_id,
                ModelRow.name == record.name,
                ModelRow.version == record.version,
                ModelRow.id != record.id,
            )
        ).first()
        if clash is not None:
            raise RegistryError(
                f"you already have a model called {record.name!r} at version "
                f"{record.version!r}; use a new version number"
            )

    def create(self, record: ModelRecord) -> ModelRecord:
        stamp = now_iso()
        model_id = record.id or new_id()
        with self._sessions.begin() as session:
            self._require_unique(session, record.model_copy(update={"id": model_id}))
            row = ModelRow(
                id=model_id,
                name=record.name,
                version=record.version,
                description=record.description,
                algorithm_type=record.algorithm_type,
                framework=record.framework,
                framework_version=record.framework_version,
                storage_key=record.storage_key,
                original_filename=record.original_filename,
                file_size=record.file_size,
                checksum=record.checksum,
                uploaded_by_user_id=record.uploaded_by_user_id,
                robot_profile_id=record.robot_profile_id,
                observation_schema=record.observation_schema.model_dump(mode="json"),
                action_schema=record.action_schema.model_dump(mode="json"),
                training_environment=record.training_environment,
                training_steps=record.training_steps,
                status=record.status.value,
                validation_status=record.validation_status.value,
                validation_message=record.validation_message,
                created_at=record.created_at or stamp,
                updated_at=stamp,
            )
            session.add(row)
            session.flush()
            return _to_model(row)

    def get(self, model_id: str) -> ModelRecord:
        with self._sessions.begin() as session:
            return _to_model(_require(session, ModelRow, model_id, "model"))

    def save(self, record: ModelRecord) -> ModelRecord:
        with self._sessions.begin() as session:
            row = _require(session, ModelRow, record.id, "model")
            self._require_unique(session, record)
            row.name = record.name
            row.version = record.version
            row.description = record.description
            row.framework = record.framework
            row.framework_version = record.framework_version
            row.storage_key = record.storage_key
            row.original_filename = record.original_filename
            row.file_size = record.file_size
            row.checksum = record.checksum
            row.robot_profile_id = record.robot_profile_id
            row.observation_schema = record.observation_schema.model_dump(mode="json")
            row.action_schema = record.action_schema.model_dump(mode="json")
            row.training_environment = record.training_environment
            row.training_steps = record.training_steps
            row.status = record.status.value
            row.validation_status = record.validation_status.value
            row.validation_message = record.validation_message
            row.updated_at = now_iso()
            session.flush()
            return _to_model(row)

    def list(self) -> list[ModelRecord]:
        with self._sessions.begin() as session:
            rows = session.scalars(select(ModelRow).order_by(ModelRow.created_at.desc())).all()
            return [_to_model(row) for row in rows]

    def list_versions(self, name: str, user_id: str) -> list[ModelRecord]:
        with self._sessions.begin() as session:
            rows = session.scalars(
                select(ModelRow)
                .where(ModelRow.name == name, ModelRow.uploaded_by_user_id == user_id)
                .order_by(ModelRow.version)
            ).all()
            return [_to_model(row) for row in rows]

    def delete(self, model_id: str) -> None:
        with self._sessions.begin() as session:
            session.delete(_require(session, ModelRow, model_id, "model"))

    # -- documents -----------------------------------------------------

    def add_document(self, document: ModelDocument) -> ModelDocument:
        row = ModelDocumentRow(
            id=document.id or new_id(),
            model_id=document.model_id,
            kind=document.kind.value,
            original_filename=document.original_filename,
            storage_key=document.storage_key,
            file_size=document.file_size,
            checksum=document.checksum,
            created_at=document.created_at or now_iso(),
        )
        with self._sessions.begin() as session:
            session.add(row)
            session.flush()
            return _to_document(row)

    def list_documents(self, model_id: str) -> list[ModelDocument]:
        with self._sessions.begin() as session:
            rows = session.scalars(
                select(ModelDocumentRow)
                .where(ModelDocumentRow.model_id == model_id)
                .order_by(ModelDocumentRow.created_at)
            ).all()
            return [_to_document(row) for row in rows]

    # -- usage ---------------------------------------------------------

    def record_usage(self, model_id: str, benchmark_id: str, version: str, checksum: str) -> None:
        with self._sessions.begin() as session:
            session.add(
                ModelUsageRow(
                    model_id=model_id,
                    benchmark_id=benchmark_id,
                    model_version=version,
                    model_checksum=checksum,
                    created_at=now_iso(),
                )
            )

    def benchmarks_using(self, model_id: str) -> list[str]:
        with self._sessions.begin() as session:
            rows = session.scalars(
                select(ModelUsageRow.benchmark_id)
                .where(ModelUsageRow.model_id == model_id)
                .distinct()
            ).all()
            return list(rows)


# ---------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------


class SqlConversationRepository:
    def __init__(self, sessions: SessionFactory) -> None:
        self._sessions = sessions

    def create(self, user_id: str, title: str, locale: str) -> dict:
        stamp = now_iso()
        row = ConversationRow(
            id=new_id(),
            user_id=user_id,
            title=title,
            locale=locale,
            created_at=stamp,
            updated_at=stamp,
        )
        with self._sessions.begin() as session:
            session.add(row)
            session.flush()
            return _to_conversation(row)

    def get(self, conversation_id: str) -> dict:
        with self._sessions.begin() as session:
            return _to_conversation(
                _require(session, ConversationRow, conversation_id, "conversation")
            )

    def list_for_user(self, user_id: str) -> list[dict]:
        with self._sessions.begin() as session:
            rows = session.scalars(
                select(ConversationRow)
                .where(ConversationRow.user_id == user_id)
                .order_by(ConversationRow.updated_at.desc())
            ).all()
            return [_to_conversation(row) for row in rows]

    def touch(self, conversation_id: str, title: str | None = None) -> dict:
        with self._sessions.begin() as session:
            row = _require(session, ConversationRow, conversation_id, "conversation")
            row.updated_at = now_iso()
            if title and not row.title:
                row.title = title
            session.flush()
            return _to_conversation(row)

    def add_message(
        self, conversation_id: str, role: str, content: str, payload: dict | None = None
    ) -> dict:
        with self._sessions.begin() as session:
            conversation = _require(session, ConversationRow, conversation_id, "conversation")
            row = ConversationMessageRow(
                conversation_id=conversation.id,
                sequence=len(conversation.messages),
                role=role,
                content=content,
                payload=payload,
                created_at=now_iso(),
            )
            session.add(row)
            session.flush()
            return _to_message(row)

    def messages(self, conversation_id: str) -> list[dict]:
        with self._sessions.begin() as session:
            conversation = _require(session, ConversationRow, conversation_id, "conversation")
            return [_to_message(row) for row in conversation.messages]

    def delete(self, conversation_id: str) -> None:
        with self._sessions.begin() as session:
            session.delete(_require(session, ConversationRow, conversation_id, "conversation"))


# ---------------------------------------------------------------------
# row <-> domain
# ---------------------------------------------------------------------


def _to_profile(row: RobotProfileRow) -> RobotProfile:
    return RobotProfile(
        id=row.id,
        name=row.name,
        version=row.version,
        description=row.description or "",
        radius=row.radius,
        footprint=row.footprint,
        max_linear_velocity=row.max_linear_velocity,
        max_angular_velocity=row.max_angular_velocity,
        lidar_beams=row.lidar_beams,
        lidar_range=row.lidar_range,
        observation_type=row.observation_type,
        action_type=row.action_type,
        created_by_user_id=row.created_by_user_id or "",
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_model(row: ModelRow) -> ModelRecord:
    return ModelRecord(
        id=row.id,
        name=row.name,
        version=row.version,
        description=row.description or "",
        algorithm_type=row.algorithm_type,
        framework=row.framework or "",
        framework_version=row.framework_version or "",
        storage_key=row.storage_key or "",
        original_filename=row.original_filename or "",
        file_size=row.file_size,
        checksum=row.checksum or "",
        uploaded_by_user_id=row.uploaded_by_user_id or "",
        robot_profile_id=row.robot_profile_id or "",
        observation_schema=ObservationSchema.model_validate(row.observation_schema or {}),
        action_schema=ActionSchema.model_validate(row.action_schema or {}),
        training_environment=row.training_environment or "",
        training_steps=row.training_steps,
        status=ModelStatus(row.status),
        validation_status=ValidationStatus(row.validation_status),
        validation_message=row.validation_message or "",
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_document(row: ModelDocumentRow) -> ModelDocument:
    return ModelDocument(
        id=row.id,
        model_id=row.model_id,
        kind=DocumentKind(row.kind),
        original_filename=row.original_filename,
        storage_key=row.storage_key,
        file_size=row.file_size,
        checksum=row.checksum or "",
        created_at=row.created_at,
    )


def _to_conversation(row: ConversationRow) -> dict:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "title": row.title or "",
        "locale": row.locale,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _to_message(row: ConversationMessageRow) -> dict:
    return {
        "sequence": row.sequence,
        "role": row.role,
        "content": row.content or "",
        "payload": row.payload,
        "created_at": row.created_at,
    }


__all__ = [
    "SqlConversationRepository",
    "SqlModelRepository",
    "SqlRobotProfileRepository",
]
