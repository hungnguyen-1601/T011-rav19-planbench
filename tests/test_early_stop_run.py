"""Early stopping inside a real sweep: what the run does and what it says.

``test_early_stop.py`` covers the arithmetic in isolation. This covers
the parts that only exist once a run is involved — the flag being off
unless asked, the floor being honoured and recorded, the retired
candidate never being ranked, and the report carrying enough for a
reader to see what was traded away.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from test_early_stop import _episode
from test_vertical_slice import write_profile

from planbench_benchmark import pipeline, selection

CANDIDATES = (("astar+dwa", "dwa_coarse"), ("rrtstar+dwa", "dwa_coarse"))


def strict_profile(directory: Path, **overrides: object) -> Path:
    """The fixture hall, made impossible to pass, so somebody gets retired.

    Two edits, and both are **deployment** declarations rather than
    sabotage of a candidate — that is how it happens in practice, and a
    fixture that lied about the mechanism would exercise a path the
    platform never takes:

    * ``success_rate_min: 1.0`` — one failed episode provably loses G3
      for good, which is exactly the acceptance-deployment posture
      (HĐ Q1) applied to a fixture.
    * ``episode_timeout_s: 2`` — a deadline the mission cannot meet, so
      episodes fail by timeout. Without it every episode succeeds here
      and there is nothing for a stopping rule to fire on.
    """
    path = write_profile(directory)
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    payload["id"] = "early_stop_fixture"
    payload["constraints"]["success_rate_min"] = 1.0
    payload["constraints"]["episode_timeout_s"] = 2
    payload["constraints"]["stuck_threshold_s"] = 1
    payload.update(overrides)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def run(workspace: Path, profile: Path, **kwargs: object) -> dict[str, object]:
    return selection.run_comparison(
        profile_path=profile,
        candidate_specs=CANDIDATES,
        scope="global_planner_selection",
        episodes=6,
        trace_root=workspace / "traces",
        run_root=workspace / "runs",
        reuse=False,
        quiet=True,
        map_base_dir=workspace,
        **kwargs,  # type: ignore[arg-type]
    )


class TestOffUnlessAsked:
    """A feature that trades data for hours has to be requested.

    Defaulting it on would quietly make every future run poorer, and the
    people losing data would not know what they had lost. The concrete
    case is the first warehouse sweep: both stacks were doomed by episode
    12 of 600, and all three findings that mattered needed hundreds.
    """

    def test_a_plain_run_never_retires_anybody(self, tmp_path: Path) -> None:
        report = run(tmp_path, strict_profile(tmp_path))
        early = report["early_stop"]
        assert early["enabled"] is False
        assert early["stopped"] == []
        assert early["episodes_saved"] == 0
        for entry in report["candidates"]:
            assert entry["stopped_early"] is None
            assert entry["n_episodes"] == 6

    def test_an_acceptance_deployment_refuses_the_flag(self, tmp_path: Path) -> None:
        """Refused, not silently ignored. A swallowed flag leaves the user
        believing they are saving time when they are not."""
        profile = strict_profile(tmp_path, deployment_role="acceptance")
        with pytest.raises(pipeline.AcceptanceFailure, match="acceptance"):
            run(tmp_path, profile, stop_early=True)


class TestTheFloor:
    def test_flag_beats_profile_beats_default(self, tmp_path: Path) -> None:
        plain = selection.load_profile(strict_profile(tmp_path))
        assert selection.resolve_stop_floor(plain, None) == 30
        declared = selection.load_profile(strict_profile(tmp_path, min_episodes_before_stop=7))
        assert selection.resolve_stop_floor(declared, None) == 7
        assert selection.resolve_stop_floor(declared, 2) == 2

    def test_the_value_actually_used_reaches_the_report(self, tmp_path: Path) -> None:
        """Two runs of one profile under two floors are two different
        measurements, and nothing else on the report would tell them
        apart — the hole ``constraints`` had in the manifest until A4."""
        report = run(
            tmp_path, strict_profile(tmp_path), stop_early=True, min_episodes_before_stop=2
        )
        assert report["early_stop"]["min_episodes_before_stop"] == 2

    def test_it_holds_a_doomed_candidate_in_the_run(self, tmp_path: Path) -> None:
        """And the report says where the rule *first* fired, so "it knew
        at episode 1, why did it run to 4?" has an answer."""
        report = run(
            tmp_path, strict_profile(tmp_path), stop_early=True, min_episodes_before_stop=4
        )
        stopped = [e for e in report["candidates"] if e["stopped_early"]]
        assert stopped, "the strict fixture should doom at least one candidate"
        for entry in stopped:
            floor = entry["stopped_early"]["floor_applied"]
            assert floor["min_episodes_before_stop"] == 4
            assert entry["stopped_early"]["episodes_run"] >= 4
            assert floor["would_have_stopped_at"] <= entry["stopped_early"]["episodes_run"]


@pytest.fixture(scope="module")
def retired_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    workspace = tmp_path_factory.mktemp("early_stop_run")
    return run(
        workspace,
        strict_profile(workspace),
        stop_early=True,
        min_episodes_before_stop=1,
    )


class TestARetiredCandidate:
    def test_somebody_was_retired_by_a_named_gate(self, retired_run: dict[str, object]) -> None:
        stopped = retired_run["early_stop"]["stopped"]
        assert stopped, "the strict fixture should doom at least one candidate"
        for entry in stopped:
            assert entry["gate"] in {"G1", "G2", "G3", "G5"}
            assert entry["rule"]
            assert entry["evidence"]

    def test_it_is_never_also_a_survivor(self, retired_run: dict[str, object]) -> None:
        """The premise the whole feature rests on: early stopping is sound
        only because a retired candidate failed a gate and so never
        reaches ΔU, which is what lets the paired-context invariant be
        narrowed to survivors."""
        retired = {e["candidate_id"] for e in retired_run["early_stop"]["stopped"]}
        for entry in retired_run["candidates"]:
            if entry["candidate_id"] in retired:
                assert entry["cleared_gates"] is False
                assert entry["blocking_gates"]

    def test_the_report_carries_its_own_denominator(self, retired_run: dict[str, object]) -> None:
        """Two success rates over different denominators are not a
        ranking, and a reader needs the denominator beside the rate."""
        for entry in retired_run["candidates"]:
            assert entry["n_episodes"] >= 1
            if entry["stopped_early"]:
                assert entry["n_episodes"] == entry["stopped_early"]["episodes_run"]
                assert entry["stopped_early"]["episodes_planned"] == 6

    def test_the_saving_is_stated_not_assumed(self, retired_run: dict[str, object]) -> None:
        """A feature that trades data for hours has to make both sides
        visible, or it gets judged only on the half that is easy to see."""
        expected = sum(6 - e["episodes_run"] for e in retired_run["early_stop"]["stopped"])
        assert retired_run["early_stop"]["episodes_saved"] == expected

    def test_no_card_when_fewer_than_two_candidates_clear(
        self, retired_run: dict[str, object]
    ) -> None:
        survivors = [e for e in retired_run["candidates"] if e["cleared_gates"]]
        if len(survivors) < 2:
            assert retired_run["decision_card"] is None

    def test_the_journal_records_the_stop_as_its_own_event(
        self, retired_run: dict[str, object]
    ) -> None:
        """A candidate leaving mid-sweep must never have to be inferred
        from a gap in the episode numbering."""
        journal = Path(str(retired_run["run_uri"]).removeprefix("file://")) / "run_journal.jsonl"
        events = [
            entry
            for entry in (json.loads(line) for line in journal.read_text("utf-8").splitlines())
            if entry.get("event") == "stopped_early"
        ]
        assert events, "a retirement should be written to the journal"
        for event in events:
            assert event["gate"]
            assert event["candidate_id"]

    def test_the_shared_context_check_names_the_set_it_means(
        self, retired_run: dict[str, object]
    ) -> None:
        joined = " ".join(retired_run["checks"])
        assert "still in the run" in joined or "retired early" in joined


class TestTheSurvivorInvariant:
    def test_a_retired_survivor_is_refused_outright(self) -> None:
        """Cannot happen: every rule holds at any sample size the run can
        end at. So it raises rather than warns — a violation means a rule
        is wrong, not that a run is unusual."""

        class _Passing:
            passed = True

        with pytest.raises(pipeline.AcceptanceFailure, match="dừng sớm nhưng vẫn qua"):
            selection._refuse_a_retired_survivor(
                {"cand": object()},
                {"cand": _Passing()},  # type: ignore[dict-item]
            )

    def test_pairing_is_only_claimed_among_the_named_subset(self) -> None:
        """The check must say which set it is talking about. One that
        quietly changed what it guarantees would be worse than none."""
        rows = {
            "full": [_row("a"), _row("b")],
            "short": [_row("a")],
        }
        with pytest.raises(pipeline.AcceptanceFailure):
            pipeline.check_shared_contexts(rows)
        assert "still in the run" in pipeline.check_shared_contexts(rows, among=["full"])

    def test_everybody_retired_is_reported_as_such_not_as_an_empty_run(self) -> None:
        """Not "nobody ran anything" — everybody ran and everybody was
        retired. Saying it the other way round would report an empty run."""
        sentence = pipeline.check_shared_contexts({"a": [_row("x")], "b": [_row("x")]}, among=[])
        assert "retired early" in sentence
        assert "2 candidates" in sentence


def _row(context_id: str):  # type: ignore[no-untyped-def]
    return _episode(0).model_copy(update={"episode_context_id": context_id})
