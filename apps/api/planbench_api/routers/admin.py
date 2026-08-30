"""Administering the deployment: accounts, the trail, and operations.

Everything here is `user.manage`, `system.configure` or `system.operate`
— the package that runs the platform and holds **no** business
capability. An administrator cannot start a run, approve one or publish
an algorithm; somebody who does both jobs holds both roles, and each act
is audited under the capability that allowed it.

**Accounts are disabled, never deleted.** The audit trail points at user
ids, and removing the row it points at turns every entry naming that
person into a record of nobody. Disabling stops them signing in, which
is the thing anybody actually needs.

**Acting on somebody else's work needs a reason.** Cancelling their job,
editing their deployment — the endpoints that do it take ``reason`` and
mark the entry ``override``. Not a mode to enter: a field to fill, on
the four routes where it applies, so an administrator stepping in is a
visible event rather than an invisible one.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from planbench_api.accounts import (
    BUSINESS_ROLES,
    AccountEvent,
    Capability,
    LastAdministratorError,
    Role,
    roles_label,
)
from planbench_api.auth import require_capability
from planbench_api.errors import DomainValidationError

logger = logging.getLogger("planbench.api.admin")

router = APIRouter(prefix="/admin", tags=["admin"])

ManagingUser = Annotated[object, Depends(require_capability(Capability.USER_MANAGE))]
OperatingUser = Annotated[object, Depends(require_capability(Capability.SYSTEM_OPERATE))]
AuditingUser = Annotated[object, Depends(require_capability(Capability.AUDIT_READ))]


class AccountResource(BaseModel):
    """One account, as the Users table shows it.

    No password hash and no token — the same rule the public user view
    follows, for the same reason: this response is rendered in a browser
    and copied into support conversations.
    """

    id: str
    nickname: str
    email: str = ""
    display_name: str = ""
    roles: list[str] = []
    capabilities: list[str] = []
    disabled: bool = False
    disabled_at: str | None = None
    last_sign_in_at: str | None = None
    created_at: str = ""


class RoleGrantRequest(BaseModel):
    role: str
    #: Required. A grant with no reason is a grant nobody can review, and
    #: this table is the one an auditor reads first.
    reason: str = Field(min_length=1)


class ReasonRequest(BaseModel):
    reason: str = Field(min_length=1)


class AccountEventResource(BaseModel):
    sequence: int
    user_id: str
    actor_user_id: str | None
    actor_roles: str
    authorized_capability: str
    action: str
    previous: str
    new: str
    reason: str
    override: bool
    created_at: str


def _users(request: Request):
    return request.app.state.repos.users


def _resource(user) -> AccountResource:
    return AccountResource(
        id=user.id,
        nickname=user.nickname,
        email=user.email,
        display_name=user.display_name,
        roles=sorted(role.value for role in user.roles),
        capabilities=sorted(capability.value for capability in user.capabilities),
        disabled=user.disabled,
        disabled_at=user.disabled_at or None,
        last_sign_in_at=None,
        created_at=user.created_at,
    )


def _record(request: Request, actor, subject_id: str, action: str, **fields) -> None:
    users = _users(request)
    try:
        users.record_account_event(
            AccountEvent(
                user_id=subject_id,
                actor_user_id=actor.id,
                actor_roles=roles_label(actor.roles),
                authorized_capability=Capability.USER_MANAGE.value,
                action=action,
                **fields,
            )
        )
    except Exception:  # noqa: BLE001 - the change happened; the note is best effort
        logger.warning("could not record an account event", exc_info=True)


@router.get("/users", response_model=list[AccountResource])
def list_accounts(request: Request, _: ManagingUser) -> list[AccountResource]:
    return [_resource(user) for user in _users(request).list()]


@router.post("/users/{user_id}/roles", response_model=AccountResource)
def grant_role(
    user_id: str, payload: RoleGrantRequest, request: Request, actor: ManagingUser
) -> AccountResource:
    """Add a package to an account.

    ``demo_owner`` is refused here whatever the profile. It carries every
    capability at once, so if an administrator could grant it, any
    administrator could make themselves a superuser — and the whole
    reason the packages do not nest is that ``admin`` is not that.
    """
    role = _parse_role(payload.role)
    user = _users(request).get(user_id)
    updated = _users(request).set_roles(
        user_id,
        user.roles | {role},
        granted_by_user_id=actor.id,
        reason=payload.reason,
    )
    _record(
        request,
        actor,
        user_id,
        "role_granted",
        previous=roles_label(user.roles),
        new=roles_label(updated.roles),
        reason=payload.reason,
    )
    return _resource(updated)


@router.delete("/users/{user_id}/roles/{role_name}", response_model=AccountResource)
def revoke_role(
    user_id: str, role_name: str, reason: str, request: Request, actor: ManagingUser
) -> AccountResource:
    """Remove a package.

    Refused when it would leave nobody able to manage accounts — checked
    by **capability** inside the write's own transaction, so two
    administrators revoking each other at the same moment cannot both
    succeed.
    """
    if not reason.strip():
        raise DomainValidationError("revoking a role needs a reason")
    role = _parse_role(role_name)
    user = _users(request).get(user_id)
    try:
        updated = _users(request).set_roles(
            user_id, user.roles - {role}, granted_by_user_id=actor.id, reason=reason
        )
    except LastAdministratorError as refusal:
        raise DomainValidationError(str(refusal)) from refusal
    _record(
        request,
        actor,
        user_id,
        "role_revoked",
        previous=roles_label(user.roles),
        new=roles_label(updated.roles),
        reason=reason,
    )
    return _resource(updated)


@router.post("/users/{user_id}/disable", response_model=AccountResource)
def disable_account(
    user_id: str, payload: ReasonRequest, request: Request, actor: ManagingUser
) -> AccountResource:
    """Stop an account signing in. Its history stays."""
    try:
        updated = _users(request).set_disabled(user_id, True)
    except LastAdministratorError as refusal:
        raise DomainValidationError(str(refusal)) from refusal
    _record(request, actor, user_id, "disabled", reason=payload.reason, new="disabled")
    return _resource(updated)


@router.post("/users/{user_id}/enable", response_model=AccountResource)
def enable_account(
    user_id: str, payload: ReasonRequest, request: Request, actor: ManagingUser
) -> AccountResource:
    updated = _users(request).set_disabled(user_id, False)
    _record(request, actor, user_id, "enabled", reason=payload.reason, previous="disabled")
    return _resource(updated)


@router.get("/audit", response_model=list[AccountEventResource])
def read_audit(
    request: Request, actor: AuditingUser, user_id: str | None = None
) -> list[AccountEventResource]:
    """Account events, oldest first.

    A reviewer holds ``audit.read`` too, and gets the same route — the
    projection is what differs: without ``user.manage`` the account trail
    is not theirs to read, so they see only their own. Two routes would
    mean two places to remember to filter.
    """
    events = _users(request).list_account_events(user_id)
    if not actor.can(Capability.USER_MANAGE):
        events = [event for event in events if event.user_id == actor.id]
    return [
        AccountEventResource(
            sequence=event.sequence,
            user_id=event.user_id,
            actor_user_id=event.actor_user_id,
            actor_roles=event.actor_roles,
            authorized_capability=event.authorized_capability,
            action=event.action,
            previous=event.previous,
            new=event.new,
            reason=event.reason,
            override=event.override,
            created_at=event.created_at,
        )
        for event in events
    ]


class JobResource(BaseModel):
    id: str
    kind: str
    state: str
    created_by: str | None = None
    purpose: str = "production"
    run_id: str | None = None
    message: str = ""


@router.get("/ops/jobs", response_model=list[JobResource])
def list_jobs(request: Request, _: OperatingUser) -> list[JobResource]:
    return [
        JobResource(
            id=job.id,
            kind=job.kind,
            state=job.state.value,
            created_by=job.created_by,
            purpose=job.purpose,
            run_id=job.run_id,
            message=job.message,
        )
        for job in request.app.state.decision_jobs.list()
    ]


@router.post("/ops/jobs/{job_id}/cancel", response_model=JobResource)
def cancel_any_job(
    job_id: str, payload: ReasonRequest, request: Request, actor: OperatingUser
) -> JobResource:
    """Cancel somebody else's job. Break-glass, so it takes a reason.

    The owner cancels their own run through the ordinary route. This one
    exists for the case an administrator has to step in, and the reason
    is what the owner reads when their three-hour sweep stops.
    """
    jobs = request.app.state.decision_jobs
    jobs.cancel(job_id)
    job = jobs.get(job_id)
    logger.info(
        "job cancelled by an administrator",
        extra={
            "context": {
                "job_id": job_id,
                "actor": actor.id,
                "owner": job.created_by,
                "reason": payload.reason,
                "override": True,
            }
        },
    )
    return JobResource(
        id=job.id,
        kind=job.kind,
        state=job.state.value,
        created_by=job.created_by,
        purpose=job.purpose,
        run_id=job.run_id,
        message=job.message,
    )


def _parse_role(name: str) -> Role:
    cleaned = (name or "").strip().lower()
    try:
        role = Role(cleaned)
    except ValueError as exc:
        allowed = ", ".join(role.value for role in BUSINESS_ROLES)
        raise DomainValidationError(f"{name!r} is not a role (expected: {allowed})") from exc
    if role is Role.DEMO_OWNER:
        raise DomainValidationError(
            "demo_owner carries every capability at once and is bound by the deployment "
            "profile, not granted here — otherwise any administrator could make themselves "
            "a superuser"
        )
    return role
