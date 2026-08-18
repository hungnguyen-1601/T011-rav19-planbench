"""H1a: the plugin SDK parses manifests without trusting or running them.

Each class pins one DoD line of the Algorithm Host plan's H1a: parse
without import, requirement strengths, the alias bridge and its
candidate-identity guarantee (§5.2 rule 1), unknown capabilities failing
loud with suggestions (§5.2 rule 2 + its round-4 exception), duplicate
(id, version) refusal, and lane consistency at parse (§5.1).
"""

from __future__ import annotations

import sys
from typing import Any

import pytest
from planbench_plugin_sdk import (
    V1_TOKEN_TO_URI,
    ChannelEnvelope,
    DuplicatePluginError,
    IncompatibleProtocolError,
    ManifestError,
    ManifestIndex,
    RequirementSet,
    UnknownCapabilityError,
    canonical_requirement,
    canonical_requirements,
    load_manifest,
    manifest_checksum,
    parse_manifest,
)

from planbench_decision.candidate import Candidate, StackComponent
from planbench_schemas.observations import KNOWN_OBSERVATIONS


def base_manifest(**overrides: Any) -> dict[str, Any]:
    """A valid local-plugin manifest; tests break one thing at a time."""
    data: dict[str, Any] = {
        "plugin_api": "1.0.0",
        "id": "org.lab.social-nav",
        "version": "0.1.0",
        "role": "local",
        "runtime": {
            "supported_lanes": ["python_in_process"],
            "production_lane": "python_in_process",
            "profiles": {
                "python_in_process": {
                    "protocol": "planbench-inproc/v1",
                    "codec": "python-object/v1",
                    "deadline_policy": "control-period",
                }
            },
        },
        "requirements": {"all_of": ["lidar_2d"], "any_of": [], "optional": []},
        "supports": {
            "action_types": ["continuous-velocity@1"],
            "robot_dynamics": ["differential-drive@1"],
            "execution_models": ["synchronous-step@1"],
        },
        "config_schema": {},
        "requires_global_path": True,
    }
    data.update(overrides)
    return data


class TestParsingNeverExecutesThePlugin:
    """§5.1: discovery reads text. A bundle whose Python raises on import
    must parse exactly as well as a healthy one."""

    def test_a_booby_trapped_bundle_parses(self, tmp_path) -> None:
        bundle = tmp_path / "social_nav_plugin"
        (bundle / ".planbench-plugin").mkdir(parents=True)
        (bundle / "__init__.py").write_text(
            'raise RuntimeError("discovery imported plugin code")', encoding="utf-8"
        )
        (bundle / "planner.py").write_text(
            'raise RuntimeError("discovery imported plugin code")', encoding="utf-8"
        )
        manifest_path = bundle / ".planbench-plugin" / "plugin.json"
        manifest_path.write_text(__import__("json").dumps(base_manifest()), encoding="utf-8")

        manifest, checksum = load_manifest(manifest_path)

        assert manifest.id == "org.lab.social-nav"
        assert checksum.startswith("sha256:")
        assert "social_nav_plugin" not in sys.modules

    def test_a_file_that_is_not_json_is_a_manifest_error(self, tmp_path) -> None:
        path = tmp_path / "plugin.json"
        path.write_text("not json", encoding="utf-8")
        with pytest.raises(ManifestError, match="cannot read manifest"):
            load_manifest(path)

    def test_an_unknown_field_is_refused(self) -> None:
        with pytest.raises(ManifestError, match="not a plugin manifest"):
            parse_manifest(base_manifest(runtimes="typo"))


class TestProtocolCompatibility:
    def test_a_newer_minor_of_the_same_major_parses(self) -> None:
        manifest = parse_manifest(base_manifest(plugin_api="1.9.3"))
        assert manifest.plugin_api == "1.9.3"

    def test_a_different_major_is_refused_outright(self) -> None:
        with pytest.raises(IncompatibleProtocolError, match="not this SDK's major"):
            parse_manifest(base_manifest(plugin_api="2.0.0"))


class TestRuntimeLanesAreConsistentAtParse:
    """§5.1: the declared production lane is candidate identity, so a
    manifest whose lane cannot exist is malformed, not merely sick."""

    def test_production_lane_must_be_supported(self) -> None:
        runtime = base_manifest()["runtime"]
        runtime["production_lane"] = "subprocess"
        with pytest.raises(ManifestError, match="production_lane"):
            parse_manifest(base_manifest(runtime=runtime))

    def test_a_profile_for_an_unsupported_lane_is_refused(self) -> None:
        runtime = base_manifest()["runtime"]
        runtime["profiles"]["subprocess"] = {
            "protocol": "planbench-subprocess/v1",
            "codec": "protobuf-v1",
            "deadline_policy": "control-period",
        }
        with pytest.raises(ManifestError, match="not in supported_lanes"):
            parse_manifest(base_manifest(runtime=runtime))


class TestRequirementStrengths:
    def test_all_of_blocks_and_optional_never_does(self) -> None:
        requirements = RequirementSet(
            all_of=("lidar_2d",),
            optional=("planbench://channel/robot-state@1",),
        )
        assert requirements.satisfied_by({"lidar_2d"})
        assert requirements.missing_from(set()) == ("lidar_2d",)

    def test_any_of_needs_exactly_one(self) -> None:
        requirements = RequirementSet(any_of=("lidar_2d", "planbench://channel/robot-state@1"))
        assert requirements.satisfied_by({"lidar_2d"})
        assert requirements.satisfied_by({"planbench://channel/robot-state@1"})
        missing = requirements.missing_from(set())
        assert missing == ("any of: lidar_2d | planbench://channel/robot-state@1",)

    def test_two_spellings_collapse_to_one_entry(self) -> None:
        requirements = RequirementSet(all_of=("lidar_2d", "planbench://channel/lidar-2d@1"))
        assert requirements.all_of == ("lidar_2d",)


class TestTheAliasBridge:
    def test_a_token_is_already_canonical(self) -> None:
        assert canonical_requirement("lidar_2d") == "lidar_2d"

    def test_an_aliasing_uri_canonicalises_to_its_token(self) -> None:
        assert canonical_requirement("planbench://channel/lidar-2d@1") == "lidar_2d"
        assert (
            canonical_requirement("planbench://channel/human-state-estimates@1")
            == "human_state_estimates"
        )

    def test_a_foreign_uri_stays_a_uri(self) -> None:
        assert (
            canonical_requirement("org.lab://channel/radar-cube@1")
            == "org.lab://channel/radar-cube@1"
        )

    def test_the_bridge_covers_the_g6_vocabulary_exactly(self) -> None:
        """Drift guard both ways: a token added to G6 without an alias, or
        an alias without a token, breaks the claim that the URI surface is
        a superset of the v1 vocabulary."""
        assert set(V1_TOKEN_TO_URI) == set(KNOWN_OBSERVATIONS)


class TestCanonicalisationPreservesCandidateIdentity:
    """§5.2 rule 1, the DoD test: two declaration styles, one candidate_id."""

    @staticmethod
    def _candidate(requirements: tuple[str, ...]) -> Candidate:
        return Candidate(
            type="modular",
            global_planner=StackComponent(name="astar"),
            local_controller=StackComponent(name="dwa"),
            observation_requirements=requirements,
            resource_profile={
                "kind": "structural",
                "target_implementation": "cpp_ros2",
                "bytes_per_search_node": 64,
                "bytes_per_tree_node": 64,
                "bytes_per_costmap_cell": 1,
                "costmap_layers": 1,
                "fixed_overhead_mb": 10.0,
            },
        )

    def test_uri_and_token_declarations_hash_identically(self) -> None:
        by_token = self._candidate(("lidar_2d",))
        by_uri = self._candidate(canonical_requirements(["planbench://channel/lidar-2d@1"]))
        assert by_token.candidate_id == by_uri.candidate_id

    def test_the_bridge_is_the_only_door(self) -> None:
        """A raw URI handed straight to ``Candidate`` must still be
        refused: stored v1 identity is untouched precisely because the
        canonicalisation happens in the SDK, not inside the hash."""
        with pytest.raises(Exception, match="unknown observation"):
            self._candidate(("planbench://channel/lidar-2d@1",))


class TestUnknownCapabilitiesFailLoud:
    """§5.2 rule 2: a typo dies at parse with a pointer, never later as
    registered_but_missing_provider."""

    def test_a_typo_token_suggests_the_real_one(self) -> None:
        with pytest.raises(ManifestError, match="lidar_2d"):
            parse_manifest(
                base_manifest(requirements={"all_of": ["lidar2d"]}),
                source="typo.json",
            )

    def test_an_unregistered_uri_without_declaration_is_refused(self) -> None:
        with pytest.raises(UnknownCapabilityError, match="capability_schemas"):
            parse_manifest(
                base_manifest(requirements={"all_of": ["planbench://channel/lidar-2d@2"]})
            )

    def test_the_same_uri_with_a_schema_declaration_registers(self) -> None:
        """The round-4 exception: declaring the schema turns an unknown
        URI into a registration instead of a typo."""
        manifest = parse_manifest(
            base_manifest(
                requirements={"all_of": ["org.lab://channel/social-costmap@1"]},
                capability_schemas=[
                    {
                        "uri": "org.lab://channel/social-costmap@1",
                        "schema": "schemas/social-costmap-v1.json",
                        "schema_digest": "sha256:" + "ab" * 32,
                        "codecs": ["json-v1"],
                    }
                ],
            )
        )
        assert "org.lab://channel/social-costmap@1" in manifest.requirements.all_of

    def test_a_builtin_schema_cannot_be_redeclared(self) -> None:
        with pytest.raises(ManifestError, match="built-in capability"):
            parse_manifest(
                base_manifest(
                    capability_schemas=[
                        {
                            "uri": "planbench://channel/lidar-2d@1",
                            "schema": "schemas/lidar.json",
                            "schema_digest": "sha256:" + "cd" * 32,
                            "codecs": ["json-v1"],
                        }
                    ]
                )
            )


class TestDuplicatesFailLoud:
    def test_rescanning_the_same_manifest_is_idempotent(self) -> None:
        index = ManifestIndex()
        data = base_manifest()
        manifest = parse_manifest(data)
        checksum = manifest_checksum(data)
        assert index.add(manifest, checksum) is index.add(manifest, checksum)
        assert len(index) == 1

    def test_two_bodies_for_one_id_and_version_are_refused(self) -> None:
        index = ManifestIndex()
        first = base_manifest()
        second = base_manifest(config_schema={"properties": {"gain": {}}})
        index.add(parse_manifest(first), manifest_checksum(first))
        with pytest.raises(DuplicatePluginError, match="two different manifests"):
            index.add(parse_manifest(second), manifest_checksum(second))

    def test_a_new_version_is_a_new_entry(self) -> None:
        index = ManifestIndex()
        first = base_manifest()
        second = base_manifest(version="0.2.0")
        index.add(parse_manifest(first), manifest_checksum(first))
        index.add(parse_manifest(second), manifest_checksum(second))
        assert len(index) == 2


class TestChannelEnvelopes:
    def test_on_change_without_a_revision_is_refused(self) -> None:
        with pytest.raises(Exception, match="revision"):
            ChannelEnvelope(
                capability="planbench://channel/global-path@1",
                cadence="on_change",
                produced_at=0.0,
                provenance="deployment",
            )

    def test_per_tick_needs_no_revision(self) -> None:
        envelope = ChannelEnvelope(
            capability="lidar_2d",
            cadence="per_tick",
            produced_at=1.25,
            provenance="deployment",
        )
        assert envelope.revision is None

    def test_a_non_canonical_capability_is_refused(self) -> None:
        """One spelling everywhere — an envelope under the URI alias while
        requirements canonicalise to the token would never match a grant."""
        with pytest.raises(Exception, match="canonical"):
            ChannelEnvelope(
                capability="planbench://channel/lidar-2d@1",
                cadence="per_tick",
                produced_at=0.0,
                provenance="deployment",
            )


class TestRoleRules:
    def test_a_monolithic_plugin_cannot_require_a_global_path(self) -> None:
        with pytest.raises(ManifestError, match="monolithic"):
            parse_manifest(base_manifest(role="monolithic", requires_global_path=True))

    def test_an_uppercase_id_is_refused(self) -> None:
        with pytest.raises(ManifestError, match="lowercase"):
            parse_manifest(base_manifest(id="My-Plugin"))
