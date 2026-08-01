"""Sign-in: OAuth with Google and GitHub, plus the optional dev login.

The browser's part of the OAuth flow is two redirects and one POST. It
never sees a client secret, never calls a provider's token endpoint, and
never receives the JWT in a URL — the callback hands back a one-time
code, and the code is exchanged over POST for the token.

Failures come back as ``?error=`` on the frontend callback route rather
than as a JSON error the browser would render as raw text: at that point
the user is mid-redirect and needs a page, not a payload.
"""

from __future__ import annotations

import logging
import secrets
from typing import Annotated
from urllib.parse import quote, urlencode

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from planbench_api.account_service import AccountService
from planbench_api.accounts import AccountError, AuthProvider, User, UserRole
from planbench_api.auth import AuthService, CurrentUser, get_auth
from planbench_api.config import Settings, get_settings, oauth_redirect_uri
from planbench_api.oauth import (
    PROVIDERS,
    STATE_COOKIE,
    STATE_TTL_SECONDS,
    ExchangeCodes,
    OAuthClient,
    OAuthError,
    ProviderCredentials,
    authorize_url,
    new_pkce_pair,
    open_state,
    seal_state,
)

logger = logging.getLogger("planbench.api.auth")

router = APIRouter(prefix="/auth", tags=["auth"])


class UserResource(BaseModel):
    """The signed-in account, as the frontend needs it."""

    id: str
    nickname: str
    email: str = ""
    display_name: str = ""
    avatar_url: str = ""
    is_admin: bool = False
    role: UserRole = UserRole.ENGINEER
    needs_nickname: bool = False
    providers: list[str] = []


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResource


class ExchangeRequest(BaseModel):
    code: str


class ProvidersResponse(BaseModel):
    """What sign-in methods this deployment actually offers.

    The login page renders from this rather than from its own build-time
    config, so a missing client id hides the button instead of producing
    a broken redirect.
    """

    google: bool
    github: bool
    dev_login: bool


class LinkStartResponse(BaseModel):
    authorize_url: str


def _accounts(request: Request) -> AccountService:
    settings = get_settings()
    return AccountService(
        request.app.state.repos.users,
        admin_nicknames=settings.admin_nicknames,
        admin_emails=settings.admin_emails,
    )


def _codes(request: Request) -> ExchangeCodes:
    return request.app.state.oauth_codes


def _client(request: Request) -> OAuthClient:
    return request.app.state.oauth_client


def _credentials(settings: Settings, provider: AuthProvider) -> ProviderCredentials:
    if provider is AuthProvider.GOOGLE:
        return ProviderCredentials(settings.google_client_id, settings.google_client_secret)
    return ProviderCredentials(settings.github_client_id, settings.github_client_secret)


def _resource(user: User, accounts: AccountService) -> UserResource:
    return UserResource(
        id=user.id,
        nickname=user.nickname,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        is_admin=user.is_admin,
        role=user.role,
        needs_nickname=user.needs_nickname,
        providers=[provider.value for provider in accounts.providers(user.id)],
    )


def _token_response(user: User, auth: AuthService, accounts: AccountService) -> TokenResponse:
    token, expires_in = auth.issue_token(user)
    return TokenResponse(access_token=token, expires_in=expires_in, user=_resource(user, accounts))


def _parse_provider(name: str) -> AuthProvider:
    try:
        return AuthProvider(name)
    except ValueError:
        raise OAuthError(f"unknown sign-in provider {name!r}") from None


# -- what this deployment offers --------------------------------------


@router.get("/providers", response_model=ProvidersResponse)
def providers(request: Request) -> ProvidersResponse:
    settings = get_settings()
    return ProvidersResponse(
        google=_credentials(settings, AuthProvider.GOOGLE).configured,
        github=_credentials(settings, AuthProvider.GITHUB).configured,
        dev_login=get_auth(request).dev_login_enabled,
    )


# -- password sign-in (development only) ------------------------------


@router.post("/login", response_model=TokenResponse)
def login(request: Request, form: Annotated[OAuth2PasswordRequestForm, Depends()]) -> TokenResponse:
    auth = get_auth(request)
    user = auth.authenticate(form.username, form.password)
    return _token_response(user, auth, _accounts(request))


@router.get("/me", response_model=UserResource)
def me(request: Request, user: CurrentUser) -> UserResource:
    return _resource(user, _accounts(request))


# -- OAuth ------------------------------------------------------------


def _begin(request: Request, provider: AuthProvider, link_user_id: str = "") -> tuple[str, str]:
    """Mint the flow state; return ``(authorize_url, sealed_state)``."""
    settings = get_settings()
    credentials = _credentials(settings, provider)
    if not credentials.configured:
        raise OAuthError(
            f"sign in with {provider.value} is not configured on this server; "
            f"set {provider.value.upper()}_CLIENT_ID and {provider.value.upper()}_CLIENT_SECRET"
        )
    config = PROVIDERS[provider]
    state = secrets.token_urlsafe(24)
    verifier, challenge = new_pkce_pair()
    sealed = seal_state(
        {
            "state": state,
            "provider": provider.value,
            # Only meaningful for PKCE providers; sealed either way so the
            # callback does not have to branch on it.
            "verifier": verifier,
            # Present only for "link this provider to my account".
            "link": link_user_id,
        },
        get_auth(request).secret,
    )
    url = authorize_url(
        config,
        credentials,
        redirect_uri=oauth_redirect_uri(settings, provider.value),
        state=state,
        challenge=challenge,
    )
    return url, sealed


def _set_state_cookie(response: Response, sealed: str) -> None:
    response.set_cookie(
        STATE_COOKIE,
        sealed,
        max_age=STATE_TTL_SECONDS,
        # httpOnly: no script needs it, and it is the CSRF token.
        httponly=True,
        # lax, not strict: the provider's redirect back is a cross-site
        # navigation, and strict would drop the cookie exactly then.
        samesite="lax",
        secure=get_settings().api_public_url.startswith("https"),
        path="/",
    )


@router.get("/oauth/{provider}/start")
def oauth_start(provider: str, request: Request) -> RedirectResponse:
    """Send the browser to the provider."""
    url, sealed = _begin(request, _parse_provider(provider))
    response = RedirectResponse(url, status_code=307)
    _set_state_cookie(response, sealed)
    return response


@router.post("/oauth/{provider}/link", response_model=LinkStartResponse)
def oauth_link_start(provider: str, request: Request, user: CurrentUser) -> Response:
    """Begin linking a second provider to the signed-in account.

    A POST carrying the bearer token, not a redirect carrying it in the
    query string: the account being linked to has to be proven, and
    proving it through a URL would leave the credential in history.
    """
    url, sealed = _begin(request, _parse_provider(provider), link_user_id=user.id)
    response = JSONResponse(LinkStartResponse(authorize_url=url).model_dump())
    _set_state_cookie(response, sealed)
    return response


@router.get("/oauth/{provider}/callback")
def oauth_callback(
    provider: str,
    request: Request,
    code: str = "",
    state: str = "",
    error: str = "",
) -> RedirectResponse:
    """Where the provider sends the browser back."""
    settings = get_settings()
    landing = f"{settings.web_app_url.rstrip('/')}/auth/callback"

    def failure(message: str) -> RedirectResponse:
        # Our message, never the provider's raw body — that can echo
        # request parameters straight back into a URL.
        response = RedirectResponse(f"{landing}?{urlencode({'error': message})}", status_code=307)
        response.delete_cookie(STATE_COOKIE, path="/")
        return response

    if error:
        return failure(f"{provider} sign-in was cancelled or refused")
    try:
        parsed = _parse_provider(provider)
        sealed = request.cookies.get(STATE_COOKIE, "")
        if not sealed:
            raise OAuthError(
                "the sign-in attempt could not be verified; start again from the login page"
            )
        body = open_state(sealed, get_auth(request).secret)
        if not state or body.get("state") != state:
            # The anti-CSRF check. A mismatch means this callback was not
            # started by this browser, so it is never "probably fine".
            raise OAuthError("the sign-in attempt could not be verified; please start again")
        if body.get("provider") != parsed.value:
            raise OAuthError("the sign-in attempt did not match this provider")
        if not code:
            raise OAuthError(f"{parsed.value} did not return an authorization code")

        client = _client(request)
        config = PROVIDERS[parsed]
        access_token = client.exchange(
            config,
            _credentials(settings, parsed),
            code=code,
            redirect_uri=oauth_redirect_uri(settings, parsed.value),
            verifier=str(body.get("verifier") or "") or None,
        )
        identity = client.identity(config, access_token)
        accounts = _accounts(request)
        link_user_id = str(body.get("link") or "")
        if link_user_id:
            accounts.link_provider(accounts.get(link_user_id), identity)
            user = accounts.get(link_user_id)
        else:
            user, _created = accounts.sign_in_with_provider(identity)
        exchange_code = _codes(request).issue(user.id)
    except (OAuthError, AccountError) as exc:
        # Our own message, and the only one that says what to do next.
        return failure(str(exc))
    except Exception as exc:  # noqa: BLE001 - the browser needs a page either way
        logger.exception("oauth callback failed: %s", exc)
        return failure("sign-in failed; please try again")

    response = RedirectResponse(f"{landing}?code={quote(exchange_code)}", status_code=307)
    response.delete_cookie(STATE_COOKIE, path="/")
    return response


@router.post("/oauth/exchange", response_model=TokenResponse)
def oauth_exchange(payload: ExchangeRequest, request: Request) -> TokenResponse:
    """Trade the one-time callback code for a PlanBench token."""
    user_id = _codes(request).redeem(payload.code)
    accounts = _accounts(request)
    return _token_response(accounts.get(user_id), get_auth(request), accounts)
