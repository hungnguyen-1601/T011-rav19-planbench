"""What a retrieval layer is allowed to hand the platform — E5.

The RAG provider belongs to the AI team, which is the party being
graded, so **the platform trusts no field it declares**. A provider that
could set ``review_status: approved`` on an entry would be able to make
its own citations promotable — the same move H3 already blocked when a
provider tried to declare ``provenance="oracle"`` about its own data.

So the contract is deliberately thin: retrieval returns **keys**. An
entry id, a version, which hypothesis it was retrieved for, and its own
retrieval score. That is all a :class:`MechanismReferenceCandidate` can
carry — ``extra="forbid"`` means a provider that tries to send the
mechanism text, the sources, or the review status gets a validation
error rather than a quietly ignored field.

What those keys *mean* comes from the canonical knowledge base in
:mod:`planbench_explanation.knowledge`, resolved here. Four ways a
candidate dies:

* the entry id is not in the base — rejected;
* the version does not match the base — rejected, because an edited
  entry does not silently become what an older citation named;
* the entry is withdrawn — rejected;
* the entry is not ``approved`` — resolved and returned, but flagged as
  unable to back a promoted claim.

The fourth is not a rejection. A draft entry is still worth showing a
reader who is looking at a detection; what it may not do is stand
underneath a claim. Every entry in v1 is a draft, so today that is the
ordinary path rather than the exception.

**No retrieval design is specified here, on purpose.** Embeddings,
chunking, reranking, hybrid search — all of it is the AI team's problem
and none of it changes what this module accepts. A contract that named
a retrieval strategy would be a contract that had to be renegotiated
every time the strategy changed.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from planbench_explanation.detectors import DetectionType
from planbench_explanation.knowledge import (
    KNOWLEDGE_BASE,
    KNOWLEDGE_BASE_ID,
    KNOWLEDGE_BASE_VERSION,
    KnowledgeEntry,
    KnowledgeRefusal,
)
from planbench_explanation.propositions import PropositionType
from planbench_explanation.subjects import Subject

#: Why a candidate did not resolve. Closed so a harness can count.
CandidateRejectionCode = Literal[
    "unknown_knowledge_base",
    "unknown_entry",
    "version_mismatch",
    "entry_withdrawn",
]


class KnowledgeQuery(BaseModel):
    """What the platform tells retrieval about the case.

    Features, not prose. A provider given the case narrative would be a
    provider given room to answer the narrative rather than the
    evidence.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    task_features: tuple[str, ...] = ()
    candidate_components: tuple[str, ...] = ()
    observations: tuple[DetectionType, ...] = ()
    #: Mechanisms the analyst has already ruled out this round. Sent so
    #: retrieval does not spend its budget re-offering them.
    excluded_mechanisms: tuple[str, ...] = ()
    hypothesis_id: str | None = None


class MechanismReferenceCandidate(BaseModel):
    """A key retrieval offers. Nothing authoritative fits in it.

    Deliberately unable to carry content: there is no field for the
    mechanism, the sources, the applicability conditions or the review
    status, and ``extra="forbid"`` turns an attempt to add one into an
    error at the boundary rather than a field nobody reads.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    knowledge_base_id: str = Field(min_length=1)
    entry_id: str = Field(min_length=1)
    entry_version: int = Field(ge=1)
    retrieved_for: str | None = None
    #: The provider's own score. Recorded for debugging retrieval, never
    #: consulted by promotion — a confident retrieval of a wrong entry
    #: is exactly the failure this separation exists for.
    retrieval_score: float = Field(ge=0.0, le=1.0)

    @property
    def citation(self) -> str:
        return f"kb:{self.entry_id}@{self.entry_version}"


class KnowledgeResult(BaseModel):
    """One retrieval round's offer."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    entries: tuple[MechanismReferenceCandidate, ...] = ()
    kb_version: str = Field(min_length=1)
    retrieval_version: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self) -> KnowledgeResult:
        keys = [(entry.entry_id, entry.entry_version) for entry in self.entries]
        duplicates = sorted({key for key in keys if keys.count(key) > 1})
        if duplicates:
            raise KnowledgeRefusal(
                f"entry key(s) {duplicates} offered twice in one result; a repeated "
                "key is a ranking artefact, not two pieces of evidence"
            )
        return self


class ResolvedReference(BaseModel):
    """A candidate that survived, with the platform's own view of it."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    candidate: MechanismReferenceCandidate
    entry: KnowledgeEntry
    #: Approved entries only. The single field a caller reads before
    #: letting a citation stand under a claim.
    may_support_a_claim: bool
    proposition_type: PropositionType
    subject: Subject

    @model_validator(mode="after")
    def _check(self) -> ResolvedReference:
        if self.may_support_a_claim != (self.entry.review_status == "approved"):
            raise KnowledgeRefusal(
                f"entry {self.entry.entry_id!r} is {self.entry.review_status!r}; "
                "may_support_a_claim is derived from review status, not declared"
            )
        if self.proposition_type != self.entry.proposition_type:
            raise KnowledgeRefusal("resolved proposition type is not the entry's")
        if self.subject != self.entry.conditions.subject:
            raise KnowledgeRefusal("resolved subject is not the entry's")
        return self


class RejectedReference(BaseModel):
    """A candidate the platform would not resolve, and why."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    candidate: MechanismReferenceCandidate
    code: CandidateRejectionCode
    detail: str = Field(min_length=1)


class ResolutionOutcome(BaseModel):
    """Both halves of a resolution. Rejections are kept, not dropped.

    A retrieval layer that offers five entries of which three do not
    exist is a retrieval layer with a problem, and the only way anyone
    finds out is if the rejections survive the call.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    resolved: tuple[ResolvedReference, ...] = ()
    rejected: tuple[RejectedReference, ...] = ()

    @property
    def promotable(self) -> tuple[ResolvedReference, ...]:
        """The approved subset — what may sit under a claim."""
        return tuple(item for item in self.resolved if item.may_support_a_claim)


def resolve_candidates(
    result: KnowledgeResult,
    *,
    entries: Sequence[KnowledgeEntry] = KNOWLEDGE_BASE,
    kb_version: str = KNOWLEDGE_BASE_VERSION,
) -> ResolutionOutcome:
    """Turn retrieval's keys into the platform's own entries.

    The knowledge base version is checked first and refuses the whole
    result rather than each candidate: a provider indexing a different
    version of the base is not making a mistake about one entry, it is
    answering about a different base.
    """
    if result.kb_version != kb_version:
        raise KnowledgeRefusal(
            f"retrieval answered against knowledge base {result.kb_version!r} while "
            f"the platform holds {kb_version!r}; entry versions are only comparable "
            "within one base version"
        )

    by_id = {entry.entry_id: entry for entry in entries}
    resolved: list[ResolvedReference] = []
    rejected: list[RejectedReference] = []

    for candidate in result.entries:
        if candidate.knowledge_base_id != KNOWLEDGE_BASE_ID:
            rejected.append(
                RejectedReference(
                    candidate=candidate,
                    code="unknown_knowledge_base",
                    detail=(
                        f"candidate names base {candidate.knowledge_base_id!r}; this "
                        f"platform resolves only {KNOWLEDGE_BASE_ID!r}"
                    ),
                )
            )
            continue
        entry = by_id.get(candidate.entry_id)
        if entry is None:
            rejected.append(
                RejectedReference(
                    candidate=candidate,
                    code="unknown_entry",
                    detail=(
                        f"no entry {candidate.entry_id!r} in the curated base; a "
                        "mechanism the platform cannot look up is a mechanism nobody "
                        "can check"
                    ),
                )
            )
            continue
        if entry.entry_version != candidate.entry_version:
            rejected.append(
                RejectedReference(
                    candidate=candidate,
                    code="version_mismatch",
                    detail=(
                        f"{candidate.citation} names version {candidate.entry_version} "
                        f"but the base holds {entry.entry_version}"
                    ),
                )
            )
            continue
        if entry.review_status == "withdrawn":
            rejected.append(
                RejectedReference(
                    candidate=candidate,
                    code="entry_withdrawn",
                    detail=f"entry {entry.entry_id!r} was withdrawn and may not be cited",
                )
            )
            continue
        resolved.append(
            ResolvedReference(
                candidate=candidate,
                entry=entry,
                may_support_a_claim=entry.review_status == "approved",
                proposition_type=entry.proposition_type,
                subject=entry.conditions.subject,
            )
        )

    resolved.sort(key=lambda item: item.entry.entry_id)
    return ResolutionOutcome(resolved=tuple(resolved), rejected=tuple(rejected))
