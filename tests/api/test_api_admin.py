"""Administering accounts: what an administrator may do, and may not.

The package is deliberately narrow. An administrator runs the platform
and holds no business capability at all — cannot start a run, approve
one, or publish an algorithm. Somebody who does both jobs holds both
roles, and every act is audited under the capability that allowed it.

The two rules worth their own tests are the ones that make the model
safe rather than merely tidy: nobody can grant themselves everything,
and nobody can leave the deployment with no way back in.
"""

from __future__ import annotations

from conftest import ADMIN, ALICE, BOB, ENGINEER, auth_headers
from fastapi.testclient import TestClient

API = "/api/v1"


def _account(client: TestClient, headers, nickname: str) -> dict:
    listed = client.get(f"{API}/admin/users", headers=headers).json()
    return next(row for row in listed if row["nickname"] == nickname)


class TestOnlyAnAdministratorGetsIn:
    def test_an_engineer_is_refused(self, client: TestClient) -> None:
        refused = client.get(f"{API}/admin/users", headers=auth_headers(client, ENGINEER))
        assert refused.status_code == 403

    def test_a_reviewer_is_refused_too(self, client: TestClient) -> None:
        """Reviewer is a business package, not a senior one."""
        refused = client.get(f"{API}/admin/users", headers=auth_headers(client, ALICE))
        assert refused.status_code == 403

    def test_the_administrator_sees_the_table(self, client: TestClient, admin_headers) -> None:
        rows = client.get(f"{API}/admin/users", headers=admin_headers).json()
        assert {row["nickname"] for row in rows} >= {ALICE[0], BOB[0], ADMIN[0], ENGINEER[0]}
        mine = next(row for row in rows if row["nickname"] == ADMIN[0])
        assert "admin" in mine["roles"]
        assert "user.manage" in mine["capabilities"]

    def test_no_password_material_comes_back(self, client: TestClient, admin_headers) -> None:
        rows = client.get(f"{API}/admin/users", headers=admin_headers).json()
        assert all("password" not in key for row in rows for key in row)


class TestGranting:
    def test_a_role_can_be_granted_with_a_reason(self, client: TestClient, admin_headers) -> None:
        erin = _account(client, admin_headers, ENGINEER[0])
        granted = client.post(
            f"{API}/admin/users/{erin['id']}/roles",
            json={"role": "reviewer", "reason": "joining the review rota"},
            headers=admin_headers,
        )
        assert granted.status_code == 200, granted.text
        assert set(granted.json()["roles"]) == {"engineer", "reviewer"}
        assert "run.review" in granted.json()["capabilities"]

    def test_a_grant_without_a_reason_is_refused(self, client: TestClient, admin_headers) -> None:
        """The Users table is the first thing an auditor reads."""
        erin = _account(client, admin_headers, ENGINEER[0])
        refused = client.post(
            f"{API}/admin/users/{erin['id']}/roles",
            json={"role": "reviewer", "reason": ""},
            headers=admin_headers,
        )
        assert refused.status_code == 422

    def test_demo_owner_cannot_be_granted_here(self, client: TestClient, admin_headers) -> None:
        """Otherwise any administrator could make themselves a superuser.

        That role carries every capability at once, and the reason the
        packages do not nest is precisely that ``admin`` is not that.
        """
        erin = _account(client, admin_headers, ENGINEER[0])
        refused = client.post(
            f"{API}/admin/users/{erin['id']}/roles",
            json={"role": "demo_owner", "reason": "for the demo"},
            headers=admin_headers,
        )
        assert refused.status_code == 422
        assert "every capability" in refused.json()["error"]["message"]

    def test_an_unknown_role_says_what_the_roles_are(
        self, client: TestClient, admin_headers
    ) -> None:
        erin = _account(client, admin_headers, ENGINEER[0])
        refused = client.post(
            f"{API}/admin/users/{erin['id']}/roles",
            json={"role": "approver", "reason": "x"},
            headers=admin_headers,
        )
        assert refused.status_code == 422
        assert "engineer" in refused.json()["error"]["message"]


class TestTheDeploymentKeepsAWayBackIn:
    def test_the_last_account_that_can_manage_users_cannot_be_demoted(
        self, client: TestClient, admin_headers
    ) -> None:
        """Counted by capability, not by the name of a role.

        With ``demo_owner`` in the model, counting the ``admin`` role is
        wrong in both directions — it would let the last real
        administrator go while a demo account holds the keys, and block
        removing a demo account that a new administrator has replaced.
        """
        dave = _account(client, admin_headers, ADMIN[0])
        refused = client.delete(
            f"{API}/admin/users/{dave['id']}/roles/admin?reason=stepping+down",
            headers=admin_headers,
        )
        assert refused.status_code == 422
        assert "no enabled account able to manage" in refused.json()["error"]["message"]
        assert "admin" in _account(client, admin_headers, ADMIN[0])["roles"]

    def test_the_last_administrator_cannot_be_disabled_either(
        self, client: TestClient, admin_headers
    ) -> None:
        """Disabling is a role change in everything but name."""
        dave = _account(client, admin_headers, ADMIN[0])
        refused = client.post(
            f"{API}/admin/users/{dave['id']}/disable",
            json={"reason": "on leave"},
            headers=admin_headers,
        )
        assert refused.status_code == 422

    def test_stepping_down_works_once_somebody_else_can(
        self, client: TestClient, admin_headers
    ) -> None:
        erin = _account(client, admin_headers, ENGINEER[0])
        client.post(
            f"{API}/admin/users/{erin['id']}/roles",
            json={"role": "admin", "reason": "taking over"},
            headers=admin_headers,
        )
        dave = _account(client, admin_headers, ADMIN[0])
        stepped = client.delete(
            f"{API}/admin/users/{dave['id']}/roles/admin?reason=handed+over",
            headers=admin_headers,
        )
        assert stepped.status_code == 200, stepped.text
        assert "admin" not in stepped.json()["roles"]


class TestDisablingIsNotDeleting:
    def test_a_disabled_account_cannot_sign_in_but_keeps_its_row(
        self, client: TestClient, admin_headers
    ) -> None:
        """The audit trail points at user ids.

        Removing the row it points at turns every entry naming that
        person into a record of nobody.
        """
        erin = _account(client, admin_headers, ENGINEER[0])
        erin_headers = auth_headers(client, ENGINEER)
        client.post(
            f"{API}/admin/users/{erin['id']}/disable",
            json={"reason": "left the project"},
            headers=admin_headers,
        )
        assert client.get(f"{API}/auth/me", headers=erin_headers).status_code == 401
        assert _account(client, admin_headers, ENGINEER[0])["disabled"] is True

    def test_enabling_brings_them_back(self, client: TestClient, admin_headers) -> None:
        erin = _account(client, admin_headers, ENGINEER[0])
        client.post(
            f"{API}/admin/users/{erin['id']}/disable",
            json={"reason": "away"},
            headers=admin_headers,
        )
        client.post(
            f"{API}/admin/users/{erin['id']}/enable",
            json={"reason": "back"},
            headers=admin_headers,
        )
        assert _account(client, admin_headers, ENGINEER[0])["disabled"] is False
        assert (
            client.get(f"{API}/auth/me", headers=auth_headers(client, ENGINEER)).status_code == 200
        )


class TestTheTrail:
    def test_every_grant_lands_in_it_with_its_reason(
        self, client: TestClient, admin_headers
    ) -> None:
        erin = _account(client, admin_headers, ENGINEER[0])
        client.post(
            f"{API}/admin/users/{erin['id']}/roles",
            json={"role": "reviewer", "reason": "joining the rota"},
            headers=admin_headers,
        )
        events = client.get(f"{API}/admin/audit", headers=admin_headers).json()
        grant = next(event for event in events if event["action"] == "role_granted")
        assert grant["reason"] == "joining the rota"
        assert grant["previous"] == "engineer"
        assert "reviewer" in grant["new"]
        assert grant["authorized_capability"] == "user.manage"
        assert "admin" in grant["actor_roles"]

    def test_a_reviewer_sees_only_their_own_account_events(
        self, client: TestClient, admin_headers
    ) -> None:
        """``audit.read`` without ``user.manage`` is not the whole table.

        One route with a projection rather than two routes, so there is
        one place to remember to filter.
        """
        erin = _account(client, admin_headers, ENGINEER[0])
        client.post(
            f"{API}/admin/users/{erin['id']}/roles",
            json={"role": "reviewer", "reason": "rota"},
            headers=admin_headers,
        )
        seen = client.get(f"{API}/admin/audit", headers=auth_headers(client, ALICE)).json()
        assert all(
            event["user_id"] == _account(client, admin_headers, ALICE[0])["id"] for event in seen
        )
