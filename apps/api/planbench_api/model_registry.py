"""Trained models as first-class records, not file paths.

Before this, running `astar+ppo` meant typing a filesystem path into a
benchmark config. That asked a user to know where files live on the
server, it could not be checked before the run, and a benchmark's record
of *which* model produced its numbers was a string that might point
somewhere else tomorrow.

A registry entry fixes all three. It carries the checksum, so "which
model was this?" has an answer that cannot drift; it carries the
observation and action shapes, so a mismatch is caught before the run
rather than as garbage output during it; and it carries an owner, so
sharing is a decision rather than an accident of the filesystem.

**What a PPO model actually is**, because the distinction is load-bearing
here: a `.zip` produced by Stable-Baselines3, containing the trained
weights. It is the only file that can be executed as a policy. A `.json`
sidecar is structured metadata *about* it. A `.pdf` is prose for humans.
Uploading a PDF does not give you a runnable model, and this module
refuses to pretend otherwise — see :class:`DocumentKind`.
"""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from planbench_api.accounts import now_iso

# ---------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------


class ModelStatus(StrEnum):
    """Whether a model may be picked for a new benchmark."""

    ACTIVE = "active"
    DISABLED = "disabled"


class ValidationStatus(StrEnum):
    """How far the file has been checked.

    ``STRUCTURAL`` means the archive is a well-formed SB3 checkpoint —
    verified by reading the zip's table of contents, which executes
    nothing. ``LOADED`` means a separate process actually deserialised
    it. The gap between them is deliberate and is the whole security
    story: deserialising a user-uploaded file runs their code, so it
    never happens inside the API process.
    """

    PENDING = "pending"
    STRUCTURAL = "structural"
    LOADED = "loaded"
    FAILED = "failed"


class DocumentKind(StrEnum):
    """The three kinds of file, and what each may be used for."""

    #: The executable artefact. Only this can be run as a policy.
    MODEL = "model"
    #: Structured metadata about the model. Validated, never executed.
    METADATA = "metadata"
    #: Prose for humans: a training report, a description. Never parsed
    #: as configuration and never loaded to run anything.
    DOCUMENT = "document"


EXTENSIONS: dict[DocumentKind, str] = {
    DocumentKind.MODEL: ".zip",
    DocumentKind.METADATA: ".json",
    DocumentKind.DOCUMENT: ".pdf",
}

#: Frameworks whose checkpoints this platform knows how to load.
SUPPORTED_FRAMEWORKS: frozenset[str] = frozenset({"stable-baselines3"})

#: Observation encodings the simulator can actually produce. A policy
#: trained on camera frames cannot run here, and saying so up front is
#: better than feeding it LiDAR and reporting the resulting nonsense.
SUPPORTED_OBSERVATION_TYPES: frozenset[str] = frozenset({"lidar_goal_velocity"})

#: Action spaces the controller interface can express.
SUPPORTED_ACTION_TYPES: frozenset[str] = frozenset({"continuous_velocity"})


class RegistryError(ValueError):
    """A registry operation cannot be done as asked."""


class ModelNotAllowed(RegistryError):
    """The caller may not use or change this model."""


# ---------------------------------------------------------------------
# Filenames
# ---------------------------------------------------------------------

#: Anything outside this is stripped. Deliberately strict: the filename
#: is shown back to the user and used to derive nothing else, so there
#: is no cost to being severe.
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")
MAX_FILENAME_LENGTH = 120


def sanitise_filename(raw: str) -> str:
    """A filename safe to store and to show back.

    Path traversal is not defended against by escaping — it is defended
    against by never letting a separator survive. ``../../etc/passwd``
    becomes ``etc_passwd``; the stored path is built from ids anyway, so
    this value never decides a location.
    """
    # Take the last segment under either separator, so a full path
    # collapses to its basename before anything else happens.
    name = raw.replace("\\", "/").split("/")[-1]
    name = _UNSAFE.sub("_", name).strip("._")
    if not name:
        name = "upload"
    if len(name) > MAX_FILENAME_LENGTH:
        stem, _, suffix = name.rpartition(".")
        keep = MAX_FILENAME_LENGTH - len(suffix) - 1
        name = f"{stem[:keep]}.{suffix}" if suffix and keep > 0 else name[:MAX_FILENAME_LENGTH]
    return name


def extension_of(filename: str) -> str:
    name = sanitise_filename(filename).lower()
    _, dot, suffix = name.rpartition(".")
    return f".{suffix}" if dot else ""


def require_extension(filename: str, kind: DocumentKind) -> None:
    """Reject anything whose extension is not the one kind allows."""
    expected = EXTENSIONS[kind]
    actual = extension_of(filename)
    if actual != expected:
        raise RegistryError(
            f"{kind.value} must be a {expected} file, got {actual or 'no extension'!r}. "
            f"A PPO model is the {EXTENSIONS[DocumentKind.MODEL]} that Stable-Baselines3 "
            "saves; a PDF is documentation and cannot be run."
        )


# ---------------------------------------------------------------------
# Metadata the uploader may supply
# ---------------------------------------------------------------------


class ObservationSchema(BaseModel):
    """What the policy expects to see.

    ``version`` is the encoding the policy was trained against. It
    matters more than it looks: a policy trained on a different layout
    consumes garbage inputs while appearing perfectly healthy, so the
    loader refuses a mismatch. An uploader who does not declare it gets
    a warning rather than a silent assumption.
    """

    model_config = ConfigDict(frozen=True)

    type: str = "lidar_goal_velocity"
    version: str = ""
    shape: tuple[int, ...] = ()
    lidar_beams: int = Field(default=0, ge=0)
    includes_goal_direction: bool = True
    includes_current_velocity: bool = True


class ActionSchema(BaseModel):
    """What the policy emits."""

    model_config = ConfigDict(frozen=True)

    type: str = "continuous_velocity"
    reward_version: str = ""
    shape: tuple[int, ...] = ()
    fields: tuple[str, ...] = ()


class TrainingInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    environment: str = ""
    total_timesteps: int = Field(default=0, ge=0)


class RobotSpec(BaseModel):
    """Robot the model was trained against, as the uploader describes it."""

    model_config = ConfigDict(frozen=True)

    radius: float = Field(default=0.0, ge=0)
    max_linear_velocity: float = Field(default=0.0, ge=0)
    max_angular_velocity: float = Field(default=0.0, ge=0)


class ModelMetadataFile(BaseModel):
    """The optional `.json` sidecar, parsed.

    ``extra="ignore"``: a sidecar written by a future trainer with more
    fields should still be usable, and unknown keys are not a reason to
    reject an otherwise good model.

    Nothing in here is trusted on its own — every value is re-checked in
    :func:`validate_metadata` and again in :func:`check_compatibility`.
    A user-supplied file describing itself as compatible does not make
    it so.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    framework: str = ""
    framework_version: str = ""
    algorithm: str = ""
    observation: ObservationSchema = ObservationSchema()
    action: ActionSchema = ActionSchema()
    robot: RobotSpec = RobotSpec()
    training: TrainingInfo = TrainingInfo()


def validate_metadata(metadata: ModelMetadataFile) -> list[str]:
    """Problems with a sidecar, as messages a person can act on.

    Returns a list rather than raising: an upload with a questionable
    sidecar is still worth storing — flagged — because the file itself
    may be fine and the user can correct the description.
    """
    problems: list[str] = []

    if metadata.algorithm and metadata.algorithm.strip().upper() != "PPO":
        problems.append(
            f"metadata says algorithm={metadata.algorithm!r}; this registry only "
            "accepts PPO checkpoints"
        )
    if metadata.framework and metadata.framework.strip().lower() not in SUPPORTED_FRAMEWORKS:
        problems.append(
            f"framework {metadata.framework!r} is not supported "
            f"(supported: {sorted(SUPPORTED_FRAMEWORKS)})"
        )
    if metadata.observation.type and metadata.observation.type not in SUPPORTED_OBSERVATION_TYPES:
        problems.append(
            f"observation type {metadata.observation.type!r} is not something the "
            f"simulator can produce (supported: {sorted(SUPPORTED_OBSERVATION_TYPES)})"
        )
    if metadata.action.type and metadata.action.type not in SUPPORTED_ACTION_TYPES:
        problems.append(
            f"action type {metadata.action.type!r} is not something the controller "
            f"interface can express (supported: {sorted(SUPPORTED_ACTION_TYPES)})"
        )
    if any(value <= 0 for value in metadata.observation.shape):
        problems.append("observation shape must be positive in every dimension")
    if any(value <= 0 for value in metadata.action.shape):
        problems.append("action shape must be positive in every dimension")
    for label, value in (
        ("radius", metadata.robot.radius),
        ("max_linear_velocity", metadata.robot.max_linear_velocity),
        ("max_angular_velocity", metadata.robot.max_angular_velocity),
    ):
        if value < 0:
            problems.append(f"robot.{label} must not be negative")
    return problems


# ---------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------


class RobotProfile(BaseModel):
    """The robot a model was trained for, and a benchmark will run.

    Exists so changing robots is a form, not a code edit. The PPO
    adapter reads its limits from here rather than from constants.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    version: str = "1"
    description: str = ""
    radius: float = Field(gt=0)
    footprint: str = "circle"
    max_linear_velocity: float = Field(gt=0)
    max_angular_velocity: float = Field(gt=0)
    lidar_beams: int = Field(default=24, ge=4)
    lidar_range: float = Field(default=6.0, gt=0)
    observation_type: str = "lidar_goal_velocity"
    action_type: str = "continuous_velocity"
    created_by_user_id: str = ""
    created_at: str = ""
    updated_at: str = ""

    @property
    def label(self) -> str:
        return f"{self.name} v{self.version}"


class ModelDocument(BaseModel):
    """A file attached to a model that is not the model."""

    model_config = ConfigDict(frozen=True)

    id: str
    model_id: str
    kind: DocumentKind
    original_filename: str
    storage_key: str
    file_size: int
    checksum: str
    created_at: str = ""


class ModelRecord(BaseModel):
    """One trained policy, as the platform knows it."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    version: str = "1"
    description: str = ""
    algorithm_type: str = "ppo"
    framework: str = "stable-baselines3"
    framework_version: str = ""
    #: Where the bytes live, resolved by the storage backend. Never
    #: shown to an ordinary user and never accepted from a client.
    storage_key: str = ""
    original_filename: str = ""
    file_size: int = 0
    checksum: str = ""
    uploaded_by_user_id: str = ""
    robot_profile_id: str = ""
    observation_schema: ObservationSchema = ObservationSchema()
    action_schema: ActionSchema = ActionSchema()
    training_environment: str = ""
    training_steps: int = 0
    status: ModelStatus = ModelStatus.ACTIVE
    validation_status: ValidationStatus = ValidationStatus.PENDING
    validation_message: str = ""
    created_at: str = ""
    updated_at: str = ""

    @property
    def label(self) -> str:
        return f"{self.name} v{self.version}"

    @property
    def usable(self) -> bool:
        """Ready to be picked for a benchmark."""
        return self.status is ModelStatus.ACTIVE and self.validation_status in {
            ValidationStatus.STRUCTURAL,
            ValidationStatus.LOADED,
        }


class ModelSummary(BaseModel):
    """The public view. No storage key, no owner id.

    A model is pickable by anyone who can see it, so what comes back is
    only what is needed to pick one and understand whether it fits.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    version: str
    description: str
    algorithm_type: str
    framework: str
    robot_profile_id: str
    status: ModelStatus
    validation_status: ValidationStatus
    validation_message: str
    file_size: int
    checksum: str
    training_environment: str
    training_steps: int
    observation_schema: ObservationSchema
    action_schema: ActionSchema
    created_at: str
    is_owner: bool = False

    @staticmethod
    def of(record: ModelRecord, viewer_id: str = "") -> ModelSummary:
        return ModelSummary(
            id=record.id,
            name=record.name,
            version=record.version,
            description=record.description,
            algorithm_type=record.algorithm_type,
            framework=record.framework,
            robot_profile_id=record.robot_profile_id,
            status=record.status,
            validation_status=record.validation_status,
            validation_message=record.validation_message,
            file_size=record.file_size,
            checksum=record.checksum,
            training_environment=record.training_environment,
            training_steps=record.training_steps,
            observation_schema=record.observation_schema,
            action_schema=record.action_schema,
            created_at=record.created_at,
            is_owner=bool(viewer_id) and record.uploaded_by_user_id == viewer_id,
        )


# ---------------------------------------------------------------------
# Compatibility
# ---------------------------------------------------------------------


class Compatibility(StrEnum):
    COMPATIBLE = "compatible"
    WARNING = "warning"
    INCOMPATIBLE = "incompatible"


class CompatibilityReport(BaseModel):
    """Whether this model can run on this robot, and why not.

    Every message is written for the person choosing the model, not for
    a log. "Model expects 36 LiDAR beams but this robot has 24" tells
    them what to change; a Pydantic traceback does not.
    """

    model_config = ConfigDict(frozen=True)

    status: Compatibility
    model_id: str = ""
    robot_profile_id: str = ""
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    checked_at: str = Field(default_factory=now_iso)

    @property
    def ok(self) -> bool:
        return self.status is not Compatibility.INCOMPATIBLE


def check_compatibility(
    model: ModelRecord | None,
    profile: RobotProfile | None,
    *,
    file_present: bool = True,
    stored_checksum: str = "",
) -> CompatibilityReport:
    """Can this model run on this robot?

    Pure: takes records, returns a verdict. The caller supplies whether
    the file is still there and what its checksum is now, so this can be
    tested without a filesystem — and so the *same* function answers both
    "may I pick this?" in the form and "may I run this?" at launch.
    """
    errors: list[str] = []
    warnings: list[str] = []

    if model is None:
        return CompatibilityReport(
            status=Compatibility.INCOMPATIBLE,
            errors=("no model was selected",),
        )

    if model.algorithm_type != "ppo":
        errors.append(f"{model.label} is a {model.algorithm_type} model, not PPO")
    if model.status is not ModelStatus.ACTIVE:
        errors.append(f"{model.label} is disabled and cannot be used in a new benchmark")
    if model.validation_status is ValidationStatus.FAILED:
        errors.append(f"{model.label} failed validation: {model.validation_message or 'unknown'}")
    elif model.validation_status is ValidationStatus.PENDING:
        warnings.append(f"{model.label} has not been checked yet")
    if model.framework and model.framework.lower() not in SUPPORTED_FRAMEWORKS:
        errors.append(
            f"framework {model.framework!r} is not supported "
            f"(supported: {sorted(SUPPORTED_FRAMEWORKS)})"
        )
    if not model.observation_schema.version:
        # Not an error: most uploads will not declare it, and refusing
        # them would be worse than saying what the risk is.
        warnings.append(
            f"{model.label} does not say which observation encoding it was trained "
            "with. If it was trained on a different one, its numbers will be "
            'meaningless — add "observation.version" to the metadata file.'
        )

    if not file_present:
        errors.append(
            f"the file for {model.label} is missing from storage; re-upload it before running"
        )
    elif stored_checksum and model.checksum and stored_checksum != model.checksum:
        # The strongest signal that something is wrong: the bytes are
        # not the bytes the benchmark record refers to.
        errors.append(
            f"the file for {model.label} has changed since it was uploaded "
            "(checksum mismatch); results from it would not be reproducible"
        )

    if profile is None:
        errors.append("no robot profile was selected")
        return CompatibilityReport(
            status=Compatibility.INCOMPATIBLE,
            model_id=model.id,
            errors=tuple(errors),
            warnings=tuple(warnings),
        )

    observation = model.observation_schema
    if observation.type and observation.type != profile.observation_type:
        errors.append(
            f"model expects {observation.type!r} observations but robot "
            f"{profile.label} provides {profile.observation_type!r}"
        )
    if observation.type and observation.type not in SUPPORTED_OBSERVATION_TYPES:
        errors.append(
            f"the simulator cannot produce {observation.type!r} observations "
            f"(it provides {sorted(SUPPORTED_OBSERVATION_TYPES)})"
        )
    if observation.lidar_beams and observation.lidar_beams != profile.lidar_beams:
        errors.append(
            f"model was trained with {observation.lidar_beams} LiDAR beams but robot "
            f"{profile.label} has {profile.lidar_beams}"
        )

    action = model.action_schema
    if action.type and action.type != profile.action_type:
        errors.append(
            f"model emits {action.type!r} actions but robot {profile.label} "
            f"accepts {profile.action_type!r}"
        )
    if action.type and action.type not in SUPPORTED_ACTION_TYPES:
        errors.append(f"the controller interface cannot express {action.type!r} actions")
    if action.shape and action.shape[-1] != 2:
        errors.append(
            f"model outputs {action.shape[-1]} action values but the simulator drives "
            "two (linear and angular velocity)"
        )

    if errors:
        status = Compatibility.INCOMPATIBLE
    elif warnings:
        status = Compatibility.WARNING
    else:
        status = Compatibility.COMPATIBLE
    return CompatibilityReport(
        status=status,
        model_id=model.id,
        robot_profile_id=profile.id,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


__all__ = [
    "EXTENSIONS",
    "SUPPORTED_ACTION_TYPES",
    "SUPPORTED_FRAMEWORKS",
    "SUPPORTED_OBSERVATION_TYPES",
    "ActionSchema",
    "Compatibility",
    "CompatibilityReport",
    "DocumentKind",
    "ModelDocument",
    "ModelMetadataFile",
    "ModelNotAllowed",
    "ModelRecord",
    "ModelStatus",
    "ModelSummary",
    "ObservationSchema",
    "RegistryError",
    "RobotProfile",
    "RobotSpec",
    "TrainingInfo",
    "ValidationStatus",
    "check_compatibility",
    "extension_of",
    "require_extension",
    "sanitise_filename",
    "validate_metadata",
]
