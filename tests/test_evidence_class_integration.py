"""H9A: the wiring, not the units — the half that let a bug through.

The first H9A test file passed 16/16 while ``evidence_class`` never
reached the recorder: ``simulate()`` accepted the argument, the address
had a namespace for it, and the one line that routed an episode into
that namespace was missing. Every test called a component directly —
``TraceLocator.load``, ``find_traces``, ``locator.usable`` — so every
test agreed with a system that did not connect.

So this file exercises the **paths a run actually takes**: a sweep
writes through ``simulate`` → ``run_contract_episode`` → the recorder; a
reuse decision goes through ``simulate(reuse=True)``; a score goes
through ``score``. A guard nobody reaches is not a guard, and a unit
test is exactly the instrument that cannot tell the difference.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from task_profile_fakes import CONSTRAINTS, make_profile

from planbench_benchmark import pipeline
from planbench_benchmark.candidates import LOCAL_CONTROLLER_CONFIGS, candidate_from_stack
from planbench_benchmark.contexts import build_evaluation_contexts
from planbench_benchmark.episode import run_contract_episode
from planbench_benchmark.task_map import load_task_map
from planbench_explanation.sidecar_writer import read_sidecar, snapshot_for
from planbench_simulator.trace import RESEARCH_USE, TraceUseRefused, read_trace_metadata

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def deployment():
    """The profile **with its own map**, and a short episode budget.

    An earlier draft paired this profile with an unrelated map, so every
    episode ended immediately as ``no_path`` — the tests passed while
    exercising a recorder that never recorded a driven episode. A fixture
    whose two halves disagree is a test agreeing with itself.
    """
    profile = make_profile(constraints={**CONSTRAINTS, "episode_timeout_s": 8})
    map_data = load_task_map(profile, base_dir=REPO_ROOT)
    contexts = build_evaluation_contexts(profile, seed_count=1)
    candidate = candidate_from_stack(
        "astar+dwa", params=dict(LOCAL_CONTROLLER_CONFIGS["dwa_coarse"])
    )
    return profile, map_data, contexts, candidate


class TestTheWriterIsToldWhatItIsRecording:
    """The bug this file exists for. ``simulate`` knew; the recorder did
    not; the namespace was separated and nothing was routed into it."""

    def test_an_episode_lands_in_the_class_it_was_run_as(self, tmp_path: Path, deployment) -> None:
        profile, map_data, contexts, candidate = deployment
        path, _ = run_contract_episode(
            candidate, profile, contexts[0], map_data, root=tmp_path, evidence_class="oracle"
        )
        assert path.parts[-4] == "oracle"
        assert read_trace_metadata(path).evidence_class == "oracle"

    def test_a_sweep_run_as_oracle_writes_into_the_oracle_namespace(
        self, tmp_path: Path, deployment
    ) -> None:
        """Through ``simulate``, the way a run reaches the recorder."""
        profile, map_data, contexts, candidate = deployment
        pipeline.simulate(
            [candidate],
            profile,
            contexts,
            map_data,
            tmp_path,
            evidence_class="oracle",
            use=RESEARCH_USE,
            reuse=False,
            say=lambda _message: None,
        )
        assert list(tmp_path.iterdir()) == [tmp_path / "oracle"]

    def test_a_default_sweep_still_writes_production(self, tmp_path: Path, deployment) -> None:
        profile, map_data, contexts, candidate = deployment
        pipeline.simulate(
            [candidate],
            profile,
            contexts,
            map_data,
            tmp_path,
            reuse=False,
            say=lambda _message: None,
        )
        assert list(tmp_path.iterdir()) == [tmp_path / "production"]


class TestTheClassesDoNotSeeEachOther:
    def test_a_production_sweep_does_not_reuse_an_oracle_episode(
        self, tmp_path: Path, deployment
    ) -> None:
        """Through ``simulate(reuse=True)`` — the decision an operator
        makes, not the predicate underneath it."""
        profile, map_data, contexts, candidate = deployment
        pipeline.simulate(
            [candidate],
            profile,
            contexts,
            map_data,
            tmp_path,
            evidence_class="oracle",
            use=RESEARCH_USE,
            reuse=False,
            say=lambda _message: None,
        )
        lines: list[str] = []
        pipeline.simulate(
            [candidate],
            profile,
            contexts,
            map_data,
            tmp_path,
            reuse=True,
            say=lines.append,
        )
        # It simulated rather than skipping: an oracle trace is not this
        # run's evidence, whatever its ids say.
        assert (tmp_path / "production").is_dir()
        assert any("astar+dwa" in line for line in lines)

    def test_a_production_sweep_does_reuse_its_own_episode(
        self, tmp_path: Path, deployment
    ) -> None:
        """The other direction, so the refusal above is not simply a
        reuse path that never fires."""
        profile, map_data, contexts, candidate = deployment
        args = ([candidate], profile, contexts, map_data, tmp_path)
        pipeline.simulate(*args, reuse=False, say=lambda _message: None)
        lines: list[str] = []
        pipeline.simulate(*args, reuse=True, say=lines.append)
        assert not any("astar+dwa" in line for line in lines)

    def test_scoring_a_production_run_refuses_an_oracle_trace(
        self, tmp_path: Path, deployment
    ) -> None:
        """Through ``score`` — what a report is built from."""
        profile, map_data, contexts, candidate = deployment
        pipeline.simulate(
            [candidate],
            profile,
            contexts,
            map_data,
            tmp_path,
            evidence_class="oracle",
            use=RESEARCH_USE,
            reuse=False,
            say=lambda _message: None,
        )
        with pytest.raises((TraceUseRefused, FileNotFoundError, OSError)):
            pipeline.score(candidate, profile, contexts, map_data, tmp_path)

    def test_the_research_lane_can_score_its_own_run(self, tmp_path: Path, deployment) -> None:
        profile, map_data, contexts, candidate = deployment
        pipeline.simulate(
            [candidate],
            profile,
            contexts,
            map_data,
            tmp_path,
            evidence_class="oracle",
            use=RESEARCH_USE,
            reuse=False,
            say=lambda _message: None,
        )
        metrics, _ = pipeline.score(
            candidate,
            profile,
            contexts,
            map_data,
            tmp_path,
            evidence_class="oracle",
            use=RESEARCH_USE,
        )
        assert len(metrics) == len(contexts)


# --------------------------------------------------------------------------
# The scoring pipeline actually writes one
# --------------------------------------------------------------------------


class TestTheSweepRecordsPlanningInputs:
    """The blocker E6b was really waiting on.

    ``run_stack`` took a recorder from the day E4.5 landed and nothing in
    the scoring pipeline passed one, so no run produced a sidecar — the
    writer existed and the data did not.
    """

    def test_an_episode_writes_its_sidecar_beside_its_trace(
        self, tmp_path: Path, deployment
    ) -> None:
        profile, map_data, contexts, candidate = deployment
        trace, run = run_contract_episode(candidate, profile, contexts[0], map_data, root=tmp_path)
        sidecar = trace.with_suffix(".planning_inputs.jsonl")
        assert sidecar.exists()

        header, records = read_sidecar(sidecar)
        assert header.candidate_id == candidate.candidate_id
        assert header.execution_environment_ref.startswith("git:")
        assert len(records) == run.replan_attempts + 1

    def test_the_sidecar_shares_the_traces_class_and_conditions(
        self, tmp_path: Path, deployment
    ) -> None:
        """One address, so an oracle run cannot overwrite a production one.

        The separation H9A added to the trace path is the separation the
        sidecar needs, and filing it anywhere else would mean deriving
        that rule a second time.
        """
        profile, map_data, contexts, candidate = deployment
        trace, _ = run_contract_episode(
            candidate, profile, contexts[0], map_data, root=tmp_path, evidence_class="oracle"
        )
        sidecar = trace.with_suffix(".planning_inputs.jsonl")
        assert sidecar.parent == trace.parent
        assert sidecar.parts[-4] == "oracle"

    def test_every_record_resolves_to_a_snapshot_a_replay_can_load(
        self, tmp_path: Path, deployment
    ) -> None:
        profile, map_data, contexts, candidate = deployment
        trace, _ = run_contract_episode(candidate, profile, contexts[0], map_data, root=tmp_path)
        sidecar = trace.with_suffix(".planning_inputs.jsonl")
        _header, records = read_sidecar(sidecar)

        for record in records:
            snapshot = snapshot_for(sidecar, record)
            assert snapshot.planner_name == "astar"
            assert len(snapshot.grid.cells) == snapshot.grid.width * snapshot.grid.height

    def test_the_grid_is_stored_encoded_rather_than_cell_by_cell(
        self, tmp_path: Path, deployment
    ) -> None:
        """The real map is 800x500; a JSON array of it is a megabyte an attempt.

        Run-length encoded it is about twenty kilobytes, and a recording
        feature that costs more disk than the traces beside it is a
        recording feature somebody turns off.
        """
        profile, map_data, contexts, candidate = deployment
        trace, _ = run_contract_episode(candidate, profile, contexts[0], map_data, root=tmp_path)
        sidecar = trace.with_suffix(".planning_inputs.jsonl")
        _header, records = read_sidecar(sidecar)
        snapshot = snapshot_for(sidecar, records[0])

        cells = len(snapshot.grid.cells)
        assert cells > 100
        assert len(snapshot.grid.cells_rle) < cells

    def test_a_run_can_decline_to_record_them(self, tmp_path: Path, deployment) -> None:
        """For the diagnostic scripts. Not a performance dial."""
        profile, map_data, contexts, candidate = deployment
        trace, _ = run_contract_episode(
            candidate,
            profile,
            contexts[0],
            map_data,
            root=tmp_path,
            record_planning_inputs=False,
        )
        assert not trace.with_suffix(".planning_inputs.jsonl").exists()
