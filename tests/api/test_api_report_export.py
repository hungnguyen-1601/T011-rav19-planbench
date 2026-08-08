"""API tests: the Markdown report export (F09).

What has to hold is not "a file comes back". The export exists so a
result can be checked by somebody outside the platform, months later,
which means three things have to survive the trip: the provenance needed
to reproduce the run, every caveat attached to the number it qualifies,
and the table structure itself when a user-supplied name contains a pipe.

A benchmark that has not run is refused rather than exported: a document
of blanks still reads like a result.
"""

from __future__ import annotations

from dataclasses import replace

from fastapi.testclient import TestClient

from planbench_api.report_markdown import _cell, render_report_markdown, report_filename
from planbench_api.repositories import StoredBenchmark
from planbench_benchmark import BenchmarkSpec


def create_benchmark(
    client: TestClient, created_map: dict, created_scenario: dict, headers: dict, **kw
) -> dict:
    payload = {
        "name": "export-benchmark",
        "map_id": created_map["id"],
        "scenario_id": created_scenario["id"],
        "algorithms": [{"id": "astar+dwa"}],
        "seeds": [1, 2],
        **kw,
    }
    response = client.post("/api/v1/benchmarks", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def run_benchmark(client: TestClient, created_map, created_scenario, headers, **kw) -> dict:
    benchmark = create_benchmark(client, created_map, created_scenario, headers, **kw)
    response = client.post(f"/api/v1/benchmarks/{benchmark['id']}/run", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["benchmark"]


def export(client: TestClient, benchmark_id: str, headers: dict):
    return client.get(f"/api/v1/benchmarks/{benchmark_id}/report.md", headers=headers)


class TestDelivery:
    def test_served_as_a_named_markdown_download(
        self, client: TestClient, created_map, created_scenario, alice_headers
    ) -> None:
        benchmark = run_benchmark(client, created_map, created_scenario, alice_headers)
        response = export(client, benchmark["id"], alice_headers)
        assert response.status_code == 200, response.text
        assert response.headers["content-type"].startswith("text/markdown")
        disposition = response.headers["content-disposition"]
        assert disposition.startswith("attachment;")
        assert benchmark["id"] in disposition
        assert disposition.endswith('.md"')

    def test_requires_a_session(
        self, client: TestClient, created_map, created_scenario, alice_headers
    ) -> None:
        benchmark = run_benchmark(client, created_map, created_scenario, alice_headers)
        assert export(client, benchmark["id"], {}).status_code == 401

    def test_readable_by_somebody_who_does_not_own_it(
        self, client: TestClient, created_map, created_scenario, alice_headers, bob_headers
    ) -> None:
        # Reading is deliberately wide across this API: a shared
        # leaderboard only means something if the runs behind it can be
        # inspected. Acting is what ownership gates.
        benchmark = run_benchmark(client, created_map, created_scenario, alice_headers)
        assert export(client, benchmark["id"], bob_headers).status_code == 200

    def test_unknown_benchmark_is_a_404(self, client: TestClient, alice_headers) -> None:
        assert export(client, "no-such-benchmark", alice_headers).status_code == 404

    def test_a_benchmark_that_has_not_run_is_refused(
        self, client: TestClient, created_map, created_scenario, alice_headers
    ) -> None:
        benchmark = create_benchmark(client, created_map, created_scenario, alice_headers)
        response = export(client, benchmark["id"], alice_headers)
        assert response.status_code == 409
        body = response.json()
        assert body["error"]["code"] == "invalid_state"
        # The message has to say what to do about it, not just that it failed.
        assert "run it" in body["error"]["message"]


class TestProvenance:
    def test_carries_everything_needed_to_reproduce_the_run(
        self, client: TestClient, created_map, created_scenario, alice_headers
    ) -> None:
        benchmark = run_benchmark(client, created_map, created_scenario, alice_headers)
        results = client.get(
            f"/api/v1/benchmarks/{benchmark['id']}/results", headers=alice_headers
        ).json()
        report = results["report"]
        document = export(client, benchmark["id"], alice_headers).text

        assert benchmark["id"] in document
        assert report["fairness"]["conditions_checksum"] in document
        assert report["fairness"]["map_checksum"] in document
        assert report["fairness"]["scenario_checksum"] in document
        assert "Git SHA" in document
        assert "Seeds" in document and "1, 2" in document
        assert "Protocol version (P05)" in document
        assert "Scenario split (P05)" in document
        assert "Scenario difficulty (P03)" in document
        assert "astar+dwa" in document

    def test_states_the_observation_classes(
        self, client: TestClient, created_map, created_scenario, alice_headers
    ) -> None:
        benchmark = run_benchmark(client, created_map, created_scenario, alice_headers)
        document = export(client, benchmark["id"], alice_headers).text
        assert "Global observation" in document
        assert "Local observation" in document
        assert "full_static_map" in document
        assert "lidar_only" in document

    def test_a_report_without_replanning_claims_no_upgrade(
        self, client: TestClient, created_map, created_scenario, alice_headers
    ) -> None:
        benchmark = run_benchmark(client, created_map, created_scenario, alice_headers)
        document = export(client, benchmark["id"], alice_headers).text
        assert "higher than the registry" not in document
        assert "full_static_map+human_states" not in document

    def test_replanning_upgrades_the_global_class_and_says_why(
        self, client: TestClient, created_map, created_scenario, alice_headers
    ) -> None:
        """The label alone would look like a registry bug to a reader.

        Anyone checking this report can look ``astar+dwa`` up and find
        ``full_static_map``. The report has to explain the discrepancy in
        the same section, or the honest label reads as a mistake.
        """
        benchmark = run_benchmark(
            client,
            created_map,
            created_scenario,
            alice_headers,
            replanning={"enabled": True, "max_replans": 2},
        )
        document = export(client, benchmark["id"], alice_headers).text
        assert "full_static_map+human_states" in document
        assert "higher than the registry" in document
        assert "ground-truth positions" in document
        # The controller is untouched, and the report must not imply it was.
        assert "lidar_only" in document


class TestNumbers:
    def test_quotes_medians_with_their_spread_and_interval(
        self, client: TestClient, created_map, created_scenario, alice_headers
    ) -> None:
        benchmark = run_benchmark(client, created_map, created_scenario, alice_headers)
        document = export(client, benchmark["id"], alice_headers).text
        assert "| Stack | Median | IQR | CI95 |" in document
        assert "Travel time (successful episodes)" in document
        assert "Path efficiency (successful episodes)" in document
        assert "Smoothness (successful episodes)" in document
        assert "CI95" in document

    def test_lists_every_run(
        self, client: TestClient, created_map, created_scenario, alice_headers
    ) -> None:
        benchmark = run_benchmark(client, created_map, created_scenario, alice_headers)
        document = export(client, benchmark["id"], alice_headers).text
        runs_section = document.split("## Runs", 1)[1]
        # One row per algorithm per seed, plus the two header lines.
        rows = [line for line in runs_section.splitlines() if line.startswith("| ")]
        assert len(rows) == 2 + 2

    def test_a_pairwise_test_never_appears_without_its_seed_count(
        self, client: TestClient, created_map, created_scenario, alice_headers
    ) -> None:
        benchmark = run_benchmark(
            client,
            created_map,
            created_scenario,
            alice_headers,
            algorithms=[{"id": "astar+dwa"}, {"id": "rrtstar+dwa"}],
        )
        document = export(client, benchmark["id"], alice_headers).text
        header = next(line for line in document.splitlines() if line.startswith("| Pair |"))
        assert "Paired seeds" in header
        assert "p-value" in header
        assert "Effect size" in header

    def test_a_single_algorithm_says_no_test_was_run(
        self, client: TestClient, created_map, created_scenario, alice_headers
    ) -> None:
        benchmark = run_benchmark(client, created_map, created_scenario, alice_headers)
        document = export(client, benchmark["id"], alice_headers).text
        assert "No head-to-head test was run" in document


class TestCaveats:
    def test_a_small_benchmark_says_so(
        self, client: TestClient, created_map, created_scenario, alice_headers
    ) -> None:
        benchmark = run_benchmark(client, created_map, created_scenario, alice_headers)
        document = export(client, benchmark["id"], alice_headers).text
        limitations = document.split("## Known limitations", 1)[1]
        assert "2 seed(s)" in limitations

    def test_an_unaccepted_result_is_flagged_as_unaccepted(
        self, client: TestClient, created_map, created_scenario, alice_headers
    ) -> None:
        benchmark = run_benchmark(client, created_map, created_scenario, alice_headers)
        document = export(client, benchmark["id"], alice_headers).text
        assert "Only accepted results reach the leaderboard" in document

    def test_the_gap_is_absent_rather_than_zero(
        self, client: TestClient, created_map, created_scenario, alice_headers
    ) -> None:
        benchmark = run_benchmark(client, created_map, created_scenario, alice_headers)
        document = export(client, benchmark["id"], alice_headers).text
        gap = document.split("## Generalization gap (P05)", 1)[1].split("## Runs", 1)[0]
        assert "not computable" in gap
        assert "not the same as a" in gap


class TestMissingValues:
    def test_an_uncomputed_number_renders_as_a_dash_not_a_zero(
        self, app, client: TestClient, created_map, created_scenario, alice_headers
    ) -> None:
        # The distribution fields are all optional: a stack that never
        # reached the goal has no median travel time, and reports stored
        # before P04 have none of them. Rendering those as 0 would turn
        # "not computed" into "instant".
        benchmark = run_benchmark(client, created_map, created_scenario, alice_headers)
        stored = app.state.repos.benchmarks.get(benchmark["id"])
        blank_fields = dict.fromkeys(
            (
                "median_travel_time_successful",
                "iqr_travel_time_successful",
                "ci95_travel_time_successful",
                "ci95_success_rate",
                "worst_min_clearance",
                "mean_local_planning_latency",
                "global_observation_class",
                "local_observation_class",
                "requires_global_path",
            )
        )
        blanked = stored.report.model_copy(
            update={
                "aggregates": tuple(
                    # Renamed to a stack the registry does not know, so
                    # the blanked snapshot cannot be recovered from it.
                    # That fallback is deliberate and is what makes the
                    # *unknown* path rare — this is the case that hits it.
                    aggregate.model_copy(update={"algorithm": "retired+stack", **blank_fields})
                    for aggregate in stored.report.aggregates
                )
            }
        )
        document = render_report_markdown(replace(stored, report=blanked))
        assert "—" in document
        assert "| 0.000 |" not in document
        # And the missing declaration is called out rather than assumed.
        assert "No observation class is recorded" in document

    def test_names_the_calibration_the_difficulty_came_from(
        self, client: TestClient, created_map, created_scenario, alice_headers
    ) -> None:
        benchmark = run_benchmark(client, created_map, created_scenario, alice_headers)
        document = export(client, benchmark["id"], alice_headers).text
        # The scenario here is created in the test, so it is uncalibrated;
        # what must still appear is which calibration was in force, so a
        # reader can tell "not measured" from "no scale exists".
        assert "calibration in force" in document


class TestMarkdownIntegrity:
    def test_a_pipe_in_a_name_cannot_split_a_row(
        self, client: TestClient, created_map, created_scenario, alice_headers
    ) -> None:
        benchmark = run_benchmark(
            client,
            created_map,
            created_scenario,
            alice_headers,
            name="evil | name",
        )
        document = export(client, benchmark["id"], alice_headers).text
        assert "evil \\| name" in document
        # Every table row keeps the column count its header declared.
        for block in _table_blocks(document):
            widths = {line.count("|") - line.count("\\|") for line in block}
            assert len(widths) == 1, block

    def test_a_newline_in_a_name_cannot_end_a_row(self) -> None:
        assert _cell("two\nlines") == "two lines"

    def test_the_filename_is_safe_and_still_identifies_the_run(self) -> None:
        stored = StoredBenchmark(
            id="abc123",
            spec=BenchmarkSpec(
                name='../../etc/passwd "quoted"', algorithms=({"id": "a"},), seeds=(1,)
            ),
            map_id="m",
            scenario_id="s",
            created_by="alice",
            created_at="2026-08-07T00:00:00Z",
        )
        name = report_filename(stored)
        assert name.endswith("-abc123.md")
        assert "/" not in name and ".." not in name and '"' not in name

    def test_an_unnamed_benchmark_still_gets_a_filename(self) -> None:
        stored = StoredBenchmark(
            id="abc123",
            spec=BenchmarkSpec(name="!!!", algorithms=({"id": "a"},), seeds=(1,)),
            map_id="m",
            scenario_id="s",
            created_by="alice",
            created_at="2026-08-07T00:00:00Z",
        )
        assert report_filename(stored) == "benchmark-abc123.md"


def _table_blocks(document: str) -> list[list[str]]:
    """Every contiguous run of table rows in the document."""
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in document.splitlines():
        if line.startswith("| "):
            current.append(line)
        elif current:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)
    return blocks
