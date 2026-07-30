"""Evidence and citations.

Every statement the agent is allowed to make must point at something a
human can open: a benchmark, a run record, an episode, a stored
artifact, or a documentation chunk. An :class:`EvidenceBundle` is that
set of pointers, assembled by code from recorded data — never by the
model.

Citation syntax in generated text is ``[kind:locator]``, e.g.
``[episode:3f9c1a2b7d40]``. It is deliberately ugly and machine-checkable:
:func:`extract_citations` finds every one, and the report validator
rejects any id that is not in the bundle. A model that invents a
plausible-looking id fails the check instead of shipping a fabricated
citation.
"""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from planbench_agent.gateway import BenchmarkSummary, EpisodeSummary
from planbench_benchmark import BenchmarkReport, FailureReport

CITATION_PATTERN = re.compile(r"\[([a-z_]+):([A-Za-z0-9_.\-+#]+)\]")


class SourceKind(StrEnum):
    BENCHMARK = "benchmark"
    AGGREGATE = "aggregate"
    RUN = "run"
    EPISODE = "episode"
    ARTIFACT = "artifact"
    DOCUMENT = "document"
    LEADERBOARD = "leaderboard"
    SCENARIO = "scenario"


class Citation(BaseModel):
    """A pointer a reviewer can follow back to stored data."""

    model_config = ConfigDict(frozen=True)

    kind: SourceKind
    locator: str
    title: str = ""
    uri: str | None = None

    @property
    def id(self) -> str:
        return f"{self.kind.value}:{self.locator}"


class EvidenceItem(BaseModel):
    """One checkable fact plus where it came from."""

    model_config = ConfigDict(frozen=True)

    citation: Citation
    statement: str
    value: float | None = None

    def render(self) -> str:
        suffix = "" if self.value is None else f" (value={self.value:g})"
        return f"[{self.citation.id}] {self.statement}{suffix}"


class InsufficientEvidence(Exception):
    """Refusal: the recorded data does not support answering."""


class EvidenceBundle(BaseModel):
    """The complete, closed set of facts a generated answer may use."""

    model_config = ConfigDict(frozen=True)

    question: str = ""
    items: tuple[EvidenceItem, ...] = ()

    @property
    def ids(self) -> frozenset[str]:
        return frozenset(item.citation.id for item in self.items)

    def of_kind(self, kind: SourceKind) -> tuple[EvidenceItem, ...]:
        return tuple(item for item in self.items if item.citation.kind is kind)

    def render(self) -> str:
        """The evidence block placed verbatim in the prompt."""
        return "\n".join(item.render() for item in self.items)

    def require(self, minimum: int = 1) -> None:
        if len(self.items) < minimum:
            raise InsufficientEvidence(
                f"need at least {minimum} evidence item(s), have {len(self.items)}"
            )


def extract_citations(text: str) -> tuple[str, ...]:
    """Every ``[kind:locator]`` token in order of appearance."""
    return tuple(f"{kind}:{locator}" for kind, locator in CITATION_PATTERN.findall(text))


def collect_benchmark_evidence(
    benchmark: BenchmarkSummary,
    report: BenchmarkReport | None,
    episodes: tuple[EpisodeSummary, ...] = (),
    analyses: tuple[tuple[str, FailureReport], ...] = (),
    question: str = "",
) -> EvidenceBundle:
    """Turn recorded benchmark data into citable evidence.

    Only values that exist in storage become items. Nothing is derived,
    averaged, or rounded here beyond what the report already computed —
    a report that never ran produces an empty bundle, and an empty
    bundle produces a refusal rather than a guess.
    """
    items: list[EvidenceItem] = []
    benchmark_citation = Citation(
        kind=SourceKind.BENCHMARK,
        locator=benchmark.id,
        title=benchmark.name,
    )
    items.append(
        EvidenceItem(
            citation=benchmark_citation,
            statement=(
                f"benchmark {benchmark.name!r} is in state {benchmark.state!r}, "
                f"algorithms={list(benchmark.algorithms)}, seeds={list(benchmark.seeds)}"
            ),
        )
    )

    if report is not None:
        fairness = report.fairness
        items.append(
            EvidenceItem(
                citation=benchmark_citation,
                statement=(
                    f"all algorithms ran under conditions_checksum "
                    f"{fairness.conditions_checksum} (map {fairness.map_name!r}, "
                    f"scenario {fairness.scenario_name!r}, seeds {list(fairness.seeds)})"
                ),
            )
        )
        for aggregate in report.aggregates:
            citation = Citation(
                kind=SourceKind.AGGREGATE,
                locator=f"{benchmark.id}#{aggregate.algorithm}",
                title=aggregate.algorithm,
            )
            items.append(
                EvidenceItem(
                    citation=citation,
                    statement=(
                        f"{aggregate.algorithm}: success_rate={aggregate.success_rate:.3f}, "
                        f"collision_rate={aggregate.collision_rate:.3f}, "
                        f"timeout_rate={aggregate.timeout_rate:.3f} "
                        f"over {aggregate.episodes} episodes"
                    ),
                    value=aggregate.success_rate,
                )
            )
            if aggregate.mean_travel_time_successful is not None:
                items.append(
                    EvidenceItem(
                        citation=citation,
                        statement=(
                            f"{aggregate.algorithm}: mean travel time over successful "
                            f"episodes = {aggregate.mean_travel_time_successful:.3f} s"
                        ),
                        value=aggregate.mean_travel_time_successful,
                    )
                )
            if aggregate.worst_min_clearance is not None:
                items.append(
                    EvidenceItem(
                        citation=citation,
                        statement=(
                            f"{aggregate.algorithm}: worst minimum clearance = "
                            f"{aggregate.worst_min_clearance:.3f} m"
                        ),
                        value=aggregate.worst_min_clearance,
                    )
                )

    for episode in episodes:
        citation = Citation(
            kind=SourceKind.EPISODE,
            locator=episode.id,
            title=f"{episode.algorithm} seed {episode.seed}",
            uri=episode.artifact_uri,
        )
        items.append(
            EvidenceItem(
                citation=citation,
                statement=(
                    f"episode {episode.algorithm} seed={episode.seed} ended "
                    f"{episode.status!r} ({episode.reason})"
                ),
            )
        )
        if episode.artifact_uri:
            items.append(
                EvidenceItem(
                    citation=Citation(
                        kind=SourceKind.ARTIFACT,
                        locator=episode.id,
                        title="stored trajectory",
                        uri=episode.artifact_uri,
                    ),
                    statement=f"full trajectory stored at {episode.artifact_uri}",
                )
            )

    for episode_id, analysis in analyses:
        citation = Citation(
            kind=SourceKind.EPISODE,
            locator=episode_id,
            title="failure analysis",
        )
        finding = analysis.primary
        items.append(
            EvidenceItem(
                citation=citation,
                statement=(
                    f"failure analysis: {finding.category.value} "
                    f"(confidence {finding.confidence.value}) — {finding.summary}"
                ),
            )
        )
        for evidence in finding.evidence:
            items.append(
                EvidenceItem(
                    citation=citation,
                    statement=f"evidence {evidence.kind}: {evidence.detail}",
                    value=evidence.value,
                )
            )

    return EvidenceBundle(question=question, items=tuple(items))


__all__ = [
    "CITATION_PATTERN",
    "Citation",
    "EvidenceBundle",
    "EvidenceItem",
    "InsufficientEvidence",
    "SourceKind",
    "collect_benchmark_evidence",
    "extract_citations",
]
