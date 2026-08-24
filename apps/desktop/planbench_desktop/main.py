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


def open_window(url: str) -> None:
    """Show the app, and return when the person closes it.

    `pywebview` renders through WebView2, which Windows 11 ships. When it
    cannot start — a missing runtime, a Python build its bridge does not
    support — the fallback is Edge in app mode: the same engine, a window
    that still looks like an application, and nothing extra to install.
    Falling back beats failing, because the alternative for somebody who
    just installed this is a window that never appears.
    """
    try:
        import webview
    except Exception as exc:  # pragma: no cover - depends on the machine
        logger.warning("pywebview unavailable (%s); opening in a browser window", exc)
        _open_in_browser(url)
        return

    try:
        webview.create_window(WINDOW_TITLE, url, width=1440, height=900)
        webview.start()
    except Exception as exc:  # pragma: no cover - depends on the machine
        logger.warning("pywebview failed to start (%s); opening in a browser window", exc)
        _open_in_browser(url)


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

    from planbench_desktop import migrate
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

    existing = running_instance(provisioned.root)
    if existing is not None:
        logger.info("another instance is serving on %s; opening a window onto it", existing)
        open_window(f"http://127.0.0.1:{existing}")
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
