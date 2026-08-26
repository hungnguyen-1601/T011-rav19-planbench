"""Imported algorithm bundles.

Sits under `/algorithms` beside the built-in catalogue, because from a
caller's point of view an imported algorithm and a registered one are
the same kind of thing — something a benchmark can name. What differs is
how it got here, and that is what this router is.

Reading needs no privilege: seeing an imported algorithm, and seeing
exactly why it cannot run, is information anybody comparing candidates
needs. Creating one runs the uploader's code on this server, so it is
administrators only (`docs/plugin_import_security.md` §5).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from pydantic import BaseModel

from planbench_api.auth import ActiveUser
from planbench_api.dependencies import get_plugin_service
from planbench_api.model_storage import CHUNK
from planbench_api.plugin_registry import PluginBundleSummary
from planbench_api.plugin_service import HostCompatibility, PluginBundleService

router = APIRouter(prefix="/algorithms/plugins", tags=["algorithms"])

Plugins = Annotated[PluginBundleService, Depends(get_plugin_service)]


class PluginBundleDetail(BaseModel):
    """One imported algorithm, with the verdict recomputed now.

    The compatibility report is not stored alongside the bundle and not
    cached here: a deployment can gain or lose a provider, and a verdict
    remembered from upload time would be a claim about a host that has
    since changed.
    """

    bundle: PluginBundleSummary
    compatibility: HostCompatibility


class PluginUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    version: str | None = None
    status: str | None = None
    robot_profile_id: str | None = None


def _chunks(upload: UploadFile):
    """Stream the upload rather than reading it whole."""
    while True:
        block = upload.file.read(CHUNK)
        if not block:
            return
        yield block


@router.get("", response_model=list[PluginBundleSummary])
def list_plugins(plugins: Plugins, user: ActiveUser) -> list[PluginBundleSummary]:
    return [PluginBundleSummary.of(record, user.id) for record in plugins.list()]


@router.post("", response_model=PluginBundleSummary, status_code=status.HTTP_201_CREATED)
async def import_plugin(
    plugins: Plugins,
    user: ActiveUser,
    name: Annotated[str, Form()],
    robot_profile_id: Annotated[str, Form()],
    version: Annotated[str, Form()] = "1",
    description: Annotated[str, Form()] = "",
    bundle: Annotated[UploadFile, File()] = ...,  # noqa: B008 - FastAPI form field
) -> PluginBundleSummary:
    """Import an algorithm bundle.

    `bundle` is a `.zip` of the directory holding the planner and its
    `.planbench-plugin/plugin.json`. Nothing in it is extracted or
    imported here: the archive's table of contents is read and its
    manifest is parsed, which is metadata parsing rather than execution.
    """
    record = plugins.upload(
        owner=user,
        name=name,
        version=version,
        description=description,
        robot_profile_id=robot_profile_id,
        filename=bundle.filename or "bundle.zip",
        chunks=_chunks(bundle),
    )
    return PluginBundleSummary.of(record, user.id)


@router.get("/{bundle_id}", response_model=PluginBundleDetail)
def get_plugin(bundle_id: str, plugins: Plugins, user: ActiveUser) -> PluginBundleDetail:
    record = plugins.get(bundle_id)
    return PluginBundleDetail(
        bundle=PluginBundleSummary.of(record, user.id),
        compatibility=plugins.compatibility(bundle_id),
    )


@router.post("/{bundle_id}/validate", response_model=PluginBundleSummary)
def validate_plugin(bundle_id: str, plugins: Plugins, user: ActiveUser) -> PluginBundleSummary:
    """Unpack the bundle and run the conformance suite again.

    Runs the uploader's code, so it is the import privilege rather than
    the read one. Worth re-asking after a deployment changes: a bundle
    left unchecked because a provider was missing is not a bundle that
    failed.
    """
    return PluginBundleSummary.of(plugins.revalidate(bundle_id, user), user.id)


@router.patch("/{bundle_id}", response_model=PluginBundleSummary)
def update_plugin(
    bundle_id: str, payload: PluginUpdateRequest, plugins: Plugins, user: ActiveUser
) -> PluginBundleSummary:
    changes = {key: value for key, value in payload.model_dump().items() if value is not None}
    return PluginBundleSummary.of(plugins.update(bundle_id, changes, user), user.id)
