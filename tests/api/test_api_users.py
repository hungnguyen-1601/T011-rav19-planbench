"""Nicknames: choosing one, and finding other members by one.

A nickname is a lookup key, never an authorization key. These tests hold
both halves of that: it must be unique and case-insensitive enough that
"send this to bob" is unambiguous, and changing it must not change what
anybody is allowed to do.
"""

from __future__ import annotations

import pytest
from conftest import ALICE, auth_headers
from fastapi.testclient import TestClient
from test_api_benchmarks import create_benchmark

from planbench_api.accounts import NICKNAME_MAX, NICKNAME_MIN, NicknameError, validate_nickname


class TestValidation:
    """The rules, at the level they are defined."""

    @pytest.mark.parametrize("nickname", ["abc", "alice", "a-b_c", "Alice99", "x" * NICKNAME_MAX])
    def test_accepts_letters_digits_hyphen_and_underscore(self, nickname: str) -> None:
        assert validate_nickname(nickname) == nickname.strip()

    @pytest.mark.parametrize(
        ("nickname", "because"),
        [
            ("ab", "too short"),
            ("x" * (NICKNAME_MAX + 1), "too long"),
            ("", "empty"),
            ("alice bob", "whitespace"),
            ("alice\tbob", "whitespace"),
            ("alice@example", "punctuation"),
            ("alice.bob", "punctuation"),
            ("ali/ce", "punctuation"),
            ("émile", "non-ascii"),
        ],
    )
    def test_rejects_everything_else(self, nickname: str, because: str) -> None:
        with pytest.raises(NicknameError):
            validate_nickname(nickname)

    def test_surrounding_whitespace_is_trimmed_not_rejected(self) -> None:
        """A pasted nickname with a trailing space is a typo, not an attack."""
        assert validate_nickname("  alice  ") == "alice"

    def test_the_minimum_is_what_the_message_says(self) -> None:
        with pytest.raises(NicknameError, match=str(NICKNAME_MIN)):
            validate_nickname("ab")


class TestChoosingANickname:
    def test_a_member_can_set_theirs(self, client: TestClient, alice_headers) -> None:
        response = client.put(
            "/api/v1/users/me/nickname", json={"nickname": "alice-renamed"}, headers=alice_headers
        )
        assert response.status_code == 200, response.text
        assert response.json()["nickname"] == "alice-renamed"
        assert response.json()["needs_nickname"] is False

    def test_a_taken_nickname_is_refused_case_insensitively(
        self, client: TestClient, alice_headers, bob_headers
    ) -> None:
        response = client.put(
            "/api/v1/users/me/nickname", json={"nickname": "ALICE"}, headers=bob_headers
        )
        assert response.status_code == 422
        assert "already taken" in response.json()["error"]["message"]

    def test_an_invalid_nickname_is_refused_with_the_rule(
        self, client: TestClient, alice_headers
    ) -> None:
        response = client.put(
            "/api/v1/users/me/nickname", json={"nickname": "not valid!"}, headers=alice_headers
        )
        assert response.status_code == 422
        assert "letters" in response.json()["error"]["message"]

    def test_keeping_your_own_nickname_is_not_a_conflict(
        self, client: TestClient, alice_headers
    ) -> None:
        response = client.put(
            "/api/v1/users/me/nickname", json={"nickname": "Alice"}, headers=alice_headers
        )
        assert response.status_code == 200
        assert response.json()["nickname"] == "Alice"

    def test_availability_is_answered_without_an_error(
        self, client: TestClient, alice_headers
    ) -> None:
        """Called per keystroke: invalid must be an answer, not a 422."""
        taken = client.get(
            "/api/v1/users/nickname-available", params={"nickname": "alice"}, headers=alice_headers
        ).json()
        assert taken == {
            "nickname": "alice",
            "available": False,
            "valid": True,
            "message": "that nickname is already taken",
        }

        free = client.get(
            "/api/v1/users/nickname-available",
            params={"nickname": "brand-new"},
            headers=alice_headers,
        ).json()
        assert free["available"] is True and free["valid"] is True

        invalid = client.get(
            "/api/v1/users/nickname-available", params={"nickname": "no"}, headers=alice_headers
        ).json()
        assert invalid["valid"] is False and invalid["available"] is False
        assert invalid["message"]


class TestSearch:
    def test_finds_members_by_prefix(self, client: TestClient, alice_headers) -> None:
        results = client.get(
            "/api/v1/users/search", params={"nickname": "b"}, headers=alice_headers
        ).json()
        assert [user["nickname"] for user in results] == ["bob"]

    def test_is_case_insensitive(self, client: TestClient, alice_headers) -> None:
        results = client.get(
            "/api/v1/users/search", params={"nickname": "BO"}, headers=alice_headers
        ).json()
        assert [user["nickname"] for user in results] == ["bob"]

    def test_returns_nothing_for_an_unknown_prefix(self, client: TestClient, alice_headers) -> None:
        results = client.get(
            "/api/v1/users/search", params={"nickname": "zzz"}, headers=alice_headers
        ).json()
        assert results == []

    def test_exposes_no_email_and_no_admin_flag(self, client: TestClient, alice_headers) -> None:
        """Anyone can search, so the result must be safe for anyone."""
        results = client.get(
            "/api/v1/users/search", params={"nickname": "dave"}, headers=alice_headers
        ).json()
        assert results
        assert set(results[0]) == {"id", "nickname", "display_name", "avatar_url"}

    def test_requires_a_signed_in_member(self, client: TestClient) -> None:
        assert client.get("/api/v1/users/search", params={"nickname": "bob"}).status_code == 401


class TestNicknameIsNotAnAuthorizationKey:
    def test_renaming_does_not_change_what_you_own(
        self, client: TestClient, created_map, created_scenario, alice_headers
    ) -> None:
        benchmark = create_benchmark(client, created_map, created_scenario, alice_headers)
        client.put(
            "/api/v1/users/me/nickname", json={"nickname": "alice-v2"}, headers=alice_headers
        )
        # Still hers: ownership is by id, and the token still resolves.
        after = client.get(f"/api/v1/benchmarks/{benchmark['id']}", headers=alice_headers).json()
        assert after["is_owner"] is True
        run = client.post(f"/api/v1/benchmarks/{benchmark['id']}/run", headers=alice_headers)
        assert run.status_code == 200, run.text

    def test_taking_a_freed_nickname_does_not_inherit_anything(
        self, client: TestClient, created_map, created_scenario, alice_headers, bob_headers
    ) -> None:
        """The nastiest version of the rule: impersonation by rename."""
        benchmark = create_benchmark(client, created_map, created_scenario, alice_headers)
        client.put(
            "/api/v1/users/me/nickname", json={"nickname": "alice-v2"}, headers=alice_headers
        )
        # Bob takes the name Alice just gave up.
        assert (
            client.put(
                "/api/v1/users/me/nickname", json={"nickname": "alice"}, headers=bob_headers
            ).status_code
            == 200
        )
        seen = client.get(f"/api/v1/benchmarks/{benchmark['id']}", headers=bob_headers).json()
        assert seen["is_owner"] is False
        assert (
            client.post(
                f"/api/v1/benchmarks/{benchmark['id']}/run", headers=bob_headers
            ).status_code
            == 403
        )

    def test_a_token_survives_its_owner_being_renamed(self, client: TestClient) -> None:
        headers = auth_headers(client, ALICE)
        client.put("/api/v1/users/me/nickname", json={"nickname": "renamed"}, headers=headers)
        me = client.get("/api/v1/auth/me", headers=headers)
        assert me.status_code == 200
        assert me.json()["nickname"] == "renamed"
