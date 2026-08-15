"""Comparing an arbitrary candidate set (plan M3).

Two things are under test here and they are different in kind.

The first is the **shared chain**: after M3 the slice, the measurement
and the comparison all call one implementation. If they ever stop doing
so, two runs could disagree and nobody could say whether the difference
came from the candidates or from which script was used.

The second is what ``compare.py`` does when the field cannot be ranked.
A gate table is a *deliverable* — "who was eliminated where, after how
many runs" is the question HĐ-12 puts on the card — so fewer than two
survivors produces a report, not an error. A tool that only succeeded
when it could rank things would put pressure on every run to be
rankable, and that pressure is what produced a Decision Card claiming a
collision bound off a single episode.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import yaml
from test_vertical_slice import slice_module, write_profile

from planbench_benchmark import pipeline, selection
from planbench_schemas.task_profile import TaskProfile

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


compare = _load("compare")
measure = _load("measure")


class TestOneChainThreeEntryPoints:
    """The M3 guarantee, asserted on identity rather than on behaviour.

    A behavioural test would say "today these agree". This says "there is
    only one implementation to disagree with" — which is the property
    that survives somebody adding a special case to one script.
    """

    @pytest.mark.parametrize("name", ["score", "simulate", "check_l_ref", "check_node_counts"])
    def test_the_slice_uses_the_shared_chain(self, name: str) -> None:
        assert getattr(slice_module, name) is getattr(pipeline, name)

    @pytest.mark.parametrize("name", ["score", "check_l_ref", "check_reproducible"])
    def test_the_measurement_uses_the_shared_chain(self, name: str) -> None:
        assert getattr(measure, name) is getattr(pipeline, name)

    def test_the_card_is_assembled_by_one_step(self) -> None:
        """A1's guarantee, and the reason it was needed.

        The slice assembled its card with the sensitivity sweeps and the
        Pareto labels; ``run_comparison`` assembled one without. Two
        producers of one artifact, and the project's first Decision Card
        came out of the poorer one — carrying
        ``weight_stability_margin: null`` and ``anchor_stability: null``
        while HĐ-12 reads null as *"not measured"*.

        Asserted on identity rather than on output: a behavioural test
        says "today they agree", this says "there is only one
        implementation to disagree with".
        """
        assert slice_module.assemble_card is selection.assemble_card

    def test_the_failure_type_is_shared(self) -> None:
        """Three names for one event. A caller should not have to catch
        two exception types to survive an acceptance failure."""
        assert slice_module.SliceFailure is pipeline.AcceptanceFailure
        assert measure.MeasurementFailure is pipeline.AcceptanceFailure
        assert compare.CompareFailure is pipeline.AcceptanceFailure


class TestParsingTheCandidateSet:
    def test_a_bare_stack_takes_the_default_controller(self) -> None:
        assert compare.parse_candidates("astar+dwa,rrtstar+dwa", "dwa_coarse") == (
            ("astar+dwa", "dwa_coarse"),
            ("rrtstar+dwa", "dwa_coarse"),
        )

    def test_the_suffix_names_a_controller_per_candidate(self) -> None:
        """What makes "same stack, two controllers" expressible at all —
        the question the convex-corner stall left open."""
        assert compare.parse_candidates("astar+dwa:dwa_coarse,astar+dwa:dwa_default", "x") == (
            ("astar+dwa", "dwa_coarse"),
            ("astar+dwa", "dwa_default"),
        )

    def test_an_unknown_controller_is_refused_by_name(self) -> None:
        with pytest.raises(SystemExit, match="unknown local controller"):
            compare.parse_candidates("astar+dwa:nope,rrtstar+dwa", "dwa_coarse")

    def test_one_candidate_is_refused_and_points_at_measure(self) -> None:
        """Not a degenerate comparison — a different artifact. ΔU, its
        interval and its label do not exist for one candidate."""
        with pytest.raises(SystemExit, match="measure.py"):
            compare.parse_candidates("astar+dwa", "dwa_coarse")


class TestScopeIsDeclaredNotInferred:
    def test_two_controllers_cannot_be_called_a_global_planner_claim(self, tmp_path: Path) -> None:
        """HĐ-1.4. Inferring the scope from the set would turn this
        refusal into a rename."""
        profile = selection.load_profile(write_profile(tmp_path))
        with pytest.raises(Exception, match="identical local layer"):
            selection.build_candidates(
                profile,
                (("astar+dwa", "dwa_coarse"), ("astar+dwa", "dwa_default")),
                "global_planner_selection",
            )

    def test_the_same_pair_is_fine_as_a_local_selection(self, tmp_path: Path) -> None:
        profile = selection.load_profile(write_profile(tmp_path))
        candidates = selection.build_candidates(
            profile,
            (("astar+dwa", "dwa_coarse"), ("astar+dwa", "dwa_default")),
            "local_controller_selection",
        )
        assert len({c.candidate_id for c in candidates}) == 2


class TestOneDirectoryPerQuestion:
    """Two comparisons on one deployment are two results, not one.

    The first draft wrote every run to ``{profile}_compare``, so the
    second comparison of the day overwrote the first — two different
    questions, one directory, and the earlier answer simply gone with no
    warning, because from the filesystem's point of view a run had merely
    been repeated. Found by losing a real result.
    """

    @staticmethod
    def _named(profile: TaskProfile, specs: tuple[tuple[str, str], ...], scope: str) -> str:
        return selection.run_dir_name(
            profile.id, scope, selection.build_candidates(profile, specs, scope)
        )

    def test_two_candidate_sets_land_in_different_directories(self, tmp_path: Path) -> None:
        profile = selection.load_profile(write_profile(tmp_path))
        first = self._named(
            profile,
            (("astar+dwa", "dwa_coarse"), ("rrtstar+dwa", "dwa_coarse")),
            "global_planner_selection",
        )
        second = self._named(
            profile,
            (("astar+dwa", "dwa_coarse"), ("astar+dwa", "dwa_default")),
            "local_controller_selection",
        )
        assert first != second

    def test_the_same_question_overwrites_itself(self, tmp_path: Path) -> None:
        """Re-running one comparison should replace its own answer, not
        accumulate copies — the name is derived, never stamped with a
        clock."""
        profile = selection.load_profile(write_profile(tmp_path))
        specs = (("astar+dwa", "dwa_coarse"), ("rrtstar+dwa", "dwa_coarse"))
        assert self._named(profile, specs, "global_planner_selection") == self._named(
            profile, specs, "global_planner_selection"
        )

    def test_changing_any_candidate_changes_the_directory(self, tmp_path: Path) -> None:
        """The hash is over ``candidate_id``, which already covers the
        stack and every parameter (HĐ-1.3). So a swapped controller is a
        different question and lands somewhere else."""
        profile = selection.load_profile(write_profile(tmp_path))
        coarse = self._named(
            profile,
            (("astar+dwa", "dwa_coarse"), ("rrtstar+dwa", "dwa_coarse")),
            "global_planner_selection",
        )
        mixed = self._named(
            profile,
            (("astar+dwa", "dwa_default"), ("rrtstar+dwa", "dwa_default")),
            "global_planner_selection",
        )
        assert coarse != mixed

    def test_the_order_candidates_were_typed_in_does_not_matter(self, tmp_path: Path) -> None:
        """Same question asked twice, one with the arguments swapped. A
        directory that depended on argument order would answer it twice
        and let the two disagree."""
        profile = selection.load_profile(write_profile(tmp_path))
        forwards = self._named(
            profile,
            (("astar+dwa", "dwa_coarse"), ("rrtstar+dwa", "dwa_coarse")),
            "global_planner_selection",
        )
        backwards = self._named(
            profile,
            (("rrtstar+dwa", "dwa_coarse"), ("astar+dwa", "dwa_coarse")),
            "global_planner_selection",
        )
        assert forwards == backwards


@pytest.fixture(scope="module")
def ranked(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    """A field that can be ranked: both candidates clear every gate."""
    workspace = tmp_path_factory.mktemp("compare_ranked")
    return selection.run_comparison(
        profile_path=write_profile(workspace),
        candidate_specs=(("astar+dwa", "dwa_coarse"), ("rrtstar+dwa", "dwa_coarse")),
        scope="global_planner_selection",
        episodes=6,
        trace_root=workspace / "traces",
        run_root=workspace / "runs",
        reuse=False,
        quiet=True,
        map_base_dir=workspace,
    )


@pytest.fixture(scope="module")
def unrankable(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    """A field that cannot be: the deployment demands more clean distinct
    episodes than the run has, so G2 eliminates everybody.

    Triggered through the *deployment's declared risk* rather than by
    breaking a candidate, because that is how it happens in practice —
    ``N_min`` is a consequence of the accepted collision probability
    (HĐ-7.1), and a short run against a strict declaration is the normal
    way to end up with nothing to rank.
    """
    workspace = tmp_path_factory.mktemp("compare_unrankable")
    path = write_profile(workspace)
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    payload["id"] = "slice_fixture_strict"
    payload["constraints"]["collision_probability_max"] = 0.01  # N_min = 300
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return selection.run_comparison(
        profile_path=path,
        candidate_specs=(("astar+dwa", "dwa_coarse"), ("rrtstar+dwa", "dwa_coarse")),
        scope="global_planner_selection",
        episodes=6,
        trace_root=workspace / "traces",
        run_root=workspace / "runs",
        reuse=False,
        quiet=True,
        map_base_dir=workspace,
    )


class TestARankableField:
    def test_it_produces_a_card(self, ranked: dict[str, object]) -> None:
        assert ranked["decision_card"] is not None
        assert ranked["decision_card"]["recommended"]["candidate_id"]  # type: ignore[index]

    def test_the_card_carries_its_sensitivity(self, ranked: dict[str, object]) -> None:
        """HĐ-11.5's two caveats, and the bug this test exists for.

        Both sweeps re-score metrics already in memory and never touch
        the simulator, so they cost seconds on a run that cost hours —
        there was never a budget reason to omit them. But
        ``run_comparison`` did omit them, and the omission was invisible
        because null is a legal value: a card with
        ``weight_stability_margin: null`` validates against the schema
        and reads, to anyone not looking for it, like a card whose
        recommendation simply never flips.

        ``weight_stability_margin`` answers "how far can the weights move
        before this recommendation changes" — the single question that
        separates a finding from an artefact of the weighting.
        """
        card = ranked["decision_card"]
        evidence = card["evidence"]  # type: ignore[index]
        assert evidence["weight_stability_margin"] is not None
        assert evidence["anchor_stability"] is not None

    def test_the_card_carries_a_pareto_verdict(self, ranked: dict[str, object]) -> None:
        """HĐ-10.1: label, never delete. A card without a Pareto verdict
        cannot say whether its winner is only winning on the weights."""
        assert ranked["decision_card"]["pareto_label"] is not None  # type: ignore[index]

    def test_the_delta_u_check_only_runs_when_there_is_a_comparison(
        self, ranked: dict[str, object]
    ) -> None:
        assert any("ΔU median" in line for line in ranked["checks"])  # type: ignore[union-attr]

    def test_every_candidate_is_reported_including_the_loser(
        self, ranked: dict[str, object]
    ) -> None:
        """HĐ-10.1: label, never delete. A candidate missing from the
        report is a candidate nobody can check the reasoning about."""
        assert len(ranked["candidates"]) == 2  # type: ignore[arg-type]

    def test_the_card_and_manifest_land_beside_the_report(
        self, tmp_path_factory: pytest.TempPathFactory, ranked: dict[str, object]
    ) -> None:
        base = Path(tmp_path_factory.getbasetemp())
        written = {p.name for p in base.rglob("compare_ranked*/runs/**/*.json")}
        assert {"comparison_report.json", "decision_card.json", "manifest.json"} <= written


class TestAFieldThatCannotBeRanked:
    def test_it_still_writes_a_report(self, unrankable: dict[str, object]) -> None:
        assert unrankable["artifact"] == "comparison_report"

    def test_there_is_no_card_and_it_says_why(self, unrankable: dict[str, object]) -> None:
        assert unrankable["decision_card"] is None
        why = unrankable["why_no_card"]
        assert "KẾT QUẢ" in why  # type: ignore[operator]
        assert "ĐĂNG KÝ MỘT CANDIDATE MỚI" in why  # type: ignore[operator]

    def test_the_gate_table_still_says_who_was_eliminated_where(
        self, unrankable: dict[str, object]
    ) -> None:
        """The deliverable of this branch. Without it the run would have
        produced nothing, and "nothing" is not what happened — two stacks
        were measured and eliminated at a named gate."""
        for entry in unrankable["candidates"]:  # type: ignore[union-attr]
            assert entry["cleared_gates"] is False
            assert entry["blocking_gates"]
            assert entry["gates"]["G2"]["n_min"] == 300
            assert entry["n_distinct_episodes"] <= 6

    def test_the_measurement_checks_still_ran(self, unrankable: dict[str, object]) -> None:
        """Not being able to rank is not a reason to stop checking that
        the measurement itself was sound."""
        joined = " ".join(unrankable["checks"])  # type: ignore[arg-type]
        assert "same 6 episode contexts" in joined
        assert "L_ref" in joined
