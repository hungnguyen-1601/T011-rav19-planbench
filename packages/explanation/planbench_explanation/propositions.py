"""The closed list of things a claim can assert.

A proposition type is *what is being said*, stripped of who says it and
how strongly. It is a closed vocabulary, and closed for the reason G6's
observation tokens are: the promotion matrix compares these strings
literally, so a tool card advertising ``geometric_infeasibilty`` would
be silently unable to support the hypothesis it was written for, and the
failure would read as "the checker found nothing".

Two families live here on purpose.

**Assertable types** are things the platform can, in principle, end up
claiming. **Inference-only types** are the over-readings a tool card
lists in ``forbidden_inference_types`` — statements no tool in the
catalog is ever allowed to support, however good its verdict. The
canonical example is ``complete_utility_attribution``: a checker showing
that a passage is too narrow has shown exactly that, and *not* that the
narrow passage accounts for the whole utility gap. Keeping the
over-reading in the vocabulary is what lets a card refuse it by name
rather than by hoping nobody asks.

Adding a type is one line here plus the tool cards that mention it.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

PropositionType = Literal[
    # --- assertable -----------------------------------------------------
    "geometric_infeasibility",
    "local_minimum_entrapment",
    "sampling_budget_insufficiency",
    "expansion_latency_association",
    "replan_instability",
    "clearance_refusal",
    "component_specific_attribution",
    "candidate_latency_attribution",
    "perception_attribution",
    "ppo_behavior_attribution",
    # --- inference-only (never assertable, only forbidden) --------------
    "complete_utility_attribution",
    "global_planner_attempt_attribution",
    "universal_algorithm_superiority",
]

ASSERTABLE_PROPOSITIONS: tuple[PropositionType, ...] = (
    "geometric_infeasibility",
    "local_minimum_entrapment",
    "sampling_budget_insufficiency",
    "expansion_latency_association",
    "replan_instability",
    "clearance_refusal",
    "component_specific_attribution",
    "candidate_latency_attribution",
    "perception_attribution",
    "ppo_behavior_attribution",
)

#: Over-readings a card may forbid. Never the type of a claim.
INFERENCE_ONLY_PROPOSITIONS: tuple[PropositionType, ...] = (
    "complete_utility_attribution",
    "global_planner_attempt_attribution",
    "universal_algorithm_superiority",
)

KNOWN_PROPOSITIONS: tuple[PropositionType, ...] = (
    *ASSERTABLE_PROPOSITIONS,
    *INFERENCE_ONLY_PROPOSITIONS,
)


class UnknownPropositionError(ValueError):
    """A proposition type outside :data:`KNOWN_PROPOSITIONS`."""


class NotAssertableError(ValueError):
    """An inference-only type used where a claim's subject was expected."""


def canonical_propositions(values: Iterable[str], *, field: str) -> tuple[PropositionType, ...]:
    """Validate, deduplicate and sort proposition types."""
    cleaned = {value.strip() for value in values}
    unknown = sorted(cleaned - set(KNOWN_PROPOSITIONS))
    if unknown:
        raise UnknownPropositionError(
            f"{field} contains unknown proposition type(s) {unknown}; "
            f"known types are {list(KNOWN_PROPOSITIONS)}. Add the type to "
            "planbench_explanation.propositions rather than spelling it "
            "differently here — the promotion matrix compares these literally."
        )
    return tuple(sorted(cleaned))  # type: ignore[arg-type]


def require_assertable(value: str, *, field: str) -> PropositionType:
    """The type, if something may actually be claimed about it."""
    (canonical,) = canonical_propositions([value], field=field)
    if canonical in INFERENCE_ONLY_PROPOSITIONS:
        raise NotAssertableError(
            f"{field}={canonical!r} is an inference-only type: it exists so tool "
            "cards can forbid it by name, and no evidence promotes it to a claim."
        )
    return canonical
