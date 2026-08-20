"""H10: the end-to-end deadline screen, and the protocol it obeys.

The tests that matter here are the ones about the **interval**, because
that is where a screen quietly lies. A gate that reads a confidence
interval computed the wrong way does not fail — it passes, confidently,
on data that does not support the verdict.

So the resampling unit is pinned twice: once as a refusal (a protocol
asking for per-tick resampling is rejected on load) and once
numerically (per-tick resampling on correlated data gives a visibly
narrower interval than per-episode, which is the whole reason v1 had to
be amended before anything was measured).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import yaml

from planbench_decision.latency_screen import (
    HostConditions,
    LatencyProtocol,
    ProtocolError,
    SentinelReading,
    pooled_percentile,
    screen,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_V2 = REPO_ROOT / "configs" / "latency-screening-v2.yaml"
PROTOCOL_V1 = REPO_ROOT / "configs" / "latency-screening-v1.yaml"


@pytest.fixture(scope="module")
def protocol() -> LatencyProtocol:
    return LatencyProtocol.load(PROTOCOL_V2)


def episodes(
    count: int, *, ticks: int = 40, mean: float = 20.0, spread: float = 2.0, seed: int = 1
) -> list[list[float]]:
    """Episodes whose ticks are **correlated within an episode**.

    Each episode gets its own offset and its ticks vary only slightly
    around it — which is what real ticks do, sharing a map, a seed and a
    trajectory. Independent-looking ticks would make the two resampling
    units agree and hide the very difference these tests exist to show.
    """
    rng = np.random.default_rng(seed)
    offsets = rng.normal(mean, spread, size=count)
    return [list(rng.normal(offset, 0.25, size=ticks)) for offset in offsets]


class TestTheProtocolIsCommittedNotArgued:
    def test_v2_loads_and_states_its_resample_unit(self, protocol) -> None:
        assert protocol.version == "latency-screening-v2"
        assert protocol.resample_unit == "episode"

    def test_v1_is_kept_and_refused(self) -> None:
        """**Both halves matter.** v1 stays on disk because the history
        has to hold the ambiguous ruler and the reason it was replaced;
        it is refused because "bootstrap, of what?" is not a protocol a
        verdict may be computed under."""
        assert PROTOCOL_V1.is_file()
        with pytest.raises(ProtocolError, match="does not say what it resamples"):
            LatencyProtocol.load(PROTOCOL_V1)

    def test_a_protocol_asking_for_per_tick_resampling_is_refused(self, tmp_path) -> None:
        data = yaml.safe_load(PROTOCOL_V2.read_text(encoding="utf-8"))
        data["resample_unit"] = "tick"
        path = tmp_path / "bad.yaml"
        path.write_text(yaml.safe_dump(data), encoding="utf-8")
        with pytest.raises(ProtocolError, match="not independent draws"):
            LatencyProtocol.load(path)


class TestTheIntervalIsHonestAboutItsSampleSize:
    def test_resampling_ticks_would_give_a_narrower_interval(self, protocol) -> None:
        """The measured reason v1 had to be amended.

        Ticks inside an episode share everything, so treating them as
        independent draws shrinks the interval for a reason that has
        nothing to do with the candidate. Shown as a number rather than
        asserted in a comment.
        """
        sample = episodes(30)
        record = screen(sample, protocol=protocol, deadline_ms=50.0)
        episode_width = record.ci_upper_ms - record.ci_lower_ms

        rng = np.random.default_rng(protocol.bootstrap_seed)
        ticks = [value for episode in sample for value in episode]
        draws = [
            float(np.percentile(rng.choice(ticks, size=len(ticks), replace=True), 99.0))
            for _ in range(400)
        ]
        tick_width = float(np.percentile(draws, 97.5) - np.percentile(draws, 2.5))

        assert tick_width < episode_width, (
            "per-tick resampling did not look narrower here, so this fixture no longer "
            "models correlated ticks and the comparison proves nothing"
        )

    def test_the_effective_sample_size_is_recorded(self, protocol) -> None:
        """Resampling episodes means the number that sets the interval's
        width is the episode count, not the tick count — so it travels
        with the interval instead of being inferred from it."""
        record = screen(episodes(30), protocol=protocol, deadline_ms=50.0)
        assert record.episodes == 30
        assert record.ticks == 30 * 40

    def test_pooled_percentile_is_not_a_mean_of_percentiles(self) -> None:
        """One slow episode among fast ones moves the pooled p99; the
        mean of per-episode p99s would bury it."""
        fast = [[10.0] * 100 for _ in range(9)]
        slow = [[90.0] * 100]
        pooled = pooled_percentile(fast + slow)
        mean_of_p99s = float(np.mean([np.percentile(e, 99.0) for e in fast + slow]))
        assert pooled > mean_of_p99s


class TestTheVerdicts:
    def test_a_comfortably_fast_candidate_passes(self, protocol) -> None:
        record = screen(episodes(30, mean=10.0), protocol=protocol, deadline_ms=50.0)
        assert record.verdict == "pass"
        assert record.ci_upper_ms < 50.0 - protocol.guard_band_ms

    def test_a_clearly_slow_candidate_fails(self, protocol) -> None:
        record = screen(episodes(30, mean=90.0), protocol=protocol, deadline_ms=50.0)
        assert record.verdict == "fail"
        assert "guard band" in record.reason

    def test_a_candidate_sitting_on_the_deadline_is_inconclusive(self, protocol) -> None:
        """Neither pass nor fail: calling it either way from an interval
        straddling the guard band is a preference, not a result."""
        record = screen(episodes(30, mean=44.0, spread=7.0), protocol=protocol, deadline_ms=50.0)
        assert record.verdict == "inconclusive"
        assert "straddles" in record.reason


class TestTheFloorsBeatTheInterval:
    def test_too_few_episodes_is_inconclusive_however_tight_the_interval(self, protocol) -> None:
        """Four identical episodes give an interval of essentially zero
        width, and it still says nothing about the fifth."""
        record = screen([[10.0] * 300 for _ in range(4)], protocol=protocol, deadline_ms=50.0)
        assert record.verdict == "inconclusive"
        assert "floor" in record.reason
        assert record.episodes == 4

    def test_too_few_ticks_is_inconclusive(self, protocol) -> None:
        record = screen([[10.0] * 2 for _ in range(30)], protocol=protocol, deadline_ms=50.0)
        assert record.verdict == "inconclusive"
        assert "percentile" in record.reason


class TestTheSentinelGuardsTheHost:
    def test_a_drifting_sentinel_makes_the_session_not_measured(self, protocol) -> None:
        """A statement about the machine, not the candidate."""
        record = screen(
            episodes(30, mean=10.0),
            protocol=protocol,
            deadline_ms=50.0,
            sentinel=SentinelReading(before_ms=20.0, after_ms=40.0),
        )
        assert record.verdict == "not_measured"
        assert "not quiet" in record.reason

    def test_a_steady_sentinel_lets_the_verdict_through(self, protocol) -> None:
        record = screen(
            episodes(30, mean=10.0),
            protocol=protocol,
            deadline_ms=50.0,
            sentinel=SentinelReading(before_ms=20.0, after_ms=21.0),
        )
        assert record.verdict == "pass"

    def test_drift_is_measured_against_the_larger_reading(self) -> None:
        """Otherwise the same physical drift reads differently depending
        on which direction the host moved."""
        up = SentinelReading(before_ms=20.0, after_ms=40.0)
        down = SentinelReading(before_ms=40.0, after_ms=20.0)
        assert up.drift_fraction == down.drift_fraction


class TestTheRecordCanBeDistrusted:
    def test_it_carries_what_the_host_was_doing(self, protocol) -> None:
        record = screen(
            episodes(30, mean=10.0),
            protocol=protocol,
            deadline_ms=50.0,
            host=HostConditions(worker_count=1, blas_threads=1, host_description="quiet-box"),
            candidate_id="3b18dfbfa9e7",
            git_sha="deadbeef",
            runtime_profile={"lane": "subprocess", "codec": "json-v1"},
        )
        assert record.host.host_description == "quiet-box"
        assert record.candidate_id == "3b18dfbfa9e7"
        assert record.git_sha == "deadbeef"
        assert record.runtime_profile["lane"] == "subprocess"
        assert record.protocol_version == "latency-screening-v2"

    def test_a_retry_says_why(self, protocol) -> None:
        """Re-running until the number is agreeable is what this field
        makes visible; the protocol forbids it, and an empty field is not
        evidence that nobody did it — a filled one is evidence somebody
        declared it."""
        record = screen(
            episodes(30, mean=10.0),
            protocol=protocol,
            deadline_ms=50.0,
            retry_reason="first session aborted: laptop lid closed",
        )
        assert "lid closed" in record.retry_reason


class TestG4KeepsBothScreens:
    def _profile(self):
        from task_profile_fakes import make_profile

        return make_profile()

    def test_the_legacy_screen_is_unchanged_when_nothing_was_measured(self) -> None:
        """Most runs. Absent is not 'passed': the gate reports exactly
        what the legacy screen said and claims nothing about the tick."""
        from planbench_decision.gates import G4Result

        result = G4Result(result="pass", n_runs=30, p99_ms=12.0, threshold_ms=50.0)
        assert result.end_to_end is None
        assert result.overall == "pass"

    def test_a_failing_end_to_end_screen_fails_the_gate(self, protocol) -> None:
        from planbench_decision.gates import G4Result

        record = screen(episodes(30, mean=90.0), protocol=protocol, deadline_ms=50.0)
        result = G4Result(
            result="pass", n_runs=30, p99_ms=12.0, threshold_ms=50.0, end_to_end=record
        )
        assert record.verdict == "fail"
        assert result.overall == "fail"

    def test_a_noisy_host_does_not_fail_a_candidate(self, protocol) -> None:
        """``not_measured`` is about the room, not the robot — letting it
        downgrade the verdict would make the gate a measure of what else
        was running on the benchmark machine."""
        from planbench_decision.gates import G4Result

        record = screen(
            episodes(30, mean=10.0),
            protocol=protocol,
            deadline_ms=50.0,
            sentinel=SentinelReading(before_ms=20.0, after_ms=40.0),
        )
        result = G4Result(
            result="pass", n_runs=30, p99_ms=12.0, threshold_ms=50.0, end_to_end=record
        )
        assert record.verdict == "not_measured"
        assert result.overall == "pass"

    def test_an_inconclusive_screen_does_not_read_as_a_pass(self, protocol) -> None:
        from planbench_decision.gates import G4Result

        record = screen(episodes(30, mean=44.0, spread=7.0), protocol=protocol, deadline_ms=50.0)
        result = G4Result(
            result="pass", n_runs=30, p99_ms=12.0, threshold_ms=50.0, end_to_end=record
        )
        assert result.overall == "inconclusive"
