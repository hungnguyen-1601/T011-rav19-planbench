"""The window shown while an update downloads.

Nothing here opens a window: that needs a display and a WebView2
runtime, and the fallback exists precisely because neither is
guaranteed. What is worth pinning is the part that decides whether the
*update* survives the window — because the window is the disposable
half, and getting that backwards means losing an update over a progress
bar.
"""

from __future__ import annotations

import threading

import pytest

from planbench_desktop import updater
from planbench_desktop.progress import LOAD_TIMEOUT_S, Progress


class TestTheWindowIsNeverWorthTheUpdate:
    def test_the_work_still_runs_when_no_toolkit_will_start(self, monkeypatch) -> None:
        """A machine that cannot draw still updates, quietly.

        `pywebview` needs a WebView2 runtime. Treating its absence as a
        failed update would trade the thing people want for the thing
        that tells them it is happening.
        """
        monkeypatch.setitem(__import__("sys").modules, "webview", None)
        done: list[str] = []

        Progress("t", "d").run(lambda view: done.append("ran"))

        assert done == ["ran"]

    def test_a_failure_inside_the_work_reaches_the_caller(self, monkeypatch) -> None:
        """Drawing a window around the download must not swallow its
        errors: a bad hash has to stay a refused update."""
        monkeypatch.setitem(__import__("sys").modules, "webview", None)

        with pytest.raises(updater.UpdateError, match="refused"):

            def work(view: Progress) -> None:
                raise updater.UpdateError("refused")

            Progress("t", "d").run(work)

    def test_reporting_progress_without_a_window_is_harmless(self) -> None:
        """`update` is called from the download loop, which does not know
        or care whether anything is on screen."""
        screen = Progress("t", "d")

        screen.update("half way", 50.0)
        screen.update("no total")
        screen.close()


class TestTheDownloadIsNeverBlockedByTheWindow:
    """The failure this module was rewritten for.

    `evaluate_js` is synchronous — it waits for the window to answer.
    Calling it from the download loop, once per chunk, meant the first
    call went out before WebView2 had loaded the page, never returned,
    and took the download with it: an hour on screen, nothing
    transferred. So `update` records, and a painter thread does the
    talking.
    """

    def test_update_never_calls_into_the_window(self) -> None:
        """The one property that matters. `update` runs on the download
        thread, so anything it waits on is something the download waits
        on."""
        called: list[str] = []
        screen = Progress("t", "d")
        screen._window = type("W", (), {"evaluate_js": lambda self, s: called.append(s)})()

        screen.update("half way", 50.0)
        screen.update("nearly", 90.0)

        assert called == []

    def test_update_keeps_only_the_latest_state(self) -> None:
        """A download reports hundreds of times; the window is repainted
        four times a second. Queueing every one would build a backlog
        the painter could never drain."""
        screen = Progress("t", "d")

        screen.update("first", 10.0)
        screen.update("second", 20.0)

        assert screen._state == ("second", 20.0)

    def test_a_window_that_stops_answering_does_not_stop_the_download(self) -> None:
        """The painter gives up; the work carries on to the end."""
        screen = Progress("t", "d")

        class Deaf:
            def evaluate_js(self, script: str) -> None:
                raise RuntimeError("the bridge is gone")

        screen._window = Deaf()
        screen._loaded.set()
        painter = threading.Thread(target=screen._paint, daemon=True)
        painter.start()
        screen.update("still going", 50.0)

        painter.join(timeout=3)
        assert not painter.is_alive(), "the painter should give up rather than spin"

    def test_the_painter_does_not_wait_forever_for_a_page_that_never_loads(self) -> None:
        """A window that never fires `loaded` must not hold the painter,
        because the painter is what a person is looking at."""
        assert LOAD_TIMEOUT_S <= 30


class TestWhatTheWindowIsToldToShow:
    """`_draw` builds the JavaScript call; these check what it builds."""

    @staticmethod
    def _recording() -> tuple[Progress, list[str]]:
        sent: list[str] = []
        screen = Progress("t", "d")
        screen._window = type("W", (), {"evaluate_js": lambda self, s: sent.append(s)})()
        return screen, sent

    def test_a_known_size_becomes_a_percentage(self) -> None:
        screen, sent = self._recording()

        screen._draw("Downloading… 41 of 82 MB", 50.0)

        assert "50.0" in sent[0]
        assert "Downloading" in sent[0]

    def test_no_total_means_no_percentage(self) -> None:
        """A server that sent no `Content-Length` has nothing to divide
        by, and a bar computed from zero is a bar that lies."""
        screen, sent = self._recording()

        screen._draw("Downloading… 41 MB", None)

        assert "null" in sent[0]

    def test_the_percentage_is_clamped(self) -> None:
        """A server under-reporting its own length would otherwise drive
        the bar past the end of its track."""
        screen, sent = self._recording()

        screen._draw("over", 140.0)
        screen._draw("under", -20.0)

        assert "100.0" in sent[0]
        assert "0.0" in sent[1]

    def test_a_quote_in_the_detail_cannot_break_out_of_the_call(self) -> None:
        """The detail carries a file name and a version, both from a
        release published by somebody else."""
        screen, sent = self._recording()

        screen._draw("it's 'quoted'", 10.0)

        assert (chr(92) + chr(39)) in sent[0]

    def test_drawing_without_a_window_reports_failure_rather_than_raising(self) -> None:
        assert Progress("t", "d")._draw("anything", 1.0) is False


class TestTheInstallerSpeaksForItself:
    def test_it_is_asked_for_a_progress_bar_not_for_silence(self, monkeypatch, tmp_path) -> None:
        """The install happens after this process is gone, so the window
        cannot cover it — the installer has to.

        `/VERYSILENT` shows nothing at all, which is what made an update
        and a crash look alike from the outside.
        """
        monkeypatch.setattr(updater.subprocess, "Popen", lambda *a, **k: None)
        installer = tmp_path / "PlanBench-Setup.exe"
        installer.write_bytes(b"")

        updater.apply(installer, ["pythonw.exe", "main.py"])
        script = (tmp_path / "apply-update.cmd").read_text(encoding="mbcs")

        assert "/SILENT" in script
        assert "/VERYSILENT" not in script
        # Still no wizard pages, and still no message boxes to click.
        assert "/SUPPRESSMSGBOXES" in script
