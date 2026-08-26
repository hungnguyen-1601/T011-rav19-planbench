"""The sidecar that makes a replay worth anything, and the rules for
scoring a replay when it does not exist.

**The data fact this is built on** (checked against the code, not
assumed): a trace Parquet holds neither the plan polyline nor the
costmap. The *outputs* — the paths the global planner returned — live in
the episode JSON as ``StackRun.plans``. The *inputs* that produced them
— the costmap snapshot, the believed start pose at replan time, the
goal, the provider revisions, the dynamic obstacles already burned into
the grid, the planner's parameter fingerprint — are recorded **nowhere**.

Two consequences, and neither is negotiable.

**Comparing output plans is a refuter, never a promoter.** Rebuild a
costmap, replan, and compare bytes with the recorded plan: a mismatch
proves the reconstruction is wrong, so the check is ``not_checkable``.
A match proves nothing — many different costmaps produce the same path.
This is the same screening logic as P1: evidence that can only
eliminate is still evidence, as long as nobody reads it in the other
direction.

**Every run recorded before this sidecar is capped at ``associated``.**
A replay over rebuilt inputs is ``reconstructed`` provenance, full stop,
even when the output matches. Quietly building a world that looks close
enough and calling the result a verified mechanism is the exact failure
this layer exists to prevent.

**Why the sidecar records failures too.** ``StackRun.plans`` keeps only
plans that found a path, and the episode most in need of explaining is
the one where the planner returned ``no_path`` — "the planner considered
that gap impassable" is the claim, and the attempt that produced it
leaves no row today. So the writer (E4.5) emits one record per planning
attempt including the failures, and :func:`validate_episode_attempts`
refuses a set with a hole in it: a missing attempt number is the
signature of exactly the case that got skipped.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from planbench_explanation.levels import ClaimLevel, weakest
from planbench_explanation.provenance import ExecutionStatus, InputProvenance
from planbench_explanation.versioning import validate_code_ref
from planbench_schemas.geometry import Pose2D

#: How one planning attempt ended.
PlanningOutcome = Literal["path", "no_path", "error"]


class PlanningQuery(BaseModel):
    """What the planner was asked, at the pose it believed it was in."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    start_pose: Pose2D
    goal_pose: Pose2D


class PlanningInputEvidence(BaseModel):
    """One planning attempt's inputs, as recorded by the runner.

    A separate file, referenced one way: it touches none of the three
    frozen contract identities and no existing schema. Adding it costs
    the runner a write per planning attempt and buys the only route to
    ``mechanism_verified`` for a replay.

    **The record is an index, not the evidence.** It carries what a
    replay *compares* — checksums, the query, the fingerprint — and a
    ``snapshot_ref`` to what a replay *loads*. Keeping the grid out of
    the record keeps the sidecar readable and one line per attempt;
    keeping the reference in it is what makes the record worth writing.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    episode_context_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    #: 1-based, one per attempt, initial plan included.
    planning_attempt: int = Field(ge=1)
    simulation_tick: int = Field(ge=0)
    query: PlanningQuery
    costmap_checksum: str = Field(min_length=1)
    #: Where the grid, the query and the planner's actual configuration
    #: were written. **A checksum cannot be replayed from.** It verifies
    #: that a snapshot somebody already has is the right one; it does not
    #: produce the snapshot, and the first cut of the writer stored only
    #: the checksum — which meant a replay had nothing to load and the
    #: whole point of the sidecar was missing while its tests passed,
    #: because they built the replay's inputs by copying the record.
    snapshot_ref: str = Field(min_length=1)
    #: SHA-256 of the **whole** snapshot, canonically serialised.
    #:
    #: ``costmap_checksum`` covers the grid, and the first version
    #: checked only that — so a snapshot whose start pose, goal, planner
    #: parameters or seed had been swapped loaded cleanly, and a replay
    #: would have answered a different question with the right grid.
    #: Every field a replay reads is inside this one.
    snapshot_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_revision_refs: tuple[str, ...] = ()
    planner_fingerprint: str = Field(min_length=1)
    #: ``git:<40 hex>`` or ``sha256:<64 hex>`` of the code that ran.
    #: Checked before a replay is attempted at all — replaying today's
    #: planner over yesterday's inputs verifies today's planner, and a
    #: label nobody can resolve makes that check unrunnable.
    execution_environment_ref: str = Field(min_length=1)
    outcome: PlanningOutcome
    output_plan_checksum: str | None = None
    #: The route this attempt returned, in world coordinates.
    #:
    #: **Nothing else persists it.** The trace records where the robot
    #: *went*; ``StackRun.plans`` lives only in the process that ran the
    #: episode; the metrics keep the plan's *length* and throw the
    #: polyline away. So a page drawing a trajectory could not show what
    #: the planner had actually asked for — and the gap between the two
    #: is most of what a replan is about.
    #:
    #: Optional, and empty for an attempt that found nothing: a refusal
    #: has no route to store. A record written before this field existed
    #: loads with it empty, which is the honest reading — that run did
    #: not keep its plans.
    output_path: tuple[tuple[float, float], ...] = ()
    failure_code: str | None = None

    @model_validator(mode="after")
    def _check(self) -> PlanningInputEvidence:
        validate_code_ref(self.execution_environment_ref, field="execution_environment_ref")
        if self.outcome == "path":
            if not self.output_plan_checksum:
                raise ValueError(
                    "a successful planning attempt must record its output plan checksum"
                )
            if self.failure_code:
                raise ValueError("a successful planning attempt has no failure code")
        else:
            if self.output_path:
                raise ValueError(
                    f"outcome={self.outcome!r} carries a route; an attempt that found "
                    "no path produced nothing to draw"
                )
            if self.output_plan_checksum is not None:
                raise ValueError(
                    f"outcome={self.outcome!r} recorded an output plan checksum; "
                    "an attempt that produced no path produced nothing to hash"
                )
            if not self.failure_code:
                raise ValueError(
                    f"outcome={self.outcome!r} must record a failure code — the "
                    "reason is the whole content of a failed attempt"
                )
        return self


class SidecarViolation(ValueError):
    """A set of attempt records that cannot describe one episode."""


def validate_episode_attempts(
    records: Sequence[PlanningInputEvidence],
    *,
    expected_attempts: int,
) -> None:
    """Every attempt of one episode is present, exactly once.

    Contiguity catches a writer wired into the success path only: a
    refused replan in the middle leaves a gap, and a gap is loud.

    Contiguity alone does **not** catch a truncated tail — records
    ``[1]`` for an episode that actually planned three times are
    perfectly contiguous, and that is the shape of a writer that died,
    a buffer that was never flushed, or a replan loop that stopped
    emitting. So the expected count is required, and it must come from
    a counter the **runner** owns, not from the records being checked:
    the episode's ``replan_count`` (the trace's own ``replan`` events)
    plus the initial plan. A validator that derives its expectation
    from its input can only ever agree with it.
    """
    if expected_attempts < 1:
        raise SidecarViolation(
            f"expected_attempts={expected_attempts}; every episode plans at least once, "
            "so a count below 1 means the runner's counter was not read"
        )
    if not records:
        raise SidecarViolation("no planning attempts recorded for this episode")

    keys = {(record.episode_context_id, record.candidate_id) for record in records}
    if len(keys) != 1:
        raise SidecarViolation(
            f"records span {len(keys)} (episode, candidate) pairs: {sorted(keys)}"
        )

    attempts = sorted(record.planning_attempt for record in records)
    duplicates = sorted({a for a in attempts if attempts.count(a) > 1})
    if duplicates:
        raise SidecarViolation(f"duplicate planning_attempt value(s) {duplicates}")
    expected = list(range(1, expected_attempts + 1))
    if attempts != expected:
        missing = sorted(set(expected) - set(attempts))
        extra = sorted(set(attempts) - set(expected))
        raise SidecarViolation(
            f"planning attempts do not match the runner's count: got {attempts}, "
            f"expected {expected}, missing {missing}, unexpected {extra}. A gap in "
            "the middle is usually a refused replan the writer never saw; a missing "
            "tail is usually a writer that stopped before the episode did."
        )


class ReplayObservation(BaseModel):
    """What a replay run actually produced, for comparison."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    costmap_checksum: str = Field(min_length=1)
    query: PlanningQuery
    planner_fingerprint: str = Field(min_length=1)
    execution_environment_ref: str = Field(min_length=1)
    outcome: PlanningOutcome
    output_plan_checksum: str | None = None
    #: Compared like every other recorded field. A replay that refuses
    #: for a different reason than the run did has not reproduced the
    #: run: "no_global_path" and "planner_timeout" are both ``no_path``
    #: and they are different mechanisms, which is the whole subject of
    #: the claim being checked.
    failure_code: str | None = None


class ReplayAdmission(BaseModel):
    """What a replay is allowed to contribute, and why."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    execution_status: ExecutionStatus
    input_provenance: InputProvenance
    #: ``None`` when the replay supports nothing at all.
    maximum_supported_level: ClaimLevel | None
    reasons: tuple[str, ...]


#: A replay reproduces a condition; it varies nothing. So no replay,
#: however well provenanced, reaches ``intervention_supported``.
REPLAY_CEILING: ClaimLevel = "mechanism_verified"


def _not_checkable(*reasons: str) -> ReplayAdmission:
    return ReplayAdmission(
        execution_status="not_checkable",
        input_provenance="missing",
        maximum_supported_level=None,
        reasons=tuple(reasons),
    )


def admit_replay_with_sidecar(
    recorded: PlanningInputEvidence,
    replayed: ReplayObservation,
    *,
    inputs_loaded_from_record: bool,
) -> ReplayAdmission:
    """Score a replay of an attempt whose inputs were recorded.

    ``inputs_loaded_from_record`` separates the two honest provenances:
    the harness read the recorded costmap and query straight back
    (``recorded``), or it rebuilt them and every fingerprint matched
    (``verified_reconstruction``). Both may reach
    ``mechanism_verified``; nothing else may.
    """
    mismatches = [
        field
        for field, left, right in (
            ("costmap_checksum", recorded.costmap_checksum, replayed.costmap_checksum),
            ("query", recorded.query, replayed.query),
            ("planner_fingerprint", recorded.planner_fingerprint, replayed.planner_fingerprint),
            (
                "execution_environment_ref",
                recorded.execution_environment_ref,
                replayed.execution_environment_ref,
            ),
            ("outcome", recorded.outcome, replayed.outcome),
            ("output_plan_checksum", recorded.output_plan_checksum, replayed.output_plan_checksum),
            ("failure_code", recorded.failure_code, replayed.failure_code),
        )
        if left != right
    ]
    if mismatches:
        return _not_checkable(*(f"mismatch:{field}" for field in mismatches))

    provenance: InputProvenance = (
        "recorded" if inputs_loaded_from_record else "verified_reconstruction"
    )
    return ReplayAdmission(
        execution_status="completed",
        input_provenance=provenance,
        maximum_supported_level=REPLAY_CEILING,
        reasons=("all_recorded_inputs_matched",),
    )


def admit_replay_without_sidecar(
    replayed: ReplayObservation,
    *,
    recorded_output_plan_checksum: str | None,
    plans_recorded: bool,
) -> ReplayAdmission:
    """Score a replay of a run predating the sidecar.

    ``plans_recorded`` distinguishes "this episode produced no plans"
    from "this episode's plans were never written down" — an empty
    ``StackRun.plans`` means the latter, and reconstructing ``(plan,)``
    for it would claim the episode never replanned.

    A byte match returns ``reconstructed`` and caps at ``associated``,
    with the reason spelled out in the record: the match is not what
    admitted the evidence, and a later reader must not mistake it for
    verification.
    """
    if not plans_recorded:
        return _not_checkable("plans_not_recorded")

    if recorded_output_plan_checksum is None or replayed.output_plan_checksum is None:
        return _not_checkable("no_output_plan_to_compare")

    if recorded_output_plan_checksum != replayed.output_plan_checksum:
        return _not_checkable("reconstruction_refuted:output_plan_differs")

    return ReplayAdmission(
        execution_status="completed",
        input_provenance="reconstructed",
        maximum_supported_level=weakest(REPLAY_CEILING, "associated"),
        reasons=(
            "inputs_were_not_recorded",
            "output_plan_match_is_not_evidence:many_costmaps_yield_one_path",
        ),
    )
