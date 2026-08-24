"""The API, running inside the desktop process on a port nobody chose.

A fixed port would be the simpler thing and it is the wrong thing: 8000
is the most contended port on a developer's machine, and the failure
mode is an app that opens onto somebody else's server or refuses to open
at all. Asking the operating system for a free one costs a few lines and
removes the whole class.

The port has to be known *before* the server starts, because the window
needs a URL to load — hence binding a socket to port 0, reading what was
assigned, and closing it again. There is a race in that gap, in theory.
In practice the gap is microseconds on a single-user machine, and the
alternative is passing a bound socket through uvicorn's configuration,
which is a great deal of machinery to close a window that nothing is
reaching through.

Uvicorn runs on a thread rather than a process. Closing the window then
sets a flag this side of a process boundary, which is what makes it
impossible to leave an orphaned server behind holding the database.
"""

from __future__ import annotations

import logging
import socket
import threading
import time
from urllib.error import URLError
from urllib.request import urlopen

logger = logging.getLogger("planbench.desktop")

#: How long to wait for the API to answer before giving up. Generous:
#: first launch imports numpy, scipy and pyarrow, and a cold filesystem
#: cache on a laptop makes that slow exactly once.
STARTUP_TIMEOUT_S = 60.0

HOST = "127.0.0.1"


def free_port() -> int:
    """A port the operating system says is free right now."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((HOST, 0))
        return int(probe.getsockname()[1])


def is_healthy(port: int, timeout: float = 1.0) -> bool:
    """Whether something on ``port`` answers as this API.

    Used both to wait for our own server and to recognise an instance
    already running — so it checks the health route rather than merely
    that the port is occupied.
    """
    try:
        with urlopen(f"http://{HOST}:{port}/api/v1/health", timeout=timeout) as response:
            return response.status == 200
    except (URLError, OSError, ValueError):
        return False


class DesktopServer:
    """Uvicorn on a background thread, with a shutdown that completes."""

    def __init__(self, port: int) -> None:
        self.port = port
        self.url = f"http://{HOST}:{port}"
        self._server = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start serving and return once the API answers.

        The application is imported here rather than at module scope:
        importing `planbench_api.main` builds the app, and the app reads
        configuration that provisioning has to have written first.
        """
        import uvicorn

        from planbench_api.main import app

        config = uvicorn.Config(
            app,
            host=HOST,
            port=self.port,
            log_config=None,  # the launcher already configured logging
            access_log=False,
        )
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, name="planbench-api", daemon=True)
        self._thread.start()

        deadline = time.monotonic() + STARTUP_TIMEOUT_S
        while time.monotonic() < deadline:
            if is_healthy(self.port):
                logger.info("api ready on %s", self.url)
                return
            if not self._thread.is_alive():
                raise RuntimeError("the API stopped while starting; see the log above")
            time.sleep(0.2)
        raise TimeoutError(f"the API did not answer within {STARTUP_TIMEOUT_S:.0f}s")

    def stop(self) -> None:
        """Ask the server to finish and wait for the thread to end.

        Waiting matters: the process exits immediately afterwards, and a
        SQLite connection closed by process death rather than by the
        server leaves a journal file behind for the next launch to
        recover.
        """
        if self._server is not None:
            self._server.should_exit = True
        if self._thread is not None:
            self._thread.join(timeout=20)
            if self._thread.is_alive():
                logger.warning("the API did not stop within 20s; exiting anyway")


__all__ = ["HOST", "STARTUP_TIMEOUT_S", "DesktopServer", "free_port", "is_healthy"]
