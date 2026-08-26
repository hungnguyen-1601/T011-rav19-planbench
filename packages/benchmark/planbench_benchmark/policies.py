"""The policy registry: ``Candidate(type="monolithic")`` becomes runnable.

This is debt A5 paid (notes 2026-08-13). The simulator side has existed
since 6.6.0 — ``MonolithicPolicy`` is the adapter, ``run_policy`` drives
one through the same loop as every stack — but nothing turned a declared
monolithic candidate into a policy object. This module is that step:
a registry keyed by ``PolicyComponent.name``, and a checkpoint rule.

**Layering, same as ``_build_ppo``.** This package knows files, never
storage: a policy with weights takes a ``resolve_checkpoint`` callable
(the API's model registry provides one), and refuses to run without it
rather than guessing where weights live. A policy *without* weights must
declare ``checkpoint="builtin"`` — any other value would imply weights
that do not exist, and since the checkpoint is hashed into
``candidate_id``, it would mint distinct candidate ids for
configurations that cannot differ.

The one registered policy is ``greedy_reference_policy`` — a reference
in the D12 sense, here so the whole path (declare → build → ``run_policy``)
is real rather than promised. It is not a contender, and the evidence
machinery of plan §5.10 will say so structurally; until then its entry
says so in text.
"""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel, ConfigDict, Field

from planbench_decision.candidate import Candidate
from planbench_planning.common.policy_base import MonolithicPolicy
from planbench_planning.common.reference_policy import GreedyReferencePolicy

#: The checkpoint a weightless policy must declare. A sentinel rather
#: than an empty string because ``PolicyComponent.checkpoint`` requires
#: content — "which weights ran" must always have an answer, and for a
#: built-in the answer is "the code itself".
BUILTIN_CHECKPOINT = "builtin"


class UnknownPolicyError(ValueError):
    """A policy name the registry has never heard of."""


class PolicyCheckpointError(ValueError):
    """The checkpoint declaration and the policy's nature disagree."""


class PolicyEntry(BaseModel):
    """One registered monolithic policy family."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    #: D12 class: a reference is never a contender. Recorded on the entry
    #: so the refusal can quote it; enforced structurally by the
    #: evidence-class machinery when it arrives (plan §5.10).
    reference: bool
    requires_checkpoint: bool
    #: Receives the *resolved filesystem path* of the weights, or None
    #: for a weightless policy. Resolution is the caller's layer.
    builder: Callable[[str | None], MonolithicPolicy]


_POLICIES: dict[str, PolicyEntry] = {}


def register_policy(entry: PolicyEntry) -> None:
    """Add a policy family. Duplicate names fail loud, same argument as
    ``ManifestIndex``: two builders under one name make "which code ran"
    unanswerable."""
    if entry.name in _POLICIES:
        raise ValueError(
            f"policy {entry.name!r} is already registered; a second builder under "
            "the same name would make candidate identity ambiguous"
        )
    _POLICIES[entry.name] = entry


def policy_entry(name: str) -> PolicyEntry:
    entry = _POLICIES.get(name)
    if entry is None:
        raise UnknownPolicyError(
            f"no policy named {name!r} is registered; known policies: {sorted(_POLICIES)}"
        )
    return entry


def list_policies() -> tuple[PolicyEntry, ...]:
    return tuple(_POLICIES[name] for name in sorted(_POLICIES))


def build_policy(
    candidate: Candidate,
    *,
    resolve_checkpoint: Callable[[str], str] | None = None,
) -> MonolithicPolicy:
    """Turn a declared monolithic candidate into the policy that runs.

    The counterpart of ``build_planners`` for the second legal candidate
    shape (HĐ-1.2). The result goes straight to ``run_policy``: same
    engine, same loop, no global search charged, no path handed over.
    """
    if candidate.type != "monolithic":
        raise UnknownPolicyError(
            "a modular candidate builds through build_planners; build_policy exists "
            "for the shape that has no layers"
        )
    assert candidate.policy is not None  # Candidate validated this shape
    entry = policy_entry(candidate.policy.name)

    if not entry.requires_checkpoint:
        if candidate.policy.checkpoint != BUILTIN_CHECKPOINT:
            raise PolicyCheckpointError(
                f"policy {entry.name!r} has no weights; declare checkpoint "
                f"{BUILTIN_CHECKPOINT!r}. {candidate.policy.checkpoint!r} implies "
                "weights that do not exist, and the checkpoint is part of "
                "candidate_id — it would mint a distinct id for a configuration "
                "that cannot differ"
            )
        return entry.builder(None)

    if resolve_checkpoint is None:
        raise PolicyCheckpointError(
            f"policy {entry.name!r} needs its checkpoint {candidate.policy.checkpoint!r} "
            "resolved to a file, and this layer only knows files — pass "
            "resolve_checkpoint (the API's model registry provides one)"
        )
    return entry.builder(resolve_checkpoint(candidate.policy.checkpoint))


register_policy(
    PolicyEntry(
        name="greedy_reference_policy",
        description=(
            "Turns toward the goal and creeps when the LiDAR says the way ahead "
            "is close. A pipeline reference (D12): it exists so the monolithic "
            "path is exercised end to end, never to be recommended."
        ),
        reference=True,
        requires_checkpoint=False,
        builder=lambda _checkpoint: GreedyReferencePolicy(),
    )
)
