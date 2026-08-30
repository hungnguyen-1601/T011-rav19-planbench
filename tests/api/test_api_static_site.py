"""Serving the exported web UI from the API process (desktop build).

The mount sits at "/" and therefore matches every path there is, which
makes exactly one thing worth pinning: that it did not take the API with
it. The rest is deep links — the three routes named after a record id,
where a reload asks the server for a file the export never wrote.
"""

from __future__ import annotations

import pytest
from conftest import isolate_environment
from fastapi.testclient import TestClient

from planbench_api.config import get_settings
from planbench_api.main import create_app


@pytest.fixture
def web_root(tmp_path):
    """A minimal stand-in for `next export` output.

    Only the files that matter to the routing decision: the index, one
    real page, one dynamic-route shell, and one asset.
    """
    root = tmp_path / "web"
    (root / "decisions").mkdir(parents=True)
    (root / "maps").mkdir(parents=True)
    (root / "_next").mkdir(parents=True)
    (root / "guide").mkdir(parents=True)
    (root / "index.html").write_text("<html>home</html>", encoding="utf-8")
    (root / "login.html").write_text("<html>login</html>", encoding="utf-8")
    (root / "guide" / "operation.html").write_text("<html>operation</html>", encoding="utf-8")
    (root / "decisions" / "_.html").write_text("<html>decision shell</html>", encoding="utf-8")
    # A real page *under* a dynamic route. Nothing in the app has one
    # today; it is here because the order the two rules run in is a
    # claim the code makes and this is the only thing that checks it.
    (root / "decisions" / "list.html").write_text("<html>decision list</html>", encoding="utf-8")
    (root / "maps" / "_.html").write_text("<html>map shell</html>", encoding="utf-8")
    (root / "_next" / "app.js").write_text("console.log(1)", encoding="utf-8")
    # `next export` writes this, and its presence changes how a miss
    # arrives: with a 404.html, StaticFiles *returns* it rather than
    # raising, so a fallback that only catches the exception silently
    # stops working. The first version of this fixture had no 404.html
    # and the deep-link tests passed against a server that answered
    # every deep link with the not-found page.
    (root / "404.html").write_text("<html>not found</html>", encoding="utf-8")
    return root


@pytest.fixture
def desktop_client(tmp_path, monkeypatch, web_root) -> TestClient:
    isolate_environment(monkeypatch)
    monkeypatch.setenv("PLANBENCH_MODEL_DIR", str(tmp_path / "models"))
    monkeypatch.setenv("PLANBENCH_WEB_DIR", str(web_root))
    get_settings.cache_clear()
    app = create_app(artifact_dir=str(tmp_path / "artifacts"))
    yield TestClient(app, raise_server_exceptions=False)
    get_settings.cache_clear()


def test_mounting_the_web_ui_does_not_swallow_the_api(desktop_client: TestClient) -> None:
    """The mount matches "/" — the API has to still be reachable under it.

    Registering the mount before the routers answers every API call with
    the web UI, and the failure is not an error anywhere: the request
    succeeds, returns HTML, and the browser reports a JSON parse error
    somewhere far away from the cause.
    """
    health = desktop_client.get("/api/v1/health")
    assert health.status_code == 200, health.text
    assert health.headers["content-type"].startswith("application/json")

    docs = desktop_client.get("/openapi.json")
    assert docs.status_code == 200
    assert "/api/v1/settings/agent" in docs.json()["paths"]


def test_the_index_is_served_at_the_root(desktop_client: TestClient) -> None:
    response = desktop_client.get("/")
    assert response.status_code == 200
    assert "home" in response.text


def test_an_exported_page_is_served_by_name(desktop_client: TestClient) -> None:
    response = desktop_client.get("/login.html")
    assert response.status_code == 200
    assert "login" in response.text


def test_a_deep_link_into_a_dynamic_route_serves_its_shell(desktop_client: TestClient) -> None:
    """Reloading on /decisions/<id> is the case the export cannot cover.

    The id is created by the person using the app, so no build ever knew
    its name. The shell is what the router hydrates into.
    """
    response = desktop_client.get("/decisions/9f2c-not-a-real-id")
    assert response.status_code == 200
    assert "decision shell" in response.text

    other = desktop_client.get("/maps/some-map")
    assert other.status_code == 200
    assert "map shell" in other.text


def test_a_missing_asset_under_a_dynamic_route_is_still_a_404(desktop_client: TestClient) -> None:
    """An <img> that renders HTML is harder to diagnose than one that 404s."""
    response = desktop_client.get("/maps/missing-picture.png")
    assert response.status_code == 404


def test_an_unknown_page_is_a_404_rather_than_the_index(desktop_client: TestClient) -> None:
    """A page missing from the export is a build failure, not a route.

    A catch-all returning index.html would turn it into a blank screen
    that looks like a client-side routing quirk, and the first person to
    see it would be a user rather than the build.
    """
    assert desktop_client.get("/nonsense").status_code == 404
    assert desktop_client.get("/decisions/one/two/three").status_code == 404


def test_the_api_is_served_alone_when_no_web_dir_is_configured(client: TestClient) -> None:
    """Every deployment but the desktop one runs the web UI separately."""
    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/").status_code == 404


def test_a_web_dir_that_is_not_a_directory_is_a_warning_not_a_crash(tmp_path, monkeypatch) -> None:
    """A typo'd path must not take the API down with it.

    The same reasoning as the plugin catalogue sync: an API that refuses
    to start reports the problem to whoever reads the logs, which on a
    desktop machine is nobody.
    """
    isolate_environment(monkeypatch)
    monkeypatch.setenv("PLANBENCH_MODEL_DIR", str(tmp_path / "models"))
    monkeypatch.setenv("PLANBENCH_WEB_DIR", str(tmp_path / "does-not-exist"))
    get_settings.cache_clear()
    app = create_app(artifact_dir=str(tmp_path / "artifacts"))
    get_settings.cache_clear()

    with TestClient(app, raise_server_exceptions=False) as probe:
        assert probe.get("/api/v1/health").status_code == 200


def test_an_exported_page_is_served_without_its_extension(desktop_client: TestClient) -> None:
    """`/login` is the URL a person types, and the one a reload asks for.

    The export writes `login.html`; nothing writes a file called
    `login`. Before this, every static page in the app was reachable
    only by client-side navigation — a reload, a pasted link or a
    bookmark got the not-found page. Nobody had hit it because the
    desktop app opens at `/` and the router never asks the server
    again.
    """
    response = desktop_client.get("/login")
    assert response.status_code == 200
    assert "login" in response.text


def test_a_page_one_level_down_is_served_without_its_extension(
    desktop_client: TestClient,
) -> None:
    """The guide is the first feature whose pages live under a segment.

    `/guide/operation` is two segments, and `guide` is *not* a dynamic
    route — so the shell rule does not apply and the file has to be
    found by name.
    """
    response = desktop_client.get("/guide/operation")
    assert response.status_code == 200
    assert "operation" in response.text


def test_serving_a_page_by_name_does_not_shadow_the_dynamic_shell(
    desktop_client: TestClient,
) -> None:
    """A record id is tried as a page first, and must still fall through.

    The extensionless rule runs before the shell rule, so this is the
    case that says the new rule did not eat the old one: there is no
    `decisions/9f2c.html`, and the answer has to be the shell.
    """
    response = desktop_client.get("/decisions/9f2c-not-a-real-id")
    assert response.status_code == 200
    assert "decision shell" in response.text


def test_a_real_page_under_a_dynamic_route_beats_the_shell(
    desktop_client: TestClient,
) -> None:
    """`/decisions/list` is a page, not a record id, and must win.

    The two rules overlap on exactly this shape, and the shell would
    answer it just as happily — with a blank screen, because the page
    it hydrates reads an id that is really the word "list". Serving the
    page first is what keeps a missing export a 404 instead of a shell
    that renders nothing.
    """
    response = desktop_client.get("/decisions/list")
    assert response.status_code == 200
    assert "decision list" in response.text
