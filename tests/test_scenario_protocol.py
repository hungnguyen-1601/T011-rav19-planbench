"""P05 — dev/held-out protocol metadata and the generalization gap.

Two properties matter more than anything else here and are tested first:

1. **A split change moves no checksum.** The split lives outside the
   scenario precisely so that re-classifying ``intersection`` tomorrow
   cannot invalidate every benchmark run on it today. If that ever stops
   holding, the whole reason the metadata is a separate file is gone.
2. **Unclassified is never dev.** A scenario nobody assigned must come
   back ``unassigned``, because defaulting it into dev is how a held-out
   set silently becomes a training set.
"""

from __future__ import annotations

import json

import pytest

from planbench_benchmark import (
    CURRICULUM_ORDER,
    build_scenario,
    protocol_version,
    scenario_protocol_metadata,
    scenario_split,
    scenarios_in_split,
)
from planbench_benchmark.generalization import (
    GAP_METRICS,
    HoldoutUse,
    build_generalization,
)
from planbench_benchmark.runner import aggregate_algorithm, run_benchmark
from planbench_benchmark.scenario_protocol import (
    ScenarioProtocolError,
    load_protocol,
    parse_protocol,
)
from planbench_benchmark.spec import (
    AlgorithmSpec,
    BenchmarkReport,
    BenchmarkSpec,
    FairnessRecord,
    RunRecord,
    _scenario_checksum,
)
from planbench_metrics import EpisodeMetrics
from planbench_schemas.episode import EpisodeStatus


def _run(
    algorithm: str,
    seed: int,
    travel_time: float,
    *,
    status: EpisodeStatus = EpisodeStatus.SUCCESS,
    efficiency: float | None = 0.9,
) -> RunRecord:
    return RunRecord(
        algorithm=algorithm,
        seed=seed,
        status=status,
        reason="",
        metrics=EpisodeMetrics(
            status=status,
            success=status is EpisodeStatus.SUCCESS,
            collision=status is EpisodeStatus.COLLISION,
            travel_time=travel_time,
            steps=int(travel_time * 10),
            trajectory_length=travel_time,
            average_speed=1.0,
            max_speed=1.2,
            smoothness=0.1,
            path_efficiency=efficiency,
        ),
        trajectory_points=2,
        episode_index=seed,
    )


def _report(
    scenario_name: str,
    split: str,
    algorithms: dict[str, list[float]],
    *,
    seeds: tuple[int, ...] = tuple(range(30)),
    protocol: str | None = "1.0.0",
    name: str = "bench",
) -> BenchmarkReport:
    """A stored report: one scenario, one split, travel times per stack."""
    spec = BenchmarkSpec(
        name=name,
        algorithms=tuple(AlgorithmSpec(id=algorithm) for algorithm in algorithms),
        seeds=seeds,
    )
    fairness = FairnessRecord(
        map_name="m",
        map_checksum="mc",
        scenario_name=scenario_name,
        scenario_checksum="sc",
        seeds=seeds,
        timeout_seconds=60.0,
        simulation_dt=0.1,
        robot_radius=0.3,
        max_linear_velocity=1.0,
        max_angular_velocity=1.5,
        lidar_num_rays=16,
        lidar_max_range=5.0,
        conditions_checksum=f"c-{scenario_name}",
    )
    runs: list[RunRecord] = []
    for algorithm, travel_times in algorithms.items():
        runs.extend(_run(algorithm, seed, value) for seed, value in enumerate(travel_times))
    aggregates = tuple(
        aggregate_algorithm(algorithm, [r for r in runs if r.algorithm == algorithm])
        for algorithm in algorithms
    )
    return BenchmarkReport(
        spec=spec,
        fairness=fairness,
        runs=tuple(runs),
        aggregates=aggregates,
        protocol_version=protocol,
        scenario_split=split,
    )


@pytest.fixture
def reclassify(tmp_path, monkeypatch):
    """Swap the protocol file for one the test writes, then restore.

    Exists so a test can actually re-classify a scenario instead of
    asserting around the shipped file. The cache is cleared on both
    sides: a stale entry would make the change invisible and the test
    pass for the wrong reason.
    """
    from planbench_benchmark import scenario_protocol as module

    def apply(scenarios: dict[str, dict], version: str = "9.9.9") -> None:
        path = tmp_path / "scenario_protocol.json"
        path.write_text(
            json.dumps({"protocol_version": version, "scenarios": scenarios}), encoding="utf-8"
        )
        monkeypatch.setattr(module, "PROTOCOL_FILE", path)
        module.load_protocol.cache_clear()

    yield apply
    module.load_protocol.cache_clear()


class TestSplitDoesNotTouchTheScenario:
    def test_scenario_schema_has_no_split_field(self) -> None:
        """The decision the whole design rests on (plan 2.1)."""
        _, scenario = build_scenario("intersection")
        assert "split" not in type(scenario).model_fields
        assert not hasattr(scenario, "split")

    def test_reclassifying_a_scenario_changes_no_checksum(self, reclassify) -> None:
        """The property the separate file exists to guarantee.

        Move ``doorway`` from dev to holdout and the scenario checksum —
        and therefore the conditions checksum of every benchmark ever run
        on it — must not move with it. Otherwise a policy decision would
        retroactively invalidate comparisons made under identical physics.
        """
        map_data, scenario = build_scenario("doorway")
        before_scenario = _scenario_checksum(scenario)
        before_conditions = FairnessRecord.build(map_data, scenario, (1, 2, 3)).conditions_checksum

        reclassify({"doorway": {"split": "dev"}})
        assert scenario_split("doorway") == "dev"
        reclassify({"doorway": {"split": "holdout", "notes": "promoted"}})
        assert scenario_split("doorway") == "holdout"

        map_after, scenario_after = build_scenario("doorway")
        assert _scenario_checksum(scenario_after) == before_scenario
        assert (
            FairnessRecord.build(map_after, scenario_after, (1, 2, 3)).conditions_checksum
            == before_conditions
        )

    def test_reclassification_applies_to_new_runs_only(self, reclassify) -> None:
        """An old report keeps the split it was produced under."""
        old = _report("doorway", "dev", {"a": [10.0] * 30}, protocol="1.0.0")
        reclassify({"doorway": {"split": "holdout"}})
        assert scenario_split("doorway") == "holdout"
        assert old.scenario_split == "dev"
        assert old.protocol_version == "1.0.0"
        assert build_generalization([old]).entries[0].dev is not None


class TestProtocolFile:
    def test_every_library_scenario_is_classified(self) -> None:
        for name in CURRICULUM_ORDER:
            assert scenario_split(name) in {"dev", "holdout"}

    def test_holdout_set_is_the_reviewed_three(self) -> None:
        assert scenarios_in_split("holdout") == (
            "bidirectional_corridor",
            "dynamic_warehouse",
            "intersection",
        )

    def test_dev_and_holdout_do_not_overlap(self) -> None:
        assert not set(scenarios_in_split("dev")) & set(scenarios_in_split("holdout"))

    def test_held_out_scenarios_state_why(self) -> None:
        """A held-out set without stated reasons is just the hard ones."""
        for name in scenarios_in_split("holdout"):
            assert scenario_protocol_metadata(name).notes

    def test_protocol_is_versioned(self) -> None:
        assert protocol_version() == load_protocol().protocol_version
        assert protocol_version()

    def test_unknown_scenario_is_unassigned_not_dev(self) -> None:
        metadata = scenario_protocol_metadata("scenario_someone_just_drew")
        assert metadata.split == "unassigned"
        assert metadata.protocol_version == protocol_version()
        assert metadata.notes is None


class TestProtocolValidation:
    def test_misspelled_split_is_rejected(self) -> None:
        with pytest.raises(ScenarioProtocolError):
            parse_protocol({"protocol_version": "1.0.0", "scenarios": {"x": {"split": "held-out"}}})

    def test_unknown_key_is_rejected(self) -> None:
        """Typos must fail, not fall through to unassigned."""
        with pytest.raises(ScenarioProtocolError):
            parse_protocol({"protocol_version": "1.0.0", "scenarios": {"x": {"splits": "holdout"}}})

    def test_missing_version_is_rejected(self) -> None:
        with pytest.raises(ScenarioProtocolError):
            parse_protocol({"scenarios": {}})

    def test_empty_version_is_rejected(self) -> None:
        with pytest.raises(ScenarioProtocolError):
            parse_protocol({"protocol_version": "", "scenarios": {}})

    def test_valid_content_parses(self) -> None:
        protocol = parse_protocol(
            {"protocol_version": "2.0.0", "scenarios": {"x": {"split": "holdout", "notes": "why"}}}
        )
        assert protocol.scenarios["x"].split == "holdout"


class TestReportSnapshot:
    def test_report_records_the_split_it_ran_under(self) -> None:
        map_data, scenario = build_scenario("open_space")
        spec = BenchmarkSpec(
            name="snapshot", algorithms=(AlgorithmSpec(id="astar+dwa"),), seeds=(1,)
        )
        report = run_benchmark(map_data, scenario, spec)
        assert report.scenario_split == "dev"
        assert report.protocol_version == protocol_version()

    def test_custom_scenario_runs_as_unassigned(self) -> None:
        """A scenario the editor could produce is not silently dev."""
        map_data, scenario = build_scenario("open_space")
        renamed = scenario.model_copy(update={"name": "my_new_scenario"})
        spec = BenchmarkSpec(name="custom", algorithms=(AlgorithmSpec(id="astar+dwa"),), seeds=(1,))
        report = run_benchmark(map_data, renamed, spec)
        assert report.scenario_split == "unassigned"

    def test_old_report_without_the_fields_still_loads(self) -> None:
        stored = _report("doorway", "dev", {"a": [10.0] * 30}).model_dump(mode="json")
        del stored["protocol_version"]
        del stored["scenario_split"]
        del stored["generalization_gap"]
        revived = BenchmarkReport.model_validate(stored)
        assert revived.protocol_version is None
        assert revived.scenario_split == "unassigned"
        assert revived.generalization_gap is None

    def test_single_scenario_report_carries_no_gap(self) -> None:
        """One scenario is one split; there is nothing to subtract."""
        assert _report("doorway", "dev", {"a": [10.0] * 30}).generalization_gap is None


class TestGeneralizationGap:
    def _dev_and_holdout(self) -> list[BenchmarkReport]:
        return [
            _report("doorway", "dev", {"a": [10.0] * 30}),
            _report("intersection", "holdout", {"a": [14.0] * 30}),
        ]

    def test_gap_is_dev_minus_holdout(self) -> None:
        summary = build_generalization(self._dev_and_holdout())
        entry = summary.entries[0]
        assert entry.gap is not None
        assert entry.gap["median_travel_time_successful"] == pytest.approx(-4.0)
        assert entry.gap["success_rate"] == pytest.approx(0.0)

    def test_gap_is_none_without_a_holdout_side(self) -> None:
        summary = build_generalization([_report("doorway", "dev", {"a": [10.0] * 30})])
        entry = summary.entries[0]
        assert entry.gap is None
        assert entry.holdout is None
        assert any("held-out" in warning for warning in entry.warnings)

    def test_gap_is_none_without_a_dev_side(self) -> None:
        summary = build_generalization([_report("intersection", "holdout", {"a": [10.0] * 30})])
        assert summary.entries[0].gap is None
        assert any("dev" in warning for warning in summary.entries[0].warnings)

    def test_unassigned_reports_are_excluded_and_counted(self) -> None:
        reports = [
            *self._dev_and_holdout(),
            _report("my_scenario", "unassigned", {"a": [1.0] * 30}),
        ]
        summary = build_generalization(reports)
        assert summary.unassigned_report_count == 1
        assert "my_scenario" not in summary.dev_scenarios + summary.holdout_scenarios
        assert any("not assigned" in warning for warning in summary.warnings)

    def test_scenarios_are_weighted_equally_not_by_report_count(self) -> None:
        """Running one dev scenario ten times must not drown out the rest."""
        reports = [
            *[_report("doorway", "dev", {"a": [10.0] * 30}, name=f"r{i}") for i in range(10)],
            _report("open_space", "dev", {"a": [20.0] * 30}),
            _report("intersection", "holdout", {"a": [15.0] * 30}),
        ]
        entry = build_generalization(reports).entries[0]
        assert entry.dev is not None
        # (10 + 20) / 2, not (10*10 + 20) / 11.
        assert entry.dev.metrics["median_travel_time_successful"] == pytest.approx(15.0)
        assert entry.dev.metric_scenario_counts["median_travel_time_successful"] == 2

    def test_repeated_runs_of_one_scenario_are_averaged_first(self) -> None:
        reports = [
            _report("doorway", "dev", {"a": [10.0] * 30}, name="r1"),
            _report("doorway", "dev", {"a": [20.0] * 30}, name="r2"),
            _report("intersection", "holdout", {"a": [15.0] * 30}),
        ]
        entry = build_generalization(reports).entries[0]
        assert entry.dev is not None
        assert entry.dev.metrics["median_travel_time_successful"] == pytest.approx(15.0)
        assert entry.dev.report_count == 2
        assert entry.dev.scenarios == ("doorway",)

    def test_metric_missing_on_one_side_is_dropped_and_disclosed(self) -> None:
        """A stack that never arrives has no median to compare."""
        failed = _report("intersection", "holdout", {"a": [0.0] * 30})
        failed = failed.model_copy(
            update={
                "aggregates": (
                    aggregate_algorithm(
                        "a",
                        [_run("a", seed, 0.0, status=EpisodeStatus.TIMEOUT) for seed in range(30)],
                    ),
                )
            }
        )
        summary = build_generalization([_report("doorway", "dev", {"a": [10.0] * 30}), failed])
        entry = summary.entries[0]
        assert entry.gap is not None
        assert "median_travel_time_successful" not in entry.gap
        assert entry.gap["success_rate"] == pytest.approx(1.0)
        assert any("median_travel_time_successful" in w for w in entry.warnings)

    def test_uneven_coverage_is_flagged(self) -> None:
        reports = [
            _report("doorway", "dev", {"a": [10.0] * 30}),
            _report("open_space", "dev", {"a": [10.0] * 30}, name="r2"),
            _report("intersection", "holdout", {"a": [14.0] * 30}),
        ]
        entry = build_generalization(reports).entries[0]
        assert any("uneven coverage" in warning for warning in entry.warnings)

    def test_thin_seed_counts_are_inherited_as_a_warning(self) -> None:
        reports = [
            _report("doorway", "dev", {"a": [10.0] * 4}, seeds=(0, 1, 2, 3)),
            _report("intersection", "holdout", {"a": [14.0] * 4}, seeds=(0, 1, 2, 3)),
        ]
        entry = build_generalization(reports).entries[0]
        assert entry.dev is not None and entry.dev.statistically_adequate is False
        assert any("too few seeds" in warning for warning in entry.warnings)

    def test_mixed_protocol_versions_are_flagged(self) -> None:
        reports = [
            _report("doorway", "dev", {"a": [10.0] * 30}, protocol="1.0.0"),
            _report("intersection", "holdout", {"a": [14.0] * 30}, protocol="2.0.0"),
        ]
        summary = build_generalization(reports)
        assert summary.protocol_versions == ("1.0.0", "2.0.0")
        assert any("protocol versions" in warning for warning in summary.warnings)

    def test_each_algorithm_gets_its_own_entry(self) -> None:
        reports = [
            _report("doorway", "dev", {"a": [10.0] * 30, "b": [12.0] * 30}),
            _report("intersection", "holdout", {"a": [14.0] * 30, "b": [13.0] * 30}),
        ]
        summary = build_generalization(reports)
        assert [entry.algorithm for entry in summary.entries] == ["a", "b"]
        assert summary.entries[0].gap is not None
        assert summary.entries[1].gap is not None

    def test_gap_metrics_declare_their_direction(self) -> None:
        """Sign alone is not readable; the UI needs to know which way is good."""
        directions = {metric.name: metric.higher_is_better for metric in GAP_METRICS}
        assert directions["success_rate"] is True
        assert directions["median_travel_time_successful"] is False


class TestHoldoutAudit:
    def test_every_holdout_run_is_recorded(self) -> None:
        summary = build_generalization(
            [
                _report("doorway", "dev", {"a": [10.0] * 30}),
                _report("intersection", "holdout", {"a": [14.0] * 30}, name="final-eval"),
            ]
        )
        assert len(summary.holdout_usage) == 1
        assert summary.holdout_usage[0].benchmark_name == "final-eval"
        assert summary.holdout_usage[0].scenario_name == "intersection"
        assert summary.holdout_usage[0].seed_count == 30

    def test_dev_runs_are_not_recorded_as_holdout_use(self) -> None:
        summary = build_generalization([_report("doorway", "dev", {"a": [10.0] * 30})])
        assert summary.holdout_usage == ()

    def test_repeated_holdout_use_is_called_out(self) -> None:
        """ "We only looked once" has to stop being sayable after twice."""
        summary = build_generalization(
            [
                _report("intersection", "holdout", {"a": [14.0] * 30}, name="run-1"),
                _report("dynamic_warehouse", "holdout", {"a": [14.0] * 30}, name="run-2"),
            ]
        )
        assert len(summary.holdout_usage) == 2
        assert any("erodes" in warning for warning in summary.warnings)

    def test_caller_supplied_audit_records_replace_derived_ones(self) -> None:
        supplied = (
            HoldoutUse(
                benchmark_id="bm-1",
                benchmark_name="final",
                scenario_name="intersection",
                algorithms=("a",),
                seed_count=30,
                finished_at="2026-08-06T00:00:00Z",
            ),
        )
        summary = build_generalization(
            [_report("intersection", "holdout", {"a": [14.0] * 30})], holdout_usage=supplied
        )
        assert summary.holdout_usage == supplied
        assert summary.holdout_usage[0].benchmark_id == "bm-1"
