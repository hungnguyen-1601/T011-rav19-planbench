"""Measuring one candidate (plan F1).

``test_vertical_slice.py`` runs the comparison chain. This runs the other
one — the chain that stops before the comparison, because with a single
candidate there is nothing to compare and every field a Decision Card
carries would be an invention.

That distinction is what most of these tests are about. A card for one
candidate would fill in ΔU, a confidence interval and a label, look
entirely ordinary, and state something the data cannot support. That is
the exact failure the hundred-episode warehouse run produced, so the
platform has to make it structurally impossible rather than discouraged.
"""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path

import pytest
from test_vertical_slice import write_profile

from planbench_benchmark.candidates import LOCAL_CONTROLLER_CONFIGS

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_measure_module():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("measure", REPO_ROOT / "scripts" / "measure.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


measure = _load_measure_module()

#: Words that turn a measurement into a verdict. A single utility has no
#: scale of its own, so any of these next to one is the report claiming
#: something it cannot know. "an toàn" and "TCO" are already banned
#: contract-wide (§17 ban 10); the rest are specific to this artifact.
VERDICT_WORDS = (
    "khuyến nghị",
    "nên dùng",
    "tốt nhất",
    "thắng",
    "vượt trội",
    "an toàn",
    "TCO",
)


@pytest.fixture(scope="module")
def measure_workspace(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Where this module's run put its files.

    Held separately from the result so the tests that read artefacts off
    disk address *this* directory. Globbing pytest's shared base temp
    instead would mean "the first matching directory any module created",
    which is fine until a second module creates one — and that is exactly
    how adding this file broke a rebuild test in ``test_vertical_slice``.
    """
    return tmp_path_factory.mktemp("measure")


@pytest.fixture(scope="module")
def measurement(measure_workspace: Path) -> dict[str, object]:
    """One real six-episode run; every test below reads the same output."""
    workspace = measure_workspace
    profile_path = write_profile(workspace)
    return measure.run_measurement(
        profile_path=profile_path,
        stack="rrtstar+dwa",
        local="dwa_coarse",
        episodes=6,
        trace_root=workspace / "traces",
        run_root=workspace / "runs",
        reuse=False,
        quiet=True,
        map_base_dir=workspace,
    )


class TestItMeasuresWithoutComparing:
    def test_the_chain_runs_end_to_end(self, measurement: dict[str, object]) -> None:
        """Episodes → traces → HĐ-6 metrics → gates → objectives, on real
        data. A broken link would not return."""
        assert measurement["artifact"] == "measurement_report"
        assert measurement["sample"]["n_episodes"] == 6  # type: ignore[index]
        assert len(measurement["metrics"]["per_episode"]) == 6  # type: ignore[index]

    def test_it_is_not_a_decision_card(self, measurement: dict[str, object]) -> None:
        """No ΔU, no interval, no label, no alternative — none of them
        exist for one candidate, and a field with a plausible value in it
        is worse than a missing one."""
        for absent in ("recommended", "evidence", "pareto_label", "alternative", "status"):
            assert absent not in measurement

    def test_it_says_so_in_words(self, measurement: dict[str, object]) -> None:
        """Whoever opens the file next may not have read this test."""
        assert "không phải một phép SO" in measurement["note"]  # type: ignore[index]

    def test_no_verdict_vocabulary_anywhere(self, measurement: dict[str, object]) -> None:
        """Checked over the serialised whole rather than field by field,
        because the point is that no path through the report reaches a
        reader as a recommendation."""
        import json

        text = json.dumps(measurement, ensure_ascii=False)
        # The disclaimer is allowed to name what the report is not.
        text = text.replace(measure.NOT_A_RECOMMENDATION, "")
        for word in VERDICT_WORDS:
            assert word not in text, word


class TestWhatTheReportCarries:
    def test_every_contracted_metric_is_present(self, measurement: dict[str, object]) -> None:
        """HĐ-6's table is what "the important numbers" means; leaving one
        out would have the next phase reach past this artifact for it."""
        row = measurement["metrics"]["per_episode"][0]  # type: ignore[index]
        for field in (
            "success",
            "collision_count",
            "path_length_m",
            "l_ref_m",
            "path_efficiency",
            "travel_time_s",
            "time_efficiency",
            "min_clearance",
            "near_miss_rate",
            "p99_latency_ms",
            "memory_estimate_mb",
        ):
            assert field in row, field

    def test_both_episode_counts_are_reported(self, measurement: dict[str, object]) -> None:
        """The bound's denominator and the row count. Printing one hides
        a replayed set; printing the other is what claimed a 3.0% bound
        off a single episode."""
        sample = measurement["sample"]
        assert "n_episodes" in sample and "n_distinct_episodes" in sample  # type: ignore[operator]

    def test_all_six_gates_with_their_evidence(self, measurement: dict[str, object]) -> None:
        for gate in ("G1", "G2", "G3", "G4", "G5", "G6"):
            assert gate in measurement["gates"], gate  # type: ignore[operator]

    def test_the_measuring_machine_is_recorded(self, measurement: dict[str, object]) -> None:
        """G4 reads wall-clock latency, so the CPU allocation is part of
        the measurement, not trivia about it (HĐ-7.4)."""
        host = measurement["measurement_environment"]["benchmark_host"]  # type: ignore[index]
        assert host["cpu"]
        assert "cpu_affinity" in host and "logical_cores" in host

    def test_utility_is_present_and_unranked(self, measurement: dict[str, object]) -> None:
        """A real property of one candidate on one anchor scale — kept so
        F4 need not change the format to start comparing, and kept
        without any sentence that reads it as a position in a field."""
        assert 0.0 <= measurement["objectives"]["set_level"]["decision_utility"] <= 1.0  # type: ignore[index]

    def test_the_report_lands_on_disk(
        self, measure_workspace: Path, measurement: dict[str, object]
    ) -> None:
        written = list(measure_workspace.rglob("measurement_report.json"))
        assert written


class TestAcceptanceChecksAreReal:
    def test_l_ref_check_catches_an_impossible_reference(self) -> None:
        """A reference longer than the driven route means one of the two
        is wrong, and both feed ``path_efficiency``."""

        class Row:
            success = True
            episode_context_id = "ctx"
            l_ref_m = 10.0
            path_length_m = 5.0

        with pytest.raises(measure.MeasurementFailure, match="exceeds the driven path"):
            measure.check_l_ref([Row()], 0.2)

    def test_l_ref_check_allows_the_tolerance_ball(self) -> None:
        """``L_ref`` measures to the goal point; an episode succeeds on
        entering the ball around it, so a legitimate drive is shorter by
        up to its radius (HĐ-15.1(5) as tightened at 2.2.1)."""

        class Row:
            success = True
            episode_context_id = "ctx"
            l_ref_m = 5.15
            path_length_m = 5.0

        measure.check_l_ref([Row()], 0.2)

    def test_reproducibility_check_is_to_six_decimals(self) -> None:
        measure.check_reproducible(0.8453971, 0.8453969)
        with pytest.raises(measure.MeasurementFailure):
            measure.check_reproducible(0.845397, 0.845400)


class TestTheCandidateIsCheckedBeforeItRuns:
    def test_a_slow_controller_is_refused(self, tmp_path: Path) -> None:
        """G4 times one controller call and never counts them, so a
        controller slower than the deployment's T_cycle passes the
        real-time gate while missing deadlines. Caught here rather than
        after the episodes."""
        profile_path = write_profile(tmp_path)
        profile = measure.load_profile(profile_path)
        strict = profile.model_copy(
            update={"robot": profile.robot.model_copy(update={"control_period": 0.01})}
        )
        with pytest.raises(Exception, match="closes its control loop"):
            measure.build_candidate(strict, "rrtstar+dwa", "dwa_coarse")

    def test_an_unknown_local_configuration_is_refused_by_name(self, tmp_path: Path) -> None:
        profile = measure.load_profile(write_profile(tmp_path))
        with pytest.raises(SystemExit, match="unknown local controller"):
            measure.build_candidate(profile, "rrtstar+dwa", "dwa_nonexistent")

    def test_the_sampling_choice_reaches_the_candidate_id(self, tmp_path: Path) -> None:
        """``dwa_coarse`` was picked for the wall clock, so it has to be
        a declared candidate rather than an invisible constant."""
        profile = measure.load_profile(write_profile(tmp_path))
        coarse = measure.build_candidate(profile, "rrtstar+dwa", "dwa_coarse")
        default = measure.build_candidate(profile, "rrtstar+dwa", "dwa_default")
        assert coarse.candidate_id != default.candidate_id
        assert (
            coarse.layer_params("dwa")["velocity_samples"]
            == (LOCAL_CONTROLLER_CONFIGS["dwa_coarse"]["velocity_samples"])
        )


class TestAFailingGateIsAResult:
    def test_the_report_is_written_whatever_the_gates_say(
        self, measurement: dict[str, object]
    ) -> None:
        """Nothing here requires a gate to pass. The reference hall has no
        moving traffic on purpose: a deterministic stack replays one
        episode per seed, G2 finds an effective sample size below N_min
        and refuses to bound the collision probability. Treating that red
        as a thing to fix by adding traffic until the numbers look usable
        is the loop this plan exists to break.
        """
        assert measurement["gates"]["G2"]["result"] in {"pass", "fail"}  # type: ignore[index]
        assert measurement["artifact"] == "measurement_report"


class TestProvenance:
    def test_it_records_what_it_was(self, measurement: dict[str, object]) -> None:
        """Anchor version and git sha, for the same reason a manifest
        carries them: a number without the scale it was computed on
        cannot be compared with a later one."""
        identity = measurement["identity"]
        assert identity["anchor_config_version"]  # type: ignore[index]
        assert identity["candidate_id"]  # type: ignore[index]
        assert identity["local_controller_config"] == "dwa_coarse"  # type: ignore[index]
        assert datetime.fromisoformat(identity["created_at"]).tzinfo is not None  # type: ignore[index,arg-type]
        assert datetime.fromisoformat(identity["created_at"]) <= datetime.now(UTC)  # type: ignore[index,arg-type]
