"""The settings page: saving an API key, and everything it must not do.

Three properties are worth a test each, and each one is here because
getting it wrong is silent rather than loud.

A key that is saved but not applied looks identical to a key that was
applied — the page comes back green either way, and the difference only
shows up as the assistant still answering from the offline responder.

A key that reaches ``.env`` but overwrites the first of two declarations
is worse: the file looks right to a reader and `dotenv` still returns
the stale value.

And a key that comes back out of the API undoes the reason for having
put it behind an admin check at all.
"""

from __future__ import annotations

import os

import pytest
from conftest import ADMIN, ALICE, auth_headers
from fastapi.testclient import TestClient

from planbench_api.config import write_env_values


@pytest.fixture
def settings_env(monkeypatch, tmp_path):
    """Run each case with its own ``.env`` and no inherited key.

    ``os.chdir`` rather than a parameter: the endpoint writes the same
    relative ``.env`` that :func:`load_provider_keys` reads, and pinning
    that path in the test would be testing a different code path from the
    one production takes.
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "PLANBENCH_AGENT_MODEL=stale\n# a comment worth keeping\n",
        encoding="utf-8",
    )
    return tmp_path


def test_reading_settings_reports_no_key_before_one_is_saved(
    client: TestClient, alice_headers, settings_env
) -> None:
    response = client.get("/api/v1/settings/agent", headers=alice_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["key_present"] is False
    assert body["key_hint"] == ""
    assert body["model"] == "o4-mini"
    assert body["models"] == ["o4-mini"]
    # The mock is what conftest pins, and the page must say so rather
    # than let a reader assume a model is answering.
    assert body["active_deterministic"] is True


def test_a_member_may_not_save_the_shared_key(
    client: TestClient, alice_headers, settings_env
) -> None:
    response = client.put(
        "/api/v1/settings/agent",
        headers=alice_headers,
        json={"api_key": "sk-test-member-attempt"},
    )
    assert response.status_code == 403, response.text
    assert os.environ.get("OPENAI_API_KEY") in (None, "")
    assert "OPENAI_API_KEY" not in (settings_env / ".env").read_text(encoding="utf-8")


def test_saving_a_key_switches_the_live_provider_without_a_restart(
    client: TestClient, app, admin_headers, settings_env, monkeypatch
) -> None:
    """The assignment to ``app.state`` is the point of the endpoint.

    ``build_provider`` is stubbed because the real one would construct an
    OpenAI client: the claim under test is that the provider in use is
    rebuilt and replaced, not that the SDK works.
    """
    built: list[tuple[str, str | None]] = []

    class FakeProvider:
        name = "openai"
        model = "o4-mini"
        deterministic = False

    def fake_build(kind: str, *, model: str | None = None, **_: object) -> FakeProvider:
        built.append((kind, model))
        return FakeProvider()

    monkeypatch.setattr("planbench_api.routers.settings.build_provider", fake_build)
    before = app.state.agent_provider

    response = client.put(
        "/api/v1/settings/agent",
        headers=admin_headers,
        json={"api_key": "sk-test-0123456789abcdef"},
    )

    assert response.status_code == 200, response.text
    assert built == [("openai", "o4-mini")]
    assert app.state.agent_provider is not before
    assert app.state.agent_provider.deterministic is False
    assert os.environ["OPENAI_API_KEY"] == "sk-test-0123456789abcdef"


def test_the_saved_key_never_comes_back_out(
    client: TestClient, admin_headers, settings_env, monkeypatch
) -> None:
    monkeypatch.setattr(
        "planbench_api.routers.settings.build_provider",
        lambda *a, **k: type(
            "P", (), {"name": "openai", "model": "o4-mini", "deterministic": False}
        )(),
    )
    secret = "sk-test-abcdefghijklmnop9876"

    saved = client.put(
        "/api/v1/settings/agent", headers=admin_headers, json={"api_key": secret}
    ).json()
    read_back = client.get("/api/v1/settings/agent", headers=admin_headers).json()

    for body in (saved, read_back):
        assert secret not in str(body)
        assert body["key_present"] is True
        assert body["key_hint"] == "••••9876"


def test_saving_persists_the_provider_choice_for_the_next_restart(
    client: TestClient, admin_headers, settings_env, monkeypatch
) -> None:
    """`.env` carries provider and model too, not only the key.

    Without them a restart reads ``PLANBENCH_AGENT_PROVIDER`` as whatever
    it was before — for a fresh deployment, `auto`, which falls back to
    the offline responder instead of failing on a bad key.
    """
    monkeypatch.setattr(
        "planbench_api.routers.settings.build_provider",
        lambda *a, **k: type(
            "P", (), {"name": "openai", "model": "o4-mini", "deterministic": False}
        )(),
    )
    client.put(
        "/api/v1/settings/agent", headers=admin_headers, json={"api_key": "sk-test-persisted-1234"}
    )

    written = (settings_env / ".env").read_text(encoding="utf-8")
    assert "PLANBENCH_AGENT_PROVIDER=openai" in written
    assert "PLANBENCH_AGENT_MODEL=o4-mini" in written
    assert "PLANBENCH_AGENT_MODEL=stale" not in written
    assert "# a comment worth keeping" in written


def test_every_declaration_of_a_key_is_rewritten_not_just_the_first(tmp_path) -> None:
    """The `.env` in this repository declares OPENAI_API_KEY twice.

    ``dotenv_values`` returns the last one. A writer that stopped at the
    first would leave the stale value winning while the file looked
    correct to anyone reading it top to bottom.
    """
    env = tmp_path / ".env"
    env.write_text(
        "OPENAI_API_KEY=first-and-stale\n"
        "PLANBENCH_DATABASE_URL=sqlite:///keep.db\n"
        "OPENAI_API_KEY=second-and-winning\n",
        encoding="utf-8",
    )

    write_env_values({"OPENAI_API_KEY": "fresh"}, env_file=env)

    lines = env.read_text(encoding="utf-8").splitlines()
    assert [line for line in lines if line.startswith("OPENAI_API_KEY")] == [
        "OPENAI_API_KEY=fresh",
        "OPENAI_API_KEY=fresh",
    ]
    assert "PLANBENCH_DATABASE_URL=sqlite:///keep.db" in lines


def test_a_variable_outside_the_allowlist_is_refused(tmp_path) -> None:
    """The same file holds the session secret and the database URL."""
    env = tmp_path / ".env"
    env.write_text("AUTH_SECRET=original\n", encoding="utf-8")

    with pytest.raises(ValueError, match="AUTH_SECRET"):
        write_env_values({"AUTH_SECRET": "hijacked"}, env_file=env)

    assert env.read_text(encoding="utf-8") == "AUTH_SECRET=original\n"


def test_a_value_carrying_a_line_break_is_refused(tmp_path) -> None:
    """Otherwise a key could append arbitrary variables of its own."""
    env = tmp_path / ".env"
    env.write_text("OPENAI_API_KEY=old\n", encoding="utf-8")

    with pytest.raises(ValueError, match="line break"):
        write_env_values({"OPENAI_API_KEY": "sk-x\nAUTH_SECRET=hijacked"}, env_file=env)

    assert env.read_text(encoding="utf-8") == "OPENAI_API_KEY=old\n"


def test_a_missing_variable_is_appended_rather_than_lost(tmp_path) -> None:
    env = tmp_path / ".env"
    env.write_text("# only a comment\n", encoding="utf-8")

    write_env_values({"OPENAI_API_KEY": "sk-appended"}, env_file=env)

    body = env.read_text(encoding="utf-8")
    assert "# only a comment" in body
    assert "OPENAI_API_KEY=sk-appended" in body


def test_settings_require_a_signed_in_reader(client: TestClient, settings_env) -> None:
    assert client.get("/api/v1/settings/agent").status_code == 401
    assert client.put("/api/v1/settings/agent", json={"api_key": "sk-anonymous"}).status_code == 401


def test_an_implausibly_short_key_is_rejected_before_anything_is_written(
    client: TestClient, settings_env
) -> None:
    headers = auth_headers(client, ADMIN)
    response = client.put("/api/v1/settings/agent", headers=headers, json={"api_key": "sk-x"})
    assert response.status_code == 422, response.text
    assert "OPENAI_API_KEY" not in (settings_env / ".env").read_text(encoding="utf-8")


def test_a_member_can_still_read_which_provider_is_answering(
    client: TestClient, settings_env
) -> None:
    """Reading is deliberately not privileged: see the router docstring."""
    headers = auth_headers(client, ALICE)
    response = client.get("/api/v1/settings/agent", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["provider"] == "openai"
