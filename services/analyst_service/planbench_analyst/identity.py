"""What a round was run *with*, as one checksum per moving part.

Three things vary between two runs that produce different answers from
the same packet: the words in the prompt, the knobs the model was given,
and the code that assembled both. The first has its own checksum in
:mod:`planbench_analyst.prompts`. This module covers the other two, and
combines all three into the key a dev cache may use and the bundle at A7
must pin.

**Generation config is flattened to JSON Pointer paths, not dotted
keys.** ``{"thinking.type": "enabled"}`` and ``{"thinking": {"type":
"enabled"}}`` flatten to the same dotted string and to different
pointers, and a checksum that cannot tell two configurations apart is a
checksum that certifies one having graded the other. Escaping follows
RFC 6901 (``~0`` for ``~``, ``~1`` for ``/``), which is what makes the
mapping injective; the duplicate-path refusal below is the assertion
that it stayed that way.

**The source hash is defined over bytes, not over git.** "the tree at
this commit" says nothing about a working copy with edits in it, and the
runs that matter most during calibration happen in exactly such a copy.
So: a fixed glob list, sorted relative paths, and the SHA-256 of each
file's contents. Never mtime — a file touched and not changed is the
same code.
"""

from __future__ import annotations

import hashlib
from collections.abc import Collection, Mapping
from pathlib import Path
from typing import Any

from planbench_analyst.features import RoundFeatures
from planbench_explanation.versioning import artifact_checksum

__all__ = [
    "SOURCE_GLOBS",
    "ConfigRefusal",
    "effective_generation_config",
    "flatten_config",
    "runtime_config_checksum",
    "source_manifest_hash",
    "validate_generation_config",
]


class ConfigRefusal(ValueError):
    """A configuration this build will not run under."""


#: Every path whose bytes change what a round would produce. Fixed, and
#: fixed here rather than passed in: a caller that chooses its own globs
#: chooses what its own identity covers, and the party whose bundle is
#: being graded must not get that choice.
#:
#: Paths that do not exist contribute nothing and are not an error —
#: ``docker/Dockerfile.analyst`` arrives at A7, and its arrival is a
#: change of identity, which is correct.
SOURCE_GLOBS: tuple[str, ...] = (
    "services/analyst_service/**/*.py",
    "services/agent_service/planbench_agent/**/*.py",
    "packages/explanation/planbench_explanation/**/*.py",
    "schemas/tools/*.json",
    "docker/Dockerfile.analyst",
    "pyproject.toml",
    "uv.lock",
    "requirements.txt",
    "requirements-optional.txt",
)


def _escape(key: str) -> str:
    """RFC 6901: ``~`` becomes ``~0``, ``/`` becomes ``~1``, in that order."""
    return key.replace("~", "~0").replace("/", "~1")


def flatten_config(config: Mapping[str, Any]) -> dict[str, Any]:
    """Nested config as ``{json_pointer: scalar}``.

    Lists are flattened by index, which keeps ``[0.2, 0.4]`` and
    ``[0.4, 0.2]`` apart — order is a setting too.
    """
    flat: dict[str, Any] = {}

    def walk(prefix: str, value: Any) -> None:
        if isinstance(value, Mapping):
            for key, item in value.items():
                walk(f"{prefix}/{_escape(str(key))}", item)
            return
        if isinstance(value, list | tuple):
            for index, item in enumerate(value):
                walk(f"{prefix}/{index}", item)
            return
        if prefix in flat:
            raise ConfigRefusal(
                f"two settings flatten to {prefix!r}; the escaping is what keeps this "
                "mapping injective, and a collision means the checksum below could "
                "give two configurations one identity"
            )
        flat[prefix] = value

    walk("", config)
    return flat


def effective_generation_config(*layers: Mapping[str, Any]) -> dict[str, Any]:
    """Merge in precedence order, later layers winning.

    Deep for mappings, replace for everything else: a per-request
    ``{"thinking": {"budget": 4000}}`` should not silently drop the
    model default's ``{"thinking": {"type": "enabled"}}``, and a
    per-request list should not be appended to the default's.
    """
    merged: dict[str, Any] = {}
    for layer in layers:
        for key, value in layer.items():
            existing = merged.get(key)
            if isinstance(existing, Mapping) and isinstance(value, Mapping):
                merged[key] = effective_generation_config(existing, value)
            else:
                merged[key] = value
    return merged


def validate_generation_config(
    config: Mapping[str, Any], *, supported: Collection[str]
) -> None:
    """Refuse before the call, not after the bill.

    A knob the model does not support is either ignored — in which case
    the recorded config describes a run that did not happen — or a 400,
    which the advisor's first live run spent a day proving is
    indistinguishable from "the model had nothing to add".
    """
    unknown = sorted(set(config) - set(supported))
    if unknown:
        raise ConfigRefusal(
            f"generation setting(s) {unknown} are not supported by this model; "
            f"it takes {sorted(supported)}. Refused before the call, because a "
            "setting that is silently ignored makes the recorded config a lie."
        )


def source_manifest_hash(root: Path, *, globs: Collection[str] = SOURCE_GLOBS) -> str:
    """SHA-256 over the bytes of every file the globs name.

    Sorted by relative path with forward slashes, so the value does not
    depend on the filesystem's ordering or on Windows separators.
    """
    entries: list[tuple[str, str]] = []
    seen: set[str] = set()
    for pattern in sorted(globs):
        for path in sorted(root.glob(pattern)):
            if not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            if relative in seen:
                continue
            seen.add(relative)
            entries.append((relative, hashlib.sha256(path.read_bytes()).hexdigest()))
    return artifact_checksum({"files": sorted(entries)})


def runtime_config_checksum(
    *,
    prompt_checksum: str,
    generation_config: Mapping[str, Any],
    catalog_version: str,
    source_manifest_hash: str,
    retrieval_config: Mapping[str, Any] | None = None,
    features: RoundFeatures | None = None,
) -> str:
    """Identity of everything except the packet.

    This is the **dev** key, used while there is no frozen bundle to
    name. From A7 the bundle's own identity checksum takes over, and the
    two are kept apart on purpose: a cache keyed on a dev checksum must
    not be able to serve a graded round.
    """
    return artifact_checksum(
        {
            "prompt": prompt_checksum,
            "generation": flatten_config(generation_config),
            "retrieval": flatten_config(retrieval_config or {}),
            "catalog_version": catalog_version,
            "source": source_manifest_hash,
            # W1.7. Two rounds shown different halves of one packet are
            # two systems, and without this they would share a checksum
            # — the second reading would look like model variance.
            "features": (features or RoundFeatures()).as_config,
        }
    )
