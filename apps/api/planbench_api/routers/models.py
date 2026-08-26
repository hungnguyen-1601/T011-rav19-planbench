"""Model registry and robot profile endpoints.

The client never sends or receives a filesystem path. It sends a model
*id*; the server resolves that to bytes when it runs. That is the whole
point of the registry — the previous design asked a user to know where
files live on a machine they have no access to.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from pydantic import BaseModel, Field, model_validator

from planbench_api.auth import ActiveUser
from planbench_api.config import get_settings
from planbench_api.dependencies import get_model_service, get_profile_service
from planbench_api.model_registry import (
    CompatibilityReport,
    DocumentKind,
    ModelStatus,
    ModelSummary,
    RegistryError,
    RobotProfile,
)
from planbench_api.model_storage import CHUNK
from planbench_api.registry_service import ModelRegistryService, RobotProfileService

router = APIRouter(tags=["models"])

Models = Annotated[ModelRegistryService, Depends(get_model_service)]
Profiles = Annotated[RobotProfileService, Depends(get_profile_service)]


# ---------------------------------------------------------------------
# Robot profiles
# ---------------------------------------------------------------------


class RobotProfileRequest(BaseModel):
    """A robot, described. Every limit is positive by construction."""

    name: str
    version: str = "1"
    description: str = ""
    radius: float = Field(gt=0)
    footprint: str = "circle"
    max_linear_velocity: float = Field(gt=0)
    max_angular_velocity: float = Field(gt=0)
    #: Optional, because a vehicle whose datasheet nobody has to hand is
    #: still a vehicle worth recording. Absent is not zero: a deployment
    #: needs both, so the form asks its author for what the profile does
    #: not know instead of filling it in for them.
    max_linear_acceleration: float | None = Field(default=None, gt=0)
    max_angular_acceleration: float | None = Field(default=None, gt=0)
    lidar_beams: int = Field(default=24, ge=4)
    lidar_range: float = Field(default=6.0, gt=0)
    observation_type: str = "lidar_goal_velocity"
    action_type: str = "continuous_velocity"

    @model_validator(mode="before")
    @classmethod
    def _control_period_belongs_to_the_deployment(cls, value: object) -> object:
        """Refuse T_cycle here rather than dropping it on the way in.

        A body carrying ``control_period`` is somebody expecting it to
        take effect. Ignoring it silently would leave them believing they
        had set a cycle time for this vehicle everywhere — and the field
        is gate G4's threshold, so "everywhere" would mean one edit
        widening a gate for every deployment using the robot, with no new
        ``task_profile_id`` to record that the standard moved.

        Named rather than blanket-forbidden: this is the one field with a
        reason, and refusing every unknown key would be a different
        decision about an endpoint this change is not otherwise touching.
        """
        if isinstance(value, dict) and "control_period" in value:
            raise ValueError(
                "control_period is a property of a deployment, not of a robot: it is the "
                "wall-clock budget one control step has on the target board (gate G4's "
                "threshold), and the same vehicle at two sites can be held to two different "
                "cycles. Declare it on the deployment's robot instead."
            )
        return value


@router.get("/robot-profiles", response_model=list[RobotProfile])
def list_profiles(profiles: Profiles, _: ActiveUser) -> list[RobotProfile]:
    # Seeding here means a first-time user never faces "invent a robot"
    # as step one of uploading a model.
    profiles.ensure_default()
    return profiles.list()


@router.post("/robot-profiles", response_model=RobotProfile, status_code=status.HTTP_201_CREATED)
def create_profile(
    payload: RobotProfileRequest, profiles: Profiles, user: ActiveUser
) -> RobotProfile:
    return profiles.create(RobotProfile(id="", **payload.model_dump()), user)


@router.get("/robot-profiles/{profile_id}", response_model=RobotProfile)
def get_profile(profile_id: str, profiles: Profiles, _: ActiveUser) -> RobotProfile:
    return profiles.get(profile_id)


@router.patch("/robot-profiles/{profile_id}", response_model=RobotProfile)
def update_profile(
    profile_id: str, payload: RobotProfileRequest, profiles: Profiles, user: ActiveUser
) -> RobotProfile:
    return profiles.update(profile_id, payload.model_dump(), user)


@router.post("/robot-profiles/{profile_id}/clone", response_model=RobotProfile)
def clone_profile(
    profile_id: str, profiles: Profiles, user: ActiveUser, name: str = ""
) -> RobotProfile:
    return profiles.clone(profile_id, name, user)


@router.delete("/robot-profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile(profile_id: str, profiles: Profiles, models: Models, user: ActiveUser) -> None:
    profiles.delete(profile_id, user, models)


# ---------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------


class ModelDetail(BaseModel):
    """One model, with what a person needs to judge it.

    No storage key and no uploader id: this is the view everybody gets,
    so it carries nothing that only the owner should know.
    """

    model: ModelSummary
    compatibility: CompatibilityReport
    used_by_benchmarks: list[str] = []
    documents: list[dict] = []


class ModelUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    version: str | None = None
    status: ModelStatus | None = None
    robot_profile_id: str | None = None


def _chunks(upload: UploadFile):
    """Stream the upload rather than reading it whole.

    A 200 MB checkpoint held in memory per concurrent upload is how a
    file-upload endpoint takes a server down.
    """
    while True:
        block = upload.file.read(CHUNK)
        if not block:
            return
        yield block


@router.get("/models", response_model=list[ModelSummary])
def list_models(models: Models, user: ActiveUser, usable_only: bool = False) -> list[ModelSummary]:
    """Every model. Seeing one is not owning one — acting on it is checked."""
    records = models.usable_models() if usable_only else models.list()
    return [ModelSummary.of(record, user.id) for record in records]


@router.post("/models/upload", response_model=ModelSummary, status_code=status.HTTP_201_CREATED)
async def upload_model(
    request: Request,
    models: Models,
    user: ActiveUser,
    name: Annotated[str, Form()],
    robot_profile_id: Annotated[str, Form()],
    version: Annotated[str, Form()] = "1",
    description: Annotated[str, Form()] = "",
    framework: Annotated[str, Form()] = "stable-baselines3",
    framework_version: Annotated[str, Form()] = "",
    training_environment: Annotated[str, Form()] = "",
    model_file: Annotated[UploadFile, File()] = ...,  # noqa: B008 - FastAPI form field
    metadata_file: Annotated[UploadFile | None, File()] = None,  # noqa: B008
    document_file: Annotated[UploadFile | None, File()] = None,  # noqa: B008
) -> ModelSummary:
    """Upload a trained PPO checkpoint.

    `model_file` must be the `.zip` Stable-Baselines3 writes. The two
    optional files are description, not code: a `.json` sidecar is parsed
    and validated, a `.pdf` is stored for humans to read and is never
    loaded to run anything.
    """
    settings = get_settings()
    metadata_bytes = await metadata_file.read() if metadata_file is not None else None

    record = models.upload(
        owner=user,
        name=name,
        version=version,
        description=description,
        framework=framework,
        framework_version=framework_version,
        robot_profile_id=robot_profile_id,
        training_environment=training_environment,
        filename=model_file.filename or "model.zip",
        chunks=_chunks(model_file),
        max_bytes=settings.max_model_upload_mb * 1024 * 1024,
        metadata_json=metadata_bytes,
    )

    if document_file is not None:
        models.attach_document(
            record.id,
            user,
            DocumentKind.DOCUMENT,
            document_file.filename or "document.pdf",
            await document_file.read(),
            settings.max_document_upload_mb * 1024 * 1024,
        )
    return ModelSummary.of(record, user.id)


@router.get("/models/{model_id}", response_model=ModelDetail)
def get_model(model_id: str, models: Models, user: ActiveUser) -> ModelDetail:
    record = models.get(model_id)
    return ModelDetail(
        model=ModelSummary.of(record, user.id),
        compatibility=models.compatibility(model_id),
        used_by_benchmarks=models.used_by(model_id),
        documents=[
            {
                "id": document.id,
                "kind": document.kind.value,
                "filename": document.original_filename,
                "size": document.file_size,
            }
            for document in models.documents(model_id)
        ],
    )


@router.patch("/models/{model_id}", response_model=ModelSummary)
def update_model(
    model_id: str, payload: ModelUpdateRequest, models: Models, user: ActiveUser
) -> ModelSummary:
    changes = {key: value for key, value in payload.model_dump().items() if value is not None}
    return ModelSummary.of(models.update(model_id, changes, user), user.id)


@router.delete("/models/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_model(model_id: str, models: Models, user: ActiveUser) -> None:
    models.delete(model_id, user)


@router.post("/models/{model_id}/validate", response_model=ModelSummary)
def validate_model(model_id: str, models: Models, user: ActiveUser) -> ModelSummary:
    """Re-check the stored file: still there, still the same bytes?"""
    return ModelSummary.of(models.revalidate(model_id), user.id)


@router.get("/models/{model_id}/compatibility", response_model=CompatibilityReport)
def model_compatibility(
    model_id: str, models: Models, _: ActiveUser, robot_profile_id: str = ""
) -> CompatibilityReport:
    return models.compatibility(model_id, robot_profile_id or None)


@router.post(
    "/models/{model_id}/documents", response_model=dict, status_code=status.HTTP_201_CREATED
)
async def add_document(
    model_id: str,
    models: Models,
    user: ActiveUser,
    kind: Annotated[str, Form()] = "document",
    file: Annotated[UploadFile, File()] = ...,  # noqa: B008
) -> dict:
    settings = get_settings()
    try:
        parsed = DocumentKind(kind)
    except ValueError:
        raise RegistryError(f"unknown document kind {kind!r}") from None
    if parsed is DocumentKind.MODEL:
        raise RegistryError(
            "the model file is set at upload time; create a new version instead of "
            "replacing the bytes of an existing one"
        )
    document = models.attach_document(
        model_id,
        user,
        parsed,
        file.filename or f"file{parsed.value}",
        await file.read(),
        settings.max_document_upload_mb * 1024 * 1024,
    )
    return {
        "id": document.id,
        "kind": document.kind.value,
        "filename": document.original_filename,
        "size": document.file_size,
    }
