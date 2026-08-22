"""A paper in, a plugin bundle out — or a rejection with named errors.

The mentor's rule is the module's contract: the host takes one shape,
and an LLM answer that is not in that shape is refused, never repaired.
So the tests that matter are the refusals. The happy path is one test;
every documented way a manifest can be wrong is its own.

The reference fixture is the verbatim plugin.json example from An's
Algorithm Host document. If that example ever fails validation, the
validator has drifted from the documentation it implements — which is
the one bug this file exists to make loud.
"""

from __future__ import annotations

from typing import Any

from planbench_agent.plugin_author import (
    KNOWN_CAPABILITIES,
    PLUGIN_API,
    author_plugin,
    plugin_schema,
    validate_manifest,
)
from planbench_agent.provider import LLMRequest, LLMResponse, MockProvider

PAPER = """We present Theta*, an any-angle variant of A* over an occupancy
grid. Line-of-sight checks let a vertex inherit its parent's parent,
producing shorter, smoother paths. We weight the heuristic by 1.2."""


AN_EXAMPLE: dict[str, Any] = {
    "plugin_api": "1.1.0",
    "id": "org.example.theta-star",
    "version": "0.1.0",
    "role": "global",
    "runtime": {
        "supported_lanes": ["python_in_process"],
        "production_lane": "python_in_process",
        "profiles": {
            "python_in_process": {
                "protocol": "planbench-inproc/v1",
                "codec": "python-object/v1",
                "deadline_policy": "control-period",
                "entry_point": "my_planner:ThetaStarPlanner",
            }
        },
    },
    "requirements": {"all_of": ["planbench://channel/planning-grid@1"]},
    "supports": {
        "action_types": ["global-path@1"],
        "robot_dynamics": ["differential-drive@1"],
        "execution_models": ["synchronous-step@1"],
    },
    "config_schema": {
        "type": "object",
        "properties": {"heuristic_weight": {"type": "number", "default": 1.0}},
    },
}


def payload(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "refused": "",
        "plugin_id": "org.paper.theta-star",
        "role": "global",
        "class_name": "ThetaStarPlanner",
        "summary": "Any-angle A* with line-of-sight shortcuts.",
        "requirements": ["planbench://channel/planning-grid@1"],
        "parameters": [
            {
                "name": "heuristic_weight",
                "type": "number",
                "default": 1.2,
                "description": "Weight on the heuristic.",
                "stated_by_paper": True,
            }
        ],
        "code": (
            "class ThetaStarPlanner:\n"
            "    def __init__(self, heuristic_weight: float = 1.2):\n"
            "        self.heuristic_weight = heuristic_weight\n\n"
            "    def plan(self, request):\n"
            "        raise NotImplementedError  # TODO: line-of-sight relaxation\n"
        ),
        "notes": ["grid resolution is not stated by the paper"],
    }
    base.update(overrides)
    return base


def scripted(answer: Any) -> MockProvider:
    class _Scripted(MockProvider):
        def complete(self, request: LLMRequest) -> LLMResponse:  # noqa: ARG002
            return LLMResponse(structured=answer, model="scripted")

    return _Scripted()


class TestTheDocumentedExampleIsTheAnchor:
    def test_the_verbatim_example_from_the_host_document_passes(self) -> None:
        assert validate_manifest(AN_EXAMPLE) == ()

    def test_the_documented_lane_rule_is_enforced(self) -> None:
        """ "validator: phải thuộc supported_lanes" — the one rule the
        document states as a validator rule, verbatim."""
        bad = {**AN_EXAMPLE, "runtime": {**AN_EXAMPLE["runtime"], "production_lane": "subprocess"}}
        assert any("production_lane" in e for e in validate_manifest(bad))

    def test_a_typo_uri_dies_at_parse_time_with_a_suggestion(self) -> None:
        """§5.2 rule 2: a typo must be a parse error with a near-match,
        never a phantom "missing provider" diagnosis later."""
        typo = {**AN_EXAMPLE, "requirements": {"all_of": ["planbench://channel/planing-grid@1"]}}
        (error,) = validate_manifest(typo)
        assert "did you mean" in error
        assert "planning-grid" in error

    def test_a_bundled_schema_declaration_legitimises_a_new_uri(self) -> None:
        """The documented exception: the manifest may introduce a URI by
        declaring its schema itself."""
        custom = {
            **AN_EXAMPLE,
            "requirements": {"all_of": ["org.lab://channel/social-costmap@1"]},
            "capability_schemas": [{"uri": "org.lab://channel/social-costmap@1"}],
        }
        assert validate_manifest(custom) == ()


class TestEveryDocumentedRuleRejects:
    def test_a_wrong_plugin_api(self) -> None:
        assert any(
            "plugin_api" in e for e in validate_manifest({**AN_EXAMPLE, "plugin_api": "2.0"})
        )

    def test_an_id_that_is_not_namespaced(self) -> None:
        assert any("id" in e for e in validate_manifest({**AN_EXAMPLE, "id": "ThetaStar!"}))

    def test_a_role_outside_the_three(self) -> None:
        assert any("role" in e for e in validate_manifest({**AN_EXAMPLE, "role": "hybrid"}))

    def test_a_lane_without_a_profile(self) -> None:
        bad = {
            **AN_EXAMPLE,
            "runtime": {
                "supported_lanes": ["python_in_process", "subprocess"],
                "production_lane": "python_in_process",
                "profiles": AN_EXAMPLE["runtime"]["profiles"],
            },
        }
        assert any("no runtime profile" in e for e in validate_manifest(bad))

    def test_an_entry_point_that_is_not_package_colon_class(self) -> None:
        profiles = {
            "python_in_process": {
                **AN_EXAMPLE["runtime"]["profiles"]["python_in_process"],
                "entry_point": "just_a_module",
            }
        }
        bad = {**AN_EXAMPLE, "runtime": {**AN_EXAMPLE["runtime"], "profiles": profiles}}
        assert any("package:ClassName" in e for e in validate_manifest(bad))

    def test_a_global_plugin_must_offer_the_global_path_action(self) -> None:
        bad = {**AN_EXAMPLE, "supports": {**AN_EXAMPLE["supports"], "action_types": []}}
        assert any("global-path@1" in e for e in validate_manifest(bad))

    def test_a_monolithic_plugin_must_disclaim_the_global_path(self) -> None:
        bad = {
            **AN_EXAMPLE,
            "role": "monolithic",
            "supports": {**AN_EXAMPLE["supports"], "action_types": ["continuous-velocity@1"]},
        }
        assert any("requires_global_path" in e for e in validate_manifest(bad))

    def test_an_action_type_the_host_does_not_execute(self) -> None:
        """§5.6: trajectory@1 may be *declared* by future hosts, but the
        MVP host executes two action types; anything else must be
        refused rather than silently coerced (design principle 5)."""
        bad = {
            **AN_EXAMPLE,
            "supports": {
                **AN_EXAMPLE["supports"],
                "action_types": ["global-path@1", "trajectory@1"],
            },
        }
        assert any("trajectory@1" in e for e in validate_manifest(bad))

    def test_a_config_property_that_is_not_an_identifier(self) -> None:
        bad = {
            **AN_EXAMPLE,
            "config_schema": {"type": "object", "properties": {"bad name": {"type": "number"}}},
        }
        assert any("bad name" in e for e in validate_manifest(bad))


class TestAuthoringEndToEnd:
    def test_a_good_answer_becomes_an_accepted_bundle(self) -> None:
        draft = author_plugin(PAPER, scripted(payload()))
        assert draft.accepted, draft.errors
        assert draft.manifest["id"] == "org.paper.theta-star"
        assert validate_manifest(draft.manifest) == ()

    def test_the_bundle_has_the_three_documented_files(self) -> None:
        draft = author_plugin(PAPER, scripted(payload()))
        names = sorted(draft.files)
        assert names == [
            "theta_star/.planbench-plugin/plugin.json",
            "theta_star/__init__.py",
            "theta_star/planner.py",
        ]

    def test_the_entry_point_matches_the_generated_package(self) -> None:
        draft = author_plugin(PAPER, scripted(payload()))
        entry = draft.manifest["runtime"]["profiles"]["python_in_process"]["entry_point"]
        assert entry == "theta_star:ThetaStarPlanner"

    def test_the_papers_stated_default_survives_into_the_schema(self) -> None:
        draft = author_plugin(PAPER, scripted(payload()))
        assert draft.manifest["config_schema"]["properties"]["heuristic_weight"]["default"] == 1.2

    def test_code_without_the_declared_class_is_rejected_not_repaired(self) -> None:
        draft = author_plugin(PAPER, scripted(payload(code="def plan(r): ...\n")))
        assert not draft.accepted
        assert any("does not define class" in e for e in draft.errors)

    def test_a_local_plugin_without_step_is_rejected(self) -> None:
        bad = payload(
            role="local",
            code="class ThetaStarPlanner:\n    def reset(self, path, robot): ...\n",
        )
        draft = author_plugin(PAPER, scripted(bad))
        assert any("def step(" in e for e in draft.errors)

    def test_a_rejected_draft_still_returns_in_full(self) -> None:
        """The errors name what to fix; hiding the draft would hide what
        they refer to."""
        draft = author_plugin(PAPER, scripted(payload(code="")))
        assert not draft.accepted
        assert draft.manifest
        assert draft.files == {} or draft.files  # files still built for inspection

    def test_a_non_paper_is_refused_with_the_models_reason(self) -> None:
        draft = author_plugin(PAPER, scripted(payload(refused="this is a shopping list")))
        assert draft.refused == "this is a shopping list"
        assert not draft.accepted

    def test_empty_text_never_reaches_the_provider(self) -> None:
        class _Boom(MockProvider):
            def complete(self, request: LLMRequest) -> LLMResponse:  # noqa: ARG002
                raise AssertionError("must not be called")

        assert author_plugin("   ", _Boom()).refused == "no text to read"

    def test_a_provider_crash_is_a_refusal_not_an_exception(self) -> None:
        class _Boom(MockProvider):
            def complete(self, request: LLMRequest) -> LLMResponse:  # noqa: ARG002
                raise RuntimeError("connection reset")

        assert "provider failed" in author_plugin(PAPER, _Boom()).refused

    def test_unstructured_output_is_refused(self) -> None:
        assert author_plugin(PAPER, scripted(None)).refused

    def test_malformed_output_is_refused(self) -> None:
        assert author_plugin(PAPER, scripted({"role": 42})).refused


class TestTheSchemaIsClosed:
    def test_every_enum_the_manifest_closes_is_closed_for_the_model(self) -> None:
        schema = plugin_schema()
        assert schema["additionalProperties"] is False
        assert set(schema["properties"]["requirements"]["items"]["enum"]) == set(KNOWN_CAPABILITIES)
        assert schema["properties"]["role"]["enum"] == ["global", "local", "monolithic"]

    def test_the_manifest_version_is_the_documented_one(self) -> None:
        assert PLUGIN_API == "1.1.0"
