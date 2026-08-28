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

#: On the two local lists and deliberately absent from the API image:
#: the desktop launcher is a different program that ships in a different
#: artifact, and the image does not ``COPY apps/desktop`` at all. Written
#: down as an exemption rather than left to a set difference, because
#: "the image is missing a package" and "the image was never meant to
#: have it" are the same shape of test failure and different bugs.
IMAGE_EXEMPT = {"apps/desktop"}


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


def image_pythonpath() -> list[str]:
    """The ``/app``-relative entries the API image runs with.

    A third list, kept by a third mechanism, with the same failure mode
    as the first two and one difference that makes it worse: the image
    is built in CI and the missing import surfaces as a container that
    exits, hours after the commit that caused it.
    """
    dockerfile = (REPO_ROOT / "docker" / "Dockerfile.api").read_text(encoding="utf-8")
    assignment = "\n".join(
        line for line in dockerfile.splitlines() if line.startswith("ENV PYTHONPATH=")
    )
    assert assignment, "PYTHONPATH is no longer set as a single ENV line in Dockerfile.api"
    return re.findall(r"/app/([A-Za-z0-9_/]+)", assignment)


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


class TestTheImageAgreesWithBoth:
    def test_the_image_can_import_everything_the_suite_can(self) -> None:
        missing = [
            entry
            for entry in pytest_pythonpath()
            if entry not in TEST_ONLY and entry not in IMAGE_EXEMPT
            if entry not in image_pythonpath()
        ]
        assert not missing, (
            f"{missing} are on pytest's pythonpath but missing from PYTHONPATH in "
            "docker/Dockerfile.api, so the suite imports them and the deployed API "
            "cannot. Add them there, or to IMAGE_EXEMPT with the reason."
        )

    def test_the_image_carries_nothing_the_suite_never_sees(self) -> None:
        extra = [entry for entry in image_pythonpath() if entry not in pytest_pythonpath()]
        assert not extra, (
            f"{extra} are on the image's PYTHONPATH but missing from pythonpath in "
            "pyproject.toml, so they run in the container and are never imported by a test."
        )

    def test_the_image_copies_what_it_puts_on_the_path(self) -> None:
        """A path entry the image never ``COPY``s is an empty directory
        at best. The two halves are written twelve lines apart and only
        one of them fails loudly."""
        dockerfile = (REPO_ROOT / "docker" / "Dockerfile.api").read_text(encoding="utf-8")
        copied = [
            source.rstrip("/")
            for source in re.findall(
                r"^COPY ([A-Za-z0-9_/.]+)\s+/app/", dockerfile, flags=re.MULTILINE
            )
        ]
        for entry in image_pythonpath():
            assert any(entry == top or entry.startswith(f"{top.rstrip('/')}/") for top in copied), (
                f"{entry} is on the image's PYTHONPATH but nothing COPYs it into /app"
            )
