"""API tests for P05: split metadata, held-out audit, generalization gap.

The endpoints exist so a reader can tell which numbers came from
scenarios the stacks were developed against and which came from
scenarios kept aside. These tests check the API never blurs that line:
the split travels with the published result, unassigned scenarios are
excluded rather than counted as dev, and every look at a held-out
scenario leaves a record.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def run_library_benchmark(
    client: TestClient, headers: dict, library: str, *, accept: bool = True, name: str = "bench"
) -> dict:
    """Import a library scenario, run one seed against it, accept it."""
    imported = client.post(f"/api/v1/scenario-library/{library}/import", headers=headers)
    assert imported.status_code == 201, imported.text
    imported = imported.json()
    created = client.post(
        "/api/v1/benchmarks",
        json={
            "name": name,
            "map_id": imported["map_id"],
            "scenario_id": imported["scenario_id"],
            "algorithms": [{"id": "astar+dwa"}],
            "seeds": [1],
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    benchmark = created.json()
    run = client.post(f"/api/v1/benchmarks/{benchmark['id']}/run", headers=headers)
    assert run.status_code == 200, run.text
    if accept:
        accepted = client.post(
            f"/api/v1/benchmarks/{benchmark['id']}/accept-result", json={}, headers=headers
        )
        assert accepted.status_code == 200, accepted.text
    return run.json()


class TestScenarioProtocolEndpoints:
    def test_library_entries_carry_their_split(self, client: TestClient) -> None:
        entries = {entry["name"]: entry for entry in client.get("/api/v1/scenario-library").json()}
        assert entries["open_space"]["split"] == "dev"
        assert entries["intersection"]["split"] == "holdout"
        assert entries["intersection"]["split_notes"]
        assert entries["intersection"]["protocol_version"]

    def test_protocol_endpoint_lists_every_library_scenario(self, client: TestClient) -> None:
        protocol = client.get("/api/v1/scenario-protocol").json()
        assert len(protocol) == 10
        assert {row["split"] for row in protocol} == {"dev", "holdout"}

    def test_unknown_scenario_resolves_to_unassigned(self, client: TestClient) -> None:
        """What the scenario editor's output will look like (plan 2.3)."""
        row = client.get("/api/v1/scenario-protocol?scenario_name=drawn_by_hand").json()[0]
        assert row["split"] == "unassigned"
        assert row["notes"] is None


class TestReportCarriesTheSplit:
    def test_dev_scenario_report_is_labelled_dev(self, client: TestClient, alice_headers) -> None:
        report = run_library_benchmark(client, alice_headers, "open_space")["report"]
        assert report["scenario_split"] == "dev"
        assert report["protocol_version"]
        assert report["generalization_gap"] is None

    def test_custom_scenario_report_is_unassigned(
        self, client: TestClient, created_map, created_scenario, alice_headers
    ) -> None:
        created = client.post(
            "/api/v1/benchmarks",
            json={
                "name": "custom",
                "map_id": created_map["id"],
                "scenario_id": created_scenario["id"],
                "algorithms": [{"id": "astar+dwa"}],
                "seeds": [1],
            },
            headers=alice_headers,
        ).json()
        run = client.post(f"/api/v1/benchmarks/{created['id']}/run", headers=alice_headers).json()
        assert run["report"]["scenario_split"] == "unassigned"


class TestGeneralizationEndpoint:
    def test_requires_authentication(self, client: TestClient) -> None:
        assert client.get("/api/v1/generalization").status_code == 401

    def test_empty_when_nothing_has_run(self, client: TestClient, carol_headers) -> None:
        summary = client.get("/api/v1/generalization", headers=carol_headers).json()
        assert summary["entries"] == []
        # Still says which protocol the reader is looking at.
        assert summary["protocol_versions"]

    def test_dev_only_results_give_no_gap(
        self, client: TestClient, alice_headers, carol_headers
    ) -> None:
        run_library_benchmark(client, alice_headers, "open_space")
        summary = client.get("/api/v1/generalization", headers=carol_headers).json()
        entry = summary["entries"][0]
        assert entry["algorithm"] == "astar+dwa"
        assert entry["dev"]["scenarios"] == ["open_space"]
        assert entry["holdout"] is None
        assert entry["gap"] is None
        assert any("held-out" in warning for warning in entry["warnings"])
        assert summary["holdout_usage"] == []

    def test_both_sides_produce_a_gap_and_an_audit_record(
        self, client: TestClient, alice_headers, carol_headers
    ) -> None:
        run_library_benchmark(client, alice_headers, "open_space", name="dev-run")
        run_library_benchmark(client, alice_headers, "intersection", name="final-eval")

        summary = client.get("/api/v1/generalization", headers=carol_headers).json()
        entry = summary["entries"][0]
        assert entry["dev"]["scenarios"] == ["open_space"]
        assert entry["holdout"]["scenarios"] == ["intersection"]
        assert entry["gap"] is not None
        assert "success_rate" in entry["gap"]
        # Thin seed counts must still be disclosed, gap or no gap.
        assert any("too few seeds" in warning for warning in entry["warnings"])

        assert summary["holdout_scenarios"] == ["intersection"]
        usage = summary["holdout_usage"]
        assert len(usage) == 1
        assert usage[0]["benchmark_name"] == "final-eval"
        assert usage[0]["benchmark_id"]
        assert usage[0]["scenario_name"] == "intersection"

    def test_metrics_declare_their_direction(self, client: TestClient, carol_headers) -> None:
        summary = client.get("/api/v1/generalization", headers=carol_headers).json()
        directions = {metric["name"]: metric["higher_is_better"] for metric in summary["metrics"]}
        assert directions["success_rate"] is True
        assert directions["median_travel_time_successful"] is False

    def test_unreviewed_runs_are_excluded_by_default(
        self, client: TestClient, alice_headers, carol_headers
    ) -> None:
        run_library_benchmark(client, alice_headers, "intersection", accept=False)
        default = client.get("/api/v1/generalization", headers=carol_headers).json()
        assert default["entries"] == []
        assert default["holdout_usage"] == []

        unfiltered = client.get(
            "/api/v1/generalization?accepted_only=false", headers=carol_headers
        ).json()
        assert unfiltered["entries"][0]["holdout"] is not None
        assert len(unfiltered["holdout_usage"]) == 1

    def test_unassigned_results_are_excluded_and_counted(
        self, client: TestClient, created_map, created_scenario, alice_headers, carol_headers
    ) -> None:
        created = client.post(
            "/api/v1/benchmarks",
            json={
                "name": "custom",
                "map_id": created_map["id"],
                "scenario_id": created_scenario["id"],
                "algorithms": [{"id": "astar+dwa"}],
                "seeds": [1],
            },
            headers=alice_headers,
        ).json()
        client.post(f"/api/v1/benchmarks/{created['id']}/run", headers=alice_headers)
        client.post(
            f"/api/v1/benchmarks/{created['id']}/accept-result", json={}, headers=alice_headers
        )
        summary = client.get("/api/v1/generalization", headers=carol_headers).json()
        assert summary["unassigned_report_count"] == 1
        assert summary["entries"] == []
        assert any("not assigned" in warning for warning in summary["warnings"])

    def test_filtering_by_algorithm_keeps_the_audit_trail(
        self, client: TestClient, alice_headers, carol_headers
    ) -> None:
        """A held-out run happened whether or not you filtered it out."""
        run_library_benchmark(client, alice_headers, "intersection")
        summary = client.get(
            "/api/v1/generalization?algorithm=nonexistent+stack", headers=carol_headers
        ).json()
        assert summary["entries"] == []
        assert len(summary["holdout_usage"]) == 1
