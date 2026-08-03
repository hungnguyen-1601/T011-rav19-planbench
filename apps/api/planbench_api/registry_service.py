"""Robot profiles and the model registry: the rules around the records.

Two responsibilities that belong together because they answer the same
question — *may this model run here?* — from two directions. Profiles
describe the robot; models describe what a policy expects. The service
keeps them consistent and refuses combinations that cannot work, before
a benchmark spends compute discovering it.

Ownership is the authority, exactly as it is for benchmarks: the person
who uploaded a model may change or delete it, everyone may see and use
it, and an admin may intervene. Sharing is the default because a
benchmark platform whose models are private to their uploader cannot
compare anything.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from pathlib import Path

from planbench_api.accounts import User
from planbench_api.errors import NotFoundError
from planbench_api.model_registry import (
    ActionSchema,
    CompatibilityReport,
    DocumentKind,
    ModelDocument,
    ModelMetadataFile,
    ModelNotAllowed,
    ModelRecord,
    ModelStatus,
    ObservationSchema,
    RegistryError,
    RobotProfile,
    ValidationStatus,
    check_compatibility,
    require_extension,
    sanitise_filename,
    validate_metadata,
)
from planbench_api.model_storage import ModelStorage, inspect_archive, storage_key
from planbench_api.repositories import new_id

logger = logging.getLogger("planbench.api.registry")

#: Seeded on first use so a fresh install can benchmark PPO without
#: anyone having to invent robot dimensions. Matches the simulator's own
#: defaults, which is what the existing DWA benchmarks already assume.
DEFAULT_PROFILE = RobotProfile(
    id="",
    name="Default AMR",
    version="1",
    description="The simulator's default differential-drive robot.",
    radius=0.3,
    max_linear_velocity=1.0,
    max_angular_velocity=2.0,
    lidar_beams=24,
    lidar_range=6.0,
)


class RobotProfileService:
    def __init__(self, profiles) -> None:
        self._profiles = profiles

    def list(self) -> list[RobotProfile]:
        return self._profiles.list()

    def get(self, profile_id: str) -> RobotProfile:
        return self._profiles.get(profile_id)

    def ensure_default(self) -> RobotProfile:
        """The profile a first-time user gets without filling a form.

        Without it, uploading a model would begin with "invent a robot",
        which is a worse first step than any default could be.
        """
        for profile in self._profiles.list():
            if profile.name == DEFAULT_PROFILE.name:
                return profile
        return self._profiles.create(DEFAULT_PROFILE)

    def create(self, profile: RobotProfile, owner: User) -> RobotProfile:
        return self._profiles.create(
            profile.model_copy(update={"id": "", "created_by_user_id": owner.id})
        )

    def update(self, profile_id: str, changes: dict, actor: User) -> RobotProfile:
        current = self._profiles.get(profile_id)
        self._require_owner(current, actor)
        return self._profiles.save(current.model_copy(update=changes))

    def delete(self, profile_id: str, actor: User, models) -> None:
        current = self._profiles.get(profile_id)
        self._require_owner(current, actor)
        used_by = [model.label for model in models.list() if model.robot_profile_id == profile_id]
        if used_by:
            raise RegistryError(
                f"{current.label} is still used by {len(used_by)} model(s): "
                f"{', '.join(used_by[:3])}. Delete or re-point those first."
            )
        self._profiles.delete(profile_id)

    def clone(self, profile_id: str, name: str, owner: User) -> RobotProfile:
        source = self._profiles.get(profile_id)
        return self._profiles.create(
            source.model_copy(
                update={
                    "id": "",
                    "name": name or f"{source.name} copy",
                    "created_by_user_id": owner.id,
                    "created_at": "",
                }
            )
        )

    @staticmethod
    def _require_owner(profile: RobotProfile, actor: User) -> None:
        if actor.is_admin:
            return
        # A profile with no owner predates accounts; treat it as shared
        # rather than stranding it.
        if profile.created_by_user_id and profile.created_by_user_id != actor.id:
            raise ModelNotAllowed(
                f"{profile.label} belongs to another member; clone it to make your own"
            )


class ModelRegistryService:
    """Uploading, describing, checking and retiring trained models."""

    def __init__(self, models, profiles, storage: ModelStorage) -> None:
        self._models = models
        self._profiles = profiles
        self._storage = storage

    # -- reading -------------------------------------------------------

    def list(self) -> list[ModelRecord]:
        return self._models.list()

    def get(self, model_id: str) -> ModelRecord:
        return self._models.get(model_id)

    def documents(self, model_id: str) -> list[ModelDocument]:
        return self._models.list_documents(model_id)

    def used_by(self, model_id: str) -> list[str]:
        return self._models.benchmarks_using(model_id)

    def usable_models(self) -> list[ModelRecord]:
        """Models a benchmark form should offer."""
        return [record for record in self._models.list() if record.usable]

    # -- uploading -----------------------------------------------------

    def upload(
        self,
        *,
        owner: User,
        name: str,
        version: str,
        description: str,
        framework: str,
        framework_version: str,
        robot_profile_id: str,
        training_environment: str,
        filename: str,
        chunks: Iterator[bytes],
        max_bytes: int,
        metadata_json: bytes | None = None,
    ) -> ModelRecord:
        """Store a checkpoint and describe it.

        The order matters. The extension is checked before a byte is
        written, the size limit is enforced *while* writing, and the
        archive is inspected after — structurally, without executing
        anything. A file that fails inspection is still stored and marked
        FAILED rather than silently dropped, because "your upload was
        rejected and here is why" needs something to point at.
        """
        if not name.strip():
            raise RegistryError("the model needs a name")
        require_extension(filename, DocumentKind.MODEL)

        profile = self._profiles.get(robot_profile_id)  # 404 if unknown
        safe_name = sanitise_filename(filename)
        model_id = new_id()
        version = (version or "1").strip()

        key = storage_key(owner.id, model_id, version, safe_name)
        stored = self._storage.save(key, chunks, max_bytes=max_bytes)

        observation, action, metadata_problems, meta = self._read_metadata(metadata_json, profile)

        # Reading the table of contents is not deserialisation; the
        # weights are never unpickled here. See model_storage.py.
        problems = list(metadata_problems)
        try:
            problems.extend(inspect_archive(self._storage.open(key)))
        except OSError as exc:  # pragma: no cover - storage-level failure
            problems.append(f"could not read the uploaded file back: {exc}")

        record = ModelRecord(
            id=model_id,
            name=name.strip(),
            version=version,
            description=description.strip(),
            framework=(meta.framework or framework or "stable-baselines3").strip(),
            framework_version=(meta.framework_version or framework_version).strip(),
            storage_key=stored.storage_key,
            original_filename=safe_name,
            file_size=stored.size_bytes,
            checksum=stored.checksum,
            uploaded_by_user_id=owner.id,
            robot_profile_id=profile.id,
            observation_schema=observation,
            action_schema=action,
            training_environment=(meta.training.environment or training_environment).strip(),
            training_steps=meta.training.total_timesteps,
            validation_status=ValidationStatus.FAILED if problems else ValidationStatus.STRUCTURAL,
            validation_message=(
                "; ".join(problems)
                if problems
                else "archive looks like a Stable-Baselines3 checkpoint"
            ),
        )

        try:
            created = self._models.create(record)
        except BaseException:
            # No orphaned bytes: a rejected record must not leave its
            # file behind consuming disk nobody can account for.
            self._storage.delete(key)
            raise

        if metadata_json is not None:
            self._attach(created, DocumentKind.METADATA, "metadata.json", metadata_json, max_bytes)
        logger.info(
            "model uploaded",
            extra={
                "context": {
                    "model_id": created.id,
                    "owner": owner.id,
                    "bytes": created.file_size,
                    "validation": created.validation_status.value,
                }
            },
        )
        return created

    def _read_metadata(
        self, metadata_json: bytes | None, profile: RobotProfile
    ) -> tuple[ObservationSchema, ActionSchema, list[str], ModelMetadataFile]:
        """Parse the optional sidecar, falling back to the robot profile.

        Nothing in the sidecar is trusted: it is validated, and where it
        says nothing the profile decides. A file that claims a shape it
        does not have will still fail compatibility later.
        """
        if metadata_json is None:
            return (
                ObservationSchema(type=profile.observation_type, lidar_beams=profile.lidar_beams),
                ActionSchema(type=profile.action_type, shape=(2,)),
                [],
                ModelMetadataFile(),
            )
        try:
            parsed = ModelMetadataFile.model_validate(json.loads(metadata_json))
        except (ValueError, UnicodeDecodeError) as exc:
            return (
                ObservationSchema(type=profile.observation_type, lidar_beams=profile.lidar_beams),
                ActionSchema(type=profile.action_type, shape=(2,)),
                [f"the metadata file is not valid JSON for this schema: {exc}"],
                ModelMetadataFile(),
            )
        problems = validate_metadata(parsed)
        observation = parsed.observation
        if not observation.type:
            observation = observation.model_copy(update={"type": profile.observation_type})
        action = parsed.action
        if not action.type:
            action = action.model_copy(update={"type": profile.action_type})
        return observation, action, problems, parsed

    def attach_document(
        self,
        model_id: str,
        actor: User,
        kind: DocumentKind,
        filename: str,
        data: bytes,
        max_bytes: int,
    ) -> ModelDocument:
        """Attach a `.json` sidecar or a `.pdf`.

        A PDF is documentation. It is stored, listed and downloadable —
        and never parsed as configuration or loaded to run anything.
        """
        record = self._models.get(model_id)
        self._require_owner(record, actor)
        require_extension(filename, kind)
        return self._attach(record, kind, filename, data, max_bytes)

    def _attach(
        self,
        record: ModelRecord,
        kind: DocumentKind,
        filename: str,
        data: bytes,
        max_bytes: int,
    ) -> ModelDocument:
        safe_name = sanitise_filename(filename)
        key = storage_key(
            record.uploaded_by_user_id, record.id, record.version, f"{kind.value}-{safe_name}"
        )
        stored = self._storage.save(key, iter([data]), max_bytes=max_bytes)
        return self._models.add_document(
            ModelDocument(
                id="",
                model_id=record.id,
                kind=kind,
                original_filename=safe_name,
                storage_key=stored.storage_key,
                file_size=stored.size_bytes,
                checksum=stored.checksum,
            )
        )

    # -- changing ------------------------------------------------------

    def update(self, model_id: str, changes: dict, actor: User) -> ModelRecord:
        record = self._models.get(model_id)
        self._require_owner(record, actor)
        # Only descriptive fields: the file, its checksum and its owner
        # are facts about what was uploaded, not preferences.
        allowed = {"name", "description", "version", "status", "robot_profile_id"}
        filtered = {key: value for key, value in changes.items() if key in allowed}
        if "robot_profile_id" in filtered:
            self._profiles.get(filtered["robot_profile_id"])
        return self._models.save(record.model_copy(update=filtered))

    def set_status(self, model_id: str, status: ModelStatus, actor: User) -> ModelRecord:
        return self.update(model_id, {"status": status}, actor)

    def delete(self, model_id: str, actor: User) -> None:
        record = self._models.get(model_id)
        self._require_owner(record, actor)
        used_by = self._models.benchmarks_using(model_id)
        if used_by:
            raise RegistryError(
                f"{record.label} was used by {len(used_by)} benchmark(s) and cannot be "
                "deleted — those results would stop being reproducible. Disable it instead."
            )
        for document in self._models.list_documents(model_id):
            self._storage.delete(document.storage_key)
        self._storage.delete(record.storage_key)
        self._models.delete(model_id)
        logger.info("model deleted", extra={"context": {"model_id": model_id, "by": actor.id}})

    # -- checking ------------------------------------------------------

    def revalidate(self, model_id: str) -> ModelRecord:
        """Re-run the structural check against the bytes on disk now.

        Catches the case that matters most: the file changed, or went
        away, after it was uploaded.
        """
        record = self._models.get(model_id)
        if not self._storage.exists(record.storage_key):
            return self._models.save(
                record.model_copy(
                    update={
                        "validation_status": ValidationStatus.FAILED,
                        "validation_message": "the model file is missing from storage",
                    }
                )
            )
        current = self._storage.checksum(record.storage_key)
        if record.checksum and current != record.checksum:
            return self._models.save(
                record.model_copy(
                    update={
                        "validation_status": ValidationStatus.FAILED,
                        "validation_message": (
                            "the file has changed since upload (checksum mismatch)"
                        ),
                    }
                )
            )
        problems = inspect_archive(self._storage.open(record.storage_key))
        return self._models.save(
            record.model_copy(
                update={
                    "validation_status": (
                        ValidationStatus.FAILED if problems else ValidationStatus.STRUCTURAL
                    ),
                    "validation_message": (
                        "; ".join(problems) if problems else "archive re-checked and unchanged"
                    ),
                }
            )
        )

    def compatibility(
        self, model_id: str, robot_profile_id: str | None = None
    ) -> CompatibilityReport:
        """Can this model run on this robot, with the file as it is now?"""
        record = self._models.get(model_id)
        profile_id = robot_profile_id or record.robot_profile_id
        try:
            profile = self._profiles.get(profile_id) if profile_id else None
        except NotFoundError:
            profile = None
        present = self._storage.exists(record.storage_key)
        checksum = self._storage.checksum(record.storage_key) if present else ""
        return check_compatibility(record, profile, file_present=present, stored_checksum=checksum)

    def internal_location(self, record: ModelRecord) -> str:
        """The path the runner opens. Never returned by the API."""
        return self._storage.internal_location(record.storage_key)

    def sidecar_location(self, record: ModelRecord) -> str:
        """Write the metadata file `load_ppo_planner` looks for, and
        return its path.

        The loader wants a sidecar naming the observation and reward
        versions, because a policy trained on a different encoding reads
        garbage while looking healthy. Our registry keeps that
        information in a different shape, so it is rendered here into
        the shape the loader expects.

        When the uploader did not declare the versions, the platform's
        current ones are written — and the compatibility report carries
        a warning saying exactly that, so the assumption is visible
        rather than silent.

        On a server without the optional RL dependencies the path is
        returned without writing anything. Nothing is lost: that server
        cannot run a PPO benchmark at all, and it says so in a sentence
        an operator can act on. Letting the missing import escape from
        *here* would replace that sentence with an internal error about
        a package the user never asked for.
        """
        model_path = Path(self._storage.internal_location(record.storage_key))
        sidecar = model_path.with_suffix(".json")

        try:
            from planbench_rl.observation import OBSERVATION_VERSION
            from planbench_rl.rewards import REWARD_VERSION
        except ModuleNotFoundError:
            return str(sidecar)

        payload = {
            "model_id": record.id,
            "algorithm": "ppo",
            "observation_version": record.observation_schema.version or OBSERVATION_VERSION,
            "reward_version": record.action_schema.reward_version or REWARD_VERSION,
            "total_timesteps": record.training_steps,
            "curriculum": [],
            "created_at": record.created_at,
            "notes": f"generated from registry record {record.id}",
        }
        sidecar.write_text(json.dumps(payload, indent=2))
        return str(sidecar)

    def record_usage(self, model_id: str, benchmark_id: str) -> None:
        record = self._models.get(model_id)
        self._models.record_usage(model_id, benchmark_id, record.version, record.checksum)

    @staticmethod
    def _require_owner(record: ModelRecord, actor: User) -> None:
        if actor.is_admin:
            return
        if record.uploaded_by_user_id and record.uploaded_by_user_id != actor.id:
            raise ModelNotAllowed(
                f"{record.label} was uploaded by another member; you can use it in a "
                "benchmark, but only its owner can change or delete it"
            )


__all__ = ["DEFAULT_PROFILE", "ModelRegistryService", "RobotProfileService"]
