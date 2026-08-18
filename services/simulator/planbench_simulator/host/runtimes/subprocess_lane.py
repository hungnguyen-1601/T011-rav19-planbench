"""The subprocess lane: a plugin that cannot take the host down (H7).

**This is the lane where the deadline is real.** The in-process host can
only *observe* an overrun — it cannot interrupt a Python call — and its
docstring says so rather than pretending otherwise. Here the plugin is a
process: a deadline is enforced by killing it, and a crash is a process
exit rather than an exception unwinding through the simulator.

**What this is, precisely: crash and interpreter isolation. It is not a
security sandbox, and calling it one would be the overclaim this project
refuses everywhere else.** The worker inherits the host's environment,
gets a ``PYTHONPATH`` that includes this repository, holds the same
filesystem and network rights as the user running the host, and takes
its configuration on a command line visible in any process listing.
What the lane buys is that a plugin which hangs, crashes or corrupts its
own state cannot take the simulator with it. What it does not buy is
safety from a plugin that means harm. A genuinely untrusted plugin needs
a container with dropped privileges and a scrubbed environment — which
is post-MVP in the plan, and the plan's own §5.7 wording ("hard
isolation") should be narrowed to match this paragraph.

**Latency is measured in layers, and the layers are not equally
trustworthy** (§5.9 rule 6). ``transport_ms`` is timed directly —
encode, write, wait, read, decode — rather than derived by subtraction,
because a layer computed as "everything left over" is a residual wearing
a measurement's name. The plugin reports its own compute time, and that
number is *diagnostic*: the host cannot check it, and a gate reading a
number the measured party supplies is not a gate.

**A dead worker stays dead.** After a timeout or a crash the handle
refuses further calls with a safe stop rather than respawning: a plugin
restarted mid-episode would answer the next tick with a fresh internal
state while the trace says one continuous episode, and no reader could
see the seam.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from queue import Empty, Queue
from typing import Any

from planbench_plugin_sdk import LocalResetRequest, LocalStepRequest, PluginManifest

from planbench_planning.common.local_base import LocalPlanResult
from planbench_schemas.robot import SimAction
from planbench_simulator.host.compatibility import CompatibilityReport
from planbench_simulator.host.latency import (
    HOST_MEASURED,
    PLUGIN_REPORTED,
    LatencyLedger,
)
from planbench_simulator.host.runtimes.trusted_python import RuntimeLoadError

#: How long to wait for the worker to say it has loaded the plugin.
STARTUP_TIMEOUT_S = 20.0

#: The codec this lane carries payloads with. Declared here and stamped
#: on every envelope, so a plugin can tell which one it is reading.
_LANE_CODEC = "json-v1"

__all__ = [
    "HOST_MEASURED",
    "PLUGIN_REPORTED",
    "STARTUP_TIMEOUT_S",
    "SubprocessPlugin",
    "SubprocessRuntime",
    "UnencodableRequest",
    "WorkerDied",
]


class WorkerDied(RuntimeError):
    """The worker process is gone, or was killed for missing its deadline."""


class UnencodableRequest(TypeError):
    """A payload this lane's codec cannot carry.

    Raised rather than substituted. An earlier draft replaced such a
    value with a ``{"__unencodable__": ...}`` marker, which let a plugin
    run on a channel it never received and report results computed from
    a placeholder — the silent-degradation failure every other refusal
    in this host exists to prevent. Preflight should have caught the
    mismatch; if it did not, the tick fails loudly and says which
    capability and which type.
    """


class _LineReader:
    """One line at a time, with a deadline.

    A thread rather than ``select``: pipes are not selectable on Windows,
    and a lane whose timeout only works on one platform is a timeout
    nobody can rely on.
    """

    def __init__(self, stream) -> None:
        self._queue: Queue[str | None] = Queue()
        self._thread = threading.Thread(target=self._pump, args=(stream,), daemon=True)
        self._thread.start()

    def _pump(self, stream) -> None:
        try:
            for line in stream:
                self._queue.put(line)
        finally:
            self._queue.put(None)  # EOF: the worker is gone

    def readline(self, timeout: float) -> str | None:
        try:
            return self._queue.get(timeout=timeout)
        except Empty:
            return ""  # distinct from None: still alive, just too slow


class _StreamDrain:
    """Keeps a pipe empty, and remembers the tail.

    **Without this the lane deadlocks on a chatty plugin.** The worker
    points the plugin's ``print`` at stderr, and stderr is a pipe with a
    finite buffer — typically 64 KB. A plugin that logs enough fills it,
    the worker blocks on the write, and the host reports a *deadline
    miss*: a plugin killed for being slow when it was only talkative,
    and the trace would say so.

    The tail is kept rather than the whole stream: diagnosis needs the
    last thing a worker said before it died, not a transcript, and an
    unbounded buffer would trade the pipe's limit for the host's memory.
    """

    def __init__(self, stream, keep: int = 8000) -> None:
        self._chunks: deque[str] = deque()
        self._kept = 0
        self._keep = keep
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._pump, args=(stream,), daemon=True)
        self._thread.start()

    def _pump(self, stream) -> None:
        try:
            for line in stream:
                with self._lock:
                    self._chunks.append(line)
                    self._kept += len(line)
                    while self._kept > self._keep and len(self._chunks) > 1:
                        self._kept -= len(self._chunks.popleft())
        except Exception:  # noqa: BLE001 - the worker's death closes this stream
            pass

    def tail(self) -> str:
        with self._lock:
            return "".join(self._chunks).strip()[-self._keep :]


@dataclass
class SubprocessPlugin:
    """A local plugin running in its own process."""

    name: str
    _process: subprocess.Popen = field(repr=False)
    _reader: _LineReader = field(repr=False)
    _stderr_drain: _StreamDrain = field(repr=False)
    #: **The deployment's control period**, not a number chosen here.
    #: A lane with its own comfortable deadline would prove a plugin
    #: answers eventually, which is not the question G4 asks.
    deadline_s: float = 0.05
    control_period: float | None = None
    #: The last tick's cost, for whoever records the trace.
    last_latency: LatencyLedger = field(default_factory=LatencyLedger)
    _dead_reason: str = ""

    # -- plugin contract ------------------------------------------------

    def reset(self, request: LocalResetRequest) -> None:
        reply = self._roundtrip("reset", _encode_reset(request))
        if "error" in reply:
            raise RuntimeLoadError(f"{self.name} failed to reset: {reply['error']}")

    def step(self, request: LocalStepRequest) -> LocalPlanResult:
        reply = self._roundtrip("step", _encode_step(request))
        if "error" in reply:
            return _safe_stop(f"{self.name}: {reply['error']}")
        action = reply.get("action")
        if not isinstance(action, dict):
            return _safe_stop(f"{self.name} returned no action", self.last_latency)
        try:
            command = SimAction(
                linear_velocity=float(action["linear_velocity"]),
                angular_velocity=float(action["angular_velocity"]),
            )
        except (KeyError, TypeError, ValueError) as error:
            # A malformed action is a contract violation, handled like a
            # crash: the model already refuses NaN and infinities, so
            # anything that fails here is a shape nobody may drive on.
            return _safe_stop(f"{self.name} sent an unusable action: {error!r}", self.last_latency)
        return LocalPlanResult(
            action=command,
            latency_layers=self.last_latency.as_trace_row(),
        )

    # -- lifecycle ------------------------------------------------------

    def close(self) -> None:
        """Shut the worker down and let go of its pipes.

        Both halves matter. Closing stdin is how a healthy worker is
        asked to finish; closing the *handles* afterwards is what stops
        the interpreter complaining at collection time about a stream
        belonging to a process that is already gone. A warning nobody can
        act on is a warning everybody learns to skip.
        """
        if self._process.poll() is None:
            try:
                self._process.stdin.close()
                self._process.wait(timeout=2.0)
            except Exception:  # noqa: BLE001 - shutting down, any failure means kill
                self._kill("did not exit when its input closed")
        for stream in (self._process.stdin, self._process.stdout, self._process.stderr):
            try:
                if stream is not None and not stream.closed:
                    stream.close()
            except OSError:
                pass  # the far end is gone; there is nothing left to close

    def _kill(self, reason: str) -> None:
        self._dead_reason = reason
        if self._process.poll() is None:
            self._process.kill()
            self._process.wait(timeout=5.0)

    # -- protocol -------------------------------------------------------

    def _roundtrip(self, kind: str, request: dict[str, Any]) -> dict[str, Any]:
        if self._dead_reason:
            # Not respawned on purpose: a fresh worker mid-episode would
            # answer with a fresh internal state under one episode id.
            return {"error": f"worker is not running ({self._dead_reason})"}

        ledger = LatencyLedger(compute_measured_by=PLUGIN_REPORTED)
        transport_start = time.perf_counter()
        # Encoding failures raise rather than returning an error dict: a
        # payload this codec cannot carry is a preflight mistake, and a
        # tick that quietly continued would compute on data the plugin
        # never received.
        encoded = json.dumps({"kind": kind, "request": request})

        try:
            self._process.stdin.write(encoded + "\n")
            self._process.stdin.flush()
        except (BrokenPipeError, OSError, ValueError):
            self._kill("the worker closed its input")
            self._finish(ledger, transport_start, None)
            return {"error": f"worker died before the request was sent; {self._tail()}"}

        line = self._reader.readline(self.deadline_s)

        if line is None:
            self._kill("the worker exited")
            self._finish(ledger, transport_start, None)
            return {"error": f"worker exited without answering; {self._tail()}"}
        if line == "":
            self._kill(f"missed its {self.deadline_s * 1000:.0f} ms deadline")
            self._finish(ledger, transport_start, None)
            return {"error": f"worker missed its {self.deadline_s * 1000:.0f} ms deadline"}

        try:
            reply = json.loads(line)
        except json.JSONDecodeError as error:
            self._finish(ledger, transport_start, None)
            return {"error": f"worker sent a line that is not a response: {error}"}

        self._finish(ledger, transport_start, reply.get("reported_compute_ms"))
        return reply

    def _finish(
        self,
        ledger: LatencyLedger,
        transport_start: float,
        reported_compute_ms: float | None,
    ) -> None:
        """Close the transport layer — **after the decode**, because
        decoding the reply is part of moving it across the boundary.

        Transport is this span minus what the plugin said it spent
        thinking, and nothing else: the tick's remaining cost belongs to
        ``host_overhead_ms``, which the host fills in once the adapter and
        validation have run. A transport layer that absorbed the
        remainder would be a residual wearing a measurement's name.
        """
        span_ms = (time.perf_counter() - transport_start) * 1000.0
        compute_ms = float(reported_compute_ms or 0.0)
        ledger.algorithm_compute_ms = compute_ms
        ledger.transport_ms = max(0.0, span_ms - compute_ms)
        self.last_latency = ledger

    def _tail(self) -> str:
        """Whatever the worker said before it stopped answering."""
        said = self._stderr_drain.tail()[-400:]
        return f"it said: {said}" if said else "it said nothing"


class SubprocessRuntime:
    """Starts a plugin in its own interpreter, after preflight allows it."""

    lane = "subprocess"

    def __init__(self, *, search_paths: tuple[str, ...] = ()) -> None:
        #: Where the worker should look for the plugin package. An
        #: installed plugin needs none; an example bundle on disk does.
        self._search_paths = search_paths

    def load(
        self,
        manifest: PluginManifest,
        report: CompatibilityReport,
        config: dict[str, Any] | None = None,
        *,
        control_period_s: float,
    ) -> SubprocessPlugin:
        """Start the worker, with the deadline the **deployment** declares.

        ``control_period_s`` is required rather than defaulted: a lane
        that picked its own comfortable deadline would prove a plugin
        answers eventually, and G4 asks whether it answers in time for
        *this* robot. Making the caller supply it means the number can
        only come from the profile.
        """
        if not report.runnable:
            raise RuntimeLoadError(
                f"refusing to start {manifest.id!r}: preflight says {report.state} "
                f"({report.explain()})"
            )
        if manifest.runtime.production_lane != self.lane:
            raise RuntimeLoadError(
                f"{manifest.id!r} declares production lane "
                f"{manifest.runtime.production_lane!r}, not {self.lane!r}"
            )
        profile = manifest.runtime.profiles.get(self.lane)
        entry_point = profile.entry_point if profile else ""
        if not entry_point:
            raise RuntimeLoadError(f"{manifest.id!r} declares no entry_point for {self.lane!r}")

        # Run **by path, not by ``-m``**. ``-m`` imports the worker's
        # parent packages first, which would drag the whole host — and
        # its benchmark dependency — into a process whose entire purpose
        # is to contain a plugin and nothing else. Measured, not feared:
        # the first attempt died with ``No module named
        # 'planbench_benchmark'`` before the plugin was even reached.
        worker = Path(__file__).with_name("subprocess_worker.py")
        process = subprocess.Popen(  # noqa: S603 - the command is built here, not supplied
            [sys.executable, str(worker), entry_point, json.dumps(config or {})],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=self._environment(),
        )
        reader = _LineReader(process.stdout)
        # Started before the handshake: a plugin that logs while loading
        # would otherwise fill the stderr pipe and block before it ever
        # said "ready", and the host would call that a startup timeout.
        drain = _StreamDrain(process.stderr)
        line = reader.readline(STARTUP_TIMEOUT_S)
        if not line:
            # Whatever the worker managed to say before dying. Without
            # this the operator gets "did not start" and no reason, and
            # the reason is sitting unread on a pipe about to be closed.
            process.kill()
            complaint = drain.tail()
            raise RuntimeLoadError(
                f"{manifest.id!r} did not start"
                + (f"; the worker said: {complaint}" if complaint else "")
            )
        handshake = json.loads(line)
        if "error" in handshake:
            process.kill()
            raise RuntimeLoadError(f"{manifest.id!r} failed to load: {handshake['error']}")

        return SubprocessPlugin(
            name=handshake.get("name") or manifest.id,
            _process=process,
            _reader=reader,
            _stderr_drain=drain,
            deadline_s=control_period_s,
            control_period=control_period_s,
        )

    def _environment(self) -> dict[str, str]:
        import os

        env = dict(os.environ)
        parts = [*self._search_paths, *_repo_paths(), env.get("PYTHONPATH", "")]
        env["PYTHONPATH"] = os.pathsep.join(part for part in parts if part)
        return env


def _repo_paths() -> tuple[str, ...]:
    """The packages the worker itself imports.

    Derived from this file's location rather than assumed from the
    working directory: a subprocess started from anywhere must find the
    same code the host is running, and a relative guess would find
    whichever copy the caller happened to be standing in.
    """
    # runtimes -> host -> planbench_simulator -> simulator -> services -> root
    root = Path(__file__).resolve().parents[5]
    return tuple(
        str(root / part)
        for part in (
            "services/simulator",
            "packages/schemas",
            "packages/planning",
            "packages/plugin_sdk",
        )
    )


def _safe_stop(reason: str, ledger: LatencyLedger | None = None) -> LocalPlanResult:
    """A stop, with the tick's cost still attached.

    The layers travel even on failure: a tick that ended in a safe stop
    still consumed time, and dropping its measurement would quietly
    shorten every percentile computed over the episode.
    """
    return LocalPlanResult(
        action=SimAction(linear_velocity=0.0, angular_velocity=0.0),
        failure_reason=reason,
        latency_layers=(ledger or LatencyLedger()).as_trace_row(),
    )


def _encode_reset(request: LocalResetRequest) -> dict[str, Any]:
    """Reset, minus what cannot cross a JSON pipe.

    ``declared`` holds deployment objects — a safety envelope, a noise
    model — that this codec cannot carry. They are dumped when they know
    how and dropped when they do not, and dropping is stated here rather
    than silently: a plugin in this lane sees less than one in-process,
    and that is a property of the lane its author must be able to read.
    """
    return {
        "plugin_api": request.plugin_api,
        "global_path": [list(point) for point in request.global_path],
        # **The robot travels.** It was missing in the first version, and
        # a controller that cannot read its own velocity and acceleration
        # limits is a controller running a different experiment from the
        # one in-process — which would make a lane comparison meaningless.
        "robot": {name: _jsonable(value) for name, value in request.robot.items()},
        "declared": {
            name: _jsonable(value) for name, value in request.declared.items() if value is not None
        },
    }


def _encode_step(request: LocalStepRequest) -> dict[str, Any]:
    return {
        "plugin_api": request.plugin_api,
        "state": {name: _jsonable(value) for name, value in request.state.items()},
        "channels": [
            {
                "capability": envelope.capability,
                "cadence": envelope.cadence,
                "produced_at": envelope.produced_at,
                "revision": envelope.revision,
                "frame_id": envelope.frame_id,
                "provenance": envelope.provenance,
                # Carried, not dropped: a plugin that reads its own
                # envelope's encoding gets the same answer in either lane,
                # and one that validates it can notice a codec it does
                # not understand instead of misreading the payload.
                "payload_encoding": _LANE_CODEC,
                "payload": _jsonable(envelope.payload, envelope.capability),
            }
            for envelope in request.channels
        ],
    }


def _jsonable(value: Any, capability: str = "") -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, (list, tuple)):
        return [_jsonable(item, capability) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item, capability) for key, item in value.items()}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise UnencodableRequest(
        f"{_LANE_CODEC} cannot carry a {type(value).__name__}"
        + (f" on {capability}" if capability else "")
        + ". Preflight should have refused this pairing; substituting a placeholder "
        "would let the plugin compute on data it never received."
    )
