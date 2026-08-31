"""PlanBench as a desktop application.

    pythonw.exe apps/desktop/planbench_desktop/main.py

The order below is the whole design, and every step depends on the one
before it:

1. make the source roots importable (no-op once packaged),
2. start logging to a file, because `pythonw` has no console and an
   unhandled error would otherwise leave nothing at all behind,
3. provision the data root and set the environment from it,
4. bring the database to head,
5. start the API on a free port,
6. open a window onto it, and when that window closes, stop the server.

Step 2 sits that early on purpose. Everything after it can fail, and on
a machine with no terminal a failure that writes nowhere is
indistinguishable from an application that silently did not start.
"""

from __future__ import annotations

import logging
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

if __package__ in (None, ""):  # invoked as a file path, not as a module
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from planbench_desktop import paths  # noqa: E402
from planbench_desktop.bootstrap import ensure_importable  # noqa: E402

logger = logging.getLogger("planbench.desktop")

WINDOW_TITLE = "PlanBench"
#: Written while the app is running so a second launch can find the
#: first rather than starting a competing server on the same database.
PORT_FILE = ".port"


def configure_logging(root: Path) -> None:
    """Log to a file, and to the console only if there is one.

    `pythonw.exe` gives the process no standard streams — `sys.stderr`
    is `None` — so a handler writing to it raises inside logging itself,
    which is a worse failure than the one being reported.
    """
    handler = RotatingFileHandler(
        root / "logs" / "planbench.log",
        maxBytes=2_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    handlers: list[logging.Handler] = [handler]
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler(sys.stderr))
    logging.basicConfig(level=logging.INFO, handlers=handlers, force=True)


def running_instance(root: Path) -> int | None:
    """The port of an instance already serving, if there is one.

    The file alone is not evidence: a crash leaves it behind pointing at
    a port that is now free or, worse, taken by something else. So the
    port is probed for this API's health route before it is believed.
    """
    from planbench_desktop.server import is_healthy

    marker = root / PORT_FILE
    if not marker.exists():
        return None
    try:
        port = int(marker.read_text(encoding="utf-8").strip())
    except ValueError:
        return None
    return port if is_healthy(port) else None


def open_window(url: str, *, attached_to: int | None = None) -> None:
    """Show the app, and return when the person closes it.

    `pywebview` renders through WebView2, which Windows 11 ships. When it
    cannot start — a missing runtime, a Python build its bridge does not
    support — the fallback is Edge in app mode: the same engine, a window
    that still looks like an application, and nothing extra to install.
    Falling back beats failing, because the alternative for somebody who
    just installed this is a window that never appears.

    ``attached_to`` is the port of *another* process's server, passed when
    this window is a second window onto an instance that was already
    running. That window outlives the thing it is showing: close the first
    window and the server goes with it, leaving this one displaying a page
    whose only symptom is the header pill reading "System unavailable" —
    an accurate sentence that names neither the cause nor the cure. When a
    port is given, this watches it and replaces the page with an
    explanation the moment it stops answering.
    """
    try:
        import webview
    except Exception as exc:  # pragma: no cover - depends on the machine
        logger.warning("pywebview unavailable (%s); opening in a browser window", exc)
        _open_in_browser(url)
        return

    try:
        window = webview.create_window(WINDOW_TITLE, url, width=1440, height=900)
        if attached_to is not None:
            _watch_instance(attached_to, window)
        webview.start()
    except Exception as exc:  # pragma: no cover - depends on the machine
        logger.warning("pywebview failed to start (%s); opening in a browser window", exc)
        _open_in_browser(url)


# Shown in place of the app when the instance a second window was
# attached to has closed. Both languages, because this window has no
# access to the app's own translations any more — the app is gone.
GONE_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>PlanBench</title></head>
<body style="margin:0;display:grid;place-items:center;height:100vh;
 font-family:Segoe UI,system-ui,sans-serif;background:#0f1115;color:#e6e8ee">
  <div style="max-width:34rem;padding:2rem;line-height:1.6">
    <h1 style="font-size:1.25rem;margin:0 0 1rem">PlanBench đã đóng</h1>
    <p style="margin:0 0 1rem;color:#9aa3b2">Cửa sổ này đang xem một bản
      PlanBench đang chạy sẵn, và bản đó vừa được đóng lại. Không có gì
      hỏng và không mất dữ liệu — đóng cửa sổ này rồi mở lại PlanBench.</p>
    <h2 style="font-size:1rem;margin:1.5rem 0 .5rem">PlanBench has closed</h2>
    <p style="margin:0;color:#9aa3b2">This window was showing an instance
      of PlanBench that was already running, and that instance has now
      been closed. Nothing is broken and no data is lost — close this
      window and open PlanBench again.</p>
  </div>
</body></html>"""


def _watch_instance(port: int, window: object) -> None:
    """Say so, once the instance this window is borrowing has gone.

    Three failures rather than one: a single missed probe is what a
    busy machine looks like, and replacing the page under somebody who
    is still using it would be the worse mistake of the two. The thread
    is a daemon so a person closing the window is never made to wait for
    a poll to come round.
    """
    import threading

    from planbench_desktop.server import is_healthy

    def watch() -> None:
        missed = 0
        while missed < 3:
            time.sleep(2.0)
            if is_healthy(port, timeout=2.0):
                missed = 0
                continue
            missed += 1
        logger.info("the instance on %s has closed; this window has nothing to show", port)
        try:
            window.load_html(GONE_HTML)  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover - the window may already be gone
            logger.debug("could not replace the page; the window was probably closed")

    threading.Thread(target=watch, name="instance-watch", daemon=True).start()


def _open_in_browser(url: str) -> None:
    """Edge in app mode, or whatever the system considers a browser.

    This blocks until the browser window closes when Edge is used, and
    returns immediately otherwise — the caller stops the server either
    way, so the worst case is the app closing while a tab is still open
    rather than a server left running.
    """
    import shutil
    import subprocess
    import webbrowser

    edge = shutil.which("msedge")
    if edge:
        subprocess.run([edge, f"--app={url}"], check=False)
        return
    webbrowser.open(url)
    input_available = sys.stdin is not None and sys.stdin.isatty()
    if input_available:
        print(f"PlanBench is running at {url} — press Enter to stop.")  # noqa: T201
        input()


def main() -> int:
    from_checkout = ensure_importable()

    from planbench_desktop import migrate, updater
    from planbench_desktop.provision import provision

    provisioned = provision()
    configure_logging(provisioned.root)
    logger.info(
        "PlanBench %s starting (%s) with data in %s",
        paths.version(),
        "checkout" if from_checkout else "installed",
        provisioned.root,
    )
    if provisioned.created:
        # The only time the password is ever logged. It is also written
        # to `.env` in the same directory; a person who can read this log
        # can already read that file.
        logger.info(
            "first run: sign in as %s / %s (also in .env)",
            provisioned.nickname,
            provisioned.password,
        )

    # Before the server starts, and before the window: the installer
    # replaces the directory this process is running out of, so the
    # update has to happen while as little as possible is open.
    if updater.offer(
        paths.version(),
        provisioned.root / "updates",
        [sys.executable, str(Path(__file__).resolve())],
    ):
        logger.info("closing for the installer")
        return 0

    existing = running_instance(provisioned.root)
    if existing is not None:
        logger.info("another instance is serving on %s; opening a window onto it", existing)
        open_window(f"http://127.0.0.1:{existing}", attached_to=existing)
        return 0

    from planbench_desktop.server import DesktopServer, free_port

    migrate.upgrade(paths.INSTALL_ROOT, provisioned.root / "planbench.db")

    server = DesktopServer(free_port())
    marker = provisioned.root / PORT_FILE
    try:
        server.start()
        marker.write_text(str(server.port), encoding="utf-8")
        open_window(server.url)
    except Exception:
        logger.exception("PlanBench failed to start")
        return 1
    finally:
        server.stop()
        marker.unlink(missing_ok=True)
    logger.info("PlanBench closed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
