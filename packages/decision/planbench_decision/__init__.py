"""Decision layer: everything downstream of the Metrics Engine.

Feasibility gates, objective normalisation, Decision Utility, Pareto
labelling, paired statistics and the Decision Card live here. The layer
reads metrics and a task profile; it never touches the simulator, which
is why it can be built and tested without running an episode
(CONTRACTS §16, plan phase 3).
"""

from planbench_decision.candidate import (
    CANDIDATE_ID_LENGTH,
    Candidate,
    CandidateSchemaError,
    CandidateType,
    ExperimentScope,
    ExperimentScopeViolation,
    PolicyComponent,
    StackComponent,
    load_candidate,
    validate_experiment_scope,
)

__all__ = [
    "CANDIDATE_ID_LENGTH",
    "Candidate",
    "CandidateSchemaError",
    "CandidateType",
    "ExperimentScope",
    "ExperimentScopeViolation",
    "PolicyComponent",
    "StackComponent",
    "load_candidate",
    "validate_experiment_scope",
]
