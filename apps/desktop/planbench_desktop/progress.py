"""A window that says the update is working, while it is working.

Between accepting an update and seeing the app again there was nothing
on screen: the window closed, eighty megabytes downloaded, an installer
ran, and the app came back some minute later. From outside that is
indistinguishable from a crash, and the first person to see it said so.

Two halves cover the gap, and they are deliberately different
mechanisms because they happen either side of this process ending:

* **while the download runs**, this module shows the window — the app is
  still alive and can draw;
* **while the installer runs**, the app is gone, so the installer shows
  its own progress instead. That is why `updater.apply` asks Inno for
  `/SILENT` rather than `/VERYSILENT`.

`pywebview` rather than a toolkit, because the embeddable Python this
ships with has **no tkinter** — no tcl, no tk, and adding them would be
another twenty megabytes to carry for one window.

The window can only be shown on the path that ends in the app exiting.
Most `pywebview` backends will not start a second event loop in one
process, so opening this and then the main window would be a gamble.
Declining the update never reaches this code.

**Nothing here may block the download, and that is the whole design.**

The first version shipped an update that sat on screen for an hour
having transferred nothing, in the release written to make updates
legible. The cause was a plain misreading of `webview.start(func,
args)`: `args` is the argument list for `func`, and it was handed the
window instead, so pywebview's `Thread(target=func, args=args)` never
ran the worker. The GUI loop came up with nothing behind it. A progress
bar that cannot move is a worse lie than no progress bar.

The queue below is not what fixed that, and is kept because it removes
the *next* way to hang. `evaluate_js` is **synchronous** — it waits for
the window to answer — and the first version called it from the
download loop, once per 256 KB chunk, the first of them before WebView2
had finished loading the page. Nothing about that was safe; it simply
had not been reached yet.

So the two are separated:

* the download thread only ever assigns to a field — it cannot block;
* a painter thread reads that field a few times a second and does the
  talking. If a call into the window never returns, the painter is what
  stops, and the download carries on to the end.

The lesson kept with the code: this module was tested by asserting the
JavaScript it *builds*, and never once by running a download through a
real window. Both defects were invisible to those tests and obvious the
first time one was run.
"""

from __future__ import annotations

import contextlib
import html
import logging
import threading
from collections.abc import Callable

logger = logging.getLogger("planbench.desktop")

WIDTH = 460
HEIGHT = 190

#: How often the painter talks to the window. Four times a second is
#: past what anybody reads and far below what a synchronous bridge call
#: costs; the old code did it three hundred times per download.
PAINT_INTERVAL_S = 0.25

#: How long to wait for the page to load before painting anyway. Only a
#: bound on being wrong: a window that never loads must not keep the
#: painter waiting forever, and painting into an unloaded page merely
#: fails.
LOAD_TIMEOUT_S = 10.0

#: Kept in one string rather than a file: it has to render before
#: anything is installed, from a directory the installer is about to
#: replace, and a missing asset there would be a blank window.
PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><style>
  :root {{ color-scheme: light dark; }}
  body {{
    margin: 0; height: 100vh; display: flex; flex-direction: column;
    justify-content: center; gap: 14px; padding: 0 28px; box-sizing: border-box;
    font: 14px/1.5 "Segoe UI", system-ui, sans-serif;
    background: #101826; color: #e8eef7;
  }}
  h1 {{ margin: 0; font-size: 15px; font-weight: 600; }}
  #detail {{ margin: 0; font-size: 13px; opacity: .75; }}
  #track {{ height: 6px; border-radius: 3px; background: #26324a; overflow: hidden; }}
  #bar {{
    height: 100%; width: 0%; border-radius: 3px; background: #5ec8ff;
    transition: width .2s ease;
  }}
  /* Indeterminate: a bar that sweeps, for the phases with no total. */
  #bar.sweep {{ width: 35%; animation: sweep 1.1s ease-in-out infinite; }}
  @keyframes sweep {{ 0% {{ margin-left: -35%; }} 100% {{ margin-left: 100%; }} }}
</style></head><body>
  <h1>{title}</h1>
  <div id="track"><div id="bar" class="sweep"></div></div>
  <p id="detail">{detail}</p>
  <script>
    function render(detail, percent) {{
      document.getElementById('detail').textContent = detail;
      var bar = document.getElementById('bar');
      if (percent === null) {{ bar.classList.add('sweep'); return; }}
      bar.classList.remove('sweep');
      bar.style.width = percent + '%';
    }}
  </script>
</body></html>"""


class Progress:
    """Shows the window, runs the work beside it, closes the window.

    Every method is safe to call when the window never opened, and every
    method returns promptly whether or not the window is answering. A
    machine that cannot draw still updates; a window that stops
    answering still lets the update finish.
    """

    def __init__(self, title: str, detail: str) -> None:
        self._title = title
        self._detail = detail
        self._window = None
        self._failure: BaseException | None = None
        #: The latest thing worth showing. Written by whichever thread is
        #: doing the work, read by the painter. A plain assignment under
        #: the GIL, so the writer never waits.
        self._state: tuple[str, float | None] = (detail, None)
        self._stop = threading.Event()
        self._loaded = threading.Event()

    def run(self, work: Callable[[Progress], None]) -> None:
        """Show the window and run ``work`` beside it until it returns.

        ``work`` runs on a thread because the window owns this one — a
        GUI event loop that is not being pumped is a window that stops
        repainting.

        An exception inside ``work`` is re-raised here, on the caller's
        thread, so the update's error handling is unchanged by having
        drawn a window around it.
        """
        try:
            import webview
        except Exception as exc:  # noqa: BLE001 - a window is never worth the update
            logger.warning("no progress window (%s); updating quietly", exc)
            work(self)
            return

        page = PAGE.format(title=html.escape(self._title), detail=html.escape(self._detail))
        self._window = webview.create_window(
            self._title,
            html=page,
            width=WIDTH,
            height=HEIGHT,
            resizable=False,
            frameless=False,
        )
        # Painting before the page exists is what hung the first
        # version. The event is the signal; the timeout in the painter
        # is what keeps a window that never fires it from mattering.
        with contextlib.suppress(Exception):
            self._window.events.loaded += self._loaded.set

        def worker() -> None:
            painter = threading.Thread(target=self._paint, name="planbench-progress", daemon=True)
            painter.start()
            try:
                work(self)
            except BaseException as exc:  # noqa: BLE001 - re-raised below
                self._failure = exc
            finally:
                self._stop.set()
                self.close()

        try:
            # `webview.start(func, args)` — `args` is the **argument
            # list** for `func`, not the window: pywebview runs
            # `Thread(target=func, args=args)`, and the window it shows
            # is the one `create_window` already registered. Passing the
            # window there meant the worker was never called at all: the
            # GUI loop came up with nothing behind it, so the app sat
            # showing a progress bar that could not move, having
            # downloaded nothing, for as long as somebody let it.
            webview.start(worker)
        except Exception as exc:  # noqa: BLE001 - depends on the machine
            logger.warning("progress window failed to start (%s); updating quietly", exc)
            self._window = None
            work(self)
            return

        if self._failure is not None:
            raise self._failure

    def update(self, detail: str, percent: float | None = None) -> None:
        """Record what to show. **Never talks to the window.**

        Called from the download loop, which must not be able to wait on
        anything. Assigning a tuple is the entire body on purpose.
        """
        self._state = (detail, percent)

    def close(self) -> None:
        self._stop.set()
        if self._window is None:
            return
        # Suppressed: the process is about to end either way, and a
        # window that will not close is not worth an error over.
        with contextlib.suppress(Exception):
            self._window.destroy()

    # -- the painter ---------------------------------------------------

    def _paint(self) -> None:
        """Push the latest state into the window until told to stop.

        Runs on its own daemon thread so that a bridge call which never
        returns strands this thread and nothing else. The download's
        completion does not depend on anything below this line.
        """
        if not self._loaded.wait(LOAD_TIMEOUT_S):
            logger.info("progress window did not report loading; painting anyway")
        last: tuple[str, float | None] | None = None
        while not self._stop.wait(PAINT_INTERVAL_S):
            state = self._state
            if state == last:
                continue
            last = state
            if not self._draw(*state):
                # One failed call is enough: whatever broke the bridge
                # will break the next one too, and retrying every 250 ms
                # for the length of a download only fills the log.
                logger.warning("progress window stopped accepting updates; carrying on")
                return

    def _draw(self, detail: str, percent: float | None) -> bool:
        """One call into the window. False when it did not work."""
        if self._window is None:
            return False
        try:
            share = "null" if percent is None else f"{max(0.0, min(100.0, percent)):.1f}"
            self._window.evaluate_js(f"render({_js(detail)}, {share})")
        except Exception:  # noqa: BLE001 - cosmetic, never fatal
            return False
        return True


def _js(text: str) -> str:
    """A JavaScript string literal for ``text``.

    Written out rather than interpolated: the detail line carries a file
    name and a version, both of which come from a release somebody else
    published.
    """
    escaped = text.replace("\\", "\\\\").replace("'", "\\'").replace("\n", " ")
    return f"'{escaped}'"


__all__ = ["HEIGHT", "LOAD_TIMEOUT_S", "PAGE", "PAINT_INTERVAL_S", "WIDTH", "Progress"]
