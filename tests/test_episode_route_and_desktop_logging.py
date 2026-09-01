"""Two faults that made one symptom: a 500 nobody could read.

Opening the episode panel on a run whose sidecar recorded a planned
route answered `internal server error`, and the installed app's log had
nothing in it — not the traceback, not even the API's own "api ready"
line. The second fault is why the first took a day to find.

* ``_first_route`` unpacked route vertices as pairs. They are written as
  ``{"x": …, "y": …}`` by ``decision_service._planned_routes`` and read
  that way by the replay view in the same file; unpacking a mapping
  yields its keys, so the first vertex asked for ``float("x")``.
* ``configure_logging`` replaced the handlers on the ``planbench``
  logger and set ``propagate = False``. In the desktop the launcher had
  already pointed the real root at a rotating file, and the app runs
  under ``pythonw.exe`` where ``sys.stderr`` is ``None`` — so the
  records went to a stream that does not exist, and propagation was off,
  so they reached nothing else.
"""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _builder():  # type: ignore[no-untyped-def]
    from planbench_explanation import episode_builder

    return episode_builder


class TestARouteVertexIsReadTheWayItWasWritten:
    """The shape on disk is a mapping. Both shapes are accepted, because
    one reader understanding only what it was shown is the mistake that
    produced this."""

    def test_the_shape_the_producer_writes(self) -> None:
        trace = {"planned_routes": [{"points": [{"x": 1.0, "y": 2.0}, {"x": 3.0, "y": 4.5}]}]}
        assert _builder()._first_route(trace) == [(1.0, 2.0), (3.0, 4.5)]

    def test_the_pair_shape_older_sidecars_hold(self) -> None:
        trace = {"planned_routes": [{"points": [[1.0, 2.0], [3.0, 4.5]]}]}
        assert _builder()._first_route(trace) == [(1.0, 2.0), (3.0, 4.5)]

    def test_numbers_arriving_as_text_still_become_numbers(self) -> None:
        """JSON round-trips have handed this both; the float() call was
        never the part that was wrong."""
        trace = {"planned_routes": [{"points": [{"x": "1.5", "y": "2.5"}]}]}
        assert _builder()._first_route(trace) == [(1.5, 2.5)]

    def test_the_first_route_is_the_one_taken(self) -> None:
        """Arc length is measured along one line for the whole episode,
        so a route produced after a replan describes only what came
        after it."""
        trace = {
            "planned_routes": [
                {"points": [{"x": 0.0, "y": 0.0}]},
                {"points": [{"x": 9.0, "y": 9.0}]},
            ]
        }
        assert _builder()._first_route(trace) == [(0.0, 0.0)]

    def test_an_episode_with_no_recorded_plan_is_not_an_error(self) -> None:
        """Every fixture the suite had looked like this, which is why the
        fault reached a release."""
        assert _builder()._first_route({"planned_routes": []}) is None
        assert _builder()._first_route({}) is None

    def test_the_producer_and_this_reader_agree(self) -> None:
        """Pinned against the source rather than a copy of the shape: the
        two disagreeing is the whole fault, and a test that restates one
        of them would not have caught it."""
        source = (REPO / "apps" / "api" / "planbench_api" / "decision_service.py").read_text(
            encoding="utf-8"
        )
        assert '"points": [{"x": x, "y": y} for x, y in record.output_path]' in source


def _logging_config():  # type: ignore[no-untyped-def]
    """Imported by path and fresh, since it mutates global logging state."""
    spec = importlib.util.spec_from_file_location(
        "logging_config_under_test",
        REPO / "apps" / "api" / "planbench_api" / "logging_config.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestTheApiDoesNotSilenceItsHost:
    """The desktop runs the API inside its own process, having already
    pointed the root logger at a rotating file."""

    def _restore(self, root_handlers, planbench_handlers, propagate):  # type: ignore[no-untyped-def]
        logging.getLogger().handlers = root_handlers
        logging.getLogger("planbench").handlers = planbench_handlers
        logging.getLogger("planbench").propagate = propagate

    def test_records_reach_a_host_that_configured_logging(self) -> None:
        root = logging.getLogger()
        planbench = logging.getLogger("planbench")
        saved = (root.handlers, planbench.handlers, planbench.propagate)
        seen: list[str] = []

        class _Collect(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                seen.append(record.getMessage())

        try:
            root.handlers = [_Collect()]
            _logging_config().configure_logging()
            logging.getLogger("planbench.api").error("a 500 happened here")
            assert seen == ["a 500 happened here"], seen
        finally:
            self._restore(*saved)

    def test_it_still_owns_the_process_when_nobody_else_does(self) -> None:
        """A plain API deployment behaves exactly as before: its own JSON
        handler, and no propagation to a root that has none."""
        root = logging.getLogger()
        planbench = logging.getLogger("planbench")
        saved = (root.handlers, planbench.handlers, planbench.propagate)
        try:
            root.handlers = []
            module = _logging_config()
            module.configure_logging()
            assert planbench.propagate is False
            assert len(planbench.handlers) == 1
            assert isinstance(planbench.handlers[0].formatter, module.JsonFormatter)
        finally:
            self._restore(*saved)

    def test_the_launcher_guards_a_stream_that_is_not_there(self) -> None:
        """Why the silence was total rather than merely misplaced: under
        `pythonw.exe` there is no stderr, so the handler this used to
        install had nowhere to write. The launcher already knew that."""
        source = (REPO / "apps" / "desktop" / "planbench_desktop" / "main.py").read_text(
            encoding="utf-8"
        )
        assert "if sys.stderr is not None:" in source
