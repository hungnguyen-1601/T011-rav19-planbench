"""The updater: what it accepts, what it refuses, and what it never does.

Nothing here reaches the network. Every check is about a decision the
updater makes on data it was handed, and those decisions are the whole
of it — the download itself is four lines of urllib.

The refusals matter more than the acceptances. This code path ends in
running an executable with the user's privileges, so a wrong "yes" is a
different category of mistake from a wrong "no": a missed update is an
old version, and an accepted bad download is somebody else's program.
"""

from __future__ import annotations

import hashlib
import json

import pytest
from planbench_desktop import updater


def _release_payload(tag: str, *, with_manifest: bool = True, draft: bool = False) -> dict:
    assets = [{"name": f"PlanBench-Setup-{tag[len('desktop-v') :]}.exe", "url": f"u://{tag}/exe"}]
    if with_manifest:
        assets.append({"name": updater.MANIFEST_ASSET, "url": f"u://{tag}/manifest"})
    return {"tag_name": tag, "draft": draft, "assets": assets, "body": "notes"}


@pytest.fixture
def api(monkeypatch):
    """Stand in for GitHub. Returns the recorder the test configures."""
    responses: dict[str, bytes] = {}
    asked: list[str] = []

    def fake_request(url: str, token: str, *, accept: str) -> bytes:
        asked.append(url)
        for key, value in responses.items():
            if key in url:
                return value
        raise updater.UpdateError(f"no stub for {url}")

    monkeypatch.setattr(updater, "_request", fake_request)
    monkeypatch.setenv(updater.TOKEN_ENV, "test-token")
    return type("Api", (), {"responses": responses, "asked": asked})()


class TestVersionComparison:
    @pytest.mark.parametrize(
        ("older", "newer"),
        [("0.9.0", "0.10.0"), ("1.0.0", "1.0.1"), ("0.1.0", "1.0.0"), ("1.2.3", "1.3.0")],
    )
    def test_it_compares_numbers_not_text(self, older: str, newer: str) -> None:
        """A string compare puts 0.10.0 before 0.9.0.

        That is the classic way an updater goes quiet a year in: it keeps
        working right up until the minor version reaches double digits.
        """
        assert updater.parse_version(older) < updater.parse_version(newer)

    def test_a_development_build_is_older_than_every_release(self) -> None:
        assert updater.parse_version("0.0.0-dev") < updater.parse_version("0.1.0")

    def test_an_unparseable_version_does_not_raise(self) -> None:
        """A malformed tag should be ignored, not fatal."""
        assert updater.parse_version("not-a-version") == (0,)


class TestChoosingARelease:
    def test_it_offers_the_newest_release_above_the_running_one(self, api) -> None:
        api.responses["/releases"] = json.dumps(
            [
                _release_payload("desktop-v0.1.0"),
                _release_payload("desktop-v0.3.0"),
                _release_payload("desktop-v0.2.0"),
            ]
        ).encode()

        release = updater.latest_release("0.1.0", "token")

        assert release is not None
        assert release.version == "0.3.0"

    def test_it_offers_nothing_when_the_running_version_is_current(self, api) -> None:
        api.responses["/releases"] = json.dumps([_release_payload("desktop-v0.2.0")]).encode()

        assert updater.latest_release("0.2.0", "token") is None

    def test_it_ignores_tags_that_are_not_this_application(self, api) -> None:
        """The repository carries tags for other things.

        Running one of those through a Windows installer is not an
        upgrade, it is a category error with an executable at the end.
        """
        api.responses["/releases"] = json.dumps(
            [{"tag_name": "v9.9.9", "assets": [], "body": ""}]
        ).encode()

        assert updater.latest_release("0.1.0", "token") is None

    def test_it_skips_a_draft(self, api) -> None:
        api.responses["/releases"] = json.dumps(
            [_release_payload("desktop-v0.5.0", draft=True)]
        ).encode()

        assert updater.latest_release("0.1.0", "token") is None

    def test_it_skips_a_release_with_no_manifest_to_check_against(self, api) -> None:
        """Without the manifest there is no hash, and without a hash the
        download is an unverified executable."""
        api.responses["/releases"] = json.dumps(
            [_release_payload("desktop-v0.5.0", with_manifest=False)]
        ).encode()

        assert updater.latest_release("0.1.0", "token") is None


class TestDownloading:
    def _release(self) -> updater.Release:
        return updater.Release(
            version="0.2.0",
            tag="desktop-v0.2.0",
            installer_url="u://exe",
            installer_name="PlanBench-Setup-0.2.0.exe",
            manifest_url="u://manifest",
            notes="",
        )

    def test_a_matching_hash_is_written_to_disk(self, api, tmp_path) -> None:
        payload = b"pretend this is an installer"
        api.responses["manifest"] = json.dumps(
            {"version": "0.2.0", "sha256": hashlib.sha256(payload).hexdigest()}
        ).encode()
        api.responses["exe"] = payload

        saved = updater.download(self._release(), "token", tmp_path)

        assert saved.read_bytes() == payload

    def test_a_mismatched_hash_is_refused_and_nothing_is_written(self, api, tmp_path) -> None:
        """The one check between a download and running somebody's code.

        Everything else this module does is convenience; this is the
        part that has to hold.
        """
        api.responses["manifest"] = json.dumps({"version": "0.2.0", "sha256": "aa" * 32}).encode()
        api.responses["exe"] = b"something else entirely"

        with pytest.raises(updater.UpdateError, match="hashes to"):
            updater.download(self._release(), "token", tmp_path)

        assert list(tmp_path.iterdir()) == []

    def test_a_manifest_for_another_version_is_refused(self, api, tmp_path) -> None:
        """A manifest that outlived its installer is a mismatch waiting."""
        api.responses["manifest"] = json.dumps({"version": "0.9.9", "sha256": "aa" * 32}).encode()

        with pytest.raises(updater.UpdateError, match="manifest for 0.9.9"):
            updater.download(self._release(), "token", tmp_path)

    def test_a_manifest_without_a_usable_hash_is_refused(self, api, tmp_path) -> None:
        api.responses["manifest"] = json.dumps({"version": "0.2.0", "sha256": "short"}).encode()

        with pytest.raises(updater.UpdateError, match="no usable sha256"):
            updater.download(self._release(), "token", tmp_path)


class TestTheFlow:
    def test_without_a_token_it_does_nothing_and_says_so(self, monkeypatch, tmp_path) -> None:
        """The right behaviour for a machine deliberately kept offline."""
        monkeypatch.delenv(updater.TOKEN_ENV, raising=False)
        called: list[str] = []
        monkeypatch.setattr(
            updater, "latest_release", lambda *a, **k: called.append("checked") or None
        )

        assert updater.offer("0.1.0", tmp_path, ["python"]) is False
        assert called == []

    def test_a_network_failure_never_stops_the_app_opening(self, api, tmp_path) -> None:
        """An updater that can prevent the application from starting is a
        worse problem than an application one version behind."""
        # No stubs registered, so the fake transport raises UpdateError —
        # the same shape a timeout or a 502 arrives in.
        api.responses.clear()
        assert updater.offer("0.1.0", tmp_path, ["python"]) is False

    def test_declining_leaves_everything_alone(self, api, monkeypatch, tmp_path) -> None:
        api.responses["/releases"] = json.dumps([_release_payload("desktop-v0.9.0")]).encode()
        monkeypatch.setattr(updater, "ask", lambda release: False)
        applied: list[object] = []
        monkeypatch.setattr(updater, "apply", lambda *a: applied.append(a))

        assert updater.offer("0.1.0", tmp_path, ["python"]) is False
        assert applied == []

    def test_accepting_downloads_and_hands_off(self, api, monkeypatch, tmp_path) -> None:
        payload = b"installer bytes"
        api.responses["/releases"] = json.dumps([_release_payload("desktop-v0.9.0")]).encode()
        api.responses["manifest"] = json.dumps(
            {"version": "0.9.0", "sha256": hashlib.sha256(payload).hexdigest()}
        ).encode()
        api.responses["exe"] = payload
        monkeypatch.setattr(updater, "ask", lambda release: True)
        handed: list[tuple] = []
        monkeypatch.setattr(updater, "apply", lambda *a: handed.append(a))

        # True means "the app should now close": the installer is about
        # to replace the directory this process is running out of.
        assert updater.offer("0.1.0", tmp_path, ["python", "main.py"]) is True
        assert handed and handed[0][1] == ["python", "main.py"]


class TestTheHandoff:
    def test_the_installer_runs_silently_and_relaunches_the_app(self, monkeypatch) -> None:
        """Windows will not overwrite a file a live process holds open.

        So the sequence is handed to a detached shell — install, then
        start the app again — and this process exits normally.
        """
        recorded: list[list[str]] = []
        monkeypatch.setattr(
            updater.subprocess,
            "Popen",
            lambda command, **kwargs: recorded.append(command),
        )

        updater.apply(updater.Path("C:/tmp/setup.exe"), ["pythonw.exe", "main.py"])

        command = " ".join(recorded[0])
        assert "/VERYSILENT" in command
        assert "/SUPPRESSMSGBOXES" in command
        assert "pythonw.exe" in command
        assert "&&" in command  # the relaunch only happens if the install did
