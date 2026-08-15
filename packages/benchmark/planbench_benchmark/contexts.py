"""Building the run plan: which episodes, in which order (HĐ-3.2).

Two responsibilities, both about pairing.

**Generating the context list up front.** The number of evaluation
episodes is not a taste setting: gate G2 needs
``ceil(3 / collision_probability_max)`` clean runs before "zero collisions
observed" bounds anything (HĐ-7.1), so the default seed count is derived
from the deployment's accepted risk rather than chosen.

**Iterating contexts outside candidates.** The contract is explicit about
the loop order::

    for ctx in contexts:          # outer
        for cand in candidates:   # inner
            run(cand, ctx)

The results are identical either way — every episode is seeded from its
context — so the reason is what happens when a run does *not* finish. Stop
a candidate-outer sweep halfway and the first candidates have 300 episodes
while the last has none: nothing is comparable, and the partial data is
worthless. Stop a context-outer sweep halfway and every candidate has the
same 140 contexts, so the comparison is still valid, just smaller. This
also makes the violation HĐ-3.2 names — "two candidates with a different
number of episodes in one run" — structurally impossible rather than
something to remember to check.
"""

from __future__ import annotations

import math
from collections.abc import Iterator, Sequence

from planbench_decision.candidate import Candidate
from planbench_schemas.episode_context import NOMINAL_VARIANT, EpisodeContext
from planbench_schemas.task_profile import TaskProfile


def evaluation_seed_count(profile: TaskProfile) -> int:
    """Seeds per mission needed to reach G2's minimum episode count.

    The gate counts episodes, not seeds, and every mission contributes one
    episode per seed — so the seeds are shared across missions and the
    count is ``ceil(N_min / n_missions)``. Rounding up rather than down:
    landing one episode short of ``N_min`` fails G2 outright, which would
    waste the whole run.
    """
    n_min = profile.constraints.n_min_evaluation_episodes
    return math.ceil(n_min / len(profile.missions))


def build_evaluation_contexts(
    profile: TaskProfile,
    *,
    seed_count: int | None = None,
    first_seed: int = 0,
) -> tuple[EpisodeContext, ...]:
    """The evaluation sample set: every mission crossed with every seed.

    A balanced design — each mission gets the same number of episodes.
    That is exactly right for a mission-level claim, and deliberately
    *not* weighted by ``Mission.probability``: turning a mission
    distribution into a matching episode budget is the Mission Sampler's
    job (§1.2, phase 2), and faking it here would let a deployment-level
    average be quoted from a balanced sample.

    ``seed_count`` defaults to :func:`evaluation_seed_count`. Passing a
    smaller number is legitimate for a smoke run, but the resulting set
    will not satisfy G2 — which the gate will say, rather than this
    function guessing what the caller meant.
    """
    count = evaluation_seed_count(profile) if seed_count is None else seed_count
    if count <= 0:
        raise ValueError(f"seed_count must be positive, got {count}")
    return tuple(
        EpisodeContext(
            task_profile_id=profile.id,
            mission_id=mission.id,
            seed=first_seed + offset,
            environment_variant=NOMINAL_VARIANT,
            sample_set="evaluation",
        )
        for offset in range(count)
        for mission in profile.missions
    )


def iter_run_plan(
    contexts: Sequence[EpisodeContext], candidates: Sequence[Candidate]
) -> Iterator[tuple[EpisodeContext, Candidate]]:
    """Yield ``(context, candidate)`` with the context loop outermost.

    Ordering is the guarantee this function exists to provide; see the
    module docstring for why it survives an interrupted run.
    """
    if not contexts:
        raise ValueError("a run plan needs at least one episode context")
    if not candidates:
        raise ValueError("a run plan needs at least one candidate")
    duplicates = _duplicate_context_ids(contexts)
    if duplicates:
        raise ValueError(
            f"duplicate episode context(s) {duplicates} in the run plan; the same "
            "conditions twice would be counted as two independent samples"
        )
    for context in contexts:
        for candidate in candidates:
            yield (context, candidate)


def _duplicate_context_ids(contexts: Sequence[EpisodeContext]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for context in contexts:
        identifier = context.episode_context_id
        if identifier in seen:
            duplicates.add(identifier)
        seen.add(identifier)
    return sorted(duplicates)


def episode_total(contexts: Sequence[EpisodeContext], candidates: Sequence[Candidate]) -> int:
    """How many episodes the plan will run — the cost of the decision.

    Worth reporting before starting: N9 is the pain point that a selection
    run nobody can afford is a selection run nobody uses.
    """
    return len(contexts) * len(candidates)
