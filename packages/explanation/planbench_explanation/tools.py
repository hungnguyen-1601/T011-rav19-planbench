"""Tool cards: what a checker is allowed to establish, in typed form.

E0 owns the **shape** of a card and the catalog that holds them; E5
fills the catalog with a card per tool across the four classes, and E6
implements the checkers themselves. The shape is here because the
promotion matrix reads it, and a matrix reading an undefined shape is a
matrix whose rules live in whoever wrote the last card.

**Prose and code path are separated by construction, not by review.**
The design note asks for a human-readable ``verifies`` /
``does_not_verify`` block *and* a typed policy, plus a test that every
prose line has a typed counterpart. A test like that passes on the day
it is written and then rots quietly. So the prose is stored **keyed by
the typed value it explains**: ``verifies`` maps each supported
proposition type to a sentence, ``does_not_verify`` maps each forbidden
inference type to a sentence, and the validator requires the key sets to
equal the typed policy. A sentence with no typed counterpart cannot be
written, and a typed entry with no sentence cannot either. Free prose
with no proposition behind it goes in ``notes``, which nothing reads.

**What the matrix actually consults**, and nothing else:
``proposition_policy`` (which propositions this tool can support, which
over-readings it must never be used for, its maximum claim level) and
``evidence_policy`` (which input provenances it accepts). Everything
outside those two blocks is documentation.

The card is also where deterministic stops meaning causal:
``latency_vs_expanded_nodes`` is a perfectly deterministic computation
whose maximum claim level is ``associated``, because correlating node
expansions with latency does not demonstrate that the expansions caused
it.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from planbench_explanation.levels import ClaimLevel
from planbench_explanation.propositions import (
    INFERENCE_ONLY_PROPOSITIONS,
    PropositionType,
    canonical_propositions,
)
from planbench_explanation.provenance import InputProvenance

#: Which of the four catalog classes a tool belongs to (design section 3.3).
ToolClass = Literal["fact_query", "evidence_navigation", "mechanism_check", "research_proposal"]

#: Which lane a tool's execution belongs to. ``diagnostic`` reads
#: recorded data; ``research`` would produce a new run, which no tool is
#: allowed to start — research tools emit specifications only.
ExecutionLane = Literal["diagnostic", "research"]


class ToolPurpose(BaseModel):
    """Prose for humans, keyed by the typed value it explains."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    verifies: dict[PropositionType, str] = Field(default_factory=dict)
    does_not_verify: dict[PropositionType, str] = Field(default_factory=dict)
    #: Sentences with no proposition behind them. Never read by code.
    notes: tuple[str, ...] = ()


class PropositionPolicy(BaseModel):
    """The typed half — the only half the promotion matrix reads."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    supported_proposition_types: tuple[PropositionType, ...] = ()
    forbidden_inference_types: tuple[PropositionType, ...] = ()
    maximum_claim_level: ClaimLevel

    @model_validator(mode="after")
    def _check(self) -> PropositionPolicy:
        canonical_propositions(
            self.supported_proposition_types, field="supported_proposition_types"
        )
        canonical_propositions(self.forbidden_inference_types, field="forbidden_inference_types")
        overlap = set(self.supported_proposition_types) & set(self.forbidden_inference_types)
        if overlap:
            raise ValueError(
                f"tool policy both supports and forbids {sorted(overlap)}; "
                "one card cannot answer both ways about the same proposition"
            )
        unassertable = set(self.supported_proposition_types) & set(INFERENCE_ONLY_PROPOSITIONS)
        if unassertable:
            raise ValueError(
                f"{sorted(unassertable)} are inference-only types and cannot be "
                "supported by any tool; list them under forbidden_inference_types"
            )
        if self.maximum_claim_level == "intervention_supported":
            raise ValueError(
                "no tool card may declare maximum_claim_level "
                "'intervention_supported': that level requires a preregistered "
                "intervention in the research lane, which no checker performs"
            )
        return self


class EvidencePolicy(BaseModel):
    """Which input pedigrees this tool's result may be trusted on."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    allowed_input_provenance: tuple[InputProvenance, ...]

    @model_validator(mode="after")
    def _check(self) -> EvidencePolicy:
        if not self.allowed_input_provenance:
            raise ValueError("allowed_input_provenance may not be empty")
        if "missing" in self.allowed_input_provenance:
            raise ValueError(
                "'missing' is never an allowed input provenance; a tool without "
                "its inputs reports execution_status 'not_checkable'"
            )
        return self


class ToolCard(BaseModel):
    """One entry of the tool catalog."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tool_id: str = Field(min_length=1)
    tool_version: str = Field(min_length=1)
    title: str = Field(min_length=1)
    tool_class: ToolClass
    lane: ExecutionLane = "diagnostic"
    #: Research-proposal tools emit a specification and nothing else. The
    #: flag sits on the card so a host can refuse to execute one without
    #: knowing what the tool does.
    execution_authorized: bool = True
    purpose: ToolPurpose = ToolPurpose()
    proposition_policy: PropositionPolicy
    evidence_policy: EvidencePolicy
    #: Evidence the packet must carry before the tool may be requested.
    required_evidence: tuple[str, ...] = ()
    failure_modes: tuple[str, ...] = ()

    @property
    def key(self) -> tuple[str, str]:
        """``(tool_id, tool_version)`` — how a result names its card."""
        return (self.tool_id, self.tool_version)

    @model_validator(mode="after")
    def _check(self) -> ToolCard:
        prose_keys = set(self.purpose.verifies)
        typed_keys = set(self.proposition_policy.supported_proposition_types)
        if prose_keys != typed_keys:
            raise ValueError(
                f"purpose.verifies covers {sorted(prose_keys)} but the typed policy "
                f"supports {sorted(typed_keys)}; every supported proposition needs a "
                "sentence and every sentence needs a supported proposition. Prose "
                "without a typed counterpart belongs in purpose.notes."
            )
        forbidden_prose = set(self.purpose.does_not_verify)
        forbidden_typed = set(self.proposition_policy.forbidden_inference_types)
        if forbidden_prose != forbidden_typed:
            raise ValueError(
                f"purpose.does_not_verify covers {sorted(forbidden_prose)} but the "
                f"typed policy forbids {sorted(forbidden_typed)}; the two halves must "
                "name the same over-readings."
            )
        if self.tool_class == "evidence_navigation" and typed_keys:
            raise ValueError(
                "evidence-navigation tools return evidence references and promote "
                "nothing; leave supported_proposition_types empty"
            )
        if self.tool_class == "research_proposal" and self.execution_authorized:
            raise ValueError(
                "research-proposal tools emit specifications only; set "
                "execution_authorized=False so no host can run one"
            )
        if self.tool_class == "research_proposal" and self.lane != "research":
            raise ValueError("research-proposal tools declare lane='research'")
        return self


class ToolNotInCatalog(KeyError):
    """A result named a tool card the catalog does not hold."""


class ToolCatalog(BaseModel):
    """The closed menu, at a version.

    The version is declared rather than derived from the contents so a
    result can name the menu it chose from. A hypothesis adjudicated
    under catalog ``1.2.0`` is not silently re-adjudicated by ``1.3.0``:
    the artifact header records which menu ran.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    catalog_version: str = Field(min_length=1)
    cards: tuple[ToolCard, ...] = ()

    @model_validator(mode="after")
    def _unique(self) -> ToolCatalog:
        keys = [card.key for card in self.cards]
        duplicates = sorted({key for key in keys if keys.count(key) > 1})
        if duplicates:
            raise ValueError(f"duplicate tool card(s) {duplicates} in one catalog")
        return self

    def card(self, tool_id: str, tool_version: str) -> ToolCard:
        for candidate in self.cards:
            if candidate.key == (tool_id, tool_version):
                return candidate
        raise ToolNotInCatalog(
            f"catalog {self.catalog_version} has no card for {tool_id}@{tool_version}; "
            "a result from a tool nobody declared cannot be scored"
        )
