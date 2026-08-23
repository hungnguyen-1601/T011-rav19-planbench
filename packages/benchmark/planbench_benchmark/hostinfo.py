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

from planbench_decision.card import AffinitySource, BenchmarkHost


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


class PinningRefused(RuntimeError):
    """The requested core count cannot be honoured on this machine."""


def pin_to_cores(count: int) -> tuple[int, ...] | None:
    """Confine this process to ``count`` cores; return the mask granted.

    ``None`` means the run was left unpinned, and the caller must say so
    rather than carry on as if it had been protected.

    **Why the process does this itself instead of trusting the operator.**
    G4 reads wall-clock latency, and CPU contention moves that number by
    more than the candidates differ from each other — 59.30 ms against
    16.10 ms for the same stack. A procedure that depends on someone
    remembering ``taskset`` protects the runs where they remembered.

    **Refused rather than clamped when the machine is too small.** Taking
    every core is not pinning: whatever else runs lands on the same cores
    as the measurement, and a manifest recording a full-machine mask
    *looks* protected. A smaller machine gets an honest unpinned run.

    **Which cores, and why the choice does not need to be clever.**
    The first ``count`` of them. Hyper-threading siblings and P/E-core
    layouts are enumerated differently on every platform, so any pick is
    a guess — but the fairness argument does not depend on the pick:
    every candidate runs in this one process under this one mask, so a
    bad placement is *common* noise and cancels in the paired difference
    (HĐ-7.4). Pinning buys isolation from other load, not optimal
    placement. Someone who knows their topology can pin externally and
    pass ``--no-pin``.
    """
    if count < 1:
        raise ValueError(f"pin_to_cores needs at least one core, got {count!r}")
    total = os.cpu_count() or 1
    if total <= count:
        raise PinningRefused(
            f"máy có {total} nhân logic, không thể ghim {count} mà còn chỗ cho phần "
            "còn lại của máy; ghim hết máy không bảo vệ được gì mà lại làm manifest "
            "trông như đã được bảo vệ"
        )

    target = list(range(count))
    setaffinity = getattr(os, "sched_setaffinity", None)
    if setaffinity is not None:
        try:
            setaffinity(0, set(target))
        except OSError:  # pragma: no cover - platform-dependent
            return None
    else:
        try:
            import psutil

            psutil.Process().cpu_affinity(target)
        except (ImportError, AttributeError, OSError):  # pragma: no cover
            return None

    # Re-read rather than return ``target``: the OS is free to grant
    # something else, and a manifest must record what the run got.
    return cpu_affinity()


def apply_pinning(cores: int | None) -> tuple[AffinitySource, str | None]:
    """Do what the CLI asked, and hand back one line saying what happened.

    Returns ``(affinity_source, message)``. The message is printed by the
    caller rather than here so this stays a library function, and it is
    never ``None`` when the outcome differs from what was requested —
    silently not pinning is the failure this whole path exists to stop.

    Called from a script's ``main()``, never from the run function. Tests
    call the run functions directly, and a test suite that pins itself to
    two cores would be both slow and rude to the machine it runs on.
    """
    if cores is None:
        return "inherited", None
    try:
        mask = pin_to_cores(cores)
    except PinningRefused as refusal:
        return "inherited", f"chạy KHÔNG ghim nhân — {refusal}"
    if mask is None:  # pragma: no cover - platform-dependent
        return "inherited", "hệ điều hành từ chối đặt affinity; run chạy KHÔNG ghim nhân"
    return "script", f"ghim vào {len(mask)} nhân: {list(mask)}"


def detect_benchmark_host(
    *, threads: int = 1, affinity_source: AffinitySource | None = None
) -> BenchmarkHost:
    """Describe the machine as it is right now, not as intended.

    ``cores_allocated`` comes from the affinity mask when there is one,
    so a run that *meant* to pin two cores and did not cannot record
    two. That was the old failure mode: the slice hard-coded
    ``cores_allocated=1`` while running on whatever the OS handed it, and
    the manifest said something true of no run that ever happened.

    ``affinity_source`` separates two situations a bare mask cannot: the
    run pinned itself (so re-running it reproduces the same protection),
    or it inherited whatever it was launched with (so the mask is a fact
    about that launch and nothing more).
    """
    affinity = cpu_affinity()
    cores = os.cpu_count() or 1
    return BenchmarkHost(
        cpu=cpu_name(),
        cores_allocated=len(affinity) if affinity else cores,
        threads=threads,
        cpu_affinity=affinity,
        logical_cores=cores,
        affinity_source=affinity_source,
    )


#: The pair of measurements the warning cites. Historical, from the
#: module docstring above — a property of ``rrtstar+dwa`` on one machine
#: on one day, **not** of the run being read. Named ``reference_`` all
#: the way out to the client for that reason: a bare ``unpinned_ms``
#: invites a reader to take it for this run's own latency.
REFERENCE_UNPINNED_MS = 59.30
REFERENCE_PINNED_MS = 16.10


def _vi_number(value: float) -> str:
    """Two decimals, Vietnamese comma — the sentence has always read
    ``59,30``, and deriving it beats a second copy of the digits."""
    return f"{value:.2f}".replace(".", ",")


def unpinned_warning(host: BenchmarkHost) -> str | None:
    """One sentence when the run held the whole machine, else ``None``.

    Not an error. A run on an idle machine is fine unpinned, and one on a
    busy machine is not — which of the two happened is not something the
    process can know. What it can do is stop the reader assuming the
    measurement was protected when nothing protected it.

    Still a string, and still Vietnamese: the export reads this key and
    so does every client written before ``warning_code`` existed. What
    changed is that it is no longer the *only* form — see
    :func:`unpinned_warning_info`.
    """
    if host.is_pinned is not False:
        return None
    return (
        f"Đo trên toàn bộ {host.logical_cores} nhân, không ghim: G4 đọc độ trễ theo "
        "đồng hồ tường nên mọi tải khác trên máy đi thẳng vào con số. Cùng candidate "
        f"đo được {_vi_number(REFERENCE_UNPINNED_MS)} ms không ghim và "
        f"{_vi_number(REFERENCE_PINNED_MS)} ms khi ghim 2 nhân"
    )


def unpinned_warning_info(host: BenchmarkHost) -> dict[str, object] | None:
    """The same warning as a code and its numbers, else ``None``.

    The sentence above is written in one language, and a client that must
    show it in another has only two bad options: reword it — which the
    detail page comments rightly refuse, because a client that rewords a
    caveat can water it down — or print Vietnamese on an English page.

    Both are avoidable, because the thing that must not be reinterpreted
    is the **numbers**, not the language. So this returns what the
    platform decided (``code``) and what it measured (``params``), and
    the wording becomes the client's business while the classification
    stays here.
    """
    if host.is_pinned is not False:
        return None
    return {
        "code": "unpinned_host",
        "params": {
            "cores": host.logical_cores,
            "reference_unpinned_ms": REFERENCE_UNPINNED_MS,
            "reference_pinned_ms": REFERENCE_PINNED_MS,
        },
    }


def measurement_environment(host: BenchmarkHost) -> dict[str, object]:
    """The block every report carries about the machine it ran on.

    One function because there are three places that build it — a ranked
    report, a report interrupted before the first episode, and
    ``scripts/measure.py`` — and a caveat that reaches two of them is a
    caveat the third silently drops.

    ``warning`` stays first and stays a string. Removing it would break
    the export and every stored run; the two keys beside it are additions
    a reader may ignore.
    """
    info = unpinned_warning_info(host)
    return {
        "benchmark_host": host.model_dump(),
        "warning": unpinned_warning(host),
        "warning_code": info["code"] if info else None,
        "warning_params": info["params"] if info else None,
    }
