"""Unit tests for Refresh Token issuance, rotation, and revocation."""

import pytest
from planbench_api.accounts import User
from planbench_api.auth import AuthError, AuthService
from planbench_api.config import Settings
from planbench_api.user_store import InMemoryUserRepository


def test_refresh_token_rotation():
    """Test issuing, refreshing, and rotation of refresh tokens."""
    settings = Settings(auth_secret="test_secret_key_12345", enable_dev_login=True)
    users = InMemoryUserRepository()
    user = users.create(nickname="alice", display_name="Alice", is_admin=False)

    auth = AuthService(settings, users)

    # Issue initial refresh token
    refresh_token_1 = auth.issue_refresh_token(user)
    assert refresh_token_1 is not None

    # Perform refresh rotation
    access_token, refresh_token_2, expires_in = auth.refresh(refresh_token_1)
    assert access_token is not None
    assert refresh_token_2 is not None
    assert refresh_token_2 != refresh_token_1
    assert expires_in > 0

    # Attempting to reuse old refresh token must fail
    with pytest.raises(AuthError) as exc_info:
        auth.refresh(refresh_token_1)
    assert "token" in str(exc_info.value).lower()


def test_refresh_token_revocation():
    """Test revoking a refresh token."""
    settings = Settings(auth_secret="test_secret_key_12345", enable_dev_login=True)
    users = InMemoryUserRepository()
    user = users.create(nickname="bob", display_name="Bob", is_admin=False)

    auth = AuthService(settings, users)
    refresh_token = auth.issue_refresh_token(user)

    # Revoke token
    auth.revoke(refresh_token)

    # Refreshing with revoked token should fail
    with pytest.raises(AuthError):
        auth.refresh(refresh_token)
