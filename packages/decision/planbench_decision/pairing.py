"""Refusing an unpaired comparison (HĐ-3.2, HĐ-11.4).

> The Decision Engine must **refuse** to compute ``ΔU`` if the two
> candidates' context sets do not match exactly.

This module is that refusal. It is separate from the statistics it guards
because the check must happen *before* any number is produced: a ΔU
computed over mismatched contexts is not a noisy answer, it is an answer
to a different question — it measures the conditions the candidates did
not share. Returning it with a caveat would be worse than raising, because
the caveat travels in prose and the number travels in a Decision Card.

Also enforced here: the ban on pooling the two sample sets. The collision
upper bound ``3/N`` assumes independent, identically distributed runs.
Neighborhood episodes are clustered by variant, so their effective sample
size is far below the row count, and pooling them would make the bound
look better than the evidence supports — the one direction of error a
safety claim must never take.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from planbench_schemas.episode_context import EpisodeContext, SampleSet


class PairingViolation(ValueError):
    """The episodes on hand cannot support a paired comparison."""


class SampleSetViolation(ValueError):
    """Episodes from the wrong sample set for the statistic requested."""


def context_ids(contexts: Iterable[EpisodeContext]) -> tuple[str, ...]:
    """Context ids in the order given, for building a manifest."""
    return tuple(context.episode_context_id for context in contexts)


def require_shared_contexts(
    contexts_by_candidate: Mapping[str, Sequence[EpisodeContext]],
) -> tuple[str, ...]:
    """Return the shared context ids, or raise if they are not shared.

    Every candidate must have run on exactly the same set — same members,
    same count. The returned tuple is sorted so the resampling order in a
    paired bootstrap does not depend on dictionary iteration order, which
    would make a seeded bootstrap irreproducible.

    Reported failures name the candidates and the difference, because the
    person reading this is deciding whether to re-run episodes or to fix a
    runner bug, and those need different evidence.
    """
    if not contexts_by_candidate:
        raise PairingViolation("no candidates to compare")

    per_candidate: dict[str, tuple[str, ...]] = {}
    for candidate_id, contexts in contexts_by_candidate.items():
        identifiers = context_ids(contexts)
        if not identifiers:
            raise PairingViolation(f"candidate {candidate_id} has no episodes")
        duplicates = sorted({i for i in identifiers if identifiers.count(i) > 1})
        if duplicates:
            raise PairingViolation(
                f"candidate {candidate_id} ran context(s) {duplicates} more than once; "
                "repeated conditions would be resampled as independent episodes"
            )
        per_candidate[candidate_id] = identifiers

    reference_id, reference = next(iter(per_candidate.items()))
    reference_set = set(reference)
    for candidate_id, identifiers in per_candidate.items():
        current = set(identifiers)
        if current == reference_set:
            continue
        missing = sorted(reference_set - current)
        extra = sorted(current - reference_set)
        raise PairingViolation(
            f"candidates {reference_id} and {candidate_id} did not run the same "
            f"episodes: {len(missing)} missing from {candidate_id} "
            f"(e.g. {missing[:3]}), {len(extra)} it ran alone (e.g. {extra[:3]}). "
            "Refusing to compute a paired difference over unmatched conditions"
        )
    return tuple(sorted(reference_set))


def require_sample_set(contexts: Iterable[EpisodeContext], expected: SampleSet) -> None:
    """Raise unless every context belongs to ``expected``.

    Used by the collision upper bound and every performance estimate,
    which are valid on ``evaluation`` only (HĐ-11.4).
    """
    wrong = sorted({context.sample_set for context in contexts if context.sample_set != expected})
    if wrong:
        raise SampleSetViolation(
            f"this statistic is defined on the {expected!r} sample set only, but the "
            f"episodes include {wrong}; pooling the sets makes the rule-of-three bound "
            "optimistic because runs within one neighborhood variant are correlated"
        )
