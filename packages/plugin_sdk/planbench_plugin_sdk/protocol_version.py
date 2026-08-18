"""The plugin protocol's version, and what "compatible" means.

One number, stated once. A manifest declares the ``plugin_api`` it was
written against; the host accepts it when the **major** matches. Minor
and patch are additive by definition — a plugin written against 1.0 must
keep parsing under 1.4 — so refusing on them would break every published
plugin each time the SDK grows a field.
"""

from __future__ import annotations

import re

#: What this SDK speaks.
#:
#: 1.1.0 (H5) added ``entry_point`` and ``python_dependencies`` to a
#: runtime profile — additive, so every 1.0 manifest still parses, which
#: is the whole reason compatibility is judged on the major.
PLUGIN_API_VERSION = "1.1.0"

PLUGIN_API_MAJOR = 1

_VERSION_PATTERN = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def is_compatible(declared: str) -> bool:
    """True when a manifest's ``plugin_api`` can be parsed by this SDK."""
    match = _VERSION_PATTERN.match(declared)
    return match is not None and int(match.group(1)) == PLUGIN_API_MAJOR
