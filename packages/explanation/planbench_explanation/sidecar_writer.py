"""Recording what the planner was asked, while it is being asked — E4.5.

E0 wrote the record schema and the rules for scoring a replay against
one. Nothing produced them. This is the writer, and the reason it is a
separate wave is that it is the only part of the explanation layer that
runs **inside** an episode: everything else reads artifacts afterwards.

**Afterwards is exactly what does not work here.** A trace Parquet holds
neither the costmap nor the plan; ``StackRun.plans`` holds the paths
that succeeded and not the queries that produced them, and not the
attempts that produced nothing. The costmap a planner saw at replan
seventeen — obstacles as the robot believed them, inflation as
configured, standing room relaxed around the robot — exists for the
duration of one call and is then gone. Reconstructing it later is the
``reconstructed`` provenance the ladder caps at ``associated``, and no
amount of care afterwards moves it up. So the record is written at the
call or it is not written.

**One record per attempt, failures included, and that is the point.**
The episode most in need of explaining is the one where the planner
returned no path — "the planner considered that gap impassable" is a
claim somebody wants to check, and the attempt behind it leaves no trace
today. :func:`~planbench_explanation.planning_input_evidence.validate_episode_attempts`
refuses a set with a gap, so a writer wired into the success path only
fails loudly rather than producing a tidy, wrong file.

**The recorder appends as it goes**, for the reason the trace recorder
does: an episode that raises halfway still leaves what it collected on
disk, and a buffer flushed at the end leaves nothing exactly when
something went wrong.

**What a checksum here has to mean.** ``costmap_checksum`` hashes the
grid **the planner was handed**, after inflation and after any
relaxation — not the map on disk. Two attempts in one episode see
different grids, and a checksum of the source map would make them look
identical, which would make a replay look reproducible when it is not.

**A checksum is not a snapshot.** The first cut recorded
``costmap_checksum`` and nothing else, which verifies a grid somebody
already has and cannot produce one — so a replay had nothing to load,
and the tests passed anyway because they built the replay's inputs by
copying the record's fields. What is written now is a
:class:`PlanningSnapshot` per attempt: the grid's cells and geometry,
the query, the planner's **actual configuration** and its seed. The
record keeps the checksum, for comparison, and a ``snapshot_ref``, for
loading. :func:`replay_inputs` is the other half — it reads a snapshot
back and hands over what a planner needs to be re-run.

**What this does not do.** It records inputs and hands them back; it
does not run the planner over them. The replay checkers are E6b. It also
does not make the golden suite official: that needs planted runs
*recorded with this writer*, which is a run to do, not a module to write.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import IO, Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from planbench_explanation.planning_input_evidence import (
    PlanningInputEvidence,
    PlanningOutcome,
    PlanningQuery,
    SidecarViolation,
    validate_episode_attempts,
)
from planbench_explanation.versioning import artifact_checksum, validate_code_ref
from planbench_schemas.geometry import Pose2D

#: Shape of the sidecar file. Bump MINOR to add an optional field.
#:
#: **0.2.0** — grids are stored run-length encoded. The real warehouse
#: map is 800x500, and a JSON array of its 400,000 cells is 1,020 KB per
#: attempt; run-length encoded it is 21.6 KB, a factor of 47, because an
#: occupancy grid is mostly long stretches of the same value. At two
#: candidates, thirty episodes and a handful of attempts each, the
#: difference is between a few megabytes and a few hundred.
SIDECAR_SCHEMA_VERSION = "0.2.0"

#: Name of the sidecar beside an episode's other artifacts.
SIDECAR_FILENAME = "planning_inputs.jsonl"


class SidecarHeader(BaseModel):
    """The first line of a sidecar: whose attempts these are.

    Present because a bare list of records cannot say which run wrote
    it, and a replay harness pointed at the wrong episode's inputs would
    produce a mismatch it reads as "the reconstruction is wrong" rather
    than "you opened the wrong file".
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: str = Field(default="planning_input_sidecar", pattern=r"^planning_input_sidecar$")
    schema_version: str = Field(default=SIDECAR_SCHEMA_VERSION, min_length=1)
    run_id: str = Field(min_length=1)
    episode_context_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    #: The build that produced these records. Repeated on every record
    #: because a replay compares it there; here for a reader who wants
    #: to know before parsing a thousand lines.
    execution_environment_ref: str = Field(min_length=1)


def costmap_checksum(
    cells: Iterable[int],
    *,
    width: int,
    height: int,
    resolution: float,
    origin_x: float = 0.0,
    origin_y: float = 0.0,
) -> str:
    """SHA-256 of the grid the planner was handed.

    Takes the cells rather than a grid object so the simulator's
    ``OccupancyGrid`` and a test's list hash identically, and so this
    module does not import the simulator — the explanation layer reads
    artifacts and must not depend on the thing that produces them.

    Dimensions, resolution **and origin** are inside the hash. The first
    version left the origin out, which made two grids with the same
    cells at different origins hash the same — and the origin is what
    turns a cell index into a world coordinate, so the start and goal a
    replay is given would land somewhere else entirely.
    """
    digest = hashlib.sha256()
    digest.update(f"grid:{width}x{height}@{resolution!r}+({origin_x!r},{origin_y!r}):".encode())
    digest.update(bytes(bytearray(int(cell) & 0xFF for cell in cells)))
    return digest.hexdigest()


def planner_fingerprint(name: str, parameters: dict[str, Any]) -> str:
    """SHA-256 of a planner's identity and its knobs.

    A replay that reproduces the path with a different sample budget has
    reproduced nothing, so the parameters are part of what a replay
    matches on. Serialised sorted so two equal configurations fingerprint
    the same however they were built.
    """
    payload = json.dumps(
        {"planner": name, "parameters": parameters}, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def run_length_encode(cells: Iterable[int]) -> tuple[tuple[int, int], ...]:
    """``(value, count)`` pairs, in order. Lossless and deterministic."""
    runs: list[list[int]] = []
    for cell in cells:
        value = int(cell)
        if runs and runs[-1][0] == value:
            runs[-1][1] += 1
        else:
            runs.append([value, 1])
    return tuple((value, count) for value, count in runs)


def run_length_decode(runs: Iterable[tuple[int, int]]) -> tuple[int, ...]:
    """The cells back, exactly."""
    out: list[int] = []
    for value, count in runs:
        out.extend([value] * count)
    return tuple(out)


class GridSnapshot(BaseModel):
    """The occupancy grid the planner was handed, in full.

    Stored **run-length encoded**, expanded on read. An occupancy grid is
    mostly long stretches of one value, and the map this platform
    actually runs on is 800x500: a JSON array of its cells is 1,020 KB
    and the encoded form is 21.6 KB. Storing the array would have made
    the sidecar cost more disk than the traces it sits beside, which is
    how a recording feature gets turned off.

    The geometry travels with it, so a replay harness can rebuild the
    grid without being the simulator — which is the point of the
    snapshot existing at all.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    width: int = Field(gt=0)
    height: int = Field(gt=0)
    resolution: float = Field(gt=0)
    origin_x: float
    origin_y: float
    #: ``(value, count)`` pairs, row-major.
    cells_rle: tuple[tuple[int, int], ...]

    @classmethod
    def from_cells(
        cls,
        cells: Iterable[int],
        *,
        width: int,
        height: int,
        resolution: float,
        origin_x: float,
        origin_y: float,
    ) -> GridSnapshot:
        return cls(
            width=width,
            height=height,
            resolution=resolution,
            origin_x=origin_x,
            origin_y=origin_y,
            cells_rle=run_length_encode(cells),
        )

    @model_validator(mode="after")
    def _check(self) -> GridSnapshot:
        if any(count < 1 for _value, count in self.cells_rle):
            raise SidecarViolation("a run of length zero encodes nothing")
        total = sum(count for _value, count in self.cells_rle)
        if total != self.width * self.height:
            raise SidecarViolation(
                f"grid says {self.width}x{self.height} = {self.width * self.height} "
                f"cells and the encoding carries {total}; a snapshot that does not "
                "describe itself cannot be replayed from"
            )
        return self

    @property
    def cells(self) -> tuple[int, ...]:
        """The grid, expanded. What a replay hands the planner."""
        return run_length_decode(self.cells_rle)

    @property
    def checksum(self) -> str:
        """Identity of the grid, over the **expanded** cells.

        Hashing the encoding would make the identity depend on how it
        was stored: two writers producing the same grid with different
        run boundaries would disagree about whether it is the same
        world. What the planner saw is the cells.
        """
        return costmap_checksum(
            self.cells,
            width=self.width,
            height=self.height,
            resolution=self.resolution,
            origin_x=self.origin_x,
            origin_y=self.origin_y,
        )


class PlanningSnapshot(BaseModel):
    """Everything needed to ask the planner the same question again.

    The configuration is stored **as values**, not as a fingerprint. A
    fingerprint answers "is this the same configuration" and a replay
    needs "what was the configuration" — two different questions, and
    only one of them can be answered by a hash.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    schema_version: str = Field(default=SIDECAR_SCHEMA_VERSION, min_length=1)
    episode_context_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    planning_attempt: int = Field(ge=1)
    grid: GridSnapshot
    start_x: float
    start_y: float
    goal_x: float
    goal_y: float
    planner_name: str = Field(min_length=1)
    #: The planner's own knobs, as they were. What the fingerprint
    #: hashes; what a replay sets.
    planner_parameters: dict[str, float | int | str | bool] = Field(default_factory=dict)
    #: Present for a sampling planner and ``None`` for a deterministic
    #: one. ``None`` is a statement, not a gap: replaying RRT* without
    #: its seed reproduces a different tree, so a snapshot that cannot
    #: name one has to say so rather than default to zero.
    seed: int | None = None

    @property
    def checksum(self) -> str:
        """SHA-256 of everything in here. What the record pins."""
        return artifact_checksum(self.model_dump(mode="json"))

    @property
    def fingerprint(self) -> str:
        """The planner's identity and knobs, hashed from the snapshot.

        Derived rather than accepted. The recorder used to take a
        fingerprint from its caller and store it beside a snapshot it
        never compared it against, so a caller could record planner A's
        hash next to planner B's configuration — and a replay checking
        the fingerprint would then agree with the wrong thing.
        """
        return planner_fingerprint(self.planner_name, dict(self.planner_parameters))


def snapshot_filename(attempt: int) -> str:
    return f"attempt-{attempt:03d}.json"


def replay_inputs(snapshot: PlanningSnapshot) -> dict[str, Any]:
    """What a replay harness needs, unpacked from a snapshot.

    A plain mapping rather than the simulator's types, for the same
    reason the snapshot is: this package must not import the thing that
    produced the run it is explaining.
    """
    return {
        "cells": snapshot.grid.cells,
        "width": snapshot.grid.width,
        "height": snapshot.grid.height,
        "resolution": snapshot.grid.resolution,
        "origin": (snapshot.grid.origin_x, snapshot.grid.origin_y),
        "start": (snapshot.start_x, snapshot.start_y),
        "goal": (snapshot.goal_x, snapshot.goal_y),
        "planner_name": snapshot.planner_name,
        "planner_parameters": dict(snapshot.planner_parameters),
        "seed": snapshot.seed,
    }


class PlanningInputRecorder:
    """Writes one episode's planning attempts as they happen.

    The caller owns the lifetime, exactly as it owns the trace
    recorder's: construct before the episode, call :meth:`record` at each
    planning call, call :meth:`close` with the runner's own attempt
    count. A run that raises leaves a partial file, which is a true
    statement about what happened and is what the validator is for.
    """

    def __init__(
        self,
        *,
        run_id: str,
        episode_context_id: str,
        candidate_id: str,
        execution_environment_ref: str,
        stream: IO[str] | None = None,
        snapshot_dir: Path | None = None,
    ) -> None:
        validate_code_ref(execution_environment_ref, field="execution_environment_ref")
        self.snapshot_dir = snapshot_dir
        self.snapshots: dict[int, PlanningSnapshot] = {}
        self.header = SidecarHeader(
            run_id=run_id,
            episode_context_id=episode_context_id,
            candidate_id=candidate_id,
            execution_environment_ref=execution_environment_ref,
        )
        self._records: list[PlanningInputEvidence] = []
        self._stream = stream
        self._closed = False
        if stream is not None:
            self._write(self.header.model_dump(mode="json"))

    @classmethod
    def to_path(
        cls,
        path: Path,
        *,
        run_id: str,
        episode_context_id: str,
        candidate_id: str,
        execution_environment_ref: str,
    ) -> PlanningInputRecorder:
        """Open a sidecar file for one episode."""
        path.parent.mkdir(parents=True, exist_ok=True)
        return cls(
            run_id=run_id,
            episode_context_id=episode_context_id,
            candidate_id=candidate_id,
            execution_environment_ref=execution_environment_ref,
            stream=path.open("w", encoding="utf-8"),
            snapshot_dir=path.parent / "snapshots",
        )

    @property
    def records(self) -> tuple[PlanningInputEvidence, ...]:
        return tuple(self._records)

    @property
    def attempts(self) -> int:
        """How many attempts this recorder saw. **Not** the expectation.

        :func:`validate_episode_attempts` needs a count from the runner's
        own counter, and returning this one to it would let a writer that
        stopped early agree with itself.
        """
        return len(self._records)

    def record(
        self,
        *,
        simulation_tick: int,
        start_pose: Pose2D,
        goal_pose: Pose2D,
        grid: GridSnapshot,
        planner_name: str,
        planner_parameters: dict[str, float | int | str | bool] | None = None,
        seed: int | None = None,
        outcome: PlanningOutcome,
        output_plan_checksum: str | None = None,
        output_path: Sequence[tuple[float, float]] = (),
        failure_code: str | None = None,
        provider_revision_refs: Sequence[str] = (),
    ) -> PlanningInputEvidence:
        """Record one planning attempt. Numbering is this recorder's.

        The attempt number comes from here rather than from the caller
        because the caller has two call sites — the initial plan and the
        replan loop — and a number each of them maintains separately is
        a number that will disagree.
        """
        if self._closed:
            raise SidecarViolation(
                "this recorder is closed; an attempt recorded after the episode "
                "ended is an attempt that belongs to a different episode"
            )
        attempt = len(self._records) + 1
        snapshot = PlanningSnapshot(
            episode_context_id=self.header.episode_context_id,
            candidate_id=self.header.candidate_id,
            planning_attempt=attempt,
            grid=grid,
            start_x=start_pose.x,
            start_y=start_pose.y,
            goal_x=goal_pose.x,
            goal_y=goal_pose.y,
            planner_name=planner_name,
            planner_parameters=dict(planner_parameters or {}),
            seed=seed,
        )
        self.snapshots[attempt] = snapshot
        snapshot_ref = snapshot_filename(attempt)
        if self.snapshot_dir is not None:
            self.snapshot_dir.mkdir(parents=True, exist_ok=True)
            (self.snapshot_dir / snapshot_ref).write_text(
                json.dumps(snapshot.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
                + "\n",
                encoding="utf-8",
            )
            snapshot_ref = f"snapshots/{snapshot_ref}"

        record = PlanningInputEvidence(
            episode_context_id=self.header.episode_context_id,
            candidate_id=self.header.candidate_id,
            planning_attempt=attempt,
            simulation_tick=simulation_tick,
            query=PlanningQuery(start_pose=start_pose, goal_pose=goal_pose),
            costmap_checksum=grid.checksum,
            snapshot_ref=snapshot_ref,
            snapshot_checksum=snapshot.checksum,
            provider_revision_refs=tuple(provider_revision_refs),
            planner_fingerprint=snapshot.fingerprint,
            execution_environment_ref=self.header.execution_environment_ref,
            outcome=outcome,
            output_plan_checksum=output_plan_checksum,
            output_path=tuple(output_path),
            failure_code=failure_code,
        )
        self._records.append(record)
        self._write(record.model_dump(mode="json"))
        return record

    def close(self, *, expected_attempts: int) -> tuple[PlanningInputEvidence, ...]:
        """Validate against the runner's count and release the file.

        ``expected_attempts`` is the episode's ``replan_count`` plus one
        for the initial plan, read off the runner. Passing this
        recorder's own count would make the check vacuous, which is why
        it is a required keyword and not a default.
        """
        self._closed = True
        try:
            validate_episode_attempts(self._records, expected_attempts=expected_attempts)
        finally:
            if self._stream is not None:
                self._stream.close()
                self._stream = None
        return tuple(self._records)

    def abandon(self) -> None:
        """Release the file without validating — for a failed episode.

        An episode that raised has a partial sidecar, and that is the
        honest artifact. Validating it here would turn one failure into
        two and hide the first.
        """
        self._closed = True
        if self._stream is not None:
            self._stream.close()
            self._stream = None

    def _write(self, payload: dict[str, Any]) -> None:
        if self._stream is None:
            return
        self._stream.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
        self._stream.flush()


def write_sidecar(
    path: Path, header: SidecarHeader, records: Sequence[PlanningInputEvidence]
) -> None:
    """Write a whole sidecar at once. For tests and for re-export."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [header.model_dump(mode="json")]
    lines.extend(record.model_dump(mode="json") for record in records)
    path.write_text(
        "".join(json.dumps(line, sort_keys=True, separators=(",", ":")) + "\n" for line in lines),
        encoding="utf-8",
    )


def read_sidecar(path: Path) -> tuple[SidecarHeader, tuple[PlanningInputEvidence, ...]]:
    """Read a sidecar, refusing anything that is not one.

    Refuses an empty file and a file whose first line is not a header:
    a replay harness handed a headerless list has no way to tell whose
    attempts it is replaying, and it would report the resulting mismatch
    as a failed reconstruction rather than as the wrong file.
    """
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise SidecarViolation(f"{path} is empty; an episode plans at least once")
    lines = text.splitlines()
    try:
        header = SidecarHeader.model_validate(json.loads(lines[0]))
    except Exception as error:
        raise SidecarViolation(
            f"{path} does not start with a sidecar header; a list of records that "
            "cannot say which episode it belongs to is a file a replay would "
            "misread as a failed reconstruction"
        ) from error
    records = tuple(
        PlanningInputEvidence.model_validate(json.loads(line)) for line in lines[1:] if line
    )
    for record in records:
        if (record.episode_context_id, record.candidate_id) != (
            header.episode_context_id,
            header.candidate_id,
        ):
            raise SidecarViolation(
                f"{path} holds a record for "
                f"{record.candidate_id}/{record.episode_context_id} under a header for "
                f"{header.candidate_id}/{header.episode_context_id}"
            )
    return header, records


def read_snapshot(path: Path) -> PlanningSnapshot:
    """Load one attempt's snapshot, checking it describes itself."""
    return PlanningSnapshot.model_validate(json.loads(path.read_text(encoding="utf-8")))


def snapshot_for(sidecar_path: Path, record: PlanningInputEvidence) -> PlanningSnapshot:
    """The snapshot a record points at, resolved beside the sidecar.

    Also checks the grid it loaded is the grid the record names. A
    snapshot directory that drifted from its sidecar is the failure this
    catches, and it would otherwise surface as a replay mismatch — read
    as "the reconstruction is wrong" rather than "these files do not
    belong together".
    """
    snapshot = read_snapshot(sidecar_path.parent / record.snapshot_ref)

    # One comparison covering every field a replay reads. Checking the
    # grid alone let a snapshot with a swapped start, goal, planner
    # configuration or seed load clean — right world, different question.
    if snapshot.checksum != record.snapshot_checksum:
        raise SidecarViolation(
            f"attempt {record.planning_attempt}: the snapshot at "
            f"{record.snapshot_ref} hashes to {snapshot.checksum[:12]} and the record "
            f"names {record.snapshot_checksum[:12]}. Something in it was edited after "
            "the run — the grid, the query, the planner's configuration or its seed."
        )

    # The narrower checks still earn their place: they say *which* field
    # moved, and a reader who has just been told a hash differs wants to
    # know that before opening a diff of forty thousand cells.
    mismatches = [
        name
        for name, left, right in (
            ("costmap_checksum", snapshot.grid.checksum, record.costmap_checksum),
            ("planning_attempt", snapshot.planning_attempt, record.planning_attempt),
            ("episode_context_id", snapshot.episode_context_id, record.episode_context_id),
            ("candidate_id", snapshot.candidate_id, record.candidate_id),
            ("start_x", snapshot.start_x, record.query.start_pose.x),
            ("start_y", snapshot.start_y, record.query.start_pose.y),
            ("goal_x", snapshot.goal_x, record.query.goal_pose.x),
            ("goal_y", snapshot.goal_y, record.query.goal_pose.y),
            ("planner_fingerprint", snapshot.fingerprint, record.planner_fingerprint),
        )
        if left != right
    ]
    if mismatches:
        raise SidecarViolation(
            f"attempt {record.planning_attempt}: snapshot and record disagree on {mismatches}"
        )
    return snapshot
