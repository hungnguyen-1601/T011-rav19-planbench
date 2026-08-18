"""H9A: an oracle episode cannot become a production number.

The gap this closes was the worst of the five left after H0–H8, and it
was worse than "a feature is missing": until now a research run and a
production run of one candidate wrote to the **same file**, so running
the oracle lane through the ordinary pipeline destroyed evidence nobody
could recover. Everything else in the host refuses; this one overwrote.

Two mechanisms, and each is insufficient alone:

* the **address** carries the evidence class and the conditions, so two
  classes cannot collide on one path — this is what stops the write;
* the **policy** is consulted by every reader, so a class a use may not
  have is refused — this is what stops the read.

A guard on read with a colliding address still loses data. An address
without a guard still lets a copied file be scored. Both, or neither.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from task_profile_fakes import make_profile
from test_trace import state

from planbench_benchmark.contexts import build_evaluation_contexts
from planbench_benchmark.pipeline import TraceLocator, trace_checksum
from planbench_benchmark.scenarios import build_scenario
from planbench_benchmark.selection import run_dir_name
from planbench_simulator.trace import (
    PRODUCTION_USE,
    RESEARCH_USE,
    EpisodeTraceRecorder,
    TraceUseRefused,
    find_traces,
    load_trace_for_use,
    metadata_for_use,
    read_trace_metadata,
)


class FakeCandidate:
    def __init__(self, candidate_id: str) -> None:
        self.candidate_id = candidate_id


@pytest.fixture(scope="module")
def deployment():
    return make_profile(), build_scenario("doorway")[0]


@pytest.fixture
def episode(deployment):
    profile, map_data = deployment
    return profile, map_data, build_evaluation_contexts(profile, seed_count=1)[0]


def write_trace_of(root: Path, episode, *, evidence_class: str, fingerprint: str = "cond0001"):
    _, _, context = episode
    with EpisodeTraceRecorder(
        context,
        "cand_a",
        root=root,
        clearance=lambda _pose: 1.0,
        execution_conditions_fingerprint=fingerprint,
        evidence_class=evidence_class,
    ) as recorder:
        recorder.record(0.0, state())
    return recorder.path


class TestTheAddressStopsTheWrite:
    def test_two_classes_of_one_episode_land_on_two_files(self, tmp_path, episode) -> None:
        production = write_trace_of(tmp_path, episode, evidence_class="production")
        oracle = write_trace_of(tmp_path, episode, evidence_class="oracle")
        assert production != oracle
        assert production.is_file() and oracle.is_file()

    def test_two_worlds_of_one_episode_land_on_two_files(self, tmp_path, episode) -> None:
        first = write_trace_of(tmp_path, episode, evidence_class="production", fingerprint="aaa")
        second = write_trace_of(tmp_path, episode, evidence_class="production", fingerprint="bbb")
        assert first != second
        assert first.is_file() and second.is_file()

    def test_the_class_is_written_into_the_file_as_well(self, tmp_path, episode) -> None:
        """The path stops an overwrite; the field is what lets a reader
        refuse a file that was moved or copied."""
        path = write_trace_of(tmp_path, episode, evidence_class="oracle")
        assert read_trace_metadata(path).evidence_class == "oracle"


class TestThePolicyStopsTheRead:
    def test_a_production_use_refuses_an_oracle_trace(self, tmp_path, episode) -> None:
        path = write_trace_of(tmp_path, episode, evidence_class="oracle")
        with pytest.raises(TraceUseRefused, match="production use"):
            load_trace_for_use(path, use=PRODUCTION_USE)

    def test_a_production_use_refuses_a_reference_trace(self, tmp_path, episode) -> None:
        """A reference adapter may be compared against and never
        recommended; scoring it here is how it becomes a recommendation."""
        path = write_trace_of(tmp_path, episode, evidence_class="reference")
        with pytest.raises(TraceUseRefused):
            load_trace_for_use(path, use=PRODUCTION_USE)

    def test_a_research_use_may_read_the_oracle(self, tmp_path, episode) -> None:
        """The lane P4 and P5 needed. Admitted, and the class travels
        with whatever it produces."""
        path = write_trace_of(tmp_path, episode, evidence_class="oracle")
        assert load_trace_for_use(path, use=RESEARCH_USE).row_count == 1

    def test_a_trace_that_cannot_say_what_it_is_fails_closed(self, tmp_path, episode) -> None:
        """Legacy traces read back as ``unknown``. **Not** promoted to
        production: exactly the traces most likely to predate the change
        are the ones a permissive default would admit."""
        path = write_trace_of(tmp_path, episode, evidence_class="production")
        _strip_evidence_class(path)
        assert read_trace_metadata(path).evidence_class == "unknown"
        for use in (PRODUCTION_USE, RESEARCH_USE):
            with pytest.raises(TraceUseRefused, match="re-simulate"):
                load_trace_for_use(path, use=use)


class TestTheTwoMustAgree:
    def test_a_file_moved_into_a_lying_directory_is_refused(self, tmp_path, episode) -> None:
        """A copy under ``production/`` whose metadata says oracle. The
        address is what prevents overwrites, so an address that disagrees
        with the file has already stopped protecting anything."""
        oracle = write_trace_of(tmp_path, episode, evidence_class="oracle")
        production = write_trace_of(tmp_path, episode, evidence_class="production")
        production.write_bytes(oracle.read_bytes())
        with pytest.raises(TraceUseRefused, match="sits under 'production'"):
            metadata_for_use(production, use=RESEARCH_USE)

    def test_a_file_under_the_wrong_conditions_is_refused(self, tmp_path, episode) -> None:
        here = write_trace_of(tmp_path, episode, evidence_class="production", fingerprint="aaa")
        elsewhere = write_trace_of(
            tmp_path, episode, evidence_class="production", fingerprint="bbb"
        )
        elsewhere.write_bytes(here.read_bytes())
        with pytest.raises(TraceUseRefused, match="sits under conditions"):
            metadata_for_use(elsewhere, use=PRODUCTION_USE)


class TestEveryConsumerUsesTheOneBoundary:
    """The lesson of 16-08: a check at one consumer with the rest open is
    the same hole, and it does not become a different hole by being about
    provenance instead of conditions."""

    def test_reuse_refuses_an_oracle_trace(self, tmp_path, episode) -> None:
        profile, map_data, context = episode
        fingerprint = TraceLocator(tmp_path, profile, map_data).fingerprint(context)
        write_trace_of(tmp_path, episode, evidence_class="oracle", fingerprint=fingerprint)
        production = TraceLocator(tmp_path, profile, map_data)
        assert not production.usable(FakeCandidate("cand_a"), context)

    def test_reuse_accepts_a_production_trace_of_the_same_world(self, tmp_path, episode) -> None:
        profile, map_data, context = episode
        locator = TraceLocator(tmp_path, profile, map_data)
        write_trace_of(
            tmp_path,
            episode,
            evidence_class="production",
            fingerprint=locator.fingerprint(context),
        )
        assert locator.usable(FakeCandidate("cand_a"), context)

    def test_scoring_refuses_an_oracle_trace(self, tmp_path, episode) -> None:
        profile, map_data, context = episode
        oracle = TraceLocator(tmp_path, profile, map_data, evidence_class="oracle")
        write_trace_of(
            tmp_path, episode, evidence_class="oracle", fingerprint=oracle.fingerprint(context)
        )
        with pytest.raises(TraceUseRefused):
            oracle.load(FakeCandidate("cand_a"), context)

    def test_the_api_search_does_not_return_an_oracle_trace(self, tmp_path, episode) -> None:
        _, _, context = episode
        write_trace_of(tmp_path, episode, evidence_class="oracle")
        assert find_traces(tmp_path, "cand_a", context.episode_context_id) == []
        assert find_traces(tmp_path, "cand_a", context.episode_context_id, use=RESEARCH_USE)

    def test_the_checksum_hashes_only_this_run_s_class(self, tmp_path, episode) -> None:
        """A run's checksum must not move because somebody ran the same
        candidate through the research lane afterwards."""
        profile, map_data, context = episode
        locator = TraceLocator(tmp_path, profile, map_data)
        candidates = [FakeCandidate("cand_a")]
        write_trace_of(
            tmp_path,
            episode,
            evidence_class="production",
            fingerprint=locator.fingerprint(context),
        )
        before = trace_checksum(candidates, [context], tmp_path, profile, map_data)
        write_trace_of(
            tmp_path, episode, evidence_class="oracle", fingerprint=locator.fingerprint(context)
        )
        assert trace_checksum(candidates, [context], tmp_path, profile, map_data) == before


class TestTheFourthAddress:
    """The run directory and its journal, one level above the traces.

    16-08 fixed a journal that mixed two worlds. The directory was still
    named from (profile, scope, candidates) — none of which change with
    the evidence class — so a research sweep and a production sweep of
    the same three things shared a folder and truncated each other.
    """

    def test_two_classes_do_not_share_a_run_directory(self) -> None:
        candidates = [FakeCandidate("cand_a")]
        production = run_dir_name("wh_v1", "compare", candidates)
        research = run_dir_name("wh_v1", "compare", candidates, "oracle")
        assert production != research

    def test_production_keeps_its_existing_directory_name(self) -> None:
        """Existing run directories stay where they are: a rename would
        orphan every stored run for a change that affects none of them."""
        candidates = [FakeCandidate("cand_a")]
        assert not run_dir_name("wh_v1", "compare", candidates).endswith("_production")


def _strip_evidence_class(path: Path) -> None:
    """Rewrite a trace's footer without the field, as a legacy file has."""
    import pyarrow.parquet as pq

    table = pq.read_table(path)
    raw = (table.schema.metadata or {})[b"planbench_trace"]
    payload = json.loads(raw)
    payload.pop("evidence_class", None)
    table = table.replace_schema_metadata({b"planbench_trace": json.dumps(payload).encode("utf-8")})
    pq.write_table(table, path)
