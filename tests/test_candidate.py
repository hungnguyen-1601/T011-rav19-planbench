"""Candidate identity and experiment scope (CONTRACTS HĐ-1)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from planbench_decision.candidate import (
    CANDIDATE_ID_LENGTH,
    Candidate,
    CandidateSchemaError,
    ExperimentScopeViolation,
    load_candidate,
    validate_experiment_scope,
)

MODULAR: dict[str, object] = {
    "id": None,
    "type": "modular",
    "global_planner": {"name": "astar", "version": "v1"},
    "local_controller": {"name": "dwa", "version": "v1"},
    "params": {
        "astar": {"heuristic": "euclidean", "tie_break": 1.001},
        "dwa": {"sim_time": 1.5, "vx_samples": 20},
    },
    "observation_requirements": ["lidar_2d"],
}

MONOLITHIC: dict[str, object] = {
    "id": None,
    "type": "monolithic",
    "policy": {"name": "ppo_navigation", "checkpoint": "ckpt_12", "version": "v1"},
    "params": {"deterministic": True},
    "observation_requirements": ["lidar_2d"],
}


def modular(**overrides: object) -> Candidate:
    return Candidate.model_validate({**MODULAR, **overrides})


class TestShape:
    def test_contract_examples_parse(self) -> None:
        assert modular().type == "modular"
        assert Candidate.model_validate(MONOLITHIC).policy is not None

    def test_monolithic_with_layers_rejected(self) -> None:
        payload = {**MONOLITHIC, "global_planner": {"name": "astar"}}
        with pytest.raises(ValidationError, match="must not declare"):
            Candidate.model_validate(payload)

    def test_monolithic_without_policy_rejected(self) -> None:
        payload = {k: v for k, v in MONOLITHIC.items() if k != "policy"}
        with pytest.raises(ValidationError, match="requires a policy"):
            Candidate.model_validate(payload)

    def test_modular_missing_layer_rejected(self) -> None:
        payload = {k: v for k, v in MODULAR.items() if k != "local_controller"}
        payload["params"] = {}
        with pytest.raises(ValidationError, match="local_controller"):
            Candidate.model_validate(payload)

    def test_modular_with_policy_rejected(self) -> None:
        with pytest.raises(ValidationError, match="must not declare a policy"):
            modular(policy={"name": "ppo", "checkpoint": "c1"})

    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            modular(global_plannr={"name": "astar"})

    def test_params_block_for_no_layer_rejected(self) -> None:
        """A block nothing reads still changes the id — see docstring."""
        with pytest.raises(ValidationError, match="match no layer"):
            modular(params={"astar": {}, "mppi": {"horizon": 3}})

    def test_frozen(self) -> None:
        candidate = modular()
        with pytest.raises(ValidationError):
            candidate.type = "monolithic"  # type: ignore[misc]

    def test_only_two_types(self) -> None:
        with pytest.raises(ValidationError):
            modular(type="hybrid")


class TestObservationRequirements:
    def test_canonicalised(self) -> None:
        candidate = modular(
            observation_requirements=["human_state_estimates", "lidar_2d", "lidar_2d"]
        )
        assert candidate.observation_requirements == ("human_state_estimates", "lidar_2d")

    def test_unknown_token_rejected(self) -> None:
        with pytest.raises(ValidationError, match="unknown observation"):
            modular(observation_requirements=["lidar2d"])

    def test_order_does_not_change_identity(self) -> None:
        a = modular(observation_requirements=["lidar_2d", "human_state_estimates"])
        b = modular(observation_requirements=["human_state_estimates", "lidar_2d"])
        assert a.candidate_id == b.candidate_id


class TestIdentity:
    def test_id_is_stable_and_short(self) -> None:
        assert modular().candidate_id == modular().candidate_id
        assert len(modular().candidate_id) == CANDIDATE_ID_LENGTH

    def test_key_order_does_not_change_identity(self) -> None:
        reordered = {
            "type": "modular",
            "observation_requirements": ["lidar_2d"],
            "local_controller": {"version": "v1", "name": "dwa"},
            "global_planner": {"version": "v1", "name": "astar"},
            "params": {
                "dwa": {"vx_samples": 20, "sim_time": 1.5},
                "astar": {"tie_break": 1.001, "heuristic": "euclidean"},
            },
        }
        assert Candidate.model_validate(reordered).candidate_id == modular().candidate_id

    def test_any_param_change_is_a_new_candidate(self) -> None:
        config_b = {
            "astar": {"heuristic": "euclidean", "tie_break": 1.001},
            "dwa": {"sim_time": 1.6, "vx_samples": 20},
        }
        assert modular(params=config_b).candidate_id != modular().candidate_id

    def test_version_is_part_of_identity(self) -> None:
        bumped = modular(local_controller={"name": "dwa", "version": "v2"})
        assert bumped.candidate_id != modular().candidate_id

    def test_requirements_are_part_of_identity(self) -> None:
        extra = modular(observation_requirements=["lidar_2d", "human_state_estimates"])
        assert extra.candidate_id != modular().candidate_id

    def test_type_is_part_of_identity(self) -> None:
        # Same params and requirements, different shape.
        mono = Candidate.model_validate(MONOLITHIC)
        assert mono.candidate_id != modular(params={}).candidate_id

    def test_stack_label_is_not_identity(self) -> None:
        config_b = {"dwa": {"sim_time": 9.0}}
        other = modular(params=config_b)
        assert other.stack_label == modular().stack_label
        assert other.candidate_id != modular().candidate_id


class TestRoundTrip:
    def test_dump_reloads_unchanged(self) -> None:
        candidate = modular()
        reloaded = Candidate.model_validate(candidate.model_dump(mode="json"))
        assert reloaded == candidate
        assert reloaded.candidate_id == candidate.candidate_id

    def test_dump_carries_the_computed_id(self) -> None:
        dumped = modular().model_dump(mode="json")
        assert dumped["candidate_id"] == modular().candidate_id

    def test_declared_id_is_not_trusted(self) -> None:
        assert modular(id="deadbeef1234").candidate_id == modular().candidate_id


class TestLoadCandidate:
    def test_null_id_accepted(self) -> None:
        assert load_candidate(MODULAR).candidate_id == modular().candidate_id

    def test_stale_id_rejected(self) -> None:
        with pytest.raises(CandidateSchemaError, match="does not match"):
            load_candidate({**MODULAR, "id": "deadbeef1234"})

    def test_stale_candidate_id_rejected(self) -> None:
        with pytest.raises(CandidateSchemaError, match="does not match"):
            load_candidate({**MODULAR, "candidate_id": "deadbeef1234"})

    def test_matching_id_accepted(self) -> None:
        expected = modular().candidate_id
        assert load_candidate({**MODULAR, "id": expected}).candidate_id == expected


def stack(global_name: str, local_name: str, **local_params: object) -> Candidate:
    return Candidate(
        type="modular",
        global_planner={"name": global_name},  # type: ignore[arg-type]
        local_controller={"name": local_name},  # type: ignore[arg-type]
        params={local_name: dict(local_params)} if local_params else {},
        observation_requirements=("lidar_2d",),
    )


class TestExperimentScope:
    def test_global_selection_allows_differing_global_planners(self) -> None:
        validate_experiment_scope(
            "global_planner_selection",
            [stack("astar", "dwa", sim_time=1.5), stack("rrtstar", "dwa", sim_time=1.5)],
        )

    def test_global_selection_rejects_differing_controller_params(self) -> None:
        """The violation HĐ-1.4 names: scope claims one layer varied,
        the candidates varied two."""
        with pytest.raises(ExperimentScopeViolation, match="identical local layer"):
            validate_experiment_scope(
                "global_planner_selection",
                [stack("astar", "dwa", sim_time=1.5), stack("rrtstar", "dwa", sim_time=2.0)],
            )

    def test_global_selection_rejects_differing_controller(self) -> None:
        with pytest.raises(ExperimentScopeViolation, match="identical local layer"):
            validate_experiment_scope(
                "global_planner_selection",
                [stack("astar", "dwa"), stack("astar", "pure_pursuit")],
            )

    def test_global_selection_rejects_differing_controller_version(self) -> None:
        a = stack("astar", "dwa")
        b = Candidate(
            type="modular",
            global_planner={"name": "rrtstar"},  # type: ignore[arg-type]
            local_controller={"name": "dwa", "version": "v2"},  # type: ignore[arg-type]
            observation_requirements=("lidar_2d",),
        )
        with pytest.raises(ExperimentScopeViolation, match="identical local layer"):
            validate_experiment_scope("global_planner_selection", [a, b])

    def test_local_selection_mirrors_the_rule(self) -> None:
        validate_experiment_scope(
            "local_controller_selection",
            [stack("astar", "dwa"), stack("astar", "pure_pursuit")],
        )
        with pytest.raises(ExperimentScopeViolation, match="identical global layer"):
            validate_experiment_scope(
                "local_controller_selection",
                [stack("astar", "dwa"), stack("rrtstar", "pure_pursuit")],
            )

    def test_full_stack_selection_constrains_nothing(self) -> None:
        validate_experiment_scope(
            "full_stack_selection",
            [stack("astar", "dwa", sim_time=1.5), stack("rrtstar", "pure_pursuit")],
        )

    def test_monolithic_cannot_join_a_layer_scoped_run(self) -> None:
        with pytest.raises(ExperimentScopeViolation, match="no layers"):
            validate_experiment_scope(
                "global_planner_selection",
                [stack("astar", "dwa"), Candidate.model_validate(MONOLITHIC)],
            )

    def test_monolithic_allowed_in_full_stack_selection(self) -> None:
        validate_experiment_scope(
            "full_stack_selection",
            [stack("astar", "dwa"), Candidate.model_validate(MONOLITHIC)],
        )

    def test_duplicate_candidate_rejected_in_every_scope(self) -> None:
        pair = [stack("astar", "dwa"), stack("astar", "dwa")]
        for scope in ("full_stack_selection", "global_planner_selection"):
            with pytest.raises(ExperimentScopeViolation, match="appears twice"):
                validate_experiment_scope(scope, pair)  # type: ignore[arg-type]

    def test_empty_set_rejected(self) -> None:
        with pytest.raises(ExperimentScopeViolation, match="at least one"):
            validate_experiment_scope("full_stack_selection", [])

    def test_single_candidate_is_allowed(self) -> None:
        validate_experiment_scope("global_planner_selection", [stack("astar", "dwa")])
