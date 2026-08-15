"""Objections to a stored run, over HTTP.

The endpoint is thin on purpose — every rule lives in
`planbench_decision.self_check` and has its own suite. What these tests
protect is the part only an API can get wrong: that the response is
*derived* rather than stored, that it is honest about having run at all,
and that the counts it publishes describe the findings beside them.

The derivation property is the load-bearing one. Nothing about a
critique is written to the database, so a rule added next month applies
to every run already on disk. A cached column would quietly answer last
month's question with last month's rules.
"""

from __future__ import annotations

import pytest
import yaml
from fastapi.testclient import TestClient

from planbench_decision.self_check import RULE_CODES

API = "/api/v1"


@pytest.fixture
def stored_run(client: TestClient, alice_headers, app, tmp_path) -> str:
    """A real selection run, through the real endpoints."""
    from test_vertical_slice import write_profile

    profile_path = write_profile(tmp_path)
    app.state.decision_map_root = tmp_path

    payload = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    created = client.post(f"{API}/task-profiles", json=payload, headers=alice_headers)
    assert created.status_code == 201, created.text

    run = client.post(
        f"{API}/decisions",
        json={
            "task_profile_id": created.json()["id"],
            "candidates": [
                {"stack": "astar+dwa", "local_config": "dwa_coarse"},
                {"stack": "rrtstar+dwa", "local_config": "dwa_coarse"},
            ],
            "episodes": 6,
        },
        headers=alice_headers,
    )
    assert run.status_code == 201, run.text
    return str(run.json()["id"])


class TestTheEndpointAnswers:
    def test_a_stored_run_can_be_critiqued(
        self, client: TestClient, alice_headers, stored_run: str
    ) -> None:
        response = client.get(f"{API}/decisions/{stored_run}/critique", headers=alice_headers)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["run_id"] == stored_run
        assert isinstance(body["findings"], list)

    def test_an_unknown_run_is_a_404(self, client: TestClient, alice_headers) -> None:
        response = client.get(f"{API}/decisions/does-not-exist/critique", headers=alice_headers)
        assert response.status_code == 404


class TestTheResponseIsHonestAboutItself:
    def test_it_says_how_many_rules_ran(
        self, client: TestClient, alice_headers, stored_run: str
    ) -> None:
        """An empty list must not read as "nothing was checked".

        This is the whole reason `rules_applied` is in the payload: a
        reviewer seeing zero findings needs to know whether that means
        the run is clean or the critic never ran.
        """
        body = client.get(f"{API}/decisions/{stored_run}/critique", headers=alice_headers).json()
        assert body["rules_applied"] == len(RULE_CODES)
        assert body["rules_applied"] > 0

    def test_the_counts_describe_the_findings_beside_them(
        self, client: TestClient, alice_headers, stored_run: str
    ) -> None:
        body = client.get(f"{API}/decisions/{stored_run}/critique", headers=alice_headers).json()
        findings = body["findings"]
        assert body["blocking"] == sum(1 for f in findings if f["severity"] == "blocking")
        assert body["material"] == sum(1 for f in findings if f["severity"] == "material")
        assert body["disclosure"] == sum(1 for f in findings if f["severity"] == "disclosure")
        assert body["omissions"] == sum(1 for f in findings if f["kind"] == "omission")

    def test_every_finding_names_a_known_rule(
        self, client: TestClient, alice_headers, stored_run: str
    ) -> None:
        body = client.get(f"{API}/decisions/{stored_run}/critique", headers=alice_headers).json()
        for finding in body["findings"]:
            assert finding["code"] in RULE_CODES

    def test_every_finding_carries_a_field_path_and_a_next_step(
        self, client: TestClient, alice_headers, stored_run: str
    ) -> None:
        """An objection a reader cannot check or act on is noise."""
        body = client.get(f"{API}/decisions/{stored_run}/critique", headers=alice_headers).json()
        for finding in body["findings"]:
            assert finding["field_path"]
            assert finding["suggested_check"]
            assert finding["ground"]


class TestItIsDerivedNotStored:
    def test_the_run_resource_is_unchanged_by_being_critiqued(
        self, client: TestClient, alice_headers, stored_run: str
    ) -> None:
        before = client.get(f"{API}/decisions/{stored_run}", headers=alice_headers).json()
        client.get(f"{API}/decisions/{stored_run}/critique", headers=alice_headers)
        after = client.get(f"{API}/decisions/{stored_run}", headers=alice_headers).json()
        assert before == after

    def test_asking_twice_gives_the_same_answer(
        self, client: TestClient, alice_headers, stored_run: str
    ) -> None:
        """Deterministic, because the rules are — no LLM on this path."""
        first = client.get(f"{API}/decisions/{stored_run}/critique", headers=alice_headers).json()
        second = client.get(f"{API}/decisions/{stored_run}/critique", headers=alice_headers).json()
        assert first == second


class TestItSitsBeforeTheHumanGate:
    def test_critiquing_does_not_review_or_approve(
        self, client: TestClient, alice_headers, stored_run: str
    ) -> None:
        """Reading objections is not an act; signing is (HĐ-14).

        The critic exists to inform the two human gates, so it must not
        move a run through either of them as a side effect.
        """
        before = client.get(f"{API}/decisions/{stored_run}", headers=alice_headers).json()
        client.get(f"{API}/decisions/{stored_run}/critique", headers=alice_headers)
        after = client.get(f"{API}/decisions/{stored_run}", headers=alice_headers).json()
        assert after["review_state"] == before["review_state"]
        assert after["config_state"] == before["config_state"]

    def test_there_is_no_write_verb_on_the_critique_path(self, client: TestClient) -> None:
        """Asserted against the published spec, not against intent.

        A route is only a risk once it is advertised, so the check reads
        the OpenAPI document the same way `test_api_chat` does for the
        assistant.
        """
        spec = client.get("/openapi.json").json()
        for path, operations in spec["paths"].items():
            if path.endswith("/critique"):
                assert set(operations) == {"get"}, f"{path} publishes {sorted(operations)}"
