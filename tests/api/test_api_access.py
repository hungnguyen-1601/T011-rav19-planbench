"""What contract 7.0.0 closed: routes that used to answer to anybody.

Three groups of endpoints had no authentication at all — `simulations`
(including the one that spends the machine's pinned cores), `scenarios`,
`maps` — and the playback socket accepted every connection. Reading a
trace, a report or an approved configuration was open too, which made
the evidence behind a decision readable by anyone who could guess an id.

These tests are about the *door*, not about what is behind it: each one
asks whether the refusal happens, and the interesting ones ask whether it
happens for the right reason.
"""

from __future__ import annotations

import pytest
from conftest import ALICE, BOB, auth_headers, ws_url
from fastapi.testclient import TestClient
from payloads import bordered_map_payload, scenario_payload


class TestWritesNeedAnAccount:
    """The three groups that used to take anybody's word for it."""

    @pytest.mark.parametrize(
        ("method", "path", "body"),
        [
            ("post", "/api/v1/maps", "map"),
            ("post", "/api/v1/scenarios", None),
            ("post", "/api/v1/simulations", None),
        ],
    )
    def test_creating_is_refused_without_a_token(
        self, anonymous: TestClient, method, path, body
    ) -> None:
        payload = bordered_map_payload() if body == "map" else {}
        assert getattr(anonymous, method)(path, json=payload).status_code == 401

    def test_running_a_simulation_is_refused_without_a_token(self, anonymous: TestClient) -> None:
        """The one that costs the machine something.

        A stranger could previously start a run on the deployment's
        pinned cores, which is both a bill and — because HĐ-7.4 forbids
        two evaluation runs at once — a way to corrupt somebody else's
        measurement.
        """
        assert anonymous.post("/api/v1/simulations/anything/run").status_code == 401

    def test_reading_is_refused_too(self, anonymous: TestClient) -> None:
        assert anonymous.get("/api/v1/maps").status_code == 401
        assert anonymous.get("/api/v1/scenarios").status_code == 401
        assert anonymous.get("/api/v1/simulations").status_code == 401


class TestEvidenceIsNotPublic:
    """A decision's evidence is readable by members, not by the internet.

    Named one route per artefact rather than swept up in a loop: these
    are the four somebody would reach for to reconstruct a conclusion,
    and each was open.
    """

    @pytest.mark.parametrize(
        "path",
        [
            "/api/v1/decisions",
            "/api/v1/decisions/whatever/audit",
            "/api/v1/decisions/whatever/report.md",
            "/api/v1/decisions/whatever/approved_config.yaml",
        ],
    )
    def test_the_route_refuses_a_stranger(self, anonymous: TestClient, path) -> None:
        assert anonymous.get(path).status_code == 401

    def test_a_member_gets_through_the_door(self, client: TestClient) -> None:
        """The refusal must be about the account, not about the route.

        Without this, a 401 for everybody would pass the test above and
        mean the endpoint is simply broken.
        """
        assert client.get("/api/v1/decisions").status_code == 200


class TestOwnership:
    """Capability says *what*; ownership says *which record*."""

    def test_a_member_may_not_edit_somebody_elses_map(self, client: TestClient) -> None:
        created = client.post("/api/v1/maps", json=bordered_map_payload())
        assert created.status_code == 201, created.text
        refused = client.put(
            f"/api/v1/maps/{created.json()['id']}",
            json=bordered_map_payload(),
            headers=auth_headers(client, BOB),
        )
        assert refused.status_code == 403
        assert "another member" in refused.json()["error"]["message"]

    def test_the_owner_may(self, client: TestClient) -> None:
        created = client.post("/api/v1/maps", json=bordered_map_payload())
        assert (
            client.put(
                f"/api/v1/maps/{created.json()['id']}",
                json=bordered_map_payload(),
                headers=auth_headers(client, ALICE),
            ).status_code
            == 200
        )

    def test_a_map_from_before_accounts_stays_shared(self, app, client: TestClient) -> None:
        """``owner_user_id IS NULL`` means shared, not protected.

        Rows made before accounts existed read that way, and so does a
        grid ``adopt`` handed back because the library already defined
        it. Refusing to let anybody edit those would strand them.
        """
        from planbench_schemas.map import MapData

        legacy = app.state.repos.maps.create(MapData.model_validate(bordered_map_payload()))
        assert legacy.owner_user_id is None
        assert (
            client.put(f"/api/v1/maps/{legacy.id}", json=bordered_map_payload()).status_code == 200
        )


class TestDeleteArchives:
    def test_a_deleted_scenario_leaves_the_list_but_not_the_store(
        self, client: TestClient, created_map: dict
    ) -> None:
        """A run made against it must still be able to say what it ran on."""
        created = client.post(
            "/api/v1/scenarios",
            json={"map_id": created_map["id"], "scenario": scenario_payload()},
        )
        scenario_id = created.json()["id"]
        assert client.delete(f"/api/v1/scenarios/{scenario_id}").status_code == 204
        listed = [row["id"] for row in client.get("/api/v1/scenarios").json()]
        assert scenario_id not in listed
        assert client.get(f"/api/v1/scenarios/{scenario_id}").status_code == 200


class TestTheSocketTicket:
    """A browser cannot set a header, and a JWT in a URL ends up in logs.

    So the socket takes a ticket that is worth one connection for one
    minute, minted over an ordinary authenticated request.
    """

    def test_a_socket_without_a_ticket_is_refused(self, client: TestClient) -> None:
        with client.websocket_connect("/ws/simulations/anything") as socket:
            message = socket.receive_json()
        assert message["code"] == "unauthorised"

    def test_a_ticket_is_spent_when_it_is_used(self, client: TestClient) -> None:
        """Single use is the property that makes a logged ticket harmless.

        A line in an access log then describes something already
        redeemed, rather than a credential good for the next hour.
        """
        url = ws_url(client, "/ws/simulations/anything")
        with client.websocket_connect(url) as first:
            assert first.receive_json()["code"] == "not_found"
        with client.websocket_connect(url) as second:
            assert second.receive_json()["code"] == "unauthorised"

    def test_an_expired_ticket_is_refused(self, client: TestClient, app) -> None:
        from datetime import UTC, datetime, timedelta

        from planbench_api.ws_tickets import TicketStore

        app.state.ws_tickets = TicketStore(ttl=timedelta(seconds=-1))
        stale = app.state.ws_tickets.issue("someone")
        assert stale.expires_at < datetime.now(UTC)
        with client.websocket_connect(f"/ws/simulations/x?ticket={stale.value}") as socket:
            assert socket.receive_json()["code"] == "unauthorised"

    def test_minting_a_ticket_needs_an_account(self, anonymous: TestClient) -> None:
        assert anonymous.post("/api/v1/ws/tickets").status_code == 401
