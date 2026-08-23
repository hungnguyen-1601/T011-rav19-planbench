"""Every runnable script can actually import what it imports.

**This repository is not packaged.** ``pyproject.toml`` says so, and
tests get their imports from the pytest ``pythonpath`` setting. Scripts
do not: each one carries its **own copy** of the source-directory list
in a ``sys.path`` preamble.

That is a fact duplicated across eight files, and it drifted. When the
explanation layer's recorder was wired into ``planbench_benchmark`` —
``episode.py`` importing ``planbench_explanation.sidecar_writer``, and
``selection.py`` the packet builder — every one of those preambles was
already missing ``packages/explanation``. **The full test suite stayed
green the whole time**, because pytest supplies the path that the
scripts do not, and the only way to see the breakage was to run a real
sweep:

    ModuleNotFoundError: No module named 'planbench_explanation'

So this file checks the thing the suite structurally cannot: that a
script's declared path list covers the packages that exist to be
imported.

**A superset rather than an exact match.** Deciding which of the source
directories each script *needs* would mean re-deriving the import graph
here, which is a second opinion about a fact the interpreter already
owns — and it would have to be re-derived again the next time a package
grows a dependency, which is exactly the maintenance this test exists
to remove. Putting a source directory on ``sys.path`` that a script does
not use costs nothing; leaving one off costs a sweep.
"""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"

#: Entries in the pytest path that are not importable source roots —
#: they exist so test helpers and the T-011 scaffold resolve, and a
#: script has no business with either.
TEST_ONLY = {".", "tests"}


def pytest_source_roots() -> list[str]:
    """The source directories the suite itself imports from."""
    config = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    entries = config["tool"]["pytest"]["ini_options"]["pythonpath"]
    return [entry for entry in entries if entry not in TEST_ONLY]


def declared_paths(script: Path) -> list[str] | None:
    """The script's own ``sys.path`` preamble, read rather than executed.

    Parsed from the source: importing the module to inspect it would run
    the preamble, which is the thing under test, and a script whose
    imports are broken would fail collection instead of failing an
    assertion with a readable message.
    """
    tree = ast.parse(script.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.For) or node.target.__class__ is not ast.Name:
            continue
        if node.target.id != "_package":  # type: ignore[attr-defined]
            continue
        if not isinstance(node.iter, (ast.Tuple, ast.List)):
            continue
        return [
            element.value
            for element in node.iter.elts
            if isinstance(element, ast.Constant) and isinstance(element.value, str)
        ]
    return None


def scripts_with_a_preamble() -> list[Path]:
    return sorted(path for path in SCRIPTS.glob("*.py") if declared_paths(path) is not None)


def test_some_scripts_actually_carry_a_preamble() -> None:
    """Otherwise every assertion below passes by having nothing to check."""
    found = scripts_with_a_preamble()
    assert len(found) >= 5, [path.name for path in found]


@pytest.mark.parametrize("script", scripts_with_a_preamble(), ids=lambda path: path.name)
def test_a_script_can_import_every_source_root_the_suite_can(script: Path) -> None:
    """The drift check.

    A package the tests can import and a script cannot is a package whose
    breakage no test will ever report.
    """
    declared = declared_paths(script)
    assert declared is not None
    missing = [root for root in pytest_source_roots() if root not in declared]
    assert not missing, (
        f"{script.name} does not put {missing} on sys.path. The suite imports from "
        "them via pyproject's pythonpath, so a module moving into one of those "
        "packages breaks this script while every test stays green."
    )


@pytest.mark.parametrize("script", scripts_with_a_preamble(), ids=lambda path: path.name)
def test_every_declared_path_exists(script: Path) -> None:
    """A renamed package leaves a dead entry that silently does nothing."""
    declared = declared_paths(script) or []
    absent = [entry for entry in declared if not (REPO_ROOT / entry).is_dir()]
    assert not absent, f"{script.name} lists {absent}, which is not a directory"
