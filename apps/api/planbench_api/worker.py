"""In-process background worker with a hard concurrency limit.

Benchmarks are CPU-bound Python, so jobs run in a thread pool sized by
``PLANBENCH_WORKER_CONCURRENCY``. That bound is the point: an unbounded
pool would let a few large benchmarks starve the API process (spec
section 28). A distributed queue can replace this class later — callers
only use ``submit`` / ``get`` / ``cancel``.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

logger = logging.getLogger("planbench.worker")


class JobState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Job:
    """A unit of background work plus its observable progress."""

    id: str
    kind: str
    state: JobState = JobState.QUEUED
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    started_at: str | None = None
    finished_at: str | None = None
    progress: int = 0
    total: int = 0
    message: str = ""
    error: str | None = None
    #: Who asked for it. Cancelling somebody else's run is an
    #: administrator acting on their behalf, which is a different act and
    #: has to be recorded as one — so the queue has to know whose it is.
    created_by: str | None = None
    #: production | validation, mirroring the run it will store.
    purpose: str = "production"
    #: The run it produced, once it has produced one.
    run_id: str | None = None
    #: What the request resolved to, so the job can be re-checked at
    #: start rather than re-resolved. Opaque here on purpose: the queue
    #: carries it and does not read it.
    pinned: object | None = None


class JobQueue:
    """Bounded background execution with observable job state."""

    def __init__(self, concurrency: int = 2) -> None:
        if concurrency < 1:
            raise ValueError(f"concurrency must be >= 1, got {concurrency}")
        self._concurrency = concurrency
        self._executor = ThreadPoolExecutor(
            max_workers=concurrency, thread_name_prefix="planbench-worker"
        )
        self._jobs: dict[str, Job] = {}
        self._futures: dict[str, Future] = {}
        self._cancelled: set[str] = set()
        self._lock = threading.Lock()

    @property
    def concurrency(self) -> int:
        return self._concurrency

    def submit(
        self,
        job_id: str,
        kind: str,
        work: Callable[[Job], None],
        total: int = 0,
        **attributes,
    ) -> Job:
        """Queue ``work``; it receives the Job so it can report progress.

        ``attributes`` are stamped onto the job before it can start —
        who asked for it, what it will run, which run it produces. Set
        here rather than by the caller afterwards because a job on a free
        queue starts immediately, and a field written after ``submit``
        returns can be read empty by the work already in flight.
        """
        with self._lock:
            if job_id in self._jobs and self._jobs[job_id].state in (
                JobState.QUEUED,
                JobState.RUNNING,
            ):
                raise ValueError(f"job {job_id!r} is already active")
            job = Job(id=job_id, kind=kind, total=total, **attributes)
            self._jobs[job_id] = job
            self._cancelled.discard(job_id)

        def run() -> None:
            if job_id in self._cancelled:
                job.state = JobState.CANCELLED
                job.finished_at = datetime.now(UTC).isoformat()
                return
            job.state = JobState.RUNNING
            job.started_at = datetime.now(UTC).isoformat()
            try:
                work(job)
                job.state = JobState.CANCELLED if job_id in self._cancelled else JobState.SUCCEEDED
            except Exception as exc:  # noqa: BLE001 - recorded, not swallowed
                job.state = JobState.FAILED
                job.error = f"{type(exc).__name__}: {exc}"
                logger.exception("background job failed", extra={"context": {"job_id": job_id}})
            finally:
                job.finished_at = datetime.now(UTC).isoformat()

        self._futures[job_id] = self._executor.submit(run)
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def list(self) -> list[Job]:
        return sorted(self._jobs.values(), key=lambda job: job.created_at)

    def cancel(self, job_id: str) -> bool:
        """Request cancellation.

        A queued job is cancelled outright; a running job is flagged and
        stops at its next cooperative check (``is_cancelled``). Work is
        never killed mid-episode, so recorded results stay consistent.
        """
        job = self._jobs.get(job_id)
        if job is None or job.state in (
            JobState.SUCCEEDED,
            JobState.FAILED,
            JobState.CANCELLED,
        ):
            return False
        self._cancelled.add(job_id)
        future = self._futures.get(job_id)
        if future is not None and future.cancel():
            job.state = JobState.CANCELLED
            job.finished_at = datetime.now(UTC).isoformat()
        return True

    def is_cancelled(self, job_id: str) -> bool:
        return job_id in self._cancelled

    def wait(self, job_id: str, timeout: float | None = None) -> Job | None:
        """Block until the job finishes (used by tests and sync endpoints)."""
        future = self._futures.get(job_id)
        if future is not None:
            future.result(timeout=timeout)
        return self._jobs.get(job_id)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
