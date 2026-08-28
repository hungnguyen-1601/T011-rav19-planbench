"""Imported algorithm bundles.

Sits under `/algorithms` beside the built-in catalogue, because from a
caller's point of view an imported algorithm and a registered one are
the same kind of thing — something a benchmark can name. What differs is
how it got here, and that is what this router is.

Reading the *catalogue* needs only an account: seeing an imported
algorithm, and seeing exactly why it cannot run, is what anybody
comparing candidates needs. Reading the *manifest in full* — entry
point, file listing, conformance log — needs `algorithm.inspect`,
because those describe code rather than capability. Importing one runs
the uploader's code on this server, and publishing one puts it in front
of everybody; both are the reviewer package
(`docs/plugin_import_security.md` §5).

**The governance routes are behind a flag.** Publish, unpublish, hold
and disable answer 404 until `PLANBENCH_ALGORITHM_GOVERNANCE` is on,
and that is deliberate rather than cautious: a kill switch is only safe
once the things downstream of it exist — a run that pinned which
revision it used, a queued job that stops when its bundle is turned off,
and an approval that can say its algorithm was withdrawn. Shipping the
switch first would give an operator a button whose consequences nothing
else in the system understands yet.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel

from planbench_api.accounts import Capability, User
from planbench_api.auth import ActiveUser, require_capability
from planbench_api.dependencies import get_plugin_service
from planbench_api.model_storage import CHUNK
from planbench_api.plugin_registry import PluginBundleSummary
from planbench_api.plugin_service import HostCompatibility, PluginBundleService

logger = logging.getLogger("planbench.api.plugins")

router = APIRouter(prefix="/algorithms/plugins", tags=["algorithms"])

Plugins = Annotated[PluginBundleService, Depends(get_plugin_service)]


InspectingUser = Annotated[User, Depends(require_capability(Capability.ALGORITHM_INSPECT))]


class PublicationView(BaseModel):
    """One row of the publication history, as the detail page shows it."""

    bundle_id: str
    revision: int
    published_at: str
    published_by_user_id: str | None = None
    superseded_at: str | None = None
    unpublished_at: str | None = None
    reason: str = ""
    is_current: bool


class PluginEventView(BaseModel):
    sequence: int
    revision: int
    actor_user_id: str | None
    actor_roles: str
    authorized_capability: str
    action: str
    reason: str
    created_at: str


class GovernanceRequest(BaseModel):
    reason: str = ""


def _require_governance(request: Request) -> None:
    """404 while the flag is off, because the route is not there yet.

    A 403 would say "you may not"; the truth is "this deployment has not
    turned publishing on", and a client that can tell the difference can
    hide the button rather than offer one that always fails.
    """
    if not request.app.state.deployment.algorithm_governance:
        raise HTTPException(
            status_code=404,
            detail=(
                "algorithm governance is not enabled on this deployment "
                "(PLANBENCH_ALGORITHM_GOVERNANCE)"
            ),
        )


class PluginBundleDetail(BaseModel):
    """One imported algorithm, with the verdict recomputed now.

    The compatibility report is not stored alongside the bundle and not
    cached here: a deployment can gain or lose a provider, and a verdict
    remembered from upload time would be a claim about a host that has
    since changed.
    """

    bundle: PluginBundleSummary
    compatibility: HostCompatibility
    #: The revision an engineer would actually get, or ``None`` while
    #: nobody has published one. Present for every reader: "why is this
    #: not in my picker?" is a question the person picking has to be able
    #: to answer without asking a reviewer.
    published_revision: int | None = None
    #: Manifest, entry point and history — code, not capability, so this
    #: half is empty for a reader without ``algorithm.inspect``.
    manifest: dict | None = None
    entry_point: str | None = None
    publications: list[PublicationView] | None = None


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
    return [
        PluginBundleSummary.of(record, user.id, inspect=user.can(Capability.ALGORITHM_INSPECT))
        for record in plugins.list()
    ]


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
    return PluginBundleSummary.of(record, user.id, inspect=user.can(Capability.ALGORITHM_INSPECT))


@router.get("/{bundle_id}", response_model=PluginBundleDetail)
def get_plugin(bundle_id: str, plugins: Plugins, user: ActiveUser) -> PluginBundleDetail:
    """One bundle. How much of it comes back depends on the caller.

    The split is between *capability* and *code*. What an algorithm
    needs, what it supports and whether this host can run it are what an
    engineer uses to decide whether to pick it — withhold those and they
    cannot configure a candidate. Its entry point, its file listing and
    its conformance log describe the code itself, and reading code is
    the reviewer's job.
    """
    record = plugins.get(bundle_id)
    inspecting = user.can(Capability.ALGORITHM_INSPECT)
    current = plugins.publication(record.plugin_id)
    return PluginBundleDetail(
        bundle=PluginBundleSummary.of(record, user.id, inspect=inspecting),
        compatibility=plugins.compatibility(bundle_id),
        published_revision=current.revision if current is not None else None,
        manifest=record.manifest if inspecting else None,
        entry_point=record.entry_point if inspecting else None,
        publications=(
            [_publication_view(row) for row in plugins.publication_history(record.plugin_id)]
            if inspecting
            else None
        ),
    )


def _publication_view(row) -> PublicationView:
    return PublicationView(
        bundle_id=row.bundle_id,
        revision=row.revision,
        published_at=row.published_at,
        published_by_user_id=row.published_by_user_id,
        superseded_at=row.superseded_at,
        unpublished_at=row.unpublished_at,
        reason=row.reason,
        is_current=row.is_current,
    )


@router.get("/{bundle_id}/events", response_model=list[PluginEventView])
def plugin_events(bundle_id: str, plugins: Plugins, _: InspectingUser) -> list[PluginEventView]:
    """Who did what to this bundle, oldest first."""
    return [
        PluginEventView(
            sequence=event.sequence,
            revision=event.revision,
            actor_user_id=event.actor_user_id,
            actor_roles=event.actor_roles,
            authorized_capability=event.authorized_capability,
            action=event.action,
            reason=event.reason,
            created_at=event.created_at,
        )
        for event in plugins.events(bundle_id)
    ]


@router.post("/{bundle_id}/publish", response_model=PluginBundleSummary)
def publish_plugin(
    bundle_id: str,
    payload: GovernanceRequest,
    plugins: Plugins,
    user: ActiveUser,
    request: Request,
) -> PluginBundleSummary:
    """Make this the revision every engineer gets."""
    _require_governance(request)
    return PluginBundleSummary.of(
        plugins.publish(bundle_id, user, payload.reason),
        user.id,
        inspect=user.can(Capability.ALGORITHM_INSPECT),
    )


@router.post("/{bundle_id}/unpublish", response_model=PluginBundleSummary)
def unpublish_plugin(
    bundle_id: str,
    payload: GovernanceRequest,
    plugins: Plugins,
    user: ActiveUser,
    request: Request,
) -> PluginBundleSummary:
    """Take it back out. Publishing again restores it."""
    _require_governance(request)
    return PluginBundleSummary.of(
        plugins.unpublish(bundle_id, user, payload.reason),
        user.id,
        inspect=user.can(Capability.ALGORITHM_INSPECT),
    )


@router.post("/{bundle_id}/hold", response_model=PluginBundleSummary)
def hold_plugin(
    bundle_id: str,
    payload: GovernanceRequest,
    plugins: Plugins,
    user: ActiveUser,
    request: Request,
) -> PluginBundleSummary:
    _require_governance(request)
    return PluginBundleSummary.of(
        plugins.hold(bundle_id, user, payload.reason),
        user.id,
        inspect=user.can(Capability.ALGORITHM_INSPECT),
    )


@router.post("/{bundle_id}/release-hold", response_model=PluginBundleSummary)
def release_plugin_hold(
    bundle_id: str,
    payload: GovernanceRequest,
    plugins: Plugins,
    user: ActiveUser,
    request: Request,
) -> PluginBundleSummary:
    _require_governance(request)
    return PluginBundleSummary.of(
        plugins.release_hold(bundle_id, user, payload.reason),
        user.id,
        inspect=user.can(Capability.ALGORITHM_INSPECT),
    )


@router.post("/{bundle_id}/disable", response_model=PluginBundleSummary)
def disable_plugin(
    bundle_id: str,
    payload: GovernanceRequest,
    plugins: Plugins,
    user: ActiveUser,
    request: Request,
) -> PluginBundleSummary:
    """Retire it for good, on governance grounds. Needs a reason.

    The administrator's kill switch is a different route with the same
    effect, so the audit row can say which job the caller was doing —
    retiring an algorithm and responding to an incident are not the same
    act, and a shared endpoint would have to guess.
    """
    _require_governance(request)
    record = plugins.disable(
        bundle_id, user, payload.reason, capability=Capability.ALGORITHM_DISABLE
    )
    _note_approvals_that_rested_on_it(request, record, user, payload.reason)
    return PluginBundleSummary.of(record, user.id, inspect=user.can(Capability.ALGORITHM_INSPECT))


def _note_approvals_that_rested_on_it(request: Request, record, user, reason: str) -> None:
    """Write into each affected run's journal that its algorithm went away.

    **Not a withdrawal.** The system does not sign anything on a
    reviewer's behalf, and disabling can happen for a security fix, a
    crash, a dependency, or an investigation — none of which prove the
    original recommendation was wrong. What it does is leave a dated
    entry beside the approval, so somebody reading that journal later
    finds out *there* rather than by noticing the algorithm is gone.

    Failure here is logged and swallowed: an incomplete journal entry is
    bad, and an algorithm that could not be turned off because writing
    one failed is worse.
    """
    runs = request.app.state.repos.decision_runs
    try:
        affected = [
            run
            for run in runs.list()
            if run.config_state == "approved"
            and any(
                entry.get("bundle_id") == record.id
                for entry in (getattr(run, "candidates", []) or [])
            )
        ]
    except Exception:  # noqa: BLE001 - see the docstring
        logger.warning("could not look for approvals resting on this bundle", exc_info=True)
        return
    for run in affected:
        try:
            runs.append_event(
                run.id,
                "algorithm_disabled_after_approval",
                user.id,
                user.nickname,
                run.config_state,
                run.config_state,
                f"{record.label} (revision {record.revision}) was disabled: {reason}",
            )
        except Exception:  # noqa: BLE001 - see the docstring
            logger.warning(
                "could not record the disable against a run", extra={"context": {"run": run.id}}
            )


@router.post("/{bundle_id}/validate", response_model=PluginBundleSummary)
def validate_plugin(bundle_id: str, plugins: Plugins, user: ActiveUser) -> PluginBundleSummary:
    """Unpack the bundle and run the conformance suite again.

    Runs the uploader's code, so it is the import privilege rather than
    the read one. Worth re-asking after a deployment changes: a bundle
    left unchecked because a provider was missing is not a bundle that
    failed.
    """
    return PluginBundleSummary.of(
        plugins.revalidate(bundle_id, user), user.id, inspect=user.can(Capability.ALGORITHM_INSPECT)
    )


@router.patch("/{bundle_id}", response_model=PluginBundleSummary)
def update_plugin(
    bundle_id: str, payload: PluginUpdateRequest, plugins: Plugins, user: ActiveUser
) -> PluginBundleSummary:
    changes = {key: value for key, value in payload.model_dump().items() if value is not None}
    return PluginBundleSummary.of(
        plugins.update(bundle_id, changes, user),
        user.id,
        inspect=user.can(Capability.ALGORITHM_INSPECT),
    )
