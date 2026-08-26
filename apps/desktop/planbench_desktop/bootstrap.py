"""Make the source roots importable when running from a checkout.

In the shipped build this does nothing, and doing nothing is the point.
The packaged runtime declares all twelve source roots in
`python312._pth`, which is the only mechanism an embeddable Python
honours — it ignores `PYTHONPATH`, ignores the registry, and ignores
anything set after startup by a process that has already failed to
import its first module.

Run from a checkout, though, nothing has put those roots anywhere, and
the first import fails. So: try the import, and only if it fails read
the declaration out of `pyproject.toml` — the same list `scripts/serve.py`
reads and for the same reason. Three hand-maintained copies of this list
already exist in the repository and one of them has already drifted; a
fourth would be a fourth chance at the same bug.
"""

from __future__ import annotations

import importlib.util
import sys
import tomllib

from planbench_desktop.paths import INSTALL_ROOT

#: On pytest's path and deliberately not on the application's — `.`
#: resolves the retired `src.*` scaffold and `tests` would let a test
#: helper shadow a real module. Kept identical to `scripts/serve.py`.
TEST_ONLY = frozenset({".", "tests"})


def source_roots() -> list[str]:
    """The package roots, from the one file that declares them."""
    config = tomllib.loads((INSTALL_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    declared = config["tool"]["pytest"]["ini_options"]["pythonpath"]
    return [str(INSTALL_ROOT / entry) for entry in declared if entry not in TEST_ONLY]


def ensure_importable() -> bool:
    """Put the source roots on ``sys.path`` if they are not already there.

    Returns whether anything had to be added, which is also the answer to
    "is this a checkout rather than an installation?" — useful in the
    log when somebody is trying to work out which one they are running.
    """
    if importlib.util.find_spec("planbench_api") is not None:
        return False
    for root in reversed(source_roots()):
        if root in sys.path:
            sys.path.remove(root)
        sys.path.insert(0, root)
    return True


__all__ = ["TEST_ONLY", "ensure_importable", "source_roots"]
