"""Retrieval: chunking, stable ids, deterministic ranking."""

from __future__ import annotations

from pathlib import Path

from planbench_agent.rag import (
    Chunk,
    KnowledgeBase,
    benchmark_chunks,
    load_markdown_directory,
    split_markdown,
    tokenize,
)

DOC = """Intro text before any heading.

# Fairness
Every algorithm runs under one conditions_checksum. Different checksums
mean the comparison is invalid.

## Seeds
Seeds drive dynamic obstacles and sampling planners.

# Approval
A reviewer must approve a benchmark before it runs.
"""


class TestTokenize:
    def test_keeps_interior_punctuation_but_drops_trailing(self):
        assert tokenize("The conditions_checksum is 0.05, see nav2-bringup.") == [
            "conditions_checksum",
            "0.05",
            "see",
            "nav2-bringup",
        ]

    def test_drops_stopwords(self):
        assert tokenize("this is the and or") == []


class TestSplitMarkdown:
    def test_one_chunk_per_heading_plus_the_preamble(self):
        chunks = split_markdown("DOC.md", DOC)
        assert [chunk.title for chunk in chunks] == [
            "DOC.md",
            "Fairness",
            "Seeds",
            "Approval",
        ]

    def test_ids_are_stable_and_citable(self):
        first = split_markdown("DOC.md", DOC)
        second = split_markdown("DOC.md", DOC)
        assert [chunk.id for chunk in first] == [chunk.id for chunk in second]
        assert first[1].id == "DOC.md#1"

    def test_heading_text_is_part_of_the_chunk_body(self):
        # So a query for the heading word retrieves its section.
        chunk = split_markdown("DOC.md", DOC)[1]
        assert chunk.text.startswith("Fairness")

    def test_empty_document_yields_nothing(self):
        assert split_markdown("EMPTY.md", "") == []


class TestKnowledgeBase:
    def test_ranks_the_relevant_section_first(self):
        base = KnowledgeBase(split_markdown("DOC.md", DOC))
        hits = base.search("conditions_checksum comparison")
        assert hits[0].chunk.title == "Fairness"

    def test_returns_nothing_when_no_term_matches(self):
        base = KnowledgeBase(split_markdown("DOC.md", DOC))
        assert base.search("hydraulic manipulator gripper") == []

    def test_empty_query_returns_nothing(self):
        base = KnowledgeBase(split_markdown("DOC.md", DOC))
        assert base.search("the and of") == []

    def test_ranking_is_deterministic(self):
        base = KnowledgeBase(split_markdown("DOC.md", DOC))
        first = [hit.chunk.id for hit in base.search("seeds approval benchmark", limit=5)]
        second = [hit.chunk.id for hit in base.search("seeds approval benchmark", limit=5)]
        assert first == second

    def test_limit_is_honoured(self):
        base = KnowledgeBase(split_markdown("DOC.md", DOC))
        assert len(base.search("benchmark seeds approval checksum", limit=2)) <= 2

    def test_adding_the_same_chunk_twice_is_a_no_op(self):
        chunks = split_markdown("DOC.md", DOC)
        base = KnowledgeBase(chunks)
        base.add(chunks)
        assert len(base) == len(chunks)

    def test_rarer_terms_outrank_common_ones(self):
        base = KnowledgeBase(
            [
                Chunk(id="a#0", document_id="a", title="a", text="benchmark benchmark rare_term"),
                Chunk(id="b#0", document_id="b", title="b", text="benchmark benchmark benchmark"),
            ]
        )
        assert base.search("benchmark rare_term")[0].chunk.id == "a#0"

    def test_hits_convert_to_document_evidence(self):
        base = KnowledgeBase(split_markdown("DOC.md", DOC))
        item = base.search("conditions_checksum")[0].as_evidence()
        assert item.citation.id.startswith("document:DOC.md#")
        assert "conditions_checksum" in item.statement


class TestCorpusLoading:
    def test_reads_the_repository_docs(self):
        docs = Path(__file__).resolve().parents[1] / "docs"
        chunks = load_markdown_directory(docs)
        assert chunks, "expected the docs/ directory to contain Markdown"
        assert all(chunk.uri for chunk in chunks)

    def test_missing_directory_is_empty_not_an_error(self, tmp_path):
        assert load_markdown_directory(tmp_path / "nope") == []

    def test_loading_is_ordered_by_filename(self, tmp_path):
        (tmp_path / "b.md").write_text("# B\nbody", encoding="utf-8")
        (tmp_path / "a.md").write_text("# A\nbody", encoding="utf-8")
        ids = [chunk.document_id for chunk in load_markdown_directory(tmp_path)]
        assert ids == ["a.md", "b.md"]


class TestBenchmarkChunks:
    def test_indexed_results_are_citable_by_benchmark_id(self):
        chunks = benchmark_chunks("abc123", "doorway run", "accepted", ["astar+dwa success 1.00"])
        assert chunks[0].id == "benchmark:abc123#0"
        base = KnowledgeBase(chunks)
        assert base.search("doorway")[0].chunk.document_id == "benchmark:abc123"
