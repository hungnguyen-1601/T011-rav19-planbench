"""Publishing an imported algorithm, and the flag that gates it.

Two properties carry this phase, and they pull in opposite directions on
purpose:

* with the flag **off**, nothing about what a deployment offers changes.
  This lands on installations that are already running, and a phase that
  quietly altered which algorithm resolves under a stack id would be a
  silent change to what future runs measure.
* with the flag **on**, an engineer can pick exactly what a reviewer
  published — and the table can still say *why* something is no longer
  published, because "a newer revision replaced it" and "a reviewer
  pulled it back" are recorded as different facts.

The second is the one an approval depends on later: a stored
recommendation has to be able to tell "merely old" from "withdrawn".
"""

from __future__ import annotations

import io

import pytest
from conftest import ADMIN, BOB, ENGINEER, auth_headers, isolate_environment
from fastapi.testclient import TestClient
from test_api_plugin_import import (
    GOOD_MANIFEST,
    PLANNER_SOURCE,
    bundle_zip,
    default_profile,
    message,
)

from planbench_api.config import get_settings
from planbench_api.main import create_app

PLUGINS = "/api/v1/algorithms/plugins"


@pytest.fixture
def governed(tmp_path, monkeypatch):
    """An app with publishing turned on."""
    isolate_environment(monkeypatch)
    monkeypatch.setenv("PLANBENCH_MODEL_DIR", str(tmp_path / "models"))
    monkeypatch.setenv("PLANBENCH_ALGORITHM_GOVERNANCE", "true")
    get_settings.cache_clear()
    application = create_app(artifact_dir=str(tmp_path / "artifacts"))
    yield application
    get_settings.cache_clear()


@pytest.fixture
def governed_client(governed) -> TestClient:
    signed_in = TestClient(governed, raise_server_exceptions=False)
    signed_in.headers.update(auth_headers(signed_in, ADMIN))
    return signed_in


def _import(client, headers=None, source: str = PLANNER_SOURCE, name: str = "VFH+"):
    """Imported by bob unless told otherwise.

    Deliberately not the client's own account: under strict duties the
    reviewer who uploads a revision is not the one who publishes it, so a
    helper that imported as the caller would make every publish in this
    file fail for a reason none of them is about.
    """
    headers = auth_headers(client, BOB) if headers is None else headers
    return client.post(
        PLUGINS,
        data={"name": name, "version": "1", "robot_profile_id": default_profile(client, headers)},
        files={
            "bundle": (
                "vfh_plus.zip",
                io.BytesIO(bundle_zip(members={"vfh_plus/planner.py": source})),
                "application/zip",
            )
        },
        headers=headers,
    )


def _stack_ids(client) -> list[str]:
    return [row["id"] for row in client.get("/api/v1/algorithms").json()]


class TestTheFlagOffChangesNothing:
    """The property that lets this land on a running deployment."""

    def test_an_imported_algorithm_is_offered_without_anybody_publishing_it(
        self, client: TestClient
    ) -> None:
        headers = auth_headers(client, ADMIN)
        assert _import(client, headers).status_code == 201
        assert any(stack.endswith("org.vinai.vfh-plus") for stack in _stack_ids(client))

    def test_the_governance_routes_are_not_there_at_all(self, client: TestClient) -> None:
        """404, not 403.

        "You may not" and "this deployment has not turned publishing on"
        are different answers, and a client that can tell them apart can
        hide the button instead of offering one that always fails.
        """
        headers = auth_headers(client, ADMIN)
        bundle = _import(client, headers).json()
        for action in ("publish", "unpublish", "hold", "release-hold", "disable"):
            response = client.post(
                f"{PLUGINS}/{bundle['id']}/{action}", json={"reason": "x"}, headers=headers
            )
            assert response.status_code == 404, action


class TestPublishingIsWhatPutsItInThePicker:
    def test_an_imported_algorithm_is_not_offered_until_it_is_published(
        self, governed_client: TestClient
    ) -> None:
        bundle = _import(governed_client).json()
        assert not any(
            stack.endswith("org.vinai.vfh-plus") for stack in _stack_ids(governed_client)
        )
        published = governed_client.post(
            f"{PLUGINS}/{bundle['id']}/publish", json={"reason": "checked"}
        )
        assert published.status_code == 200, published.text
        assert any(stack.endswith("org.vinai.vfh-plus") for stack in _stack_ids(governed_client))

    def test_publishing_needs_a_bundle_that_actually_loaded(
        self, governed_client: TestClient
    ) -> None:
        """``structural`` means the archive is shaped right, nothing more.

        Reading a zip's table of contents executes none of it, so
        publishing on that verdict would put code in front of every
        engineer that no conformance suite has run.
        """
        broken = _import(governed_client, {}, source="raise RuntimeError('nope')\n").json()
        assert broken["validation_status"] != "loaded"
        refused = governed_client.post(f"{PLUGINS}/{broken['id']}/publish", json={})
        assert refused.status_code == 403
        assert "conformance" in message(refused)

    def test_an_engineer_cannot_publish(self, governed_client: TestClient) -> None:
        bundle = _import(governed_client).json()
        refused = governed_client.post(
            f"{PLUGINS}/{bundle['id']}/publish",
            json={},
            headers=auth_headers(governed_client, ENGINEER),
        )
        assert refused.status_code == 403
        assert "reviewer" in message(refused)

    def test_a_reviewer_does_not_publish_their_own_upload_under_strict_duties(
        self, governed_client: TestClient
    ) -> None:
        """A signature its own signer could have produced alone.

        Not because uploading is suspect — because the second pair of
        eyes is the entire content of the step.
        """
        bundle = _import(governed_client).json()
        refused = governed_client.post(
            f"{PLUGINS}/{bundle['id']}/publish",
            json={},
            headers=auth_headers(governed_client, BOB),
        )
        assert refused.status_code == 403
        assert "separates duties" in message(refused)


class TestUnpublishIsNotSupersede:
    """The distinction a stored approval needs later.

    Both leave the revision out of the picker. Only one of them is
    evidence about the revision, and an approval made against it has to
    be able to tell which happened — "there is a newer one" says nothing
    about whether this one was any good.
    """

    def _published(self, client, source: str = PLANNER_SOURCE):
        bundle = _import(client, source=source).json()
        assert client.post(f"{PLUGINS}/{bundle['id']}/publish", json={}).status_code == 200
        return bundle

    def test_a_newer_revision_supersedes_the_older_one(self, governed_client: TestClient) -> None:
        first = self._published(governed_client)
        second = self._published(governed_client, source=PLANNER_SOURCE + "\n# changed\n")
        history = governed_client.get(f"{PLUGINS}/{second['id']}").json()["publications"]
        by_bundle = {row["bundle_id"]: row for row in history}
        assert by_bundle[first["id"]]["superseded_at"] is not None
        assert by_bundle[first["id"]]["unpublished_at"] is None
        assert by_bundle[second["id"]]["is_current"] is True

    def test_withdrawing_records_that_a_person_did_it(self, governed_client: TestClient) -> None:
        bundle = self._published(governed_client)
        withdrawn = governed_client.post(
            f"{PLUGINS}/{bundle['id']}/unpublish", json={"reason": "looks wrong"}
        )
        assert withdrawn.status_code == 200
        row = governed_client.get(f"{PLUGINS}/{bundle['id']}").json()["publications"][0]
        assert row["unpublished_at"] is not None
        assert row["superseded_at"] is None
        assert row["reason"] == "looks wrong"
        assert not any(
            stack.endswith("org.vinai.vfh-plus") for stack in _stack_ids(governed_client)
        )

    def test_publishing_again_restores_it(self, governed_client: TestClient) -> None:
        bundle = self._published(governed_client)
        governed_client.post(f"{PLUGINS}/{bundle['id']}/unpublish", json={"reason": "wait"})
        assert governed_client.post(f"{PLUGINS}/{bundle['id']}/publish", json={}).status_code == 200
        assert any(stack.endswith("org.vinai.vfh-plus") for stack in _stack_ids(governed_client))

    def test_a_new_revision_does_not_disable_the_one_it_replaces(
        self, governed_client: TestClient
    ) -> None:
        """``_retire_previous`` is off under governance, and had to be.

        It disabled the older upload the moment a newer one passed a
        check — the machine deciding what runs. Under publishing the
        older revision stays perfectly enabled; it simply stops being
        current, which is a thing a person did.
        """
        first = self._published(governed_client)
        _import(governed_client, {}, source=PLANNER_SOURCE + "\n# changed\n")
        assert (
            governed_client.get(f"{PLUGINS}/{first['id']}").json()["bundle"]["status"] == "active"
        )


    def test_the_list_view_learns_the_published_set_in_one_request(
        self, governed_client: TestClient
    ) -> None:
        """A list page asks once, not once per row.

        The route exists because the alternative is a detail request per
        bundle to learn one bit each, and the answer a list needs is a
        set: in it means "this is what an engineer gets", out of it with
        a sibling in it means "a newer revision took over", and out with
        no sibling means nobody published this algorithm at all. The
        three read differently to a reviewer and only the first is
        visible from a single row.
        """
        first = self._published(governed_client)
        second = self._published(
            governed_client, source=PLANNER_SOURCE + "\n# changed\n"
        )

        published = governed_client.get(f"{PLUGINS}/published")
        assert published.status_code == 200
        assert published.json() == [second["id"]]
        assert first["id"] not in published.json()

        governed_client.post(f"{PLUGINS}/{second['id']}/unpublish", json={"reason": "wait"})
        assert governed_client.get(f"{PLUGINS}/published").json() == []

    def test_published_is_a_route_and_not_read_as_a_bundle_id(
        self, governed_client: TestClient
    ) -> None:
        """Registered before ``/{bundle_id}``, which would swallow it.

        FastAPI matches in registration order, so declaring this after
        the detail route would make it a lookup for a bundle called
        "published" and answer 404 forever.
        """
        assert governed_client.get(f"{PLUGINS}/published").status_code == 200
        assert governed_client.get(f"{PLUGINS}/no-such-bundle").status_code == 404

    def test_it_answers_empty_rather_than_404_with_governance_off(
        self, client: TestClient
    ) -> None:
        """Nothing published is a true answer, not a missing feature.

        The governed *acts* 404 while the flag is off, because offering a
        kill switch nothing downstream understands is worse than not
        offering it. Reading the set is not an act: with no publications
        the honest answer is that none exist, and a list page that got a
        404 here would have to guess whether to grey every row.
        """
        _import(client)
        answered = client.get(f"{PLUGINS}/published")
        assert answered.status_code == 200
        assert answered.json() == []


class TestHoldAndDisable:
    def test_a_held_bundle_leaves_the_catalogue_and_comes_back(
        self, governed_client: TestClient
    ) -> None:
        bundle = _import(governed_client).json()
        governed_client.post(f"{PLUGINS}/{bundle['id']}/publish", json={})
        governed_client.post(f"{PLUGINS}/{bundle['id']}/hold", json={"reason": "checking"})
        assert not any(
            stack.endswith("org.vinai.vfh-plus") for stack in _stack_ids(governed_client)
        )
        assert (
            governed_client.post(f"{PLUGINS}/{bundle['id']}/release-hold", json={}).status_code
            == 200
        )

    def test_disabling_needs_a_reason(self, governed_client: TestClient) -> None:
        """It is what somebody reads when a stored approval says the
        algorithm behind it was turned off."""
        bundle = _import(governed_client).json()
        refused = governed_client.post(f"{PLUGINS}/{bundle['id']}/disable", json={"reason": "  "})
        assert refused.status_code == 403
        assert "needs a reason" in message(refused)

    def test_disabling_is_terminal(self, governed_client: TestClient) -> None:
        """No enable route, and releasing a hold will not do it either.

        "Turn it back on" and "upload the fixed one" should not both
        exist: only the second is honest about what changed in between.
        """
        bundle = _import(governed_client).json()
        governed_client.post(f"{PLUGINS}/{bundle['id']}/publish", json={})
        governed_client.post(f"{PLUGINS}/{bundle['id']}/disable", json={"reason": "unsafe"})
        refused = governed_client.post(f"{PLUGINS}/{bundle['id']}/release-hold", json={})
        assert refused.status_code == 403
        assert "final" in message(refused)
        assert not any(
            stack.endswith("org.vinai.vfh-plus") for stack in _stack_ids(governed_client)
        )

    def test_every_act_lands_in_the_bundle_trail_with_its_capability(
        self, governed_client: TestClient
    ) -> None:
        bundle = _import(governed_client).json()
        governed_client.post(f"{PLUGINS}/{bundle['id']}/publish", json={"reason": "ok"})
        governed_client.post(f"{PLUGINS}/{bundle['id']}/disable", json={"reason": "unsafe"})
        events = governed_client.get(f"{PLUGINS}/{bundle['id']}/events").json()
        actions = [event["action"] for event in events]
        assert "published" in actions and "disabled" in actions
        published = next(event for event in events if event["action"] == "published")
        assert published["authorized_capability"] == "algorithm.publish"
        assert published["actor_roles"]


class TestReadingCodeIsTheReviewersJob:
    def test_an_engineer_sees_what_it_needs_but_not_what_it_is(self, client: TestClient) -> None:
        """Capability, yes; code, no.

        Requirements and compatibility are what an engineer uses to
        decide whether to pick an algorithm — withhold those and they
        cannot configure a candidate. The entry point and the archive's
        checksum describe the code itself.
        """
        bundle = _import(client, auth_headers(client, ADMIN)).json()
        detail = client.get(
            f"{PLUGINS}/{bundle['id']}", headers=auth_headers(client, ENGINEER)
        ).json()
        assert detail["bundle"]["requirements"] == ["lidar_2d"]
        assert detail["compatibility"] is not None
        assert detail["manifest"] is None
        assert detail["entry_point"] is None
        assert detail["bundle"]["checksum"] == ""

    def test_a_reviewer_sees_the_manifest(self, client: TestClient) -> None:
        headers = auth_headers(client, ADMIN)
        bundle = _import(client, headers).json()
        detail = client.get(f"{PLUGINS}/{bundle['id']}", headers=headers).json()
        assert detail["manifest"]["id"] == GOOD_MANIFEST["id"]
        assert detail["entry_point"]
        assert detail["bundle"]["checksum"]

    def test_the_events_trail_is_reviewer_only(self, client: TestClient) -> None:
        bundle = _import(client, auth_headers(client, ADMIN)).json()
        refused = client.get(
            f"{PLUGINS}/{bundle['id']}/events", headers=auth_headers(client, ENGINEER)
        )
        assert refused.status_code == 403


class TestAnApprovalOutlivesTheAlgorithmItRestedOn:
    """The two questions, over HTTP.

    Disabling an algorithm must not rewrite what a person decided, and
    must not leave a dead recommendation reading as a live one. So the
    approval stands, the file still downloads, and the file says why it
    is no longer something to run.
    """

    def test_the_journal_gains_an_entry_and_the_approval_stands(
        self, governed_client: TestClient, governed
    ) -> None:
        from planbench_api.decisions import StoredDecisionRun

        bundle = _import(governed_client).json()
        governed_client.post(f"{PLUGINS}/{bundle['id']}/publish", json={"reason": "ok"})

        # A run that already carries an approval and names this bundle.
        # Injected rather than driven over HTTP: what is under test is
        # what happens to a *stored* approval, and simulating six
        # episodes to reach one would test the simulator instead.
        governed.state.repos.decision_runs.create(
            StoredDecisionRun(
                id="run_approved",
                task_profile_id="p1",
                artifact_kind="decision_card",
                experiment_scope="global_planner_selection",
                contracts_version="7.0.0",
                created_at="2026-08-27T10:00:00Z",
                created_by="somebody_else",
                report={},
                card={"status": "recommended"},
                manifest=None,
                recommended_candidate_id="c1",
                status="recommended",
                config_state="approved",
                config_decided_by="u1",
                config_decided_at="2026-08-27T11:00:00Z",
                candidates=[
                    {
                        "slot": 0,
                        "stack": "astar+org.vinai.vfh-plus",
                        "local_config": "",
                        "bundle_id": bundle["id"],
                        "plugin_id": "org.vinai.vfh-plus",
                        "revision": bundle["revision"],
                        "archive_checksum": "",
                        "provider_fingerprint": "",
                        "runtime_profile": "local",
                    }
                ],
            )
        )

        disabled = governed_client.post(
            f"{PLUGINS}/{bundle['id']}/disable", json={"reason": "unsafe near glass"}
        )
        assert disabled.status_code == 200, disabled.text

        run = governed_client.get("/api/v1/decisions/run_approved").json()
        assert run["config_state"] == "approved", "nobody withdrew anything"

        trail = governed_client.get("/api/v1/decisions/run_approved/audit").json()
        entry = next(
            event for event in trail if event["action"] == "algorithm_disabled_after_approval"
        )
        assert "unsafe near glass" in entry["comment"]
        assert entry["previous_state"] == entry["new_state"] == "approved"

    def test_the_configuration_still_downloads_and_says_why_not_to_use_it(
        self, governed_client: TestClient, governed
    ) -> None:
        """Refusing would only make the evidence hard to reach at the
        moment somebody is investigating why it was withdrawn."""
        from planbench_api.decisions import StoredDecisionRun

        bundle = _import(governed_client).json()
        governed_client.post(f"{PLUGINS}/{bundle['id']}/publish", json={"reason": "ok"})
        governed.state.repos.decision_runs.create(
            StoredDecisionRun(
                id="run_two",
                task_profile_id="p1",
                artifact_kind="decision_card",
                experiment_scope="global_planner_selection",
                contracts_version="7.0.0",
                created_at="2026-08-27T10:00:00Z",
                created_by="somebody_else",
                report={},
                card={"status": "recommended", "recommended": {"candidate_id": "c1"}},
                manifest=None,
                recommended_candidate_id="c1",
                status="recommended",
                config_state="approved",
                config_decided_by="u1",
                config_decided_at="2026-08-27T11:00:00Z",
                candidates=[
                    {
                        "slot": 0,
                        "stack": "astar+org.vinai.vfh-plus",
                        "local_config": "",
                        "bundle_id": bundle["id"],
                        "plugin_id": "org.vinai.vfh-plus",
                        "revision": bundle["revision"],
                        "archive_checksum": "abc",
                        "provider_fingerprint": "",
                        "runtime_profile": "local",
                    }
                ],
            )
        )
        governed_client.post(f"{PLUGINS}/{bundle['id']}/disable", json={"reason": "unsafe"})

        exported = governed_client.get("/api/v1/decisions/run_two/approved_config.yaml")
        assert exported.status_code == 200, exported.text
        body = exported.text
        assert "reliance_status: revoked" in body
        assert "algorithm_disabled_after_approval" in body
        assert "unsafe" in body
        # And it still says what was decided, unchanged.
        assert "status: approved" in body
