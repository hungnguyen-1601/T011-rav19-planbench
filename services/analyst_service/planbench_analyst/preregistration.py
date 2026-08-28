"""What the bar is, written down before any run that could move it.

The platform's own rule for a gate — thresholds preregistered against a
hidden suite, re-derived rather than trusted — applies just as much to
the experiments that lead up to one. A primary endpoint chosen after the
numbers are in is the flattering one; a margin chosen after is the one
the result clears. So this module is a constant, its checksum goes on
every report, and the test suite pins the checksum: changing any value
here is a diff somebody has to explain, not an edit somebody makes.

Three parts, in the order a reader should apply them:

**Hard constraints** veto. A configuration that violates one is not
compared on anything else.

**The primary endpoint** is one number, tested one way, against one
margin. Everything else is secondary and is read only if the primary
passed — hierarchical testing, so a shopping trip through eight metrics
cannot find one that happens to look good.

**The utility function** is how "best" is defined for the router
oracle. Weights fixed here; an oracle whose weights move after the
arms are scored is an oracle chosen to be beaten.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from planbench_explanation.versioning import artifact_checksum

__all__ = ["PREREGISTRATION", "Preregistration", "preregistration_checksum"]


@dataclass(frozen=True)
class Preregistration:
    """The bar, as data. Frozen, hashed, pinned by a test."""

    #: Metrics that veto before any comparison. Name → required value.
    hard_constraints: tuple[tuple[str, float], ...] = (
        ("structural_violations", 0.0),
        ("budget_and_protocol_pass", 1.0),
        ("menu_recall_when_filtering", 1.0),
    )

    #: The one number the conclusion is about: share of cases where the
    #: mechanism the analyst proposed matches the planted one, case-level.
    primary_endpoint: str = "case_level_mechanism_correctness"
    #: Paired exact test on the discordant cases (McNemar), analyst
    #: against the model-free floor on the same packets.
    primary_test: str = "mcnemar_exact_paired"
    #: Non-inferiority margin on the primary endpoint, as an absolute
    #: difference in the case-level rate. Analyst is non-inferior when
    #: the lower confidence bound of (analyst − floor) exceeds −δ.
    delta: float = 0.10
    #: Two-sided for superiority, one-sided for non-inferiority.
    alpha: float = 0.05
    confidence: float = 0.95

    #: Read only if the primary passed, in this order, and only the ones
    #: that were declared here.
    secondary_endpoints: tuple[str, ...] = (
        "component_attribution_accuracy",
        "abstention_correctness",
        "evidence_relevance",
        "checker_selection_model_chosen",
        "verified_rate_case_level",
        "cost_median_tokens_itt",
    )

    #: Fewer cases than this and ``pass^k`` is not reported as a number,
    #: only as counts. On three cases one flip is thirty-three points.
    min_cases_for_pass_k: int = 12
    #: Repeats per configuration for reliability. Every repeat is an
    #: independent model call; the harness asserts zero cache hits.
    repeats: int = 3

    #: Router oracle: ``U = w_q·quality − w_c·cost − w_l·latency``.
    #: quality in [0, 1]; cost in thousands of tokens; latency in seconds.
    utility_weights: tuple[tuple[str, float], ...] = (
        ("quality", 1.0),
        ("cost_k_tokens", 0.02),
        ("latency_s", 0.005),
    )

    #: Which families the development set holds. Reported beside every
    #: macro average so 3/6 is never read as 6/6.
    families_staged: tuple[str, ...] = (
        "inflation_gap_closure",
        "rrt_sample_starvation",
        "dwa_local_minimum",
    )
    families_total: int = 6

    notes: tuple[str, ...] = field(
        default_factory=lambda: (
            "Locked 2026-08-26 before B1. Any change is a new version with a diff.",
            "Development set only. The confirmatory set is the hidden suite behind "
            "run_gate, and its thresholds are CALIBRATION_TARGETS.",
        )
    )

    def as_record(self) -> dict[str, object]:
        return {
            "hard_constraints": dict(self.hard_constraints),
            "primary_endpoint": self.primary_endpoint,
            "primary_test": self.primary_test,
            "delta": self.delta,
            "alpha": self.alpha,
            "confidence": self.confidence,
            "secondary_endpoints": list(self.secondary_endpoints),
            "min_cases_for_pass_k": self.min_cases_for_pass_k,
            "repeats": self.repeats,
            "utility_weights": dict(self.utility_weights),
            "families_staged": list(self.families_staged),
            "families_total": self.families_total,
            "notes": list(self.notes),
        }


PREREGISTRATION = Preregistration()


def preregistration_checksum(spec: Preregistration = PREREGISTRATION) -> str:
    """Goes on every report. Pinned by a test so a change is a decision."""
    return artifact_checksum(spec.as_record())
