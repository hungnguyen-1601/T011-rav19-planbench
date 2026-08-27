"""The analyst package is reachable, and reachable the same way everywhere.

A0 of plan bản 8 ships no behaviour: it ships a package and the four
lists that have to name it. That is worth a test file of its own because
the failure mode is not an exception — it is an import that resolves in
one environment and not in another, which is how ``packages/decision``
once passed 2277 tests while the API could not start.

The lists themselves are compared against each other in
``test_dev_stack_pythonpath.py``. This file asks the narrower question:
is *this* package on them, and does it import.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

from test_dev_stack_pythonpath import (
    dev_stack_pythonpath,
    image_pythonpath,
    pytest_pythonpath,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

ENTRY = "services/analyst_service"

#: What the analyst image is actually asked to import. Not the whole
#: package list — these are the modules a round touches on its way from
#: a frame to an answer, plus the two that carry no dependency at all
#: and so would still import if the graph above them were broken.
IMAGE_IMPORTS = (
    "planbench_analyst",
    "planbench_analyst.packet_view",
    "planbench_analyst.runner",
    "planbench_analyst.guard",
    "planbench_analyst.round_host",
    "planbench_analyst.stdio_lane",
    "planbench_analyst.model_gateway",
    "planbench_analyst.sanitize",
    "planbench_analyst.prompts",
    "planbench_explanation",
    "planbench_explanation.host",
    "planbench_benchmark.traits_store",
    "planbench_agent.provider",
)


#: The phases that have landed, as the modules they brought. Edited when
#: a phase lands and never otherwise — the test below reads it as the
#: claim "this is all there is", and a module on disk that nobody
#: exports is a stub left behind.
PHASES_LANDED = [
    "analyst",
    "bundle_builder",
    "cache",
    "candidates",
    "episode_guard",
    "episode_view",
    "eval_spec",
    "features",
    "guard",
    "harness",
    "identity",
    "knowledge_provider",
    "model_gateway",
    "packet_view",
    "preregistration",
    "prompts",
    "restricted",
    "round_host",
    "routing",
    "runner",
    "sanitize",
    "scoring",
    "stdio_lane",
    "stdio_protocol",
    "traits_snapshot",
]


def test_the_analyst_package_imports() -> None:
    import planbench_analyst

    assert planbench_analyst.__all__


def test_the_package_exports_what_it_has_built_and_nothing_more() -> None:
    """The cheapest fake completion in a plan this long is a module that
    imports, exports nothing, and returns ``None`` — from outside it
    looks exactly like a phase that landed."""
    import planbench_analyst

    module_dir = Path(planbench_analyst.__file__).parent
    built = sorted(path.stem for path in module_dir.glob("*.py") if path.stem != "__init__")
    assert built == PHASES_LANDED, (
        f"modules on disk are {built} and PHASES_LANDED says {PHASES_LANDED}. "
        "This list is meant to be edited as the phases land, not deleted."
    )

    exported = [getattr(planbench_analyst, name) for name in planbench_analyst.__all__]
    covered = {getattr(item, "__module__", "").rsplit(".", 1)[-1] for item in exported}
    orphans = [module for module in built if module not in covered]
    assert not orphans, f"{orphans} are on disk but contribute no exported name"


def test_the_analyst_service_is_on_every_path_list() -> None:
    """Named explicitly rather than left to a set comparison.

    A generic "the lists agree" test passes again the moment somebody
    removes an entry from all of them at once, which is exactly what a
    hasty revert does.
    """
    assert ENTRY in pytest_pythonpath(), "missing from pyproject.toml pythonpath"
    assert ENTRY in dev_stack_pythonpath(), "missing from PY_PATH in scripts/dev_stack.sh"
    assert ENTRY in image_pythonpath(), "missing from PYTHONPATH in docker/Dockerfile.api"


def analyst_image_pythonpath() -> list[str]:
    """The ``/app``-relative entries the **analyst** image runs with.

    A fourth list, and the one with the narrowest contents by design:
    ``Dockerfile.analyst`` deliberately carries no ``services/simulator``,
    no ``apps/``, no ``ml/``.
    """
    dockerfile = (REPO_ROOT / "docker" / "Dockerfile.analyst").read_text(encoding="utf-8")
    assignment = "\n".join(
        line for line in dockerfile.splitlines() if line.startswith("ENV PYTHONPATH=")
    )
    assert assignment, "PYTHONPATH is no longer set as a single ENV line in Dockerfile.analyst"
    return re.findall(r"/app/([A-Za-z0-9_/]+)", assignment)


class TestTheAnalystImageCanImportItself:
    """The list-comparison tests ask whether every path entry has a
    ``COPY``. They cannot ask the question that actually bit: does the
    package **import** under that path and no other.

    It did not. ``planbench_analyst/__init__`` reaches
    ``planbench_benchmark.traits_store`` for ``TraitSource``; the
    benchmark package body used to import its engine eagerly, which
    reached ``planbench_metrics`` and then ``planbench_simulator`` —
    a source root the analyst image deliberately does not carry. Every
    module died, down to ``sanitize``, and the suite stayed green
    because pytest runs with the simulator on ``sys.path``.

    So this runs a subprocess whose ``PYTHONPATH`` is exactly the
    image's, and asserts twice: the imports resolve, and the simulator
    is *not* among the loaded modules. The second half is the one that
    keeps the test honest — an import can succeed by pulling in the very
    thing the image was built without.
    """

    def _run(self, code: str) -> subprocess.CompletedProcess[str]:
        entries = analyst_image_pythonpath()
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join(str(REPO_ROOT / entry) for entry in entries)
        return subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            env=env,
            cwd=REPO_ROOT,
            check=False,
        )

    def test_every_module_a_round_touches_imports(self) -> None:
        code = "import importlib\n" + "\n".join(
            f"importlib.import_module({name!r})" for name in IMAGE_IMPORTS
        )
        result = self._run(code)
        assert result.returncode == 0, (
            "the analyst image cannot import its own package:\n" + result.stderr
        )

    def test_the_simulator_is_not_dragged_in(self) -> None:
        """A lazy body is only lazy until somebody adds one eager import."""
        code = (
            "import sys, importlib\n"
            + "\n".join(f"importlib.import_module({name!r})" for name in IMAGE_IMPORTS)
            + "\nleaked = [m for m in sys.modules if m.startswith('planbench_simulator')]\n"
            "assert not leaked, leaked\n"
        )
        result = self._run(code)
        assert result.returncode == 0, (
            "importing the analyst package pulled the simulator into the image's "
            "import graph, which the image does not carry:\n" + result.stderr
        )


def test_ruff_sorts_the_analyst_package_as_first_party() -> None:
    """The fifth list, and the one with the quietest failure.

    ``known-first-party`` missing a ``planbench_*`` package is what the
    comment in ruff.toml records as having broken CI once already: import
    blocks that sort correctly on one machine and not on another.
    """
    config = tomllib.loads((REPO_ROOT / "ruff.toml").read_text(encoding="utf-8"))
    assert "planbench_analyst" in config["lint"]["isort"]["known-first-party"]
