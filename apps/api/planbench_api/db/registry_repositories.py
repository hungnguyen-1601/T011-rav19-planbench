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
    ModelDocumentRow,
    ModelRow,
    ModelUsageRow,
    PluginBundleRow,
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
from planbench_api.plugin_registry import PluginBundleRecord
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
            max_linear_acceleration=profile.max_linear_acceleration,
            max_angular_acceleration=profile.max_angular_acceleration,
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
            row.max_linear_acceleration = profile.max_linear_acceleration
            row.max_angular_acceleration = profile.max_angular_acceleration
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
        max_linear_acceleration=row.max_linear_acceleration,
        max_angular_acceleration=row.max_angular_acceleration,
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


class SqlPluginBundleRepository:
    """Imported algorithm bundles, in SQL.

    No ``delete``, matching the in-memory repository and for the same
    reason: a bundle is what a benchmark ran, and deleting the row turns
    those measurements into records of nothing.
    """

    def __init__(self, sessions: SessionFactory) -> None:
        self._sessions = sessions

    def _require_unique(self, session: Session, record: PluginBundleRecord) -> None:
        """The readable half of the (plugin_id, plugin_version) rule.

        The unique index is the guarantee; this is the explanation.
        """
        clash = session.scalars(
            select(PluginBundleRow).where(
                PluginBundleRow.plugin_id == record.plugin_id,
                PluginBundleRow.checksum == record.checksum,
                PluginBundleRow.id != record.id,
            )
        ).first()
        if clash is not None:
            raise RegistryError(
                f"this exact bundle is already imported as {clash.name!r} v{clash.version} "
                f"(revision {clash.revision}). Nothing in it has changed, so there is "
                "nothing new to measure; change the code and upload again"
            )

    def create(self, record: PluginBundleRecord) -> PluginBundleRecord:
        stamp = now_iso()
        bundle_id = record.id or new_id()
        with self._sessions.begin() as session:
            self._require_unique(session, record.model_copy(update={"id": bundle_id}))
            row = PluginBundleRow(
                id=bundle_id,
                name=record.name,
                version=record.version,
                description=record.description,
                plugin_id=record.plugin_id,
                plugin_version=record.plugin_version,
                revision=record.revision,
                role=record.role,
                entry_point=record.entry_point,
                manifest=record.manifest,
                manifest_checksum=record.manifest_checksum,
                package_dir=record.package_dir,
                storage_key=record.storage_key,
                original_filename=record.original_filename,
                file_size=record.file_size,
                checksum=record.checksum,
                uploaded_by_user_id=record.uploaded_by_user_id,
                robot_profile_id=record.robot_profile_id,
                status=record.status.value,
                validation_status=record.validation_status.value,
                validation_message=record.validation_message,
                created_at=record.created_at or stamp,
                updated_at=stamp,
            )
            session.add(row)
            session.flush()
            return _to_bundle(row)

    def next_revision(self, plugin_id: str) -> int:
        """Which upload of this plugin the next one will be."""
        with self._sessions.begin() as session:
            rows = session.scalars(
                select(PluginBundleRow).where(PluginBundleRow.plugin_id == plugin_id)
            ).all()
            return max((row.revision or 1 for row in rows), default=0) + 1

    def others_of(self, plugin_id: str, exclude_id: str) -> list[PluginBundleRecord]:
        """Every other upload of the same plugin, newest first."""
        with self._sessions.begin() as session:
            rows = session.scalars(
                select(PluginBundleRow)
                .where(PluginBundleRow.plugin_id == plugin_id, PluginBundleRow.id != exclude_id)
                .order_by(PluginBundleRow.created_at.desc())
            ).all()
            return [_to_bundle(row) for row in rows]

    def get(self, bundle_id: str) -> PluginBundleRecord:
        with self._sessions.begin() as session:
            return _to_bundle(_require(session, PluginBundleRow, bundle_id, "algorithm bundle"))

    def save(self, record: PluginBundleRecord) -> PluginBundleRecord:
        with self._sessions.begin() as session:
            row = _require(session, PluginBundleRow, record.id, "algorithm bundle")
            self._require_unique(session, record)
            row.name = record.name
            row.version = record.version
            row.description = record.description
            row.robot_profile_id = record.robot_profile_id
            row.status = record.status.value
            row.validation_status = record.validation_status.value
            row.validation_message = record.validation_message
            row.updated_at = now_iso()
            session.flush()
            return _to_bundle(row)

    def list(self) -> list[PluginBundleRecord]:
        with self._sessions.begin() as session:
            rows = session.scalars(
                select(PluginBundleRow).order_by(PluginBundleRow.created_at.desc())
            ).all()
            return [_to_bundle(row) for row in rows]

    def find_by_plugin(self, plugin_id: str, plugin_version: str) -> PluginBundleRecord | None:
        with self._sessions.begin() as session:
            row = session.scalars(
                select(PluginBundleRow).where(
                    PluginBundleRow.plugin_id == plugin_id,
                    PluginBundleRow.plugin_version == plugin_version,
                )
            ).first()
            return _to_bundle(row) if row is not None else None


def _to_bundle(row: PluginBundleRow) -> PluginBundleRecord:
    return PluginBundleRecord(
        id=row.id,
        name=row.name,
        version=row.version,
        description=row.description or "",
        plugin_id=row.plugin_id or "",
        plugin_version=row.plugin_version or "",
        revision=row.revision or 1,
        role=row.role or "local",
        entry_point=row.entry_point or "",
        manifest=row.manifest or {},
        manifest_checksum=row.manifest_checksum or "",
        package_dir=row.package_dir or "",
        storage_key=row.storage_key or "",
        original_filename=row.original_filename or "",
        file_size=row.file_size,
        checksum=row.checksum or "",
        uploaded_by_user_id=row.uploaded_by_user_id or "",
        robot_profile_id=row.robot_profile_id or "",
        status=ModelStatus(row.status),
        validation_status=ValidationStatus(row.validation_status),
        validation_message=row.validation_message or "",
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


__all__ = [
    "SqlModelRepository",
    "SqlPluginBundleRepository",
    "SqlRobotProfileRepository",
]
