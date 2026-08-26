"""Sign in with Google and GitHub, with FastAPI as the authority.

The backend already owns JWT issuance and every permission check, so
putting the OAuth exchange anywhere else would create a second source of
truth about who someone is. The browser never sees a client secret and
never talks to a provider's token endpoint; it only follows a redirect
and, at the end, trades a short-lived one-time code for a PlanBench JWT.

The flow, and why each step is there:

1. ``/auth/oauth/{provider}/start`` mints a random ``state`` and (where
   the provider supports it) a PKCE verifier, seals both into a signed
   httpOnly cookie, and redirects to the provider. The cookie is signed
   rather than stored server-side so the flow survives more than one
   worker process.
2. The provider redirects back with ``code`` and ``state``. The state
   must match the sealed copy — that is the CSRF check, and a callback
   without a matching cookie is rejected rather than guessed at.
3. The backend exchanges the code for an access token **server-side**,
   reads the profile, and creates or updates the account.
4. It redirects to the frontend with a one-time code that expires in
   seconds. The JWT itself never appears in a URL, so it cannot be left
   behind in browser history, a Referer header, or a proxy log.

Two rules about identity that are easy to get wrong:

* **Only a verified email is trusted.** An unverified address proves
  nothing; treating it as an identity would let anyone claim an account
  by signing up elsewhere with the same address.
* **Matching emails never merge accounts.** Linking Google and GitHub to
  one account is something a signed-in member does deliberately via
  ``link``. Auto-merging on a shared address would let whoever controls
  either provider account take over the other.

No secret is read from anywhere but the environment, and none is logged.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from dataclasses import dataclass
from typing import Any

from planbench_api.accounts import AuthProvider

logger = logging.getLogger("planbench.api.oauth")

#: How long a start→callback round trip may take.
STATE_TTL_SECONDS = 600
#: How long the frontend has to trade the one-time code for a JWT. Short
#: because the code sits in a URL; the JWT it buys never does.
EXCHANGE_TTL_SECONDS = 120
STATE_COOKIE = "planbench_oauth"


class OAuthError(Exception):
    """The OAuth exchange failed or was rejected."""


@dataclass(frozen=True)
class ProviderConfig:
    """Endpoints and scopes for one identity provider."""

    provider: AuthProvider
    authorize_url: str
    token_url: str
    userinfo_url: str
    scopes: str
    #: GitHub's classic OAuth apps do not implement PKCE; Google does.
    #: Sending a challenge to a provider that ignores it is harmless, but
    #: claiming support we cannot verify is not, so this is explicit.
    supports_pkce: bool
    #: Extra endpoint used when the profile response omits the email.
    emails_url: str = ""


PROVIDERS: dict[AuthProvider, ProviderConfig] = {
    AuthProvider.GOOGLE: ProviderConfig(
        provider=AuthProvider.GOOGLE,
        authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        userinfo_url="https://openidconnect.googleapis.com/v1/userinfo",
        scopes="openid email profile",
        supports_pkce=True,
    ),
    AuthProvider.GITHUB: ProviderConfig(
        provider=AuthProvider.GITHUB,
        authorize_url="https://github.com/login/oauth/authorize",
        token_url="https://github.com/login/oauth/access_token",
        userinfo_url="https://api.github.com/user",
        emails_url="https://api.github.com/user/emails",
        scopes="read:user user:email",
        supports_pkce=False,
    ),
}


@dataclass(frozen=True)
class ProviderCredentials:
    client_id: str
    client_secret: str

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)


@dataclass(frozen=True)
class OAuthIdentity:
    """A provider profile, normalised.

    ``email`` is empty unless the provider said it is verified: a caller
    must not have to remember to check a separate flag.
    """

    provider: AuthProvider
    account_id: str
    email: str = ""
    display_name: str = ""
    avatar_url: str = ""


# -- signed state ------------------------------------------------------


def _sign(payload: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode(), payload, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def seal_state(data: dict[str, Any], secret: str) -> str:
    """Serialise and sign the flow state for the cookie."""
    body = dict(data)
    body["exp"] = int(time.time()) + STATE_TTL_SECONDS
    encoded = base64.urlsafe_b64encode(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).decode()
    return f"{encoded}.{_sign(encoded.encode(), secret)}"


def open_state(sealed: str, secret: str) -> dict[str, Any]:
    """Verify and decode the flow state, or raise :class:`OAuthError`."""
    try:
        encoded, signature = sealed.rsplit(".", 1)
    except ValueError:
        raise OAuthError("malformed OAuth state") from None
    # Constant-time: a timing oracle here would let an attacker forge the
    # CSRF token one byte at a time.
    if not hmac.compare_digest(signature, _sign(encoded.encode(), secret)):
        raise OAuthError("OAuth state failed signature validation")
    try:
        body = json.loads(base64.urlsafe_b64decode(encoded.encode()))
    except (ValueError, json.JSONDecodeError):
        raise OAuthError("malformed OAuth state") from None
    if int(body.get("exp", 0)) < time.time():
        raise OAuthError("the sign-in attempt expired; please start again")
    return body


def new_pkce_pair() -> tuple[str, str]:
    """A PKCE ``(verifier, S256 challenge)`` pair."""
    verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return verifier, challenge


def authorize_url(
    config: ProviderConfig,
    credentials: ProviderCredentials,
    *,
    redirect_uri: str,
    state: str,
    challenge: str | None,
) -> str:
    """The provider URL to send the browser to."""
    from urllib.parse import urlencode

    params = {
        "client_id": credentials.client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": config.scopes,
        "state": state,
    }
    if config.provider is AuthProvider.GOOGLE:
        # Ask for a fresh consent screen rather than silently reusing a
        # session, so "sign in with a different account" actually works.
        params["prompt"] = "select_account"
    if challenge and config.supports_pkce:
        params["code_challenge"] = challenge
        params["code_challenge_method"] = "S256"
    return f"{config.authorize_url}?{urlencode(params)}"


# -- the server-side exchange -----------------------------------------


class OAuthClient:
    """Talks to the provider. Split out so tests can replace it whole."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def exchange(
        self,
        config: ProviderConfig,
        credentials: ProviderCredentials,
        *,
        code: str,
        redirect_uri: str,
        verifier: str | None,
    ) -> str:
        """Trade the authorization code for an access token."""
        import httpx

        data = {
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
        if verifier and config.supports_pkce:
            data["code_verifier"] = verifier
        try:
            response = httpx.post(
                config.token_url,
                data=data,
                headers={"Accept": "application/json"},
                timeout=self._timeout,
            )
        except Exception as exc:  # network shape varies by failure
            raise OAuthError(f"could not reach {config.provider.value}: {exc}") from exc
        if response.status_code >= 400:
            # The body can echo the client_id; the status alone is enough
            # to act on and cannot leak a secret into the logs.
            raise OAuthError(
                f"{config.provider.value} rejected the authorization code "
                f"(HTTP {response.status_code})"
            )
        payload = response.json()
        token = payload.get("access_token")
        if not token:
            raise OAuthError(f"{config.provider.value} returned no access token")
        return str(token)

    def identity(self, config: ProviderConfig, access_token: str) -> OAuthIdentity:
        """Read the profile and normalise it."""
        import httpx

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        try:
            response = httpx.get(config.userinfo_url, headers=headers, timeout=self._timeout)
            response.raise_for_status()
            profile = response.json()
            emails: list[dict[str, Any]] = []
            if config.emails_url:
                extra = httpx.get(config.emails_url, headers=headers, timeout=self._timeout)
                if extra.status_code < 400:
                    emails = extra.json()
        except OAuthError:
            raise
        except Exception as exc:
            raise OAuthError(f"could not read the {config.provider.value} profile: {exc}") from exc
        return normalise_identity(config.provider, profile, emails)


def normalise_identity(
    provider: AuthProvider, profile: dict[str, Any], emails: list[dict[str, Any]] | None = None
) -> OAuthIdentity:
    """Map a provider profile onto :class:`OAuthIdentity`.

    Pure, so the shape of every provider response is testable without a
    network call — which is the only way this code gets exercised at all
    without live credentials.
    """
    if provider is AuthProvider.GOOGLE:
        account_id = str(profile.get("sub") or "")
        # Google reports verification per address; an unverified one is
        # not an identity.
        verified = bool(profile.get("email_verified"))
        email = str(profile.get("email") or "") if verified else ""
        return OAuthIdentity(
            provider=provider,
            account_id=account_id,
            email=email,
            display_name=str(profile.get("name") or ""),
            avatar_url=str(profile.get("picture") or ""),
        )

    account_id = str(profile.get("id") or "")
    email = ""
    for entry in emails or []:
        if entry.get("verified") and entry.get("primary"):
            email = str(entry.get("email") or "")
            break
    if not email:
        for entry in emails or []:
            if entry.get("verified"):
                email = str(entry.get("email") or "")
                break
    return OAuthIdentity(
        provider=provider,
        account_id=account_id,
        email=email,
        display_name=str(profile.get("name") or profile.get("login") or ""),
        avatar_url=str(profile.get("avatar_url") or ""),
    )


class ExchangeCodes:
    """One-time codes traded for a JWT right after the callback.

    In memory, because the codes live for seconds and losing them on a
    restart only means signing in again. It does mean a multi-worker
    deployment needs sticky routing or a shared store — recorded in
    docs/KNOWN_LIMITATIONS.md rather than papered over.
    """

    def __init__(self, ttl_seconds: int = EXCHANGE_TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._codes: dict[str, tuple[str, float]] = {}

    def issue(self, user_id: str) -> str:
        self._prune()
        code = secrets.token_urlsafe(32)
        self._codes[code] = (user_id, time.time() + self._ttl)
        return code

    def redeem(self, code: str) -> str:
        """Return the user id and burn the code."""
        self._prune()
        entry = self._codes.pop(code, None)
        if entry is None:
            raise OAuthError("this sign-in link has already been used or has expired")
        return entry[0]

    def _prune(self) -> None:
        now = time.time()
        for code in [code for code, (_, expiry) in self._codes.items() if expiry < now]:
            self._codes.pop(code, None)


__all__ = [
    "EXCHANGE_TTL_SECONDS",
    "PROVIDERS",
    "STATE_COOKIE",
    "STATE_TTL_SECONDS",
    "ExchangeCodes",
    "OAuthClient",
    "OAuthError",
    "OAuthIdentity",
    "ProviderConfig",
    "ProviderCredentials",
    "authorize_url",
    "new_pkce_pair",
    "normalise_identity",
    "open_state",
    "seal_state",
]
