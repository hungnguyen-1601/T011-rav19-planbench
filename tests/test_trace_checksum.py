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
from task_profile_fakes import make_profile

from planbench_benchmark.contexts import build_evaluation_contexts
from planbench_benchmark.pipeline import TraceLocator, trace_checksum
from planbench_benchmark.scenarios import build_scenario


class FakeCandidate:
    def __init__(self, candidate_id: str) -> None:
        self.candidate_id = candidate_id


@pytest.fixture(scope="module")
def deployment():
    """A real profile and map, because since H9A a trace's **address**
    depends on the conditions it ran under — a fake pair of ids can no
    longer say where a trace belongs."""
    profile = make_profile()
    map_data, _ = build_scenario("doorway")
    return profile, map_data


def write(locator: TraceLocator, candidate, context, payload: bytes) -> Path:
    path = locator.path(candidate, context)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


@pytest.fixture
def field(tmp_path: Path, deployment):
    profile, map_data = deployment
    candidates = [FakeCandidate("cand_a"), FakeCandidate("cand_b")]
    contexts = list(build_evaluation_contexts(profile, seed_count=2))
    locator = TraceLocator(tmp_path, profile, map_data)
    for candidate in candidates:
        for context in contexts:
            write(
                locator,
                candidate,
                context,
                f"{candidate.candidate_id}/{context.episode_context_id}".encode(),
            )
    return candidates, contexts, tmp_path


class TestItFingerprintsWhatTheRunHad:
    def test_the_same_files_give_the_same_digest(self, field, deployment) -> None:
        candidates, contexts, root = field
        assert trace_checksum(candidates, contexts, root, *deployment) == trace_checksum(
            candidates, contexts, root, *deployment
        )

    def test_one_changed_byte_changes_it(self, field, deployment) -> None:
        """Content, not size and mtime. A stale file of the right length
        is exactly the case worth catching, and mtime is a fact about the
        filesystem rather than about the episode."""
        candidates, contexts, root = field
        before = trace_checksum(candidates, contexts, root, *deployment)
        locator = TraceLocator(root, *deployment)
        path = locator.path(candidates[0], contexts[0])
        path.write_bytes(path.read_bytes() + b"x")
        assert trace_checksum(candidates, contexts, root, *deployment) != before

    def test_a_missing_trace_changes_it_rather_than_raising(self, field, deployment) -> None:
        """A run whose traces are incomplete should be *recognisable*,
        not unhashable — the fingerprint records what the run had."""
        candidates, contexts, root = field
        before = trace_checksum(candidates, contexts, root, *deployment)
        TraceLocator(root, *deployment).path(candidates[1], contexts[1]).unlink()
        assert trace_checksum(candidates, contexts, root, *deployment) != before

    def test_the_order_of_candidates_does_not_matter(self, field, deployment) -> None:
        """Two callers listing the same field differently are describing
        one run; a digest that disagreed would report a difference where
        there is none."""
        candidates, contexts, root = field
        assert trace_checksum(candidates, contexts, root, *deployment) == trace_checksum(
            list(reversed(candidates)), list(reversed(contexts)), root, *deployment
        )

    def test_identical_content_under_two_names_still_differs(
        self, tmp_path: Path, deployment
    ) -> None:
        """Each digest carries its own key, so two episodes that happen to
        produce byte-identical traces are still two episodes — otherwise a
        run that lost a file could match one that never had it."""
        profile, _ = deployment
        one = [FakeCandidate("cand_a")]
        two = [FakeCandidate("cand_b")]
        contexts = list(build_evaluation_contexts(profile, seed_count=1))
        locator = TraceLocator(tmp_path, *deployment)
        write(locator, one[0], contexts[0], b"identical")
        write(locator, two[0], contexts[0], b"identical")
        assert trace_checksum(one, contexts, tmp_path, *deployment) != trace_checksum(
            two, contexts, tmp_path, *deployment
        )

    def test_an_empty_field_is_still_a_digest(self, tmp_path: Path, deployment) -> None:
        assert trace_checksum([], [], tmp_path, *deployment)
