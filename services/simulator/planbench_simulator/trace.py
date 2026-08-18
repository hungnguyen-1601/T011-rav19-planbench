"""Episode trace: one Parquet file per episode (CONTRACTS HĐ-5).

> Each episode writes exactly one Parquet file. This is the **only**
> data source of the Metrics Engine — no metric is computed during the
> simulation.

That sentence is the whole design. Everything the decision layer will
ever claim — success rate, the collision upper bound, p99 latency, path
and time efficiency, the memory estimate behind G5 — is recomputed from
these files, so a quantity missing from a trace is a quantity that costs
a full re-run of the evaluation set to obtain. The schema below is
therefore frozen (CONTRACTS §0) and is deliberately wider than what the
first metrics need.

Three consequences shape the API:

**Clearance is computed while writing, never afterwards.** Given only a
trajectory, nobody can reconstruct how close the forklift was at t = 7.4
s: dynamic obstacles have moved on, and re-deriving their position needs
the episode's whole random state. The recorder takes a ``clearance``
callable and evaluates it at each sample, at the one moment the answer
is knowable. This is also why ``min_clearance`` and ``near_miss_rate``
(HĐ-6) can be pure functions of the file.

**Identity comes from the context and the candidate, not from a file
name.** A trace is addressed by ``(candidate_id, episode_context_id)``,
the exact pair paired statistics key on (HĐ-3.2), and both ids travel
*inside* the file as well. A renamed or moved file therefore stays
interpretable, and a file whose name and content disagree is detectable.

**The recorder refuses malformed traces at the point of writing.**
Out-of-order timestamps, an event outside the closed vocabulary, a
non-finite number: each of them survives a run silently and only shows
up as a strange number in a Decision Card weeks later, by which time the
episodes that produced it are gone.

``peak_rss_mb`` is recorded and is **diagnostic only** (HĐ-6): it is the
RSS of a Python process holding the interpreter, NumPy, the simulator
and this recorder, and comparing it with a target board's RAM budget is
wrong by an order of magnitude in an unpredictable direction. G5 uses
``memory_estimate_mb``, built from the structural counters below.
"""

from __future__ import annotations

import contextlib
import json
import math
import os
import sys
import time
from collections.abc import Callable, Iterable, Iterator, Mapping
from pathlib import Path
from typing import Any, Literal

import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import BaseModel, ConfigDict, Field

from planbench_schemas.episode import EpisodeStatus
from planbench_schemas.episode_context import EpisodeContext, SampleSet
from planbench_schemas.geometry import Point2D, Pose2D
from planbench_schemas.robot import RobotState
from planbench_schemas.scenario import CircleObstacle, RectangleObstacle
from planbench_simulator.collision import clearance_to_grid_within, clearance_to_obstacles
from planbench_simulator.grid import OccupancyGrid

#: Where run artifacts live (CONTRACTS §16: logical ``runs/``).
DEFAULT_TRACE_ROOT = Path("artifacts") / "runs"

#: Key the trace metadata is stored under in the Parquet file footer.
METADATA_KEY = b"planbench_trace"

#: The event vocabulary of HĐ-5, closed. An event outside it means some
#: caller invented a name, and every consumer that switches on the value
#: would silently take its default branch.
TraceEvent = Literal["collision", "goal_reached", "timeout", "stuck", "replan", "no_path"]
TRACE_EVENTS: frozenset[str] = frozenset(
    ("collision", "goal_reached", "timeout", "stuck", "replan", "no_path")
)

#: Columns of HĐ-5, in order. Written as an explicit Arrow schema rather
#: than inferred from the data: inference would type an all-null
#: ``event`` column as ``null`` and an all-integer ``t`` as ``int64``, so
#: two traces of the same episode set could disagree on types and fail to
#: concatenate — the exact silent breakage a frozen schema exists to
#: prevent.
TRACE_SCHEMA = pa.schema(
    [
        pa.field("t", pa.float64(), nullable=False),
        pa.field("x", pa.float64(), nullable=False),
        pa.field("y", pa.float64(), nullable=False),
        pa.field("theta", pa.float64(), nullable=False),
        pa.field("v", pa.float64(), nullable=False),
        pa.field("omega", pa.float64(), nullable=False),
        pa.field("clearance_m", pa.float64(), nullable=False),
        pa.field("planner_latency_ms", pa.float64(), nullable=False),
        pa.field("event", pa.string(), nullable=True),
    ]
)

TRACE_COLUMNS: tuple[str, ...] = tuple(TRACE_SCHEMA.names)

#: The six layers of §5.9, appended when a run actually measures them.
#:
#: **Opt-in, and that is a measurement decision rather than a
#: compatibility dodge.** An in-process legacy stack has no transport and
#: no adapter chain; writing six columns of zeros for it would put
#: numbers nobody measured into the file the Metrics Engine treats as the
#: single source of truth, and a reader could not tell "zero milliseconds
#: of transport" from "this lane has no transport". A run that measures
#: the layers writes them; a run that does not, does not — and the
#: column's absence is the honest statement.
LATENCY_LAYER_COLUMNS: tuple[str, ...] = (
    "shared_provider_ms",
    "candidate_provider_ms",
    "transport_ms",
    "algorithm_compute_ms",
    "action_adapter_ms",
    "host_overhead_ms",
)

#: Who measured ``algorithm_compute_ms`` on each row (§5.9 rule 6). A
#: gate must not read that column where this says ``plugin``, so the two
#: travel together — a number whose provenance lives somewhere else is a
#: number somebody will read without it.
COMPUTE_MEASURED_BY_COLUMN = "compute_measured_by"

_LATENCY_FIELDS = [
    *(pa.field(name, pa.float64(), nullable=False) for name in LATENCY_LAYER_COLUMNS),
    pa.field(COMPUTE_MEASURED_BY_COLUMN, pa.string(), nullable=False),
]

#: The schema of a trace that records the layers: HĐ-5's columns, then
#: the layers. HĐ-5's own columns keep their positions, so every existing
#: reader keeps working.
TRACE_SCHEMA_WITH_LAYERS = pa.schema([*TRACE_SCHEMA, *_LATENCY_FIELDS])

TRACE_COLUMNS_WITH_LAYERS: tuple[str, ...] = tuple(TRACE_SCHEMA_WITH_LAYERS.names)

#: Repo statuses that HĐ-5's vocabulary does not distinguish.
#: ``no_progress`` is this simulator's "moved less than the threshold in
#: the window"; the contract calls both that and a wedged robot
#: ``stuck``, and HĐ-6's ``failure_reason`` has no finer bucket either.
_STATUS_TO_EVENT: dict[EpisodeStatus, TraceEvent] = {
    EpisodeStatus.SUCCESS: "goal_reached",
    EpisodeStatus.COLLISION: "collision",
    EpisodeStatus.TIMEOUT: "timeout",
    EpisodeStatus.STUCK: "stuck",
    EpisodeStatus.NO_PROGRESS: "stuck",
    EpisodeStatus.NO_GLOBAL_PATH: "no_path",
}


class TraceError(ValueError):
    """A trace that would misinform the Metrics Engine."""


def event_for_status(status: EpisodeStatus) -> TraceEvent | None:
    """The HĐ-5 event a terminal status maps to, if any.

    ``running`` and ``stopped`` map to nothing: neither is a verdict on
    the episode, and an episode that was stopped by an operator must not
    be counted as a failure of the candidate.
    """
    return _STATUS_TO_EVENT.get(status)


class TraceMetadata(BaseModel):
    """What the rows cannot say: which episode this is, and what it cost.

    The first four fields are the join keys of everything downstream —
    pairing (HĐ-3.2), gates, ΔU — and ``sample_set`` is the one that
    keeps the collision upper bound honest, since pooling neighborhood
    episodes into a rule-of-three bound would make it far too optimistic
    (HĐ-11.4).

    The three counters ``peak_search_nodes``, ``peak_tree_nodes`` and
    ``costmap_cells`` are the *entire* input of ``memory_estimate_mb``
    (HĐ-7.3). They are counts of data structures — algorithm behaviour
    the simulator observes exactly, in any implementation language —
    which is why G5 uses them and not the RSS below.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    episode_context_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    task_profile_id: str = Field(min_length=1)
    sample_set: SampleSet

    global_plan_length_m: float | None = Field(default=None, ge=0)
    global_plan_time_ms: float | None = Field(default=None, ge=0)

    peak_search_nodes: int = Field(default=0, ge=0)
    peak_tree_nodes: int = Field(default=0, ge=0)
    costmap_cells: int = Field(default=0, ge=0)

    #: Diagnostic only — see the module docstring and HĐ-6. Never compare
    #: with ``hardware.available_ram_mb``.
    peak_rss_mb: float = Field(default=0.0, ge=0)
    cpu_time_s: float = Field(default=0.0, ge=0)

    #: What this episode was simulated **under**, hashed.
    #:
    #: The two ids above say *which* episode this is; they do not say
    #: what the world looked like, because HĐ-3.1 freezes
    #: ``episode_context_id`` at *(task profile, mission, variant, seed)*
    #: and the environment is not in that. Without this field a trace
    #: from a world that no longer exists is indistinguishable from a
    #: fresh one, and the reuse paths take it — which is how one
    #: ``run_journal.jsonl`` came to hold sixty ``stuck`` episodes and
    #: sixty ``success`` ones under identical ids.
    #:
    #: Empty on traces written before this existed. Readers must treat
    #: the empty string as **unknown, therefore unusable**, never as
    #: "matches": a trace that cannot say what it ran under is exactly
    #: the trace this field was added to distrust.
    execution_conditions_fingerprint: str = ""

    @classmethod
    def for_episode(
        cls,
        context: EpisodeContext,
        candidate_id: str,
        **fields: Any,
    ) -> TraceMetadata:
        """Build metadata from a context so the ids cannot disagree."""
        return cls(
            episode_context_id=context.episode_context_id,
            candidate_id=candidate_id,
            task_profile_id=context.task_profile_id,
            sample_set=context.sample_set,
            **fields,
        )


class LoadedTrace(BaseModel):
    """One trace read back: its metadata and its rows."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    metadata: TraceMetadata
    table: pa.Table
    path: Path

    def column(self, name: str) -> list[Any]:
        """One column as a Python list, in recorded order."""
        if name not in TRACE_COLUMNS_WITH_LAYERS:
            raise TraceError(
                f"{name!r} is not an HĐ-5 column; columns are {TRACE_COLUMNS_WITH_LAYERS}"
            )
        if name not in self.table.column_names:
            raise TraceError(
                f"{name!r} is a latency layer and this trace does not carry them: it was "
                "written by a run that did not measure them, and answering with zeros "
                "would report measurements nobody made"
            )
        return self.table.column(name).to_pylist()

    @property
    def row_count(self) -> int:
        return self.table.num_rows


def trace_path(
    candidate_id: str,
    episode_context_id: str,
    *,
    root: Path | str = DEFAULT_TRACE_ROOT,
) -> Path:
    """Where the trace for one (candidate, context) pair belongs.

    Grouping by candidate and naming by context makes the pairing rule
    visible in the filesystem: two candidates compared on the same set of
    contexts hold two directories with identical file names, and
    ``ls`` answers "did both run the same episodes" (HĐ-3.2).
    """
    return Path(root) / candidate_id / f"{episode_context_id}.parquet"


class EpisodeTraceRecorder:
    """Collects one episode's samples and writes one Parquet file.

    Implements the ``TraceRecorder`` protocol of HĐ-4 (``record(t, state,
    event)``) with two keyword extras the protocol's prose assumes: the
    per-step planner latency, and an explicit clearance for callers that
    already computed it.

    Usage is a context manager so an episode that raises still leaves a
    file behind — a crashed episode with 400 recorded samples is
    evidence; a missing file is a hole in a paired comparison.

    >>> with EpisodeTraceRecorder(context, candidate_id, clearance=probe) as rec:
    ...     rec.record(t, state, planner_latency_ms=latency)
    ... path = rec.path
    """

    def __init__(
        self,
        context: EpisodeContext,
        candidate_id: str,
        *,
        clearance: Callable[[Pose2D], float] | None = None,
        root: Path | str = DEFAULT_TRACE_ROOT,
        costmap_cells: int = 0,
        global_plan_length_m: float | None = None,
        global_plan_time_ms: float | None = None,
        execution_conditions_fingerprint: str = "",
        latency_layers: bool = False,
    ) -> None:
        self._context = context
        self._candidate_id = candidate_id
        self._clearance = clearance
        self._path = trace_path(candidate_id, context.episode_context_id, root=root)
        self._costmap_cells = costmap_cells
        self._global_plan_length_m = global_plan_length_m
        self._global_plan_time_ms = global_plan_time_ms
        self._fingerprint = execution_conditions_fingerprint

        #: Decided once, at construction, because a Parquet file has one
        #: schema: a recorder that started plain and grew columns midway
        #: could not write the rows it had already taken.
        self._latency_layers = latency_layers
        self._schema = TRACE_SCHEMA_WITH_LAYERS if latency_layers else TRACE_SCHEMA
        self._columns = TRACE_COLUMNS_WITH_LAYERS if latency_layers else TRACE_COLUMNS
        self._rows: dict[str, list[Any]] = {name: [] for name in self._columns}
        self._last_t: float | None = None
        self._cpu_start = time.process_time()
        self._peak_rss_mb = 0.0
        self._closed = False

    # -- recording ---------------------------------------------------

    def record(
        self,
        t: float,
        state: RobotState,
        event: str | None = None,
        *,
        planner_latency_ms: float = 0.0,
        clearance_m: float | None = None,
        latency_layers: dict[str, Any] | None = None,
    ) -> None:
        """Append one sample (HĐ-4/HĐ-5).

        ``clearance_m`` is measured now if not supplied, because it
        cannot be measured later: by the end of the episode the moving
        obstacles are somewhere else.

        ``latency_layers`` carries the six layers of §5.9 plus who
        measured the compute. Required on every row when the recorder was
        built with ``latency_layers=True`` and refused otherwise: a file
        whose layer columns are present on some rows and absent on others
        would make a percentile over them a percentile over an unstated
        subset.
        """
        if self._closed:
            raise TraceError(
                f"trace {self._path.name} is already written; recording after close would "
                "produce a file that disagrees with the one on disk"
            )
        self._require_finite("t", t)
        if self._last_t is not None and t <= self._last_t:
            raise TraceError(
                f"trace timestamps must increase: got t={t} after t={self._last_t}. "
                "Out-of-order samples silently corrupt every rate and percentile "
                "computed from this file"
            )
        if event is not None and event not in TRACE_EVENTS:
            raise TraceError(
                f"unknown trace event {event!r}; HĐ-5 fixes the vocabulary as "
                f"{sorted(TRACE_EVENTS)}"
            )

        if clearance_m is None:
            clearance_m = self._measure_clearance(state.pose)
        for name, value in (
            ("t", t),
            ("x", state.pose.x),
            ("y", state.pose.y),
            ("theta", state.pose.theta),
            ("v", state.linear_velocity),
            ("omega", state.angular_velocity),
            ("clearance_m", clearance_m),
            ("planner_latency_ms", planner_latency_ms),
        ):
            self._require_finite(name, value)
            self._rows[name].append(float(value))
        self._rows["event"].append(event)
        self._record_layers(latency_layers)

        self._last_t = t
        self._sample_rss()

    def _record_layers(self, layers: dict[str, Any] | None) -> None:
        """The six §5.9 columns, all present or all absent — never mixed."""
        if not self._latency_layers:
            if layers is not None:
                raise TraceError(
                    "latency layers were supplied to a recorder that was not built to "
                    "write them; pass latency_layers=True at construction, because a "
                    "Parquet file has one schema and it is fixed before the first row"
                )
            return
        if layers is None:
            raise TraceError(
                "this recorder writes latency layers, so every row needs them: a file "
                "carrying them on some rows and not others makes any percentile over "
                "them a percentile over an unstated subset"
            )
        for name in LATENCY_LAYER_COLUMNS:
            value = layers.get(name, 0.0)
            self._require_finite(name, value)
            self._rows[name].append(float(value))
        self._rows[COMPUTE_MEASURED_BY_COLUMN].append(
            str(layers.get(COMPUTE_MEASURED_BY_COLUMN, "host"))
        )

    def _measure_clearance(self, pose: Pose2D) -> float:
        if self._clearance is None:
            raise TraceError(
                "no clearance probe was given and no clearance_m was passed. "
                "clearance_m cannot be recovered after the episode — dynamic "
                "obstacles have moved — so HĐ-5 requires it to be computed while "
                "writing"
            )
        return self._clearance(pose)

    def bind_clearance(self, probe: Callable[[Pose2D], float]) -> None:
        """Attach a clearance probe that only the episode loop can build.

        The probe has to query the moving obstacles *now* (see
        :func:`clearance_probe`), so it needs the running engine — which
        exists inside ``run_stack``, after the caller has already built
        this recorder. Hence a second entry point rather than a
        constructor argument.

        An explicit probe passed to ``__init__`` wins: swapping the
        instrument halfway through an episode would give one file two
        definitions of the same column.
        """
        if self._clearance is None:
            self._clearance = probe

    @staticmethod
    def _require_finite(name: str, value: float) -> None:
        if not math.isfinite(value):
            raise TraceError(
                f"{name} must be finite, got {value!r}; a NaN here propagates into "
                "every aggregate computed from this trace"
            )

    # -- finishing ---------------------------------------------------

    def close(
        self,
        *,
        peak_search_nodes: int = 0,
        peak_tree_nodes: int = 0,
        costmap_cells: int | None = None,
        global_plan_length_m: float | None = None,
        global_plan_time_ms: float | None = None,
    ) -> Path:
        """Write the file and return its path.

        The planner counters arrive here rather than in ``__init__``
        because they are peaks: they are only known once the episode has
        finished, and they are what G5's ``memory_estimate_mb`` is built
        from (HĐ-7.3).
        """
        if self._closed:
            raise TraceError(f"trace {self._path.name} was already written")
        if not self._rows["t"]:
            raise TraceError(
                "refusing to write an empty trace: an episode that produced no sample "
                "would still be counted as one paired observation, so a missing file "
                "is safer than an empty one"
            )

        metadata = TraceMetadata.for_episode(
            self._context,
            self._candidate_id,
            global_plan_length_m=(
                self._global_plan_length_m if global_plan_length_m is None else global_plan_length_m
            ),
            global_plan_time_ms=(
                self._global_plan_time_ms if global_plan_time_ms is None else global_plan_time_ms
            ),
            peak_search_nodes=peak_search_nodes,
            peak_tree_nodes=peak_tree_nodes,
            costmap_cells=self._costmap_cells if costmap_cells is None else costmap_cells,
            peak_rss_mb=self._peak_rss_mb,
            cpu_time_s=max(time.process_time() - self._cpu_start, 0.0),
            execution_conditions_fingerprint=self._fingerprint,
        )
        write_trace(self._path, self._rows, metadata)
        self._closed = True
        return self._path

    def __enter__(self) -> EpisodeTraceRecorder:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> Literal[False]:
        if not self._closed and self._rows["t"]:
            self.close()
        return False

    # -- accessors ---------------------------------------------------

    @property
    def path(self) -> Path:
        return self._path

    @property
    def sample_count(self) -> int:
        return len(self._rows["t"])

    def _sample_rss(self) -> None:
        rss = process_rss_mb()
        if rss > self._peak_rss_mb:
            self._peak_rss_mb = rss


def clearance_probe(
    grid: OccupancyGrid,
    static_obstacles: Iterable[CircleObstacle | RectangleObstacle],
    robot_radius: float,
    dynamic_obstacles_now: Callable[[], Iterable[CircleObstacle]] | None = None,
) -> Callable[[Pose2D], float]:
    """Clearance probe that reads the world *at the moment it is called*.

    The map and the static obstacles never move, but the dynamic ones do,
    and the whole reason HĐ-5 stores ``clearance_m`` per sample is that
    the number is unrecoverable afterwards. So the moving half arrives as
    a callable — typically ``engine.dynamic_obstacles_now`` — queried per
    sample, never as a snapshot taken once.

    Ground truth is legitimate here: this is measurement, not perception.
    Nothing the probe sees reaches a planner, so the observation-parity
    declaration (P02/G6) is untouched.

    The grid is required rather than optional because it is what keeps
    the value finite: with no obstacle anywhere, clearance to a set of
    shapes is infinity, and an infinity in the column would poison every
    percentile computed from the file. Against a grid the map boundary
    always answers.
    """
    statics = tuple(static_obstacles)

    def probe(pose: Pose2D) -> float:
        center = Point2D(x=pose.x, y=pose.y)
        moving = tuple(dynamic_obstacles_now()) if dynamic_obstacles_now is not None else ()
        # Windowed against the grid: this runs once per recorded control
        # step, and the exhaustive scan is a whole-map sweep per row (see
        # clearance_to_grid_within). The shape obstacles stay exact —
        # there are a handful of them, and they are the moving ones.
        return min(
            clearance_to_obstacles(center, robot_radius, statics),
            clearance_to_obstacles(center, robot_radius, moving),
            clearance_to_grid_within(center, robot_radius, grid),
        )

    return probe


def write_trace(
    path: Path,
    columns: Mapping[str, list[Any]],
    metadata: TraceMetadata,
) -> Path:
    """Write rows plus metadata as one Parquet file.

    The metadata rides in the Parquet footer instead of as repeated
    columns: it is one value per episode, and duplicating it down every
    row invites a file whose rows disagree about which candidate ran.
    """
    missing = [name for name in TRACE_COLUMNS if name not in columns]
    if missing:
        raise TraceError(f"trace is missing HĐ-5 column(s) {missing}")
    # The layers are all-or-nothing: whichever schema the caller filled,
    # it filled completely, and a half-populated one is a bug worth
    # failing on rather than a file worth writing.
    with_layers = all(name in columns for name in LATENCY_LAYER_COLUMNS)
    schema = TRACE_SCHEMA_WITH_LAYERS if with_layers else TRACE_SCHEMA
    names = TRACE_COLUMNS_WITH_LAYERS if with_layers else TRACE_COLUMNS
    table = pa.table({name: columns[name] for name in names}, schema=schema)
    table = table.replace_schema_metadata(
        {METADATA_KEY: metadata.model_dump_json().encode("utf-8")}
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)
    return path


def read_trace_metadata(path: Path | str) -> TraceMetadata:
    """Just the footer, without reading a single row.

    The reuse checks ask one question of every trace on disk before a
    sweep starts — *were you made under these conditions?* — and reading
    a whole episode's samples to answer it would make the check cost more
    than the simulation it saves.
    """
    path = Path(path)
    raw = (pq.read_schema(path).metadata or {}).get(METADATA_KEY)
    if raw is None:
        raise TraceError(
            f"{path} carries no {METADATA_KEY.decode()} metadata; without "
            "episode_context_id and candidate_id it cannot take part in a paired "
            "comparison"
        )
    return TraceMetadata.model_validate(json.loads(raw))


def read_trace(path: Path | str) -> LoadedTrace:
    """Read one trace back, metadata included.

    A file without the metadata block is refused rather than defaulted:
    a trace whose candidate is unknown cannot be paired, and guessing it
    from the directory name would make a misplaced file look valid.
    """
    path = Path(path)
    table = pq.read_table(path)
    raw = (table.schema.metadata or {}).get(METADATA_KEY)
    if raw is None:
        raise TraceError(
            f"{path} carries no {METADATA_KEY.decode()} metadata; without "
            "episode_context_id and candidate_id it cannot take part in a paired "
            "comparison"
        )
    metadata = TraceMetadata.model_validate(json.loads(raw))
    return LoadedTrace(metadata=metadata, table=table, path=path)


def iter_traces(root: Path | str = DEFAULT_TRACE_ROOT) -> Iterator[LoadedTrace]:
    """Every trace under ``root``, in a stable order."""
    for path in sorted(Path(root).rglob("*.parquet")):
        yield read_trace(path)


def process_rss_mb() -> float:
    """Resident set size of this process, in MB. Diagnostic only.

    Deliberately dependency-free — reading ``/proc`` on Linux and asking
    the Win32 API on Windows — because the value's only jobs are leak
    detection and relative comparison between candidates on one machine
    (HĐ-6). Returns 0.0 where neither source exists rather than raising:
    an episode must not fail over a diagnostic.
    """
    if sys.platform.startswith("linux"):
        with contextlib.suppress(OSError, ValueError, IndexError):
            with open("/proc/self/statm", encoding="ascii") as handle:
                pages = int(handle.read().split()[1])
            return pages * os.sysconf("SC_PAGE_SIZE") / (1024 * 1024)
        return 0.0
    if sys.platform == "win32":
        return _windows_rss_mb()
    with contextlib.suppress(ImportError, ValueError):
        import resource

        usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # macOS reports bytes, other Unixes kilobytes.
        divisor = 1024 * 1024 if sys.platform == "darwin" else 1024
        return usage / divisor
    return 0.0


def _windows_rss_mb() -> float:
    import ctypes
    from ctypes import wintypes

    class _Counters(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    counters = _Counters()
    counters.cb = ctypes.sizeof(_Counters)
    psapi = ctypes.WinDLL("psapi")  # type: ignore[attr-defined]
    kernel32 = ctypes.WinDLL("kernel32")  # type: ignore[attr-defined]
    # Without this the pseudo-handle (-1) comes back as a 32-bit int and
    # is passed truncated on 64-bit Windows, so the call fails silently
    # and every trace reports 0 MB.
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    handle = ctypes.c_void_p(kernel32.GetCurrentProcess())
    if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
        return 0.0
    return counters.WorkingSetSize / (1024 * 1024)
