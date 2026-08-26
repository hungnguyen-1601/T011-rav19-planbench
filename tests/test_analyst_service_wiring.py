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


def test_the_analyst_package_imports() -> None:
    import planbench_analyst

    assert planbench_analyst.__all__ == ()


def test_the_package_exports_nothing_it_has_not_built_yet() -> None:
    """An empty ``__all__`` is the honest state at A0.

    The modules arrive with their phases. A name published before the
    thing behind it exists is the promise this layer is built to refuse,
    and it is the cheapest kind of fake completion to leave lying around
    — an import that succeeds and a function that returns ``None``.
    """
    import planbench_analyst

    module_dir = Path(planbench_analyst.__file__).parent
    built = sorted(path.stem for path in module_dir.glob("*.py") if path.stem != "__init__")
    assert built == [], (
        f"{built} exist but are not exported; either export them or say why here. "
        "This assertion is meant to be edited as the phases land, not deleted."
    )


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
