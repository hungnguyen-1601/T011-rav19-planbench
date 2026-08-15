"""A sweep can be stopped, and the episodes it managed are a result.

``simulate`` has always filled contexts outermost so that stopping
halfway leaves every candidate on the same episodes — a smaller valid
comparison rather than a ragged one. But nothing cashed that in: the
report was written after the last episode, so a 600-episode run killed
at 491 left three hours of traces on disk and no file saying what had
been measured.

Two things changed and both are under test here: the journal written as
each episode finishes, and the report a stopped run can still produce.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_vertical_slice import write_profile

from planbench_benchmark import pipeline, selection
from planbench_benchmark.contexts import build_evaluation_contexts
from planbench_simulator.trace import trace_path

CANDIDATES = (("astar+dwa", "dwa_coarse"), ("rrtstar+dwa", "dwa_coarse"))


@pytest.fixture(scope="module")
def stopped(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    """Simulate six episodes, then score as if the run had asked for ten
    and been killed — which is what ``--score-only`` recovers."""
    workspace = tmp_path_factory.mktemp("compare_stopped")
    common = {
        "profile_path": write_profile(workspace),
        "candidate_specs": CANDIDATES,
        "scope": "global_planner_selection",
        "trace_root": workspace / "traces",
        "run_root": workspace / "runs",
        "quiet": True,
        "map_base_dir": workspace,
    }
    selection.run_comparison(episodes=6, reuse=False, **common)  # type: ignore[arg-type]
    return selection.run_comparison(
        episodes=10,
        reuse=True,
        score_only=True,
        **common,  # type: ignore[arg-type]
    )


@pytest.fixture(scope="module")
def complete(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    workspace = tmp_path_factory.mktemp("compare_complete")
    return selection.run_comparison(
        profile_path=write_profile(workspace),
        candidate_specs=CANDIDATES,
        scope="global_planner_selection",
        episodes=6,
        trace_root=workspace / "traces",
        run_root=workspace / "runs",
        reuse=False,
        quiet=True,
        map_base_dir=workspace,
    )


class TestTheJournal:
    def test_it_records_every_episode_as_it_finishes(self, complete: dict[str, object]) -> None:
        journal = Path(str(complete["run_uri"]).removeprefix("file://")) / "run_journal.jsonl"
        entries = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
        episodes = [e for e in entries if "event" not in e]
        assert len(episodes) == 12  # 6 contexts x 2 candidates
        assert {e["seed"] for e in episodes} == set(range(6))
        # Every field a later reader needs to tie a line back to an
        # episode without the process that wrote it.
        for entry in episodes:
            assert entry["episode_context_id"]
            assert entry["candidate_id"]
            assert entry["status"]
            assert entry["wall_clock_s"] >= 0


class TestARunThatDidNotReachItsOwnEnding:
    def test_it_scores_the_episodes_it_has(self, stopped: dict[str, object]) -> None:
        assert stopped["sample"]["n_episodes"] == 6
        assert stopped["candidates"]

    def test_the_report_says_it_is_smaller_than_what_was_asked_for(
        self, stopped: dict[str, object]
    ) -> None:
        """The distinction the field exists for: "we chose 6" and "the
        machine was taken back at 6" are different claims about the same
        number, and only one of them is true here."""
        assert stopped["sample"]["interrupted"] is True
        assert stopped["sample"]["n_episodes_requested"] == 10

    def test_every_candidate_is_scored_on_the_same_episodes(
        self, stopped: dict[str, object]
    ) -> None:
        """The point of the prefix rule. Taking the *set* of finished
        episodes instead would let one candidate carry an episode the
        other never ran, and HĐ-7.3's paired design would be gone without
        anything failing."""
        assert "the same 6 episode contexts" in " ".join(stopped["checks"])

    def test_a_complete_run_is_not_labelled_interrupted(self, complete: dict[str, object]) -> None:
        assert complete["sample"]["interrupted"] is False
        assert complete["sample"]["n_episodes_requested"] == 6


class TestThePrefixRule:
    def test_it_stops_at_the_first_gap_rather_than_taking_the_set(self, tmp_path: Path) -> None:
        """A hole in the middle ends the prefix. The episodes after it are
        real, but keeping them would mean comparing candidates on episode
        lists that differ by whatever the hole was."""
        profile = selection.load_profile(write_profile(tmp_path))
        candidates = selection.build_candidates(profile, CANDIDATES, "global_planner_selection")
        contexts = build_evaluation_contexts(profile, seed_count=5)
        root = tmp_path / "traces"
        for index, context in enumerate(contexts):
            for candidate in candidates:
                if index == 2 and candidate is candidates[1]:
                    continue  # the half-finished context
                path = trace_path(candidate.candidate_id, context.episode_context_id, root=root)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"")
        kept = pipeline.paired_prefix(candidates, contexts, root)
        assert [c.seed for c in kept] == [0, 1]
