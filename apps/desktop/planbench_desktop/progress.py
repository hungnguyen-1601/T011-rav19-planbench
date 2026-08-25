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
  `/SILENT` rather than `/VERYSILENT`: the first shows a progress bar,
  the second shows nothing at all.

`pywebview` rather than a toolkit, because the embeddable Python this
ships with has **no tkinter** — no tcl, no tk, and adding them would be
another twenty megabytes to carry for one window. pywebview is already
here to draw the app itself.

The window can only be shown on the path that ends in the app exiting,
and that is not a limitation being worked around: most `pywebview`
backends will not start a second event loop in one process, so opening
this and then the main window would be a gamble. Declining the update
never reaches this code.
"""

from __future__ import annotations

import contextlib
import html
import logging
from collections.abc import Callable

logger = logging.getLogger("planbench.desktop")

WIDTH = 460
HEIGHT = 190

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
    """Shows the window, runs the work, closes the window.

    Every method is safe to call when the window never opened: a machine
    where the toolkit will not start still updates, it just updates
    without saying so. Losing the update because its progress bar failed
    would be the wrong trade.
    """

    def __init__(self, title: str, detail: str) -> None:
        self._title = title
        self._detail = detail
        self._window = None
        self._failure: BaseException | None = None

    def run(self, work: Callable[[Progress], None]) -> None:
        """Show the window and run ``work`` beside it until it returns.

        ``work`` runs on a thread because the window owns this one — a
        GUI event loop that is not being pumped is a window that stops
        repainting, which is worse than no window.

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

        def worker() -> None:
            try:
                work(self)
            except BaseException as exc:  # noqa: BLE001 - re-raised below
                self._failure = exc
            finally:
                self.close()

        try:
            webview.start(worker, self._window)
        except Exception as exc:  # noqa: BLE001 - depends on the machine
            logger.warning("progress window failed to start (%s); updating quietly", exc)
            self._window = None
            work(self)
            return

        if self._failure is not None:
            raise self._failure

    def update(self, detail: str, percent: float | None = None) -> None:
        """Say what is happening; ``percent`` of None means "no total".

        A download whose server sent no `Content-Length` has no
        percentage to show, and inventing one would be a bar that jumps.
        """
        if self._window is None:
            return
        try:
            share = "null" if percent is None else f"{max(0.0, min(100.0, percent)):.1f}"
            self._window.evaluate_js(f"render({_js(detail)}, {share})")
        except Exception:  # noqa: BLE001 - cosmetic, never fatal
            pass

    def close(self) -> None:
        if self._window is None:
            return
        # Suppressed: the process is about to end either way, and a
        # window that will not close is not worth an error over.
        with contextlib.suppress(Exception):
            self._window.destroy()


def _js(text: str) -> str:
    """A JavaScript string literal for ``text``.

    Written out rather than interpolated: the detail line carries a file
    name and a version, both of which come from a release somebody else
    published.
    """
    escaped = text.replace("\\", "\\\\").replace("'", "\\'").replace("\n", " ")
    return f"'{escaped}'"


__all__ = ["HEIGHT", "PAGE", "WIDTH", "Progress"]
