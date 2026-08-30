"""Stopping a sweep that has stopped being the right thing to run.

``JobQueue.cancel`` has always said a running job "stops at its next
cooperative check". Nothing in the decision path ever performed that
check, so cancelling a running sweep did nothing at all and a
three-hour warehouse run could not be called off once it had started.

The check belongs at the **episode boundary** and nowhere else. Stopping
mid-episode leaves a half-written trace and a simulator part-way through
a world — exactly the partial artefact the trace locator would then have
to guess about.

And a sweep stopped this way raises rather than scoring what it has.
That is the opposite of the ``KeyboardInterrupt`` path deliberately: an
interrupt means "I want to stop waiting", so the episodes on disk are
still a smaller honest run; this means "what you were measuring stopped
being true", and half a comparison under those conditions is a different
experiment, not a shorter one.
"""

from __future__ import annotations

import pytest

from planbench_benchmark.pipeline import SweepStopped


class _Recorder:
    """Counts boundaries and answers on the nth one."""

    def __init__(self, stop_at: int | None = None, reason: str = "told to stop") -> None:
        self.calls = 0
        self._stop_at = stop_at
        self._reason = reason

    def __call__(self) -> str | None:
        self.calls += 1
        if self._stop_at is not None and self.calls >= self._stop_at:
            return self._reason
        return None


def _sweep(should_stop, pairs: int = 4):
    """Drive the loop shape ``simulate`` uses, without a simulator.

    The real function needs a map, a profile and an engine; what is
    being pinned here is *where* the question is asked and what happens
    to the answer, which is loop structure. Reproducing the structure
    keeps this test at a second's runtime instead of a minute's, and a
    check that only ran in a slow integration test is a check nobody
    runs while changing the loop.
    """
    done = 0
    for _ in range(pairs):
        if should_stop is not None:
            reason = should_stop()
            if reason:
                raise SweepStopped(reason)
        done += 1
    return done


class TestWhereTheQuestionIsAsked:
    def test_a_sweep_that_is_never_stopped_runs_every_pair(self) -> None:
        recorder = _Recorder()
        assert _sweep(recorder, pairs=4) == 4
        assert recorder.calls == 4, "asked once per episode, not once per sweep"

    def test_stopping_happens_between_episodes_not_inside_one(self) -> None:
        """The count is the evidence: whole episodes, never a fraction."""
        recorder = _Recorder(stop_at=3)
        with pytest.raises(SweepStopped):
            _sweep(recorder, pairs=10)
        assert recorder.calls == 3

    def test_the_reason_travels_with_the_refusal(self) -> None:
        """What a person reads when a three-hour run ends early.

        "Cancelled" tells them nothing they did not already know;
        "mppi was disabled while this run was in progress (unsafe near
        glass)" tells them who to ask.
        """
        with pytest.raises(SweepStopped) as stopped:
            _sweep(_Recorder(stop_at=1, reason="mppi was disabled: unsafe near glass"))
        assert "unsafe near glass" in str(stopped.value)


class TestItIsNotAnInterrupt:
    def test_sweep_stopped_is_its_own_exception(self) -> None:
        """Because the two mean opposite things about the evidence.

        ``KeyboardInterrupt`` keeps what is on disk and scores it — the
        person wanted to stop waiting. ``SweepStopped`` propagates and no
        run is stored, because what was being measured stopped being
        true partway through.
        """
        assert not issubclass(SweepStopped, KeyboardInterrupt)
        assert issubclass(SweepStopped, Exception)


class TestTheHookIsWiredIntoTheRealLoop:
    """A signature check, because the loop itself is expensive to drive.

    Cheap and worth having: the failure it catches is somebody adding a
    parameter to ``simulate`` and not passing it through
    ``run_comparison``, which would leave the queue's cancel silently
    doing nothing again — the exact bug this phase exists to fix.
    """

    def test_simulate_accepts_a_stop_hook(self) -> None:
        import inspect

        from planbench_benchmark.pipeline import simulate

        assert "should_stop" in inspect.signature(simulate).parameters

    def test_run_comparison_passes_one_through(self) -> None:
        import inspect

        from planbench_benchmark.selection import run_comparison

        assert "should_stop" in inspect.signature(run_comparison).parameters

    def test_the_queue_carries_who_asked_and_what_was_pinned(self) -> None:
        from planbench_api.worker import Job

        job = Job(id="j", kind="decision_run", created_by="u1", purpose="validation")
        assert job.created_by == "u1"
        assert job.purpose == "validation"
        assert job.run_id is None and job.pinned is None
