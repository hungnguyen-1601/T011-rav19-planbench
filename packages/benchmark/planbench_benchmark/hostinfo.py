"""What machine this run is actually getting (HĐ-7.4).

The decision layer is a pure function of its inputs and must stay that
way — a module that reads the clock and asks the OS about CPUs cannot be
tested for reproducibility, which is the one property the manifest
exists to provide. So the measuring happens here, on the runner side,
and the answer is passed in.

**Why the affinity matters enough to have its own module.** G4 reads
wall-clock latency. CPU contention moves that number by more than the
candidates differ from each other: the same ``rrtstar+dwa`` measured
59.30 ms pooled p99 unpinned and 16.10 ms pinned to two cores. That
factor of 3.7 has already been misread once as a property of a candidate
— contract 3.0.0 records A\\* being eliminated at G4 for the machine's
behaviour rather than its own.

Interleaving candidates (``iter_run_plan``) turns machine load into
*common* noise that cancels in a paired difference, and that is the
structural defence. Pinning is the other half, and it is an operating
procedure rather than a property of the data model — which is exactly
why it has to be written down per run instead of trusted.
"""

from __future__ import annotations

import os
import platform

from planbench_decision.card import BenchmarkHost


def cpu_name() -> str:
    """A human-recognisable name for the processor, never empty."""
    return platform.processor() or platform.machine() or "unknown"


def cpu_affinity() -> tuple[int, ...] | None:
    """The cores this process may run on, or ``None`` if unknowable.

    ``os.sched_getaffinity`` exists on Linux only; ``psutil`` covers
    Windows. Returning ``None`` rather than guessing is deliberate: a
    manifest saying "not recorded" is honest, while one saying "all
    cores" when nobody asked is a measurement claim nobody made.
    """
    getaffinity = getattr(os, "sched_getaffinity", None)
    if getaffinity is not None:
        return tuple(sorted(getaffinity(0)))
    try:
        import psutil
    except ImportError:  # pragma: no cover - psutil is a pinned dependency
        return None
    try:
        return tuple(sorted(psutil.Process().cpu_affinity()))
    except (AttributeError, OSError):  # pragma: no cover - platform-dependent
        return None


def logical_cores() -> int | None:
    return os.cpu_count()


def detect_benchmark_host(*, threads: int = 1) -> BenchmarkHost:
    """Describe the machine as it is right now, not as intended.

    ``cores_allocated`` comes from the affinity mask when there is one,
    so a run that *meant* to pin two cores and did not cannot record
    two. That was the old failure mode: the slice hard-coded
    ``cores_allocated=1`` while running on whatever the OS handed it, and
    the manifest said something true of no run that ever happened.
    """
    affinity = cpu_affinity()
    cores = os.cpu_count() or 1
    return BenchmarkHost(
        cpu=cpu_name(),
        cores_allocated=len(affinity) if affinity else cores,
        threads=threads,
        cpu_affinity=affinity,
        logical_cores=cores,
    )


def unpinned_warning(host: BenchmarkHost) -> str | None:
    """One sentence when the run held the whole machine, else ``None``.

    Not an error. A run on an idle machine is fine unpinned, and one on a
    busy machine is not — which of the two happened is not something the
    process can know. What it can do is stop the reader assuming the
    measurement was protected when nothing protected it.
    """
    if host.is_pinned is not False:
        return None
    return (
        f"Đo trên toàn bộ {host.logical_cores} nhân, không ghim: G4 đọc độ trễ theo "
        "đồng hồ tường nên mọi tải khác trên máy đi thẳng vào con số. Cùng candidate "
        "đo được 59,30 ms không ghim và 16,10 ms khi ghim 2 nhân"
    )
