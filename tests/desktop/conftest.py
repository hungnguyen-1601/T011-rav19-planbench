"""Make the packaging helpers importable to these tests.

`scripts/desktop/` is not on the application's path and must not be:
nothing the app runs comes from there, and putting build tooling where
the shipped code can import it invites exactly the accident the
`._pth` test-only exclusions exist to prevent. It is on *this* path
because the tests assert things about the generator's output, and
importing it beats re-reading it as text.
"""

from __future__ import annotations

import sys
from pathlib import Path

_HELPERS = Path(__file__).resolve().parents[2] / "scripts" / "desktop"
if str(_HELPERS) not in sys.path:
    sys.path.insert(0, str(_HELPERS))
