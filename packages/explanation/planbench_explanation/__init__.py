"""Explanation layer contracts (E0) — the *why* behind a Decision Card.

The Decision Card answers *which candidate won*. This package owns the
contracts for answering *why*: the ledger objects, the evidence ladder
they sit on, the tool cards that license a checker to establish
something, the deterministic promotion matrix that is the only producer
of claims, and the sidecar that decides whether a replay is worth
anything.

Nothing here talks to a model. An external analyst subsystem proposes
hypotheses and requests checks; this package defines what such a
proposal may contain, what a signed checker result looks like, and what
evidence is required before a sentence reaches a screen.
"""

from planbench_explanation.ledger import (
    CheckerResult,
    Claim,
    EvidenceKind,
    EvidenceLane,
    EvidenceRef,
    HypothesisProposal,
    ImpactKind,
    ImpactRef,
    InterventionEvidence,
    InvestigationRecord,
    KnownUnknown,
    PropositionOutcome,
    RecordStatus,
    RequestedCheck,
)
from planbench_explanation.levels import (
    CLAIM_LEVEL_ORDER,
    ENGLISH_PHRASES,
    KNOWN_QUALIFIERS,
    ClaimLevel,
    PhrasePolicy,
    Qualifier,
    canonical_qualifiers,
    check_phrases,
    level_rank,
    weakest,
)
from planbench_explanation.planning_input_evidence import (
    REPLAY_CEILING,
    PlanningInputEvidence,
    PlanningOutcome,
    PlanningQuery,
    ReplayAdmission,
    ReplayObservation,
    SidecarViolation,
    admit_replay_with_sidecar,
    admit_replay_without_sidecar,
    validate_episode_attempts,
)
from planbench_explanation.promotion import PromotionOutcome, promote, promote_measurement
from planbench_explanation.propositions import (
    ASSERTABLE_PROPOSITIONS,
    INFERENCE_ONLY_PROPOSITIONS,
    KNOWN_PROPOSITIONS,
    NotAssertableError,
    PropositionType,
    UnknownPropositionError,
    canonical_propositions,
    require_assertable,
)
from planbench_explanation.provenance import (
    EXECUTION_STATUSES,
    INPUT_PROVENANCES,
    PROPOSITION_VERDICTS,
    ExecutionStatus,
    InputProvenance,
    MissingInputEvidence,
    PropositionVerdict,
    provenance_ceiling,
)
from planbench_explanation.subjects import (
    KNOWN_SUBJECTS,
    PRE_H4_CAPPED_SUBJECTS,
    Subject,
    UnknownSubjectError,
    canonical_subjects,
    subject_ceiling,
)
from planbench_explanation.tools import (
    EvidencePolicy,
    ExecutionLane,
    PropositionPolicy,
    ToolCard,
    ToolCatalog,
    ToolClass,
    ToolNotInCatalog,
    ToolPurpose,
)
from planbench_explanation.versioning import (
    ARTIFACT_CHECKSUM_VERSION,
    EXPLANATION_SCHEMA_VERSION,
    PROMOTION_MATRIX_VERSION,
    ExplanationArtifactHeader,
    artifact_checksum,
    file_checksum,
)

__all__ = [
    "ARTIFACT_CHECKSUM_VERSION",
    "ASSERTABLE_PROPOSITIONS",
    "CLAIM_LEVEL_ORDER",
    "ENGLISH_PHRASES",
    "EXECUTION_STATUSES",
    "EXPLANATION_SCHEMA_VERSION",
    "INFERENCE_ONLY_PROPOSITIONS",
    "INPUT_PROVENANCES",
    "KNOWN_PROPOSITIONS",
    "KNOWN_QUALIFIERS",
    "KNOWN_SUBJECTS",
    "PRE_H4_CAPPED_SUBJECTS",
    "PROMOTION_MATRIX_VERSION",
    "PROPOSITION_VERDICTS",
    "REPLAY_CEILING",
    "CheckerResult",
    "Claim",
    "ClaimLevel",
    "EvidenceKind",
    "EvidenceLane",
    "EvidencePolicy",
    "EvidenceRef",
    "ExecutionLane",
    "ExecutionStatus",
    "ExplanationArtifactHeader",
    "HypothesisProposal",
    "ImpactKind",
    "ImpactRef",
    "InputProvenance",
    "InterventionEvidence",
    "InvestigationRecord",
    "KnownUnknown",
    "MissingInputEvidence",
    "NotAssertableError",
    "PhrasePolicy",
    "PlanningInputEvidence",
    "PlanningOutcome",
    "PlanningQuery",
    "PromotionOutcome",
    "PropositionOutcome",
    "PropositionPolicy",
    "PropositionType",
    "PropositionVerdict",
    "Qualifier",
    "RecordStatus",
    "ReplayAdmission",
    "ReplayObservation",
    "RequestedCheck",
    "SidecarViolation",
    "Subject",
    "ToolCard",
    "ToolCatalog",
    "ToolClass",
    "ToolNotInCatalog",
    "ToolPurpose",
    "UnknownPropositionError",
    "UnknownSubjectError",
    "admit_replay_with_sidecar",
    "admit_replay_without_sidecar",
    "artifact_checksum",
    "canonical_propositions",
    "canonical_qualifiers",
    "canonical_subjects",
    "check_phrases",
    "file_checksum",
    "level_rank",
    "promote",
    "promote_measurement",
    "provenance_ceiling",
    "require_assertable",
    "subject_ceiling",
    "validate_episode_attempts",
    "weakest",
]
