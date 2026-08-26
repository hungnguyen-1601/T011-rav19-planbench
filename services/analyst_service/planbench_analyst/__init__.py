"""The analyst: the half of the explanation layer that proposes.

``packages/explanation`` owns the evidence, the sixteen tool cards, the
four mechanism checkers, the promotion matrix and the gate. It can say
what a claim is allowed to be, and it can refuse one. What it cannot do
is read a case packet and say *what the mechanism might be* — that is
the one job in this layer that needs a model, and it is this package.

Four rules every module under here inherits, from the E0–E6 contract
and from plan bản 8 §1. They are restated here rather than left in the
plan because a module that forgets one of them looks, from the outside,
exactly like a module that is working:

1. **It proposes; it never stamps.** The analyst returns
   :class:`~planbench_explanation.ledger.HypothesisProposal` objects,
   which carry no status, no confidence and no number — ``extra="forbid"``
   turns that policy into a parse error rather than a review comment.
2. **The model is never the source of a number.** Numbers shown to a
   reader are read out of the packet's fact index by the renderer. A
   statement that carries a quantity is a statement the guard drops.
3. **The tool menu is closed.** Sixteen cards, catalog version pinned in
   the bundle. There is no free-form check.
4. **It does not read raw traces.** The case packet and the tool results
   are the whole world; a Parquet file opened here would be evidence
   nobody could re-derive from the artifact the gate holds.

The modules arrive with their phases (A1 packet view, A2 engine, A3
guard, A4 runner and lane, A5 knowledge, A6 harness, A7 bundle builder),
and each one is exported as it lands. A name published before the thing
behind it exists is the sort of promise the rest of this layer is built
to refuse, and ``tests/test_analyst_service_wiring.py`` holds the two
halves together: a module on disk that nothing here exports is a stub
somebody left behind.
"""

from __future__ import annotations

from planbench_analyst.analyst import (
    AnalystRefusal,
    CheckFeedback,
    RoundCost,
    RoundReport,
    catalog_text,
    propose,
)
from planbench_analyst.bundle_builder import (
    CalibrationRun,
    FreezeRefusal,
    ModelIdentity,
    calibrate,
    freeze_bundle,
)
from planbench_analyst.cache import CacheStats, ResponseCache, cache_key
from planbench_analyst.candidates import (
    CandidateRefusal,
    MechanismCandidate,
    VerificationOption,
    generate_candidates,
    generator_recall_at_k,
    inject_distractors,
    render_candidates,
)
from planbench_analyst.eval_spec import (
    CaseLabels,
    EvalSpec,
    EvalSpecRefusal,
    RefPredicate,
    assert_no_label_in,
    load_eval_spec,
    refs_satisfy,
)
from planbench_analyst.features import FeatureRefusal, RoundFeatures
from planbench_analyst.guard import Blocked, GuardResult, critique, guard, quantities_in
from planbench_analyst.harness import (
    CaseResult,
    FloorComparison,
    HarnessReport,
    compare_with_floor,
    failure_table,
    mcnemar_exact,
    pass_hat_k,
    quality_pass_hat_k,
    routing_failures,
    wilson_interval,
)
from planbench_analyst.identity import (
    SOURCE_GLOBS,
    ConfigRefusal,
    effective_generation_config,
    flatten_config,
    runtime_config_checksum,
    source_manifest_hash,
    validate_generation_config,
)
from planbench_analyst.knowledge_provider import (
    RETRIEVAL_VERSION,
    TraitOffer,
    query_for,
    retrieve,
    trait_offers,
)
from planbench_analyst.model_gateway import GatewayRefusal, ModelGateway
from planbench_analyst.packet_view import (
    Fact,
    PacketView,
    PacketViewRefusal,
    build_packet_view,
)
from planbench_analyst.preregistration import (
    PREREGISTRATION,
    Preregistration,
    preregistration_checksum,
)
from planbench_analyst.prompts import (
    ANALYST_SYSTEM,
    PROMPT_VERSION,
    analyst_schema,
    prompt_checksum,
)
from planbench_analyst.restricted import RestrictedArtifact, case_token, public_error
from planbench_analyst.round_host import (
    InProcessHost,
    PreparedRound,
    RoundEvidence,
    RoundHostProtocol,
    evidence_for,
    in_process_round,
    platform_implementation_ref,
)
from planbench_analyst.runner import RoundOutcome, run_round
from planbench_analyst.sanitize import Aliases, canonical, is_suspicious, label_components
from planbench_analyst.stdio_lane import FrameHost, FrameProvider, FrameStream
from planbench_analyst.stdio_protocol import (
    Frame,
    FrameSession,
    ProtocolViolation,
)
from planbench_analyst.traits_snapshot import (
    SnapshotRefusal,
    TraitsSnapshot,
    delete_snapshot,
    read_snapshot,
    snapshot_from,
    verify_snapshot,
    write_snapshot,
)

__all__ = [
    "MechanismCandidate",
    "VerificationOption",
    "CandidateRefusal",
    "generate_candidates",
    "generator_recall_at_k",
    "inject_distractors",
    "render_candidates",
    "TraitsSnapshot",
    "SnapshotRefusal",
    "snapshot_from",
    "read_snapshot",
    "write_snapshot",
    "delete_snapshot",
    "verify_snapshot",
    "RoundFeatures",
    "FeatureRefusal",
    "wilson_interval",
    "refs_satisfy",
    "quality_pass_hat_k",
    "preregistration_checksum",
    "load_eval_spec",
    "assert_no_label_in",
    "RefPredicate",
    "Preregistration",
    "PREREGISTRATION",
    "EvalSpecRefusal",
    "EvalSpec",
    "CaseLabels",
    "ANALYST_SYSTEM",
    "RETRIEVAL_VERSION",
    "SOURCE_GLOBS",
    "PROMPT_VERSION",
    "Aliases",
    "AnalystRefusal",
    "CheckFeedback",
    "Blocked",
    "InProcessHost",
    "RoundEvidence",
    "platform_implementation_ref",
    "Frame",
    "FrameHost",
    "FrameProvider",
    "FrameStream",
    "FreezeRefusal",
    "FrameSession",
    "GatewayRefusal",
    "ModelGateway",
    "ModelIdentity",
    "CacheStats",
    "CalibrationRun",
    "CaseResult",
    "ConfigRefusal",
    "Fact",
    "FloorComparison",
    "GuardResult",
    "HarnessReport",
    "PacketView",
    "PacketViewRefusal",
    "PreparedRound",
    "ProtocolViolation",
    "RestrictedArtifact",
    "ResponseCache",
    "RoundCost",
    "RoundHostProtocol",
    "RoundOutcome",
    "TraitOffer",
    "RoundReport",
    "analyst_schema",
    "build_packet_view",
    "cache_key",
    "calibrate",
    "case_token",
    "canonical",
    "catalog_text",
    "compare_with_floor",
    "critique",
    "evidence_for",
    "in_process_round",
    "effective_generation_config",
    "failure_table",
    "freeze_bundle",
    "flatten_config",
    "guard",
    "is_suspicious",
    "label_components",
    "mcnemar_exact",
    "pass_hat_k",
    "prompt_checksum",
    "query_for",
    "retrieve",
    "routing_failures",
    "trait_offers",
    "public_error",
    "propose",
    "quantities_in",
    "run_round",
    "runtime_config_checksum",
    "source_manifest_hash",
    "validate_generation_config",
]
