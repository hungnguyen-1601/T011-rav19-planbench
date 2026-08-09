"""Decision layer: everything downstream of the Metrics Engine.

Feasibility gates, objective normalisation, Decision Utility, Pareto
labelling, paired statistics and the Decision Card live here. The layer
reads metrics and a task profile; it never touches the simulator, which
is why it can be built and tested without running an episode
(CONTRACTS §16, plan phase 3).
"""

from planbench_decision.candidate import (
    CANDIDATE_ID_LENGTH,
    ArtifactResourceProfile,
    Candidate,
    CandidateSchemaError,
    CandidateType,
    ExperimentScope,
    ExperimentScopeViolation,
    PolicyComponent,
    ResourceProfile,
    StackComponent,
    StructuralResourceProfile,
    load_candidate,
    validate_experiment_scope,
)
from planbench_decision.pairing import (
    PairingViolation,
    SampleSetViolation,
    context_ids,
    require_sample_set,
    require_shared_contexts,
)

__all__ = [
    "CANDIDATE_ID_LENGTH",
    "ArtifactResourceProfile",
    "Candidate",
    "CandidateSchemaError",
    "CandidateType",
    "ExperimentScope",
    "ExperimentScopeViolation",
    "PairingViolation",
    "PolicyComponent",
    "ResourceProfile",
    "SampleSetViolation",
    "StackComponent",
    "StructuralResourceProfile",
    "context_ids",
    "load_candidate",
    "require_sample_set",
    "require_shared_contexts",
    "validate_experiment_scope",
]
