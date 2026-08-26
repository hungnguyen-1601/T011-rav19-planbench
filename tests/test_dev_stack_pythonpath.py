"""The server and the suite must import the same packages.

This project is not installed. Every package under ``packages/`` and
``services/`` reaches ``sys.path`` twice over, by two mechanisms that
know nothing about each other:

* ``pyproject.toml`` ``[tool.pytest.ini_options] pythonpath`` — for the
  suite;
* ``PY_PATH`` in ``scripts/dev_stack.sh`` — for the running API.

Nothing kept them in step, and the drift is not hypothetical. When the
decision layer landed, ``packages/decision`` was added to the pytest list
and not to the script. The suite imported ``planbench_decision`` happily
— 2277 tests green — while ``dev_stack.sh start`` could not bring the API
up at all, because ``planbench_benchmark.candidates`` imports it at
module level and the API imports that.

**A green suite was no evidence at all here**, and could not have been:
pytest supplies its own path and never runs the script. That is the shape
of gap this file exists to close, and it is the same shape as the
``psutil`` one found the same day — a dependency the tests happened to
satisfy by a route production does not use.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

#: Present for the suite and deliberately absent from the server's path.
#: ``.`` resolves the ``src.*`` scaffold and ``tests`` makes shared
#: helpers importable as top-level modules; neither is something the API
#: should be able to reach.
TEST_ONLY = {".", "tests"}


def pytest_pythonpath() -> list[str]:
    config = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return list(config["tool"]["pytest"]["ini_options"]["pythonpath"])


def dev_stack_pythonpath() -> list[str]:
    """The ``$ROOT``-relative entries ``PY_PATH`` is built from.

    Parsed rather than executed: running the script would start servers.
    The assignment is a handful of plain lines, so a regex over
    ``$ROOT/<path>`` reads them without pretending to be a shell.
    """
    script = (REPO_ROOT / "scripts" / "dev_stack.sh").read_text(encoding="utf-8")
    assignment = "\n".join(line for line in script.splitlines() if line.startswith("PY_PATH="))
    assert assignment, "PY_PATH is no longer assigned at the top level of dev_stack.sh"
    return re.findall(r"\$ROOT/([A-Za-z0-9_/]+)", assignment)


class TestTheTwoPathListsAgree:
    def test_the_server_can_import_everything_the_suite_can(self) -> None:
        """The direction that actually broke.

        A package the suite can import and the server cannot is a green
        test run over code that will not start.
        """
        missing = [
            p for p in pytest_pythonpath() if p not in TEST_ONLY and p not in dev_stack_pythonpath()
        ]
        assert not missing, (
            f"{missing} are on pytest's pythonpath but missing from PY_PATH in "
            "scripts/dev_stack.sh, so the suite imports them and the API cannot. "
            "Add them there."
        )

    def test_the_suite_can_import_everything_the_server_can(self) -> None:
        """The other direction is quieter but not harmless: a package the
        server loads and the suite never sees is code shipped untested."""
        extra = [p for p in dev_stack_pythonpath() if p not in pytest_pythonpath()]
        assert not extra, (
            f"{extra} are on the server's PY_PATH but missing from pythonpath in "
            "pyproject.toml, so they run in production and are never imported by a test."
        )

    def test_every_named_directory_exists(self) -> None:
        """A path entry pointing at nothing fails silently — imports just
        keep looking elsewhere — so a renamed package leaves a dead entry
        nobody notices until something else breaks."""
        for entry in set(pytest_pythonpath()) | set(dev_stack_pythonpath()):
            assert (REPO_ROOT / entry).is_dir(), (
                f"{entry} is on a python path but is not a directory"
            )

    def test_the_decision_layer_is_on_both(self) -> None:
        """Named explicitly, because this is the one that broke and a
        generic set comparison would pass again the moment somebody
        removed it from both lists at once."""
        assert "packages/decision" in pytest_pythonpath()
        assert "packages/decision" in dev_stack_pythonpath()
