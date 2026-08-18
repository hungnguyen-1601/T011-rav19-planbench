"""The child side of the subprocess lane: one plugin, one pipe.

Runs as ``python -m planbench_simulator.host.runtimes.subprocess_worker``.
Reads one JSON request per line on stdin, writes one JSON response per
line on stdout, until stdin closes.

**stdout is the protocol, so nothing else may write to it.** A plugin
that prints — and plugins print — would inject a line the host tries to
parse as a response. So the first thing this does is move the real
stdout aside and point ``sys.stdout`` at stderr: the plugin's prints
become diagnostics on the host's error stream, where they are readable
and harmless, instead of protocol corruption that looks like a
malformed response from a plugin that did nothing wrong.

Errors travel as data (``{"error": ...}``), never as a traceback on a
closed pipe: a worker that dies without answering is indistinguishable
from a hung one, and the host would have to wait out a timeout to learn
something the worker already knew.
"""

from __future__ import annotations

import json
import sys
import time
import traceback
from importlib import import_module
from typing import Any


def _install_protocol_stdout():
    """Take the real stdout for the protocol; give the plugin stderr."""
    protocol = sys.stdout
    sys.stdout = sys.stderr
    return protocol


def _load(entry_point: str, config: dict[str, Any]) -> Any:
    module_name, _, attribute = entry_point.partition(":")
    module = import_module(module_name)
    return getattr(module, attribute)(**config)


def _respond(protocol, payload: dict[str, Any]) -> None:
    protocol.write(json.dumps(payload) + "\n")
    protocol.flush()


def main(argv: list[str]) -> int:
    protocol = _install_protocol_stdout()
    entry_point = argv[1]
    config = json.loads(argv[2]) if len(argv) > 2 else {}

    try:
        plugin = _load(entry_point, config)
    except Exception:
        # Reported rather than raised: the host is waiting on a line, and
        # a traceback on a dead pipe would read as a timeout.
        _respond(protocol, {"error": f"load failed: {traceback.format_exc()}"})
        return 1

    _respond(protocol, {"ready": True, "name": getattr(plugin, "name", "")})

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError as error:
            _respond(protocol, {"error": f"malformed request: {error}"})
            continue

        started = time.perf_counter()
        try:
            result = _dispatch(plugin, message)
        except Exception:
            _respond(protocol, {"error": traceback.format_exc()})
            continue
        # The plugin's own compute time, measured where the plugin
        # actually runs. The host cannot see this — see §5.9 rule 6 for
        # why that makes it diagnostic rather than gate-authoritative.
        result["reported_compute_ms"] = (time.perf_counter() - started) * 1000.0
        _respond(protocol, result)
    return 0


def _dispatch(plugin: Any, message: dict[str, Any]) -> dict[str, Any]:
    kind = message.get("kind")
    if kind == "reset":
        plugin.reset(_Request(message["request"]))
        return {"ok": True}
    if kind == "step":
        result = plugin.step(_Request(message["request"]))
        return {"action": _action_of(result)}
    if kind == "ping":
        return {"ok": True}
    if kind == "shutdown":
        return {"ok": True}
    return {"error": f"unknown request kind {kind!r}"}


def _action_of(result: Any) -> dict[str, float]:
    """The command, however the plugin chose to express it.

    A subprocess plugin cannot return a ``LocalPlanResult`` — that model
    lives on the host side of the pipe — so it may return one if it has
    the package, or a plain mapping if it does not. Both are read here,
    and neither is guessed at: an object with neither shape is an error
    the host turns into a safe stop.
    """
    action = getattr(result, "action", None)
    if action is not None:
        return {
            "linear_velocity": float(action.linear_velocity),
            "angular_velocity": float(action.angular_velocity),
        }
    if isinstance(result, dict):
        return {
            "linear_velocity": float(result["linear_velocity"]),
            "angular_velocity": float(result["angular_velocity"]),
        }
    raise TypeError(f"plugin returned {type(result).__name__}, which carries no action")


class _Request:
    """Attribute access over a decoded request.

    The plugin sees ``request.channels[0].payload`` exactly as it would
    in-process, so one plugin can run in either lane without knowing
    which — that equivalence is what makes a lane comparison meaningful.
    """

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def __getattr__(self, name: str) -> Any:
        try:
            value = self._data[name]
        except KeyError as error:
            raise AttributeError(name) from error
        if name == "channels":
            return tuple(_Request(entry) for entry in value)
        return value

    def get(self, name: str, default: Any = None) -> Any:
        return self._data.get(name, default)


if __name__ == "__main__":  # pragma: no cover - exercised as a subprocess
    raise SystemExit(main(sys.argv))
