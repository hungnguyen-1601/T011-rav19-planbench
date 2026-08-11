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

from planbench_benchmark.hostinfo import (
    cpu_affinity,
    cpu_name,
    detect_benchmark_host,
    unpinned_warning,
)
from planbench_decision.card import BenchmarkHost


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
