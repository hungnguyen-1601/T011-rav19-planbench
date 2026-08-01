"""Sign in with Google and GitHub, against a fake provider.

**No test here touches the network.** The provider client is replaced
wholesale with a stub that returns the payloads Google and GitHub
actually send. That is not a shortcut around testing the real thing — it
is the only way to test this at all without live credentials, and it
means the suite gives the same answer on a laptop, in CI, and in a
checkout with no OAuth configured.

What the stub cannot prove is recorded in docs/KNOWN_LIMITATIONS.md: that
the real endpoints still speak this shape.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest
from conftest import isolate_environment
from fastapi.testclient import TestClient

from planbench_api.accounts import AuthProvider
from planbench_api.config import get_settings
from planbench_api.main import create_app
from planbench_api.oauth import (
    STATE_COOKIE,
    OAuthError,
    OAuthIdentity,
    normalise_identity,
    open_state,
    seal_state,
)

GOOGLE_PROFILE = {
    "sub": "google-account-1",
    "email": "alice@example.com",
    "email_verified": True,
    "name": "Alice Example",
    "picture": "https://example.com/a.png",
}

GITHUB_PROFILE = {"id": 4242, "login": "alice-gh", "avatar_url": "https://example.com/gh.png"}
GITHUB_EMAILS = [
    {"email": "old@example.com", "primary": False, "verified": True},
    {"email": "alice@users.noreply.github.com", "primary": True, "verified": True},
]


class FakeOAuthClient:
    """Stands in for the provider. Records what it was asked for."""

    def __init__(self, identity: OAuthIdentity | None = None) -> None:
        self.identity_to_return = identity
        self.exchanges: list[dict] = []

    def exchange(self, config, credentials, *, code, redirect_uri, verifier):
        self.exchanges.append(
            {
                "provider": config.provider.value,
                "code": code,
                "redirect_uri": redirect_uri,
                "verifier": verifier,
                "client_secret": credentials.client_secret,
            }
        )
        return "provider-access-token"

    def identity(self, config, access_token):
        if self.identity_to_return is not None:
            return self.identity_to_return
        if config.provider is AuthProvider.GOOGLE:
            return normalise_identity(AuthProvider.GOOGLE, GOOGLE_PROFILE)
        return normalise_identity(AuthProvider.GITHUB, GITHUB_PROFILE, GITHUB_EMAILS)


@pytest.fixture
def oauth_app(tmp_path, monkeypatch):
    """An app with both providers configured with placeholder credentials."""
    isolate_environment(monkeypatch)
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "google-client-id-placeholder")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "google-client-secret-placeholder")
    monkeypatch.setenv("GITHUB_CLIENT_ID", "github-client-id-placeholder")
    monkeypatch.setenv("GITHUB_CLIENT_SECRET", "github-client-secret-placeholder")
    get_settings.cache_clear()
    application = create_app(artifact_dir=str(tmp_path / "artifacts"))
    application.state.oauth_client = FakeOAuthClient()
    yield application
    get_settings.cache_clear()


@pytest.fixture
def oauth_client(oauth_app) -> TestClient:
    # follow_redirects=False so each hop can be inspected: the whole
    # point is what happens between them.
    return TestClient(oauth_app, raise_server_exceptions=False, follow_redirects=False)


def start(client: TestClient, provider: str = "google"):
    response = client.get(f"/api/v1/auth/oauth/{provider}/start")
    assert response.status_code == 307, response.text
    return response


def sign_in(client: TestClient, provider: str = "google") -> dict:
    """The whole flow: start, callback, exchange the one-time code."""
    started = start(client, provider)
    state = parse_qs(urlparse(started.headers["location"]).query)["state"][0]
    callback = client.get(
        f"/api/v1/auth/oauth/{provider}/callback", params={"code": "provider-code", "state": state}
    )
    assert callback.status_code == 307, callback.text
    code = parse_qs(urlparse(callback.headers["location"]).query)["code"][0]
    token = client.post("/api/v1/auth/oauth/exchange", json={"code": code})
    assert token.status_code == 200, token.text
    return token.json()


class TestTheAuthorizeRedirect:
    def test_google_gets_pkce_and_the_derived_redirect_uri(self, oauth_client) -> None:
        query = parse_qs(urlparse(start(oauth_client, "google").headers["location"]).query)
        assert query["client_id"] == ["google-client-id-placeholder"]
        assert query["response_type"] == ["code"]
        assert query["code_challenge_method"] == ["S256"]
        assert query["code_challenge"][0]
        assert query["redirect_uri"] == ["http://localhost:8000/api/v1/auth/oauth/google/callback"]

    def test_github_gets_no_pkce_because_it_does_not_implement_it(self, oauth_client) -> None:
        query = parse_qs(urlparse(start(oauth_client, "github").headers["location"]).query)
        assert "code_challenge" not in query
        assert query["scope"] == ["read:user user:email"]

    def test_the_client_secret_never_leaves_the_server(self, oauth_client) -> None:
        response = start(oauth_client)
        assert "secret" not in response.headers["location"]
        assert "google-client-secret-placeholder" not in response.headers["location"]
        assert "google-client-secret-placeholder" not in str(response.headers)

    def test_the_state_cookie_is_httponly_and_scoped(self, oauth_client) -> None:
        header = start(oauth_client).headers["set-cookie"]
        assert STATE_COOKIE in header
        assert "HttpOnly" in header
        assert "samesite=lax" in header.lower()
        assert "Path=/" in header

    def test_an_unconfigured_provider_says_which_variables_to_set(self, client: TestClient) -> None:
        """The default checkout has no OAuth: it must explain, not crash."""
        response = client.get("/api/v1/auth/oauth/google/start", follow_redirects=False)
        assert response.status_code == 400
        message = response.json()["error"]["message"]
        assert "GOOGLE_CLIENT_ID" in message and "GOOGLE_CLIENT_SECRET" in message

    def test_an_unknown_provider_is_refused(self, oauth_client) -> None:
        assert oauth_client.get("/api/v1/auth/oauth/facebook/start").status_code == 400


class TestSignIn:
    def test_google_creates_an_account_that_still_needs_a_nickname(self, oauth_client) -> None:
        body = sign_in(oauth_client, "google")
        assert body["access_token"]
        assert body["user"]["email"] == "alice@example.com"
        assert body["user"]["display_name"] == "Alice Example"
        assert body["user"]["providers"] == ["google"]
        # Onboarding is a separate step; nothing invents a nickname.
        assert body["user"]["nickname"] == ""
        assert body["user"]["needs_nickname"] is True

    def test_github_signs_in_with_its_verified_primary_email(self, oauth_client) -> None:
        body = sign_in(oauth_client, "github")
        assert body["user"]["email"] == "alice@users.noreply.github.com"
        assert body["user"]["providers"] == ["github"]

    def test_signing_in_twice_returns_the_same_account(self, oauth_client) -> None:
        first = sign_in(oauth_client, "google")
        second = sign_in(oauth_client, "google")
        assert first["user"]["id"] == second["user"]["id"]

    def test_the_exchange_happens_server_side_with_the_secret(self, oauth_app) -> None:
        client = TestClient(oauth_app, raise_server_exceptions=False, follow_redirects=False)
        sign_in(client, "google")
        exchange = oauth_app.state.oauth_client.exchanges[-1]
        assert exchange["client_secret"] == "google-client-secret-placeholder"
        assert exchange["verifier"], "PKCE verifier must reach the token endpoint"

    def test_the_jwt_never_appears_in_a_url(self, oauth_client) -> None:
        """The callback hands back a one-time code, not the token."""
        started = start(oauth_client)
        state = parse_qs(urlparse(started.headers["location"]).query)["state"][0]
        callback = oauth_client.get(
            "/api/v1/auth/oauth/google/callback",
            params={"code": "provider-code", "state": state},
        )
        location = callback.headers["location"]
        code = parse_qs(urlparse(location).query)["code"][0]
        assert "access_token" not in location
        # A JWT has two dots; the exchange code must not be one.
        assert code.count(".") != 2

        token = oauth_client.post("/api/v1/auth/oauth/exchange", json={"code": code}).json()
        assert token["access_token"].count(".") == 2

    def test_the_one_time_code_cannot_be_replayed(self, oauth_client) -> None:
        started = start(oauth_client)
        state = parse_qs(urlparse(started.headers["location"]).query)["state"][0]
        callback = oauth_client.get(
            "/api/v1/auth/oauth/google/callback",
            params={"code": "provider-code", "state": state},
        )
        code = parse_qs(urlparse(callback.headers["location"]).query)["code"][0]
        assert (
            oauth_client.post("/api/v1/auth/oauth/exchange", json={"code": code}).status_code == 200
        )
        replay = oauth_client.post("/api/v1/auth/oauth/exchange", json={"code": code})
        assert replay.status_code == 400
        assert "already been used" in replay.json()["error"]["message"]

    def test_the_token_works_on_the_rest_of_the_api(self, oauth_client) -> None:
        token = sign_in(oauth_client, "google")["access_token"]
        me = oauth_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["email"] == "alice@example.com"


class TestCsrfProtection:
    def test_a_callback_without_the_cookie_is_refused(self, oauth_client) -> None:
        response = oauth_client.get(
            "/api/v1/auth/oauth/google/callback",
            params={"code": "provider-code", "state": "anything"},
        )
        assert response.status_code == 307
        assert "error=" in response.headers["location"]
        assert "could not be verified" in response.headers["location"].replace("+", " ")

    def test_a_mismatched_state_is_refused(self, oauth_client) -> None:
        start(oauth_client)  # the cookie is now set
        response = oauth_client.get(
            "/api/v1/auth/oauth/google/callback",
            params={"code": "provider-code", "state": "not-the-one-we-issued"},
        )
        assert "error=" in response.headers["location"]

    def test_a_state_signed_with_another_secret_is_refused(self, oauth_client) -> None:
        forged = seal_state(
            {"state": "x", "provider": "google", "verifier": "", "link": ""}, "wrong"
        )
        oauth_client.cookies.set(STATE_COOKIE, forged)
        response = oauth_client.get(
            "/api/v1/auth/oauth/google/callback", params={"code": "c", "state": "x"}
        )
        assert "error=" in response.headers["location"]

    def test_a_state_issued_for_another_provider_is_refused(self, oauth_client) -> None:
        started = start(oauth_client, "google")
        state = parse_qs(urlparse(started.headers["location"]).query)["state"][0]
        response = oauth_client.get(
            "/api/v1/auth/oauth/github/callback", params={"code": "c", "state": state}
        )
        assert "error=" in response.headers["location"]

    def test_a_provider_refusal_becomes_a_readable_error_page(self, oauth_client) -> None:
        response = oauth_client.get(
            "/api/v1/auth/oauth/google/callback", params={"error": "access_denied"}
        )
        assert response.status_code == 307
        assert "error=" in response.headers["location"]
        assert response.headers["location"].startswith("http://localhost:3000/auth/callback")


class TestAccountsAreNotMergedByEmail:
    def test_two_providers_with_the_same_email_are_two_accounts(self, oauth_app) -> None:
        """Auto-merging would let either provider account take the other."""
        client = TestClient(oauth_app, raise_server_exceptions=False, follow_redirects=False)
        google = sign_in(client, "google")

        # GitHub, same verified address, different provider identity.
        oauth_app.state.oauth_client = FakeOAuthClient(
            OAuthIdentity(
                provider=AuthProvider.GITHUB,
                account_id="github-99",
                email="alice@example.com",
                display_name="Alice",
            )
        )
        github = sign_in(client, "github")
        assert github["user"]["id"] != google["user"]["id"]
        assert github["user"]["providers"] == ["github"]

    def test_one_provider_identity_cannot_be_linked_to_two_accounts(self, oauth_app) -> None:
        client = TestClient(oauth_app, raise_server_exceptions=False, follow_redirects=False)
        # Alice signs in with Google and takes a nickname.
        alice = sign_in(client, "google")
        # Bob signs in with GitHub.
        oauth_app.state.oauth_client = FakeOAuthClient(
            OAuthIdentity(
                provider=AuthProvider.GITHUB, account_id="github-bob", email="bob@example.com"
            )
        )
        bob = sign_in(client, "github")
        assert bob["user"]["id"] != alice["user"]["id"]

        # Bob now tries to link Alice's Google identity to his account.
        oauth_app.state.oauth_client = FakeOAuthClient(
            normalise_identity(AuthProvider.GOOGLE, GOOGLE_PROFILE)
        )
        started = client.post(
            "/api/v1/auth/oauth/google/link",
            headers={"Authorization": f"Bearer {bob['access_token']}"},
        )
        assert started.status_code == 200, started.text
        state = parse_qs(urlparse(started.json()["authorize_url"]).query)["state"][0]
        callback = client.get(
            "/api/v1/auth/oauth/google/callback", params={"code": "c", "state": state}
        )
        assert "error=" in callback.headers["location"]
        assert "already linked" in callback.headers["location"].replace("+", " ")


class TestLinkingASecondProvider:
    def test_a_signed_in_member_can_link_github_to_their_google_account(self, oauth_app) -> None:
        client = TestClient(oauth_app, raise_server_exceptions=False, follow_redirects=False)
        session = sign_in(client, "google")
        headers = {"Authorization": f"Bearer {session['access_token']}"}

        oauth_app.state.oauth_client = FakeOAuthClient(
            normalise_identity(AuthProvider.GITHUB, GITHUB_PROFILE, GITHUB_EMAILS)
        )
        started = client.post("/api/v1/auth/oauth/github/link", headers=headers)
        assert started.status_code == 200, started.text
        state = parse_qs(urlparse(started.json()["authorize_url"]).query)["state"][0]
        callback = client.get(
            "/api/v1/auth/oauth/github/callback", params={"code": "c", "state": state}
        )
        assert "error=" not in callback.headers["location"], callback.headers["location"]

        me = client.get("/api/v1/auth/me", headers=headers).json()
        assert sorted(me["providers"]) == ["github", "google"]
        # Still one account, and it kept its own email.
        assert me["id"] == session["user"]["id"]
        assert me["email"] == "alice@example.com"

    def test_linking_requires_being_signed_in(self, oauth_client) -> None:
        assert oauth_client.post("/api/v1/auth/oauth/github/link").status_code == 401

    def test_signing_in_with_the_linked_provider_reaches_the_same_account(self, oauth_app) -> None:
        """The point of linking: one identity, two front doors."""
        client = TestClient(oauth_app, raise_server_exceptions=False, follow_redirects=False)
        session = sign_in(client, "google")
        headers = {"Authorization": f"Bearer {session['access_token']}"}
        oauth_app.state.oauth_client = FakeOAuthClient(
            normalise_identity(AuthProvider.GITHUB, GITHUB_PROFILE, GITHUB_EMAILS)
        )
        started = client.post("/api/v1/auth/oauth/github/link", headers=headers)
        state = parse_qs(urlparse(started.json()["authorize_url"]).query)["state"][0]
        client.get("/api/v1/auth/oauth/github/callback", params={"code": "c", "state": state})

        again = sign_in(client, "github")
        assert again["user"]["id"] == session["user"]["id"]


class TestIdentityNormalisation:
    """Pure mapping of provider payloads. No app, no network."""

    def test_google_verified_email_is_trusted(self) -> None:
        identity = normalise_identity(AuthProvider.GOOGLE, GOOGLE_PROFILE)
        assert identity.account_id == "google-account-1"
        assert identity.email == "alice@example.com"

    def test_google_unverified_email_is_dropped(self) -> None:
        """An unverified address proves nothing and must not become an identity."""
        profile = {**GOOGLE_PROFILE, "email_verified": False}
        assert normalise_identity(AuthProvider.GOOGLE, profile).email == ""
        # The account id is still usable, so sign-in works without an email.
        assert normalise_identity(AuthProvider.GOOGLE, profile).account_id == "google-account-1"

    def test_github_prefers_the_primary_verified_address(self) -> None:
        identity = normalise_identity(AuthProvider.GITHUB, GITHUB_PROFILE, GITHUB_EMAILS)
        assert identity.email == "alice@users.noreply.github.com"

    def test_github_falls_back_to_any_verified_address(self) -> None:
        emails = [{"email": "only@example.com", "primary": False, "verified": True}]
        assert normalise_identity(AuthProvider.GITHUB, GITHUB_PROFILE, emails).email == (
            "only@example.com"
        )

    def test_github_unverified_addresses_are_ignored(self) -> None:
        emails = [{"email": "spoofed@example.com", "primary": True, "verified": False}]
        assert normalise_identity(AuthProvider.GITHUB, GITHUB_PROFILE, emails).email == ""

    def test_github_falls_back_to_the_login_for_a_display_name(self) -> None:
        assert normalise_identity(AuthProvider.GITHUB, GITHUB_PROFILE).display_name == "alice-gh"


class TestSealedState:
    SECRET = "state-signing-secret-for-tests"

    def test_round_trips(self) -> None:
        sealed = seal_state({"state": "abc", "provider": "google"}, self.SECRET)
        assert open_state(sealed, self.SECRET)["state"] == "abc"

    def test_a_tampered_payload_is_rejected(self) -> None:
        sealed = seal_state({"state": "abc"}, self.SECRET)
        body, signature = sealed.rsplit(".", 1)
        with pytest.raises(OAuthError, match="signature"):
            open_state(f"{body}x.{signature}", self.SECRET)

    def test_another_secret_cannot_open_it(self) -> None:
        with pytest.raises(OAuthError):
            open_state(seal_state({"state": "abc"}, self.SECRET), "different-secret")

    def test_a_malformed_value_is_rejected_rather_than_crashing(self) -> None:
        with pytest.raises(OAuthError, match="malformed"):
            open_state("not-sealed-at-all", self.SECRET)
