"""Mission parsing and the validation wall in front of it."""

from __future__ import annotations

import pytest

from planbench_agent.specs import (
    DEFAULT_SEEDS,
    MAX_SEEDS,
    MissionDraft,
    agent_selectable_algorithms,
    benchmarkable_algorithms,
    mission_schema,
    parse_mission_text,
    parse_structured,
    validate_draft,
)
from planbench_benchmark import ALGORITHMS, CURRICULUM_ORDER


def draft(**overrides) -> MissionDraft:
    payload = {
        "name": "n",
        "scenario": "doorway",
        "algorithms": ("astar+dwa",),
        "seeds": (1, 2),
    }
    payload.update(overrides)
    return MissionDraft(**payload)


class TestSchema:
    def test_enumerates_only_real_scenarios(self):
        assert mission_schema()["properties"]["scenario"]["enum"] == list(CURRICULUM_ORDER)

    def test_excludes_the_non_benchmarkable_reference_adapter(self):
        allowed = mission_schema()["properties"]["algorithms"]["items"]["enum"]
        assert "astar+pure_pursuit" not in allowed
        assert set(allowed) == agent_selectable_algorithms()

    def test_excludes_stacks_that_need_a_checkpoint_the_agent_cannot_know(self):
        # astar+ppo is benchmarkable, but only a human can say which
        # trained model to load. Offering it would invite a made-up path.
        allowed = set(mission_schema()["properties"]["algorithms"]["items"]["enum"])
        assert "astar+ppo" in benchmarkable_algorithms()
        assert "astar+ppo" not in allowed

    def test_forbids_extra_properties(self):
        assert mission_schema()["additionalProperties"] is False


class TestParseStructured:
    def test_accepts_a_well_formed_object(self):
        parsed, errors = parse_structured(
            {
                "name": "doorway comparison",
                "description": "",
                "scenario": "doorway",
                "algorithms": ["astar+dwa"],
                "seeds": [1, 2, 3],
            }
        )
        assert errors == ()
        assert parsed is not None
        assert parsed.episode_count == 3

    def test_rejects_unknown_fields_rather_than_ignoring_them(self):
        # An extra field means the model answered a different question
        # than the one asked; silently dropping it hides that.
        parsed, errors = parse_structured(
            {
                "name": "n",
                "scenario": "doorway",
                "algorithms": ["astar+dwa"],
                "seeds": [1],
                "run_immediately": True,
            }
        )
        assert parsed is None
        assert any("run_immediately" in error for error in errors)

    def test_rejects_a_missing_field(self):
        parsed, errors = parse_structured({"name": "n", "scenario": "doorway"})
        assert parsed is None
        assert len(errors) == 2

    def test_rejects_a_non_object_payload(self):
        parsed, errors = parse_structured("doorway with dwa")
        assert parsed is None
        assert "expected a JSON object" in errors[0]


class TestValidateDraft:
    def test_a_registry_backed_draft_passes(self):
        assert validate_draft(draft()) == ()

    def test_unknown_scenario_is_rejected(self):
        errors = validate_draft(draft(scenario="warehouse_of_doom"))
        assert any("unknown scenario" in error for error in errors)

    def test_unknown_algorithm_is_rejected(self):
        errors = validate_draft(draft(algorithms=("astar+teleport",)))
        assert any("unknown algorithm" in error for error in errors)

    def test_stack_needing_a_checkpoint_is_refused_with_the_missing_field(self):
        errors = validate_draft(draft(algorithms=("astar+dwa", "astar+ppo")))
        assert any("model_id" in error for error in errors)
        assert any("a human has to create this benchmark" in error for error in errors)

    def test_reference_adapter_may_not_be_benchmarked(self):
        assert ALGORITHMS["astar+pure_pursuit"].info.benchmarkable is False
        errors = validate_draft(draft(algorithms=("astar+dwa", "astar+pure_pursuit")))
        assert any("reference adapter" in error for error in errors)

    def test_duplicate_seeds_are_rejected(self):
        assert any("unique" in error for error in validate_draft(draft(seeds=(1, 1, 2))))

    def test_seed_count_is_bounded(self):
        errors = validate_draft(draft(seeds=tuple(range(MAX_SEEDS + 1))))
        assert any("at most" in error for error in errors)

    def test_negative_seeds_are_rejected(self):
        assert any("non-negative" in error for error in validate_draft(draft(seeds=(-1, 2))))


class TestDeterministicTextParser:
    def test_extracts_scenario_algorithms_and_seeds(self):
        parsed = parse_mission_text("Compare DWA and PPO on the doorway scenario, seeds 4 5 6")
        assert parsed is not None
        assert parsed.scenario == "doorway"
        assert parsed.algorithms == ("astar+dwa", "astar+ppo")
        assert parsed.seeds == (4, 5, 6)

    def test_seed_count_phrasing_expands_to_a_range(self):
        parsed = parse_mission_text("run narrow_corridor with dwa over 5 seeds")
        assert parsed is not None and parsed.seeds == (1, 2, 3, 4, 5)

    def test_falls_back_to_the_default_seed_list(self):
        parsed = parse_mission_text("benchmark dwa on open_space")
        assert parsed is not None and parsed.seeds == DEFAULT_SEEDS

    def test_defaults_to_every_agent_selectable_stack(self):
        parsed = parse_mission_text("evaluate open_space")
        assert parsed is not None
        assert set(parsed.algorithms) == agent_selectable_algorithms()

    def test_returns_none_rather_than_guessing_a_scenario(self):
        assert parse_mission_text("please make the robot go fast") is None

    def test_is_deterministic(self):
        text = "compare ppo and dwa on dynamic_warehouse with seeds 7, 8"
        assert parse_mission_text(text) == parse_mission_text(text)

    @pytest.mark.parametrize("name", sorted(CURRICULUM_ORDER))
    def test_every_library_scenario_is_recognisable(self, name):
        parsed = parse_mission_text(f"run {name} with dwa")
        assert parsed is not None and parsed.scenario == name
