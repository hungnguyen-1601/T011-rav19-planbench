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
    credentials: list[str] = []
    accepts: list[tuple[str, str]] = []
    reported: list[object] = []

    def fake_request(url: str, token: str = "", *, accept: str, on_progress=None) -> bytes:
        asked.append(url)
        credentials.append(token)
        accepts.append((url, accept))
        if on_progress is not None:
            reported.append(on_progress)
        for key, value in responses.items():
            if key in url:
                return value
        raise updater.UpdateError(f"no stub for {url}")

    monkeypatch.setattr(updater, "_request", fake_request)
    monkeypatch.delenv(updater.TOKEN_ENV, raising=False)
    return type(
        "Api",
        (),
        {
            "responses": responses,
            "asked": asked,
            "credentials": credentials,
            "accepts": accepts,
            "reported": reported,
        },
    )()


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

    def test_both_assets_are_fetched_as_bytes_not_as_metadata(self, api, tmp_path) -> None:
        """The header that broke a shipped release.

        A release asset asked for as `application/json` answers with the
        asset's *metadata* — id, name, size, uploader. That parses
        cleanly and has no `sha256` in it, so every update refused
        itself with "carries no usable sha256" while the published
        manifest was correct the whole time. Only `octet-stream` returns
        the file.
        """
        payload = b"installer"
        api.responses["manifest"] = json.dumps(
            {"version": "0.2.0", "sha256": hashlib.sha256(payload).hexdigest()}
        ).encode()
        api.responses["exe"] = payload

        updater.download(self._release(), "token", tmp_path)

        assert [accept for _, accept in api.accepts] == [
            "application/octet-stream",
            "application/octet-stream",
        ]

    def test_the_release_listing_is_still_asked_for_as_json(self, api) -> None:
        """The listing is an API resource, not an asset — it really is
        JSON, and asking for octet-stream there would be the mirror of
        the same mistake."""
        api.responses["/releases"] = json.dumps([]).encode()

        updater.latest_release("0.1.0", "")

        assert api.accepts == [
            (
                "https://api.github.com/repos/" + updater.REPOSITORY + "/releases?per_page=30",
                "application/vnd.github+json",
            )
        ]


class TestTheFlow:
    def test_it_checks_without_a_token_because_the_releases_are_public(
        self, api, monkeypatch, tmp_path
    ) -> None:
        """The default install has no credential, and must still update.

        Requiring one would mean every person who installed the app had
        to paste a token before it would ever notice a new version —
        indistinguishable, from their side, from having no updater.
        """
        monkeypatch.delenv(updater.TOKEN_ENV, raising=False)
        api.responses["/releases"] = json.dumps([_release_payload("desktop-v0.9.0")]).encode()
        monkeypatch.setattr(updater, "ask", lambda release: False)

        updater.offer("0.1.0", tmp_path, ["python"])

        assert any("/releases" in url for url in api.asked)
        assert api.credentials == [""]

    def test_a_token_is_used_when_one_is_configured(self, api, monkeypatch, tmp_path) -> None:
        """Honoured, not required: it raises the anonymous rate limit and
        is what would keep this working if the repository went private."""
        monkeypatch.setenv(updater.TOKEN_ENV, "  configured-token  ")
        api.responses["/releases"] = json.dumps([]).encode()

        updater.offer("0.1.0", tmp_path, ["python"])

        assert api.credentials == ["configured-token"]

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
        monkeypatch.setattr(updater, "apply", lambda *a, **kw: applied.append(a))

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
        monkeypatch.setattr(updater, "apply", lambda *a, **kw: handed.append(a))

        # True means "the app should now close": the installer is about
        # to replace the directory this process is running out of.
        assert updater.offer("0.1.0", tmp_path, ["python", "main.py"]) is True
        assert handed and handed[0][1] == ["python", "main.py"]


class TestTheHandoff:
    """What the update actually runs, and why it is a file.

    The first version chained three commands with `&` through
    `cmd /c`. On a real machine the middle one — the installer — did not
    run: the app closed, reopened on the version it started with, and
    left no installer log, because the installer was never reached.
    A script on disk removes the quoting layer that swallowed it, and
    leaves the exact commands beside their log.
    """

    @staticmethod
    def _script(tmp_path, **kwargs) -> str:
        installer = tmp_path / "PlanBench-Setup.exe"
        installer.write_bytes(b"")
        updater.apply(installer, ["pythonw.exe", "main.py"], **kwargs)
        return (tmp_path / "apply-update.cmd").read_text(encoding="mbcs")

    def test_it_writes_a_script_rather_than_chaining_a_command_string(
        self, monkeypatch, tmp_path
    ) -> None:
        monkeypatch.setattr(updater.subprocess, "Popen", lambda *a, **k: None)

        script = self._script(tmp_path)

        assert (tmp_path / "apply-update.cmd").is_file()
        assert "/SILENT" in script
        assert "pythonw.exe" in script

    def test_the_installer_is_called_so_control_comes_back(self, monkeypatch, tmp_path) -> None:
        """Without `call`, a batch-file installer takes the rest of the
        script with it and the app is never restarted — measured, not
        feared: a stand-in used while proving this out did exactly that.
        """
        monkeypatch.setattr(updater.subprocess, "Popen", lambda *a, **k: None)

        assert "call " in self._script(tmp_path)

    def test_it_waits_before_replacing_the_running_interpreter(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr(updater.subprocess, "Popen", lambda *a, **k: None)

        assert "timeout /t" in self._script(tmp_path)

    def test_it_closes_whatever_still_holds_a_file(self, monkeypatch, tmp_path) -> None:
        """In silent mode, giving up on a locked file looks like success."""
        monkeypatch.setattr(updater.subprocess, "Popen", lambda *a, **k: None)

        assert "/FORCECLOSEAPPLICATIONS" in self._script(tmp_path)

    def test_the_exit_code_is_recorded(self, monkeypatch, tmp_path) -> None:
        """The app is gone by the time the installer finishes, so this
        line is the only thing that can report what happened."""
        monkeypatch.setattr(updater.subprocess, "Popen", lambda *a, **k: None)

        assert "%ERRORLEVEL%" in self._script(tmp_path)

    def test_the_app_comes_back_even_if_the_install_failed(self, monkeypatch, tmp_path) -> None:
        """No conditional between the installer and the relaunch: being
        left with no window at all is worse than being left on the
        version you had."""
        script = self._script(tmp_path)
        lines = [line for line in script.splitlines() if line.strip()]

        assert lines[-1].startswith("start ")
        assert "&&" not in script

    def test_no_console_window_is_opened_over_the_person_using_it(
        self, monkeypatch, tmp_path
    ) -> None:
        """A black window counting down, with the app gone, reads as a
        crash rather than as an update."""
        flags: list[int] = []
        monkeypatch.setattr(
            updater.subprocess,
            "Popen",
            lambda *a, **k: flags.append(k.get("creationflags", 0)),
        )

        self._script(tmp_path)

        assert flags[0] & updater.subprocess.CREATE_NO_WINDOW

    def test_the_installer_is_asked_to_write_a_log_when_given_a_path(
        self, monkeypatch, tmp_path
    ) -> None:
        monkeypatch.setattr(updater.subprocess, "Popen", lambda *a, **k: None)
        log = tmp_path / "installer.log"

        assert f'/LOG="{log}"' in self._script(tmp_path, log=log)
