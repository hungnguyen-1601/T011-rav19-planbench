"""What machine the run actually got (CONTRACTS HĐ-7.4).

The seventh fairness axis, and the one no schema can enforce: every
candidate must run on the same machine under the same CPU allocation.
That is a property of the *procedure*, not of the data model, so the
only defence available is to record what happened and let a reader see
when nothing protected the measurement.

The stakes are measured, not assumed: the same ``rrtstar+dwa`` gave a
pooled p99 of 59.30 ms unpinned and 16.10 ms pinned to two cores. A 3.7×
swing on the gate's own input, and it has already been read once as a
property of a candidate.
"""

from __future__ import annotations

import os

import pytest

from planbench_benchmark.hostinfo import (
    PinningRefused,
    apply_pinning,
    cpu_affinity,
    cpu_name,
    detect_benchmark_host,
    pin_to_cores,
    unpinned_warning,
)
from planbench_decision.card import BenchmarkHost


@pytest.fixture
def restore_affinity():
    """Put the mask back, whatever the test did to it.

    Pinning is process-wide. Without this, one test that pins to two
    cores leaves every later test in the session running on two cores —
    slower, and quietly changing the conditions of any timing assertion
    that follows.
    """
    before = cpu_affinity()
    yield
    if before is None:  # pragma: no cover - platform without affinity
        return
    setaffinity = getattr(os, "sched_setaffinity", None)
    if setaffinity is not None:
        setaffinity(0, set(before))
        return
    import psutil

    psutil.Process().cpu_affinity(list(before))


class TestDetection:
    def test_it_describes_this_machine(self) -> None:
        host = detect_benchmark_host()
        assert host.cpu
        assert host.logical_cores == os.cpu_count()
        assert host.cores_allocated >= 1

    def test_cores_allocated_follows_the_affinity_mask(self) -> None:
        """Not the number someone typed into a launch script.

        The old slice hard-coded ``cores_allocated=1`` while running on
        whatever the OS handed it, so the manifest described a run that
        never happened.
        """
        host = detect_benchmark_host()
        affinity = cpu_affinity()
        if affinity is not None:
            assert host.cores_allocated == len(affinity)

    def test_cpu_name_is_never_empty(self) -> None:
        """``platform.processor()`` returns an empty string on some
        platforms, and a manifest field with ``min_length=1`` would then
        refuse to build at the end of a three-hour run."""
        assert cpu_name()


class TestPinnedVerdict:
    def test_a_subset_of_cores_is_pinned(self) -> None:
        host = BenchmarkHost(
            cpu="x86", cores_allocated=2, threads=1, cpu_affinity=(0, 1), logical_cores=20
        )
        assert host.is_pinned is True
        assert unpinned_warning(host) is None

    def test_holding_every_core_is_not_pinned(self) -> None:
        """Whatever else the machine was doing landed on the same cores
        as the measurement."""
        host = BenchmarkHost(
            cpu="x86", cores_allocated=4, threads=1, cpu_affinity=(0, 1, 2, 3), logical_cores=4
        )
        assert host.is_pinned is False
        warning = unpinned_warning(host)
        assert warning is not None
        assert "59,30" in warning and "16,10" in warning

    def test_not_recorded_is_not_the_same_as_not_pinned(self) -> None:
        """An older manifest does not say, and inventing an answer for it
        would turn a gap in the record into a claim about the run."""
        host = BenchmarkHost(cpu="x86", cores_allocated=1, threads=1)
        assert host.is_pinned is None
        assert unpinned_warning(host) is None


class TestPinning:
    """The run protects its own measurement (HĐ-7.4, contract 6.2.0).

    A procedure that depends on someone remembering ``taskset`` protects
    the runs where they remembered. G4 reads wall-clock latency, and the
    same stack measured 59.30 ms unpinned against 16.10 ms on two cores.
    """

    def test_it_pins_and_reports_the_mask_the_os_granted(self, restore_affinity) -> None:
        total = os.cpu_count() or 1
        if total < 3:
            pytest.skip("needs a machine with cores to spare")
        mask = pin_to_cores(2)
        assert mask is not None
        # Re-read, not the mask we asked for: the OS is free to grant
        # something else and a manifest must record what the run got.
        assert mask == cpu_affinity()
        assert len(mask) == 2

    def test_taking_the_whole_machine_is_refused(self) -> None:
        """Not clamped — refused. Pinning to every core protects nothing
        while making the manifest look protected, which is worse than an
        honest unpinned run."""
        total = os.cpu_count() or 1
        with pytest.raises(PinningRefused, match="ghim hết máy"):
            pin_to_cores(total)

    def test_zero_cores_is_a_programming_error(self) -> None:
        with pytest.raises(ValueError):
            pin_to_cores(0)

    def test_the_host_record_says_who_pinned_it(self, restore_affinity) -> None:
        """A mask alone cannot tell a self-pinned run from one that
        inherited whatever it was launched with, and only the first
        reproduces its own protection."""
        total = os.cpu_count() or 1
        if total < 3:
            pytest.skip("needs a machine with cores to spare")
        source, message = apply_pinning(2)
        assert source == "script"
        assert message is not None
        host = detect_benchmark_host(affinity_source=source)
        assert host.affinity_source == "script"
        assert host.cores_allocated == 2
        assert host.is_pinned is True

    def test_no_pin_is_recorded_as_inherited_and_says_nothing(self) -> None:
        """``--no-pin`` is a legitimate choice — someone may have pinned
        externally — so it is not a warning, but it must not be recorded
        as if the run had pinned itself."""
        source, message = apply_pinning(None)
        assert source == "inherited"
        assert message is None

    def test_a_refusal_is_reported_not_swallowed(self) -> None:
        """Silently carrying on unpinned is the failure this whole path
        exists to stop."""
        total = os.cpu_count() or 1
        source, message = apply_pinning(total + 8)
        assert source == "inherited"
        assert message is not None
        assert "KHÔNG ghim" in message
