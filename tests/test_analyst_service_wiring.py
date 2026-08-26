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

import tomllib
from pathlib import Path

from test_dev_stack_pythonpath import (
    dev_stack_pythonpath,
    image_pythonpath,
    pytest_pythonpath,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

ENTRY = "services/analyst_service"


#: The phases that have landed, as the modules they brought. Edited when
#: a phase lands and never otherwise — the test below reads it as the
#: claim "this is all there is", and a module on disk that nobody
#: exports is a stub left behind.
PHASES_LANDED = [
    "analyst",
    "bundle_builder",
    "cache",
    "guard",
    "harness",
    "identity",
    "knowledge_provider",
    "model_gateway",
    "packet_view",
    "prompts",
    "restricted",
    "round_host",
    "runner",
    "sanitize",
    "stdio_lane",
    "stdio_protocol",
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


def test_ruff_sorts_the_analyst_package_as_first_party() -> None:
    """The fifth list, and the one with the quietest failure.

    ``known-first-party`` missing a ``planbench_*`` package is what the
    comment in ruff.toml records as having broken CI once already: import
    blocks that sort correctly on one machine and not on another.
    """
    config = tomllib.loads((REPO_ROOT / "ruff.toml").read_text(encoding="utf-8"))
    assert "planbench_analyst" in config["lint"]["isort"]["known-first-party"]
