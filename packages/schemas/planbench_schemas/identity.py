"""Canonical hashing for contract identities (HĐ-1.3, HĐ-3.1).

Both frozen identities in the contract — ``candidate_id`` and
``episode_context_id`` — are ``sha256_short(canonical_json(...))``. They
live in different packages but must agree byte for byte, so the two
primitives sit here rather than being reimplemented on each side: an id
computed two slightly different ways would silently split one candidate,
or one episode, into two.

This is deliberately *not* the same as ``planbench_benchmark.spec._canonical``,
which builds a ``repr``-based string for the older fairness checksum.
That one must keep hashing exactly as it always has, or every stored
benchmark report would declare itself incomparable.
"""

from __future__ import annotations

import hashlib
import json


def canonical_json(payload: object) -> str:
    """Deterministic JSON: sorted keys, no incidental whitespace.

    Sorted keys are the point — a mapping is unordered as data but ordered
    as text, and an id depending on the order somebody typed the fields
    would not be an id.
    """
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_short(payload: str, *, length: int) -> str:
    """First ``length`` hex characters of the SHA-256 of ``payload``."""
    if length <= 0:
        raise ValueError(f"length must be positive, got {length}")
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:length]
