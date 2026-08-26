"""A cache for development rounds, and the two things it must never do.

Calibration reads the same thirteen packets many times while a prompt is
being tuned, and each read is a paid call. So responses are cached — but
a cache over a model is a place where two mistakes hide, and both are
closed here rather than left to the caller's care:

**It must not serve a graded round.** The key carries the runtime
identity it was written under. From A7 that is the frozen bundle's
identity; before A7 it is the dev checksum from
:mod:`planbench_analyst.identity`. A cache written under one cannot be
read under the other, because the key is not the same string.

**A hit must not be mistaken for a repetition.** Reading the same answer
twice says nothing about whether the model would say it twice, and the
non-determinism smoke test at A7 exists to ask exactly that. So every
read reports itself: :attr:`CacheStats.hits` is what the harness asserts
is **zero** when it means to be measuring the model.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from planbench_explanation.versioning import artifact_checksum

__all__ = ["CacheStats", "ResponseCache", "cache_key"]


def cache_key(*, runtime_checksum: str, packet_checksum: str) -> str:
    """One entry per (what was run, what it was run on)."""
    return artifact_checksum({"runtime": runtime_checksum, "packet": packet_checksum})


@dataclass
class CacheStats:
    """Reads, and where they came from. Published, never inferred."""

    hits: int = 0
    misses: int = 0
    writes: int = 0

    @property
    def served_from_cache(self) -> bool:
        return self.hits > 0


@dataclass
class ResponseCache:
    """Structured model answers on disk, one JSON file per key.

    ``root=None`` is a working cache that stores nothing — the shape a
    graded run uses, so the calling code has no branch that only exists
    for grading and therefore only breaks there.
    """

    root: Path | None = None
    stats: CacheStats = field(default_factory=CacheStats)

    def _path(self, key: str) -> Path | None:
        if self.root is None:
            return None
        return self.root / f"{key}.json"

    def get(self, key: str) -> Mapping[str, Any] | None:
        path = self._path(key)
        if path is None or not path.exists():
            self.stats.misses += 1
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # A corrupt entry is a miss, not a crash: the answer is
            # recoverable by calling the model, and a cache that can
            # fail a run is worse than no cache.
            self.stats.misses += 1
            return None
        if not isinstance(payload, Mapping):
            self.stats.misses += 1
            return None
        self.stats.hits += 1
        return payload

    def put(self, key: str, payload: Mapping[str, Any]) -> None:
        path = self._path(key)
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8"
        )
        self.stats.writes += 1
