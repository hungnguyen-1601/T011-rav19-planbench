"""Structured (JSON-lines) logging for the API process."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0] is not None:
            payload["exception"] = self.formatException(record.exc_info)
        extra = getattr(record, "context", None)
        if extra:
            payload["context"] = extra
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(debug: bool = False) -> None:
    """JSON lines on stderr, unless somebody else already arranged a home.

    **Taking the tree unconditionally silenced the desktop app.** This
    replaced the handlers on ``planbench`` and set ``propagate = False``,
    which is right when the API owns the process and wrong when it does
    not. The desktop launcher runs the API in a thread of its own
    process, having first pointed the real root at a rotating file — and
    then this ran during ``from planbench_api.main import app`` and cut
    every ``planbench.*`` logger off from it.

    Two things followed, and the second hid the first. The app writes to
    that file under ``pythonw.exe``, where ``sys.stderr`` is ``None``, so
    the handler installed here had nowhere to write; and with propagation
    off, nothing reached the file either. A 500 in the shipped app logged
    its traceback into a stream that does not exist. Reproducing one
    against a running installation produced the error and not one line in
    ``planbench.log`` — including the API's own "api ready" line, which is
    what made it findable.

    So: when the root logger already has handlers, this leaves the tree
    alone and lets records propagate to them. That is the desktop, and
    any host that configured logging before importing the app. When it
    does not, the API owns the process and behaves exactly as before.
    """
    logger = logging.getLogger("planbench")
    logger.setLevel(logging.DEBUG if debug else logging.INFO)

    if logging.getLogger().handlers:
        # Somebody outside configured logging. Records belong to them.
        logger.handlers = []
        logger.propagate = True
        return

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger.handlers = [handler]
    logger.propagate = False
