"""What a selection run will execute, decided once and written down.

**The problem is a gap in time.** A request names stacks —
``astar+org.vinai.vfh-plus`` — and a stack name is a *pointer*: it
resolves to whichever bundle is current when somebody asks. On a queue,
"when somebody asks" is not "when the request was made". A reviewer can
publish a new revision or withdraw one in between, and the job then
measures code the requester never chose, files the result under an id
that claims otherwise, and leaves nothing behind that could tell.

So the pointer is followed once, at the moment of the request, and the
answer is kept: the bundle, its revision, the checksum of the archive
that will run, and the fingerprint of the providers this deployment
could offer. Starting the job re-checks that answer rather than asking
the question again — the difference being that a re-check can *fail
loudly*, and a second resolution cannot even notice.

Two rules follow from that, and they are the reason this module is
separate from the router:

* a **production** run may only pin what a reviewer published, so a
  conclusion never rests on code nobody vouched for;
* a **validation** run may pin an unpublished bundle, but it must name
  it outright. A stack alias resolves to the current publication by
  definition, so a reviewer asking to watch revision 4 behave has to say
  ``bundle_id`` — the alias would silently hand them revision 3.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import StrEnum


class RunPurpose(StrEnum):
    #: The ordinary case: evidence somebody may submit and approve.
    PRODUCTION = "production"
    #: A reviewer watching a bundle behave before publishing it. Never
    #: submitted, never approved — see :mod:`planbench_api.decisions`.
    VALIDATION = "validation"


class IdentityError(Exception):
    """The request cannot be pinned to code, and running it would guess."""


@dataclass(frozen=True)
class CandidateIdentity:
    """One candidate, resolved to the code that will actually run."""

    slot: int
    stack: str
    local_config: str = ""
    bundle_id: str | None = None
    plugin_id: str | None = None
    revision: int | None = None
    archive_checksum: str | None = None
    provider_fingerprint: str = ""
    runtime_profile: str = ""

    @property
    def is_imported(self) -> bool:
        return self.bundle_id is not None

    def describe(self) -> str:
        if not self.is_imported:
            return self.stack
        return f"{self.stack} (revision {self.revision})"


@dataclass(frozen=True)
class PinnedRun:
    """Everything a job needs to run exactly what was asked for."""

    purpose: RunPurpose
    task_profile_id: str
    candidates: tuple[CandidateIdentity, ...] = field(default_factory=tuple)

    @property
    def specs(self) -> list[tuple[str, str]]:
        """The ``(stack, local_config)`` pairs the engine still takes."""
        return [(row.stack, row.local_config) for row in self.candidates]


def plugin_id_in(stack: str) -> str | None:
    """The imported plugin a stack id names, if it names one.

    Stack ids are ``<global>+<local>`` and an imported controller puts
    its own plugin id on the right (``stack_id_for``). A plugin id
    contains dots and a built-in controller's name does not, which is
    enough to tell them apart without asking the registry — and asking
    the registry here would mean this module could not answer during a
    migration or a backfill, when the runtime catalogue is not loaded.
    """
    _, separator, local = stack.partition("+")
    if not separator or "." not in local:
        return None
    return local


def provider_fingerprint(capabilities: list[str] | tuple[str, ...]) -> str:
    """A stable digest of what this deployment could offer.

    Sorted before hashing, because the set is what matters and the order
    a provider graph happens to enumerate in is not something a stored
    run should be sensitive to.
    """
    joined = "\n".join(sorted(capabilities))
    return hashlib.sha256(joined.encode()).hexdigest()[:16]


def resolve(
    *,
    purpose: RunPurpose,
    task_profile_id: str,
    specs: list[tuple[str, str]],
    bundle_ids: list[str | None] | None = None,
    lookup,
    governance: bool,
    fingerprint: str = "",
) -> PinnedRun:
    """Follow every pointer once and return what was found.

    ``lookup`` answers two questions about a plugin, and is passed in
    rather than imported so this stays testable without a database:
    ``current(plugin_id)`` gives the published bundle, and
    ``get(bundle_id)`` gives a named one.

    With governance off, an imported stack still resolves — to whatever
    the older rule would have offered — but a missing answer is not
    fatal. That asymmetry is deliberate: before publishing exists there
    is no such thing as "not published", so refusing here would refuse
    runs that are perfectly ordinary today.
    """
    named = list(bundle_ids or [])
    resolved: list[CandidateIdentity] = []
    for slot, (stack, local_config) in enumerate(specs):
        explicit = named[slot] if slot < len(named) else None
        plugin_id = plugin_id_in(stack)

        if explicit is not None:
            if purpose is RunPurpose.PRODUCTION:
                raise IdentityError(
                    "a production run picks the published revision by its stack name. "
                    "Naming a bundle outright is how a reviewer watches an unpublished "
                    "one behave, which is a validation run"
                )
            record = lookup.get(explicit)
            resolved.append(_identity(slot, stack, local_config, record, fingerprint))
            continue

        if plugin_id is None:
            resolved.append(
                CandidateIdentity(
                    slot=slot,
                    stack=stack,
                    local_config=local_config,
                    provider_fingerprint=fingerprint,
                )
            )
            continue

        record = lookup.current(plugin_id)
        if record is None:
            if governance:
                raise IdentityError(
                    f"{stack!r} names an imported algorithm that has no published "
                    "revision. A reviewer publishes one before it can carry a "
                    "conclusion; until then it can only be used in a validation run, "
                    "which names the bundle outright"
                )
            record = lookup.newest(plugin_id)
            if record is None:
                raise IdentityError(f"{stack!r} names an imported algorithm nothing knows about")
        resolved.append(_identity(slot, stack, local_config, record, fingerprint))
    return PinnedRun(purpose=purpose, task_profile_id=task_profile_id, candidates=tuple(resolved))


def _identity(slot, stack, local_config, record, fingerprint) -> CandidateIdentity:
    return CandidateIdentity(
        slot=slot,
        stack=stack,
        local_config=local_config,
        bundle_id=record.id,
        plugin_id=record.plugin_id,
        revision=record.revision,
        archive_checksum=record.checksum,
        provider_fingerprint=fingerprint,
        runtime_profile=record.role,
    )


def recheck(pinned: PinnedRun, lookup, governance: bool) -> None:
    """Confirm, at start, that the answer found at request time still holds.

    **Not a second resolution.** Re-resolving would quietly run whatever
    is current now; this compares against what was pinned and refuses
    with the name of what moved. A job that fails saying "revision 3 was
    unpublished while this was queued" is recoverable; one that silently
    measures revision 4 is not.

    A validation run checks only that its bundle is not disabled: the
    whole point of it is to run something unpublished.
    """
    for row in pinned.candidates:
        if not row.is_imported:
            continue
        record = lookup.get(row.bundle_id)
        if record.status.value == "disabled":
            raise IdentityError(
                f"{row.stack} was disabled while this run was queued "
                f"({record.disabled_reason or 'no reason recorded'})"
            )
        if pinned.purpose is RunPurpose.VALIDATION:
            continue
        if record.status.value != "active":
            raise IdentityError(f"{row.stack} was put on hold while this run was queued")
        if not governance:
            continue
        current = lookup.current(row.plugin_id)
        if current is None or current.id != row.bundle_id:
            raise IdentityError(
                f"{row.stack} pinned revision {row.revision}, which is no longer the "
                "published one. Start the run again to measure what is published now"
            )


__all__ = [
    "CandidateIdentity",
    "IdentityError",
    "PinnedRun",
    "RunPurpose",
    "plugin_id_in",
    "provider_fingerprint",
    "recheck",
    "resolve",
]
