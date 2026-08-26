"""Write the tool catalog's JSON Schema files under ``schemas/tools/``.

The schemas are **generated**, never hand-edited: the source of truth is
each card's :class:`~planbench_explanation.tools.ToolIO`, which is also
what the tool host enforces at admission. Two hand-maintained
descriptions of one contract disagree eventually, and the one nobody
executes is the one that rots.

``tests/test_explanation_e5.py`` re-runs the generator in memory and
compares against what is on disk, so a card edited without re-exporting
fails there rather than shipping a schema that describes the old tool.

Usage::

    python scripts/export_tool_schemas.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "explanation"))
sys.path.insert(0, str(ROOT / "packages" / "schemas"))
sys.path.insert(0, str(ROOT / "packages" / "decision"))
sys.path.insert(0, str(ROOT / "packages" / "metrics"))
sys.path.insert(0, str(ROOT / "packages" / "planning"))
sys.path.insert(0, str(ROOT / "packages" / "benchmark"))

from planbench_explanation.catalog import TOOL_CATALOG  # noqa: E402
from planbench_explanation.tools import write_tool_schemas  # noqa: E402


def main() -> int:
    written = write_tool_schemas(TOOL_CATALOG, ROOT)
    for path in written:
        print(path.relative_to(ROOT).as_posix())
    print(f"{len(written)} schema file(s) for catalog {TOOL_CATALOG.catalog_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
