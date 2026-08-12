"""The fingerprint that makes ``run_uri`` mean something (D15).

A card and its manifest live in the row; the Parquet traces behind them
are megabytes per episode and stay in the artifact store. That split is
deliberate — but it leaves a stored result pointing at files it cannot
vouch for, and "the traces moved on" is precisely the failure a result
cannot detect about itself.

So the checksum is not decoration. These tests are about the two ways it
could be decoration: hashing something that does not change when the
traces do, or changing when they did not.

No episodes are simulated here. The traces are bytes on disk, which is
all this function looks at.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from planbench_benchmark.pipeline import trace_checksum
from planbench_simulator.trace import trace_path


class FakeCandidate:
    def __init__(self, candidate_id: str) -> None:
        self.candidate_id = candidate_id


class FakeContext:
    def __init__(self, context_id: str) -> None:
        self.episode_context_id = context_id


def write(root: Path, candidate_id: str, context_id: str, payload: bytes) -> Path:
    path = trace_path(candidate_id, context_id, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


@pytest.fixture
def field(tmp_path: Path):
    candidates = [FakeCandidate("cand_a"), FakeCandidate("cand_b")]
    contexts = [FakeContext("ctx_1"), FakeContext("ctx_2")]
    for candidate in candidates:
        for context in contexts:
            write(
                tmp_path,
                candidate.candidate_id,
                context.episode_context_id,
                f"{candidate.candidate_id}/{context.episode_context_id}".encode(),
            )
    return candidates, contexts, tmp_path


class TestItFingerprintsWhatTheRunHad:
    def test_the_same_files_give_the_same_digest(self, field) -> None:
        candidates, contexts, root = field
        assert trace_checksum(candidates, contexts, root) == trace_checksum(
            candidates, contexts, root
        )

    def test_one_changed_byte_changes_it(self, field) -> None:
        """Content, not size and mtime. A stale file of the right length
        is exactly the case worth catching, and mtime is a fact about the
        filesystem rather than about the episode."""
        candidates, contexts, root = field
        before = trace_checksum(candidates, contexts, root)
        path = trace_path("cand_a", "ctx_1", root=root)
        path.write_bytes(path.read_bytes() + b"x")
        assert trace_checksum(candidates, contexts, root) != before

    def test_a_missing_trace_changes_it_rather_than_raising(self, field) -> None:
        """A run whose traces are incomplete should be *recognisable*,
        not unhashable — the fingerprint records what the run had."""
        candidates, contexts, root = field
        before = trace_checksum(candidates, contexts, root)
        trace_path("cand_b", "ctx_2", root=root).unlink()
        assert trace_checksum(candidates, contexts, root) != before

    def test_the_order_of_candidates_does_not_matter(self, field) -> None:
        """Two callers listing the same field differently are describing
        one run; a digest that disagreed would report a difference where
        there is none."""
        candidates, contexts, root = field
        assert trace_checksum(candidates, contexts, root) == trace_checksum(
            list(reversed(candidates)), list(reversed(contexts)), root
        )

    def test_identical_content_under_two_names_still_differs(self, tmp_path: Path) -> None:
        """Each digest carries its own key, so two episodes that happen to
        produce byte-identical traces are still two episodes — otherwise a
        run that lost a file could match one that never had it."""
        one = [FakeCandidate("cand_a")]
        two = [FakeCandidate("cand_b")]
        contexts = [FakeContext("ctx_1")]
        write(tmp_path, "cand_a", "ctx_1", b"identical")
        write(tmp_path, "cand_b", "ctx_1", b"identical")
        assert trace_checksum(one, contexts, tmp_path) != trace_checksum(two, contexts, tmp_path)

    def test_an_empty_field_is_still_a_digest(self, tmp_path: Path) -> None:
        assert trace_checksum([], [], tmp_path)
