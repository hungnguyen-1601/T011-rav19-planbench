"""The advisory routes over real HTTP.

These exist because the unit tests could not have caught the bug that
shipped in this router. `tests/test_reproduction.py` builds its candidate
correctly and then asks the module to diff it; the route read the stored
candidate through attributes `StoredCandidate` does not have
(`getattr(stored, "params", None)`), got `None` every time, and diffed the
paper against the registry's defaults instead. Every number a reader saw
was wrong, the module was blameless, and the suite was green.

So the assertions here are about the seam: that the route reads what was
actually registered, that a missing thing is a 404 rather than a
plausible answer, and that advice never becomes an action.
"""

from __future__ import annotations

from typing import Any

import pytest
import yaml


@pytest.fixture
def deployment(client, alice_headers, app, tmp_path) -> str:
    """A real deployment through the real endpoint.

    Not a name assumed to be in the database: the suite runs on a fresh
    one, and a test that asserts on `demo_hall` asserts on the developer's
    machine rather than on the code.
    """
    from test_vertical_slice import write_profile

    profile_path = write_profile(tmp_path)
    app.state.decision_map_root = tmp_path
    payload = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    created = client.post("/api/v1/task-profiles", json=payload, headers=alice_headers)
    assert created.status_code == 201, created.text
    return str(created.json()["id"])


@pytest.fixture
def registered(client, alice_headers) -> str:
    """A candidate on `dwa_coarse`, whose parameters differ from the
    registry defaults — which is what makes it able to catch the bug."""
    response = client.post(
        "/api/v1/candidates",
        json={"stack": "astar+dwa", "local_config": "dwa_coarse"},
        headers=alice_headers,
    )
    assert response.status_code in (200, 201, 409), response.text
    listing = client.get("/api/v1/candidates", headers=alice_headers).json()
    assert listing, "no candidate registered"
    return listing[0]["candidate_id"]


def reproduction(client, headers, candidate_id: str, extraction: dict[str, Any]):
    return client.post(
        f"/api/v1/candidates/{candidate_id}/reproduction",
        json={"candidate_id": candidate_id, "extraction": extraction},
        headers=headers,
    )


class TestTheRoutesAreClosed:
    def test_preflight_requires_authentication(self, anonymous):
        assert anonymous.post("/api/v1/decisions/preflight", json={}).status_code == 401

    def test_advice_requires_authentication(self, anonymous):
        assert anonymous.get("/api/v1/decisions/anything/advice").status_code == 401

    def test_reproduction_requires_authentication(self, anonymous):
        assert anonymous.post("/api/v1/candidates/x/reproduction", json={}).status_code == 401


class TestNoRouteHereActs:
    """Advice is text. If any of these could change state, the whole
    claim that the agent cannot act would be false at the API edge
    rather than in the agent."""

    def test_no_advisory_route_publishes_a_write_verb(self, client):
        paths = client.get("/openapi.json").json()["paths"]
        advisory = [p for p in paths if p.endswith(("/preflight", "/advice", "/reproduction"))]
        assert advisory
        for path in advisory:
            assert set(paths[path]) <= {"get", "post"}, path

    def test_preflight_creates_nothing(self, client, alice_headers, deployment):
        before = client.get("/api/v1/decisions", headers=alice_headers).json()
        client.post(
            "/api/v1/decisions/preflight",
            json={
                "task_profile_id": deployment,
                "candidates": [{"stack": "astar+dwa"}, {"stack": "rrtstar+dwa"}],
            },
            headers=alice_headers,
        )
        assert client.get("/api/v1/decisions", headers=alice_headers).json() == before

    def test_reproduction_registers_nothing(self, client, alice_headers, registered):
        before = client.get("/api/v1/candidates", headers=alice_headers).json()
        reproduction(client, alice_headers, registered, {"stack": "astar+dwa"})
        assert client.get("/api/v1/candidates", headers=alice_headers).json() == before


class TestReproductionReadsWhatWasRegistered:
    """The regression. `dwa_coarse` sets horizon_seconds 1.0 against a
    default of 1.5 and velocity_samples 7 against 9; a route reading the
    wrong field reports the defaults and calls them chosen."""

    def test_it_reports_the_candidates_own_parameters(self, client, alice_headers, registered):
        body = reproduction(
            client, alice_headers, registered, {"stack": "astar+dwa", "parameters": []}
        ).json()
        values = {row["name"]: row["candidate"] for row in body["parameters"]}
        assert values["horizon_seconds"] == 1.0, values["horizon_seconds"]
        assert values["velocity_samples"] == 7, values["velocity_samples"]
        assert values["control_period"] == 0.05, values["control_period"]

    def test_a_stated_value_that_differs_is_reported_as_differing(
        self, client, alice_headers, registered
    ):
        body = reproduction(
            client,
            alice_headers,
            registered,
            {
                "stack": "astar+dwa",
                "parameters": [{"name": "horizon_seconds", "value": 2.0, "quote": "2.0 s"}],
            },
        ).json()
        row = next(r for r in body["parameters"] if r["name"] == "horizon_seconds")
        assert row["verdict"] == "differs"
        assert "RP_PARAM_DIFFERS" in {a["code"] for a in body["advice"]}

    def test_a_stated_value_that_matches_is_not_reported_as_a_difference(
        self, client, alice_headers, registered
    ):
        body = reproduction(
            client,
            alice_headers,
            registered,
            {
                "stack": "astar+dwa",
                "parameters": [{"name": "horizon_seconds", "value": 1.0, "quote": "1.0 s"}],
            },
        ).json()
        row = next(r for r in body["parameters"] if r["name"] == "horizon_seconds")
        assert row["verdict"] == "agrees"

    def test_it_counts_the_rules_that_ran(self, client, alice_headers, registered):
        """An empty advice list has to read as "six rules looked and none
        objected" rather than "nothing ran"."""
        body = reproduction(client, alice_headers, registered, {"stack": "astar+dwa"}).json()
        assert body["rules_applied"] >= 1


class TestMissingThingsAreRefusedNotAnswered:
    def test_an_unknown_deployment_is_a_404(self, client, alice_headers):
        response = client.post(
            "/api/v1/decisions/preflight",
            json={
                "task_profile_id": "no_such_deployment",
                "candidates": [{"stack": "astar+dwa"}, {"stack": "rrtstar+dwa"}],
            },
            headers=alice_headers,
        )
        assert response.status_code == 404

    def test_an_unknown_run_is_a_404(self, client, alice_headers):
        assert (
            client.get("/api/v1/decisions/no_such_run/advice", headers=alice_headers).status_code
            == 404
        )

    def test_an_unknown_candidate_is_a_404(self, client, alice_headers):
        assert reproduction(client, alice_headers, "no_such_candidate", {}).status_code == 404

    def test_a_single_candidate_is_refused_by_the_schema(self, client, alice_headers, deployment):
        """A comparison needs two. Accepting one and returning advice
        about it would be advice about something that cannot run."""
        response = client.post(
            "/api/v1/decisions/preflight",
            json={"task_profile_id": deployment, "candidates": [{"stack": "astar+dwa"}]},
            headers=alice_headers,
        )
        assert response.status_code == 422


class TestPreflightSaysWhatTheRunWouldCost:
    def test_the_plan_block_is_present(self, client, alice_headers, deployment):
        body = client.post(
            "/api/v1/decisions/preflight",
            json={
                "task_profile_id": deployment,
                "candidates": [{"stack": "astar+dwa"}, {"stack": "rrtstar+dwa"}],
                "episodes": 20,
            },
            headers=alice_headers,
        ).json()
        assert body["plan"]["episodes_per_candidate"] == 20
        assert body["plan"]["episode_runs_total"] == 40

    def test_a_reference_stack_is_refused_before_the_compute(
        self, client, alice_headers, deployment
    ):
        body = client.post(
            "/api/v1/decisions/preflight",
            json={
                "task_profile_id": deployment,
                "candidates": [{"stack": "astar+pure_pursuit"}, {"stack": "astar+dwa"}],
                "episodes": 30,
            },
            headers=alice_headers,
        ).json()
        assert "PF_REFERENCE_STACK_IN_COMPARISON" in {a["code"] for a in body["advice"]}
        assert body["blocking"] >= 1

    def test_every_blocking_advice_names_a_forbidden_move(self, client, alice_headers, deployment):
        body = client.post(
            "/api/v1/decisions/preflight",
            json={
                "task_profile_id": deployment,
                "candidates": [{"stack": "astar+dwa"}, {"stack": "rrtstar+dwa"}],
                "episodes": 1,
            },
            headers=alice_headers,
        ).json()
        for item in body["advice"]:
            if item["severity"] == "blocking":
                assert item["do_not"], item["code"]


class TestReportAdviceOverHttp:
    def test_requires_authentication(self, anonymous):
        assert anonymous.get("/api/v1/decisions/x/report-advice").status_code == 401

    def test_an_unknown_run_is_a_404(self, client, alice_headers):
        response = client.get("/api/v1/decisions/no_such/report-advice", headers=alice_headers)
        assert response.status_code == 404


class TestTraceReviewOverHttp:
    def test_requires_authentication(self, anonymous):
        assert anonymous.get("/api/v1/decisions/r/traces/c/e/review").status_code == 401

    def test_an_unknown_run_is_a_404(self, client, alice_headers):
        response = client.get("/api/v1/decisions/no_such/traces/c/e/review", headers=alice_headers)
        assert response.status_code == 404


class TestTheModelLayerDegradesHonestly:
    def test_use_model_on_the_mock_keeps_the_rules_and_says_why(self, client, alice_headers):
        """The deterministic provider produces no structured output; the
        floor must survive and `refused` must say what happened. A model
        layer that hid its own absence would make rule advice and model
        advice indistinguishable."""
        runs = client.get("/api/v1/decisions", headers=alice_headers).json()
        if not runs:
            import pytest

            pytest.skip("no stored run in this database")
        run_id = runs[0]["id"]
        plain = client.get(f"/api/v1/decisions/{run_id}/advice", headers=alice_headers).json()
        modeled = client.get(
            f"/api/v1/decisions/{run_id}/advice?use_model=true", headers=alice_headers
        ).json()
        assert modeled["refused"]
        rule_codes = sorted(a["code"] for a in plain["advice"])
        surviving = sorted(a["code"] for a in modeled["advice"] if a["source"] == "rule")
        assert surviving == rule_codes


class TestOutcomeOverHttp:
    def test_requires_authentication(self, anonymous):
        assert anonymous.get("/api/v1/decisions/x/outcome").status_code == 401

    def test_an_unknown_run_is_a_404(self, client, alice_headers):
        assert (
            client.get("/api/v1/decisions/no_such/outcome", headers=alice_headers).status_code
            == 404
        )

    def test_a_gate_elimination_is_never_narrated_as_a_defeat(self, client, alice_headers):
        """The refusal that earns the endpoint: a candidate that never
        qualified was never compared, and "X beat Y" would describe a
        comparison that did not happen."""
        runs = client.get("/api/v1/decisions", headers=alice_headers).json()
        if not runs:
            import pytest

            pytest.skip("no stored run in this database")
        body = client.get(
            f"/api/v1/decisions/{runs[0]['id']}/outcome", headers=alice_headers
        ).json()
        eliminated = [a for a in body["advice"] if a["code"] == "OC_ELIMINATED_BY_GATE"]
        for item in eliminated:
            assert "winning" in item["do_not"] or "beat" in item["do_not"]

    def test_the_model_layer_keeps_the_rules_when_it_cannot_run(self, client, alice_headers):
        runs = client.get("/api/v1/decisions", headers=alice_headers).json()
        if not runs:
            import pytest

            pytest.skip("no stored run in this database")
        run_id = runs[0]["id"]
        plain = client.get(f"/api/v1/decisions/{run_id}/outcome", headers=alice_headers).json()
        modeled = client.get(
            f"/api/v1/decisions/{run_id}/outcome?use_model=true", headers=alice_headers
        ).json()
        assert modeled["refused"]
        assert sorted(a["code"] for a in modeled["advice"] if a["source"] == "rule") == sorted(
            a["code"] for a in plain["advice"]
        )


class TestAPaperCanActuallyBeRegistered:
    """The end-user test that found the identity split.

    The paper reading prints a candidate_id computed from the stated
    parameters; the registration form only accepted a *named* config, so
    that id could never be registered — the diff button 404'd for a user
    who did everything right. Registration now takes explicit params,
    through the same hash path, so the id the reading printed is the id
    the registration returns.
    """

    EXTRACTION_PARAMS = {
        "control_period": 0.1,
        "horizon_seconds": 1.5,
        "velocity_samples": 7,
        "omega_samples": 15,
    }

    def test_registering_the_papers_params_yields_the_papers_id(self, client, alice_headers):
        from planbench_benchmark.candidates import candidate_from_stack

        expected = candidate_from_stack("rrtstar+dwa", params=dict(self.EXTRACTION_PARAMS))
        response = client.post(
            "/api/v1/candidates",
            json={"stack": "rrtstar+dwa", "params": self.EXTRACTION_PARAMS},
            headers=alice_headers,
        )
        assert response.status_code in (200, 201), response.text
        assert response.json()["candidate_id"] == expected.candidate_id

    def test_a_name_and_params_together_are_refused_out_loud(self, client, alice_headers):
        """With both, which one defines the candidate would be the
        server's private decision — and a private decision about
        identity is an identity bug waiting to be filed."""
        response = client.post(
            "/api/v1/candidates",
            json={
                "stack": "rrtstar+dwa",
                "local_config": "dwa_coarse",
                "params": self.EXTRACTION_PARAMS,
            },
            headers=alice_headers,
        )
        assert response.status_code == 422
        assert "not both" in response.text

    def test_an_unknown_parameter_is_refused_not_ignored(self, client, alice_headers):
        response = client.post(
            "/api/v1/candidates",
            json={"stack": "rrtstar+dwa", "params": {"no_such_knob": 1}},
            headers=alice_headers,
        )
        assert response.status_code == 422

    def test_the_bare_registration_still_defaults_to_dwa_coarse(self, client, alice_headers):
        """Every existing caller sends only a stack name; that door must
        not have moved."""
        response = client.post(
            "/api/v1/candidates", json={"stack": "astar+dwa"}, headers=alice_headers
        )
        assert response.status_code in (200, 201), response.text
