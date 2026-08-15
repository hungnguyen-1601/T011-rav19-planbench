"""Episode context identity, run plan and pairing (CONTRACTS HĐ-3)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from task_profile_fakes import constraints, make_profile, three_missions

from planbench_benchmark.candidates import candidate_from_stack
from planbench_benchmark.contexts import (
    build_evaluation_contexts,
    episode_total,
    evaluation_seed_count,
    iter_run_plan,
)
from planbench_decision.pairing import (
    PairingViolation,
    SampleSetViolation,
    context_ids,
    require_sample_set,
    require_shared_contexts,
)
from planbench_schemas.episode_context import (
    EPISODE_CONTEXT_ID_LENGTH,
    NOMINAL_VARIANT,
    EpisodeContext,
)


def context(**overrides: object) -> EpisodeContext:
    payload: dict[str, object] = {
        "task_profile_id": "warehouse_a_v1",
        "mission_id": "m1",
        "seed": 7,
    }
    payload.update(overrides)
    return EpisodeContext.model_validate(payload)


class TestIdentity:
    def test_id_is_stable_and_short(self) -> None:
        assert context().episode_context_id == context().episode_context_id
        assert len(context().episode_context_id) == EPISODE_CONTEXT_ID_LENGTH

    def test_every_hashed_field_changes_the_id(self) -> None:
        baseline = context().episode_context_id
        assert context(task_profile_id="other").episode_context_id != baseline
        assert context(mission_id="m2").episode_context_id != baseline
        assert context(seed=8).episode_context_id != baseline
        variant = context(environment_variant="v3", sample_set="neighborhood")
        assert variant.episode_context_id != baseline

    def test_sample_set_is_not_hashed(self) -> None:
        """HĐ-3.1 fixes the hashed payload; an id computed from anything
        else would not match another implementation of the contract."""
        payload = {"task_profile_id": "p", "mission_id": "m", "seed": 1}
        from planbench_schemas.identity import canonical_json, sha256_short

        expected = sha256_short(
            canonical_json({**payload, "environment_variant": NOMINAL_VARIANT}),
            length=EPISODE_CONTEXT_ID_LENGTH,
        )
        assert context(**payload).episode_context_id == expected

    def test_dump_reloads_unchanged(self) -> None:
        original = context()
        reloaded = EpisodeContext.model_validate(original.model_dump(mode="json"))
        assert reloaded == original
        assert reloaded.episode_context_id == original.episode_context_id

    def test_frozen(self) -> None:
        with pytest.raises(ValidationError):
            context().seed = 9  # type: ignore[misc]

    def test_negative_seed_rejected(self) -> None:
        with pytest.raises(ValidationError):
            context(seed=-1)


class TestSampleSetInvariant:
    def test_evaluation_defaults_to_nominal(self) -> None:
        assert context().sample_set == "evaluation"
        assert context().environment_variant == NOMINAL_VARIANT

    def test_evaluation_on_a_variant_rejected(self) -> None:
        with pytest.raises(ValidationError, match="nominal environment"):
            context(environment_variant="jitter_03")

    def test_neighborhood_on_nominal_rejected(self) -> None:
        """Otherwise the two sets collide on one id and the ban on
        pooling them (HĐ-11.4) stops being checkable."""
        with pytest.raises(ValidationError, match="must name the variant"):
            context(sample_set="neighborhood")

    def test_neighborhood_variant_accepted(self) -> None:
        ctx = context(sample_set="neighborhood", environment_variant="jitter_03")
        assert ctx.sample_set == "neighborhood"


class TestSeedCount:
    def test_derived_from_accepted_risk(self) -> None:
        # 1% risk -> 300 episodes, one mission -> 300 seeds.
        assert evaluation_seed_count(make_profile()) == 300

    def test_shared_across_missions(self) -> None:
        profile = make_profile(claim_level="deployment", missions=three_missions())
        assert evaluation_seed_count(profile) == 100
        assert len(build_evaluation_contexts(profile)) == 300

    def test_rounds_up_so_g2_is_reachable(self) -> None:
        profile = make_profile(
            claim_level="deployment",
            missions=[
                {"id": "m1", "start": [0, 0, 0], "goal": [1, 1, 0], "probability": 0.5},
                {"id": "m2", "start": [0, 0, 0], "goal": [2, 2, 0], "probability": 0.5},
            ],
            constraints=constraints(collision_probability_max=0.02),
        )
        # ceil(3 / 0.02) = 150 episodes over 2 missions -> 75 seeds each.
        assert evaluation_seed_count(profile) == 75
        assert len(build_evaluation_contexts(profile)) >= 150


class TestBuildEvaluationContexts:
    def test_all_evaluation_on_nominal(self) -> None:
        contexts = build_evaluation_contexts(make_profile(), seed_count=4)
        assert len(contexts) == 4
        assert {c.sample_set for c in contexts} == {"evaluation"}
        assert {c.environment_variant for c in contexts} == {NOMINAL_VARIANT}

    def test_ids_are_unique(self) -> None:
        contexts = build_evaluation_contexts(
            make_profile(claim_level="deployment", missions=three_missions()), seed_count=10
        )
        assert len(set(context_ids(contexts))) == len(contexts) == 30

    def test_balanced_across_missions(self) -> None:
        profile = make_profile(claim_level="deployment", missions=three_missions())
        contexts = build_evaluation_contexts(profile, seed_count=5)
        counts = {m.id: sum(1 for c in contexts if c.mission_id == m.id) for m in profile.missions}
        assert set(counts.values()) == {5}

    def test_probability_does_not_weight_the_budget(self) -> None:
        """Weighting is the Mission Sampler's job (phase 2); doing it here
        would let a deployment average be quoted from a balanced sample."""
        profile = make_profile(claim_level="deployment", missions=three_missions())
        contexts = build_evaluation_contexts(profile, seed_count=4)
        m1 = sum(1 for c in contexts if c.mission_id == "m1")  # probability 0.40
        m3 = sum(1 for c in contexts if c.mission_id == "m3")  # probability 0.25
        assert m1 == m3

    def test_reproducible(self) -> None:
        a = build_evaluation_contexts(make_profile(), seed_count=6)
        b = build_evaluation_contexts(make_profile(), seed_count=6)
        assert context_ids(a) == context_ids(b)

    def test_first_seed_shifts_the_set(self) -> None:
        a = build_evaluation_contexts(make_profile(), seed_count=3)
        b = build_evaluation_contexts(make_profile(), seed_count=3, first_seed=100)
        assert not set(context_ids(a)) & set(context_ids(b))

    def test_non_positive_seed_count_rejected(self) -> None:
        with pytest.raises(ValueError, match="must be positive"):
            build_evaluation_contexts(make_profile(), seed_count=0)


class TestRunPlan:
    def test_context_loop_is_outermost(self) -> None:
        """HĐ-3.2's order: interrupting the sweep leaves every candidate
        with the same completed contexts."""
        contexts = build_evaluation_contexts(make_profile(), seed_count=3)
        candidates = [candidate_from_stack("astar+dwa"), candidate_from_stack("rrtstar+dwa")]
        plan = list(iter_run_plan(contexts, candidates))

        assert len(plan) == 6
        # First two entries share a context and differ in candidate.
        assert plan[0][0] == plan[1][0]
        assert plan[0][1] != plan[1][1]
        # Truncating anywhere on a context boundary keeps the counts equal.
        prefix = plan[:4]
        per_candidate = [
            sum(1 for _, cand in prefix if cand.candidate_id == c.candidate_id) for c in candidates
        ]
        assert len(set(per_candidate)) == 1

    def test_every_pair_appears_once(self) -> None:
        contexts = build_evaluation_contexts(make_profile(), seed_count=4)
        candidates = [candidate_from_stack("astar+dwa"), candidate_from_stack("rrtstar+dwa")]
        pairs = [
            (c.episode_context_id, k.candidate_id) for c, k in iter_run_plan(contexts, candidates)
        ]
        assert len(pairs) == len(set(pairs)) == episode_total(contexts, candidates)

    def test_duplicate_contexts_rejected(self) -> None:
        contexts = build_evaluation_contexts(make_profile(), seed_count=2)
        with pytest.raises(ValueError, match="duplicate episode context"):
            list(iter_run_plan([*contexts, contexts[0]], [candidate_from_stack("astar+dwa")]))

    def test_empty_inputs_rejected(self) -> None:
        contexts = build_evaluation_contexts(make_profile(), seed_count=1)
        with pytest.raises(ValueError, match="at least one episode context"):
            list(iter_run_plan([], [candidate_from_stack("astar+dwa")]))
        with pytest.raises(ValueError, match="at least one candidate"):
            list(iter_run_plan(contexts, []))


class TestRequireSharedContexts:
    def test_matching_sets_return_sorted_ids(self) -> None:
        contexts = build_evaluation_contexts(make_profile(), seed_count=5)
        shared = require_shared_contexts({"a": contexts, "b": list(reversed(contexts))})
        assert shared == tuple(sorted(context_ids(contexts)))

    def test_order_does_not_matter(self) -> None:
        contexts = build_evaluation_contexts(make_profile(), seed_count=4)
        first = require_shared_contexts({"a": contexts, "b": list(reversed(contexts))})
        second = require_shared_contexts({"b": list(reversed(contexts)), "a": contexts})
        assert first == second

    def test_different_counts_refused(self) -> None:
        contexts = build_evaluation_contexts(make_profile(), seed_count=5)
        with pytest.raises(PairingViolation, match="did not run the same episodes"):
            require_shared_contexts({"a": contexts, "b": contexts[:3]})

    def test_disjoint_sets_refused(self) -> None:
        a = build_evaluation_contexts(make_profile(), seed_count=3)
        b = build_evaluation_contexts(make_profile(), seed_count=3, first_seed=50)
        with pytest.raises(PairingViolation, match="did not run the same episodes"):
            require_shared_contexts({"a": a, "b": b})

    def test_repeated_context_within_one_candidate_refused(self) -> None:
        contexts = build_evaluation_contexts(make_profile(), seed_count=3)
        with pytest.raises(PairingViolation, match="more than once"):
            require_shared_contexts({"a": [*contexts, contexts[0]], "b": contexts})

    def test_candidate_without_episodes_refused(self) -> None:
        contexts = build_evaluation_contexts(make_profile(), seed_count=2)
        with pytest.raises(PairingViolation, match="no episodes"):
            require_shared_contexts({"a": contexts, "b": []})

    def test_no_candidates_refused(self) -> None:
        with pytest.raises(PairingViolation, match="no candidates"):
            require_shared_contexts({})

    def test_single_candidate_is_trivially_paired(self) -> None:
        contexts = build_evaluation_contexts(make_profile(), seed_count=2)
        assert len(require_shared_contexts({"a": contexts})) == 2


class TestRequireSampleSet:
    def test_evaluation_only_passes(self) -> None:
        require_sample_set(build_evaluation_contexts(make_profile(), seed_count=3), "evaluation")

    def test_pooled_sets_refused(self) -> None:
        contexts = list(build_evaluation_contexts(make_profile(), seed_count=3))
        contexts.append(context(sample_set="neighborhood", environment_variant="jitter_01"))
        with pytest.raises(SampleSetViolation, match="rule-of-three"):
            require_sample_set(contexts, "evaluation")

    def test_neighborhood_can_be_required_too(self) -> None:
        neighborhood = [context(sample_set="neighborhood", environment_variant="v1")]
        require_sample_set(neighborhood, "neighborhood")
        with pytest.raises(SampleSetViolation):
            require_sample_set(neighborhood, "evaluation")
