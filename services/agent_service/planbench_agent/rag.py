"""Retrieval over project documentation and recorded results.

Deliberately not a vector database. Requirements that actually matter
here are: every returned chunk carries a stable source id, the same
query always returns the same chunks, and the whole thing runs offline
with no model and no network. A TF-IDF-weighted overlap score over
heading-delimited Markdown sections satisfies all three; an embedding
index would satisfy none of them without extra infrastructure.

Chunk ids are ``<document_id>#<section index>``, so a citation such as
``[document:ROS2_INTEGRATION.md#3]`` points at a specific section of a
specific file that a reviewer can open.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable, Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict

_TOKEN = re.compile(r"[a-z0-9_+*][a-z0-9_+*.\-]*")
_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")

# Words carrying no retrieval signal in this corpus. Kept short and
# explicit: an aggressive stop list silently drops real query terms.
_STOPWORDS = frozenset(
    # English
    ("a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "have")
    + ("how", "in", "is", "it", "its", "of", "on", "or", "that", "the", "this", "to")
    + ("was", "were", "what", "when", "where", "which", "who", "why", "with", "your")
    # Vietnamese — parts of the corpus are written in Vietnamese.
    + ("la", "va", "co", "khong", "cho", "cua", "duoc", "mot", "nay", "khi", "thi")
)


class Chunk(BaseModel):
    """One retrievable section."""

    model_config = ConfigDict(frozen=True)

    id: str
    document_id: str
    title: str
    text: str
    uri: str | None = None


class RetrievedChunk(BaseModel):
    model_config = ConfigDict(frozen=True)

    chunk: Chunk
    score: float

    def citation_id(self) -> str:
        """How a hit is quoted: ``document:<chunk id>``.

        The one thing callers ever needed from the old evidence adapter,
        kept as a string because that is what both the tool result and a
        finding's ``field_path`` check actually compare.
        """
        return f"document:{self.chunk.id}"


def _condense(text: str, limit: int = 600) -> str:
    collapsed = " ".join(text.split())
    return collapsed if len(collapsed) <= limit else collapsed[: limit - 1] + "…"


def tokenize(text: str) -> list[str]:
    """Lowercase tokens with trailing punctuation trimmed.

    Interior ``.`` and ``-`` are kept on purpose — ``0.05``,
    ``nav2-bringup`` and ``conditions_checksum`` are single terms in this
    corpus — but a trailing one is sentence punctuation, and leaving it
    attached makes ``checksum.`` miss the query ``checksum``.
    """
    tokens = (token.strip(".-") for token in _TOKEN.findall(text.lower()))
    return [token for token in tokens if token and token not in _STOPWORDS]


def split_markdown(document_id: str, text: str, uri: str | None = None) -> list[Chunk]:
    """Split on Markdown headings; the preamble becomes section 0.

    Sections are the natural citation unit for these docs — each one
    answers a distinct question, and the heading gives the chunk a title
    without any summarisation step.
    """
    sections: list[tuple[str, list[str]]] = [("", [])]
    for line in text.splitlines():
        heading = _HEADING.match(line)
        if heading:
            sections.append((heading.group(2).strip(), []))
        else:
            sections[-1][1].append(line)

    chunks: list[Chunk] = []
    for index, (title, lines) in enumerate(sections):
        body = "\n".join(lines).strip()
        if not body and not title:
            continue
        chunks.append(
            Chunk(
                id=f"{document_id}#{index}",
                document_id=document_id,
                title=title or document_id,
                text=f"{title}\n{body}".strip(),
                uri=uri,
            )
        )
    return chunks


class KnowledgeBase:
    """An in-memory TF-IDF index over chunks.

    Rebuilt whenever chunks are added, which is cheap at this corpus
    size and keeps the scoring function a pure function of the current
    chunk set — no incremental-update drift between processes.
    """

    def __init__(self, chunks: Iterable[Chunk] = ()) -> None:
        self._chunks: list[Chunk] = []
        self._terms: list[Counter[str]] = []
        self._idf: dict[str, float] = {}
        self.add(chunks)

    def __len__(self) -> int:
        return len(self._chunks)

    @property
    def chunks(self) -> tuple[Chunk, ...]:
        return tuple(self._chunks)

    @property
    def document_ids(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(chunk.document_id for chunk in self._chunks))

    def add(self, chunks: Iterable[Chunk]) -> None:
        known = {chunk.id for chunk in self._chunks}
        for chunk in chunks:
            if chunk.id in known:
                continue
            known.add(chunk.id)
            self._chunks.append(chunk)
            self._terms.append(Counter(tokenize(chunk.text)))
        self._reindex()

    def _reindex(self) -> None:
        total = len(self._chunks)
        document_frequency: Counter[str] = Counter()
        for terms in self._terms:
            document_frequency.update(terms.keys())
        # Smoothed IDF; +1 keeps a term appearing in every chunk at a
        # small positive weight rather than exactly zero.
        self._idf = {
            term: math.log((total + 1) / (count + 1)) + 1.0
            for term, count in document_frequency.items()
        }

    def search(self, query: str, limit: int = 5, min_score: float = 1e-9) -> list[RetrievedChunk]:
        """Rank chunks by IDF-weighted, length-normalised term overlap.

        Ties break on chunk id so the ordering is total and stable.
        """
        query_terms = Counter(tokenize(query))
        if not query_terms:
            return []
        scored: list[RetrievedChunk] = []
        for chunk, terms in zip(self._chunks, self._terms, strict=True):
            length = sum(terms.values()) or 1
            score = 0.0
            for term, query_count in query_terms.items():
                count = terms.get(term, 0)
                if count:
                    score += query_count * (count / length) * self._idf.get(term, 1.0)
            if score > min_score:
                scored.append(RetrievedChunk(chunk=chunk, score=score))
        scored.sort(key=lambda item: (-item.score, item.chunk.id))
        return scored[:limit]


def load_markdown_directory(
    directory: str | Path, patterns: Sequence[str] = ("*.md",)
) -> list[Chunk]:
    """Read Markdown docs into chunks, sorted by path for determinism.

    **Recursive, and the document id is the relative path.** Both halves
    are load-bearing and neither works without the other.

    Reading only the top level meant the agent saw eleven files out of a
    hundred and thirty-five: every design note under a dated subdirectory
    and the contract itself were invisible to it, so it answered
    questions about this project from whatever it remembered about
    projects in general.

    Keying chunks on ``path.name`` alone would have made the recursion
    worse than useless. Two notes written on different days share a file
    name often, and ``KnowledgeBase.add`` drops a chunk whose id it has
    already seen — the second day's work would vanish silently. The
    relative path is unique by construction and it is also what a reader
    needs: ``antongduy/plans/2026-08-05/mvp.md#3`` says where to look,
    ``mvp.md#3`` does not.
    """
    root = Path(directory)
    if not root.is_dir():
        return []
    chunks: list[Chunk] = []
    seen: set[Path] = set()
    for pattern in patterns:
        for path in sorted(root.rglob(pattern)):
            if path in seen or not path.is_file():
                continue
            seen.add(path)
            document_id = path.relative_to(root).as_posix()
            chunks.extend(
                split_markdown(document_id, path.read_text(encoding="utf-8"), uri=str(path))
            )
    return chunks


__all__ = [
    "Chunk",
    "KnowledgeBase",
    "RetrievedChunk",
    "load_markdown_directory",
    "split_markdown",
    "tokenize",
]
