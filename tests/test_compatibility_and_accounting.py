"""H4: preflight, the fingerprint extension, and the ownership split.

Three DoD lines, and the first is the one with teeth: extending the
execution fingerprint must not move the fingerprint of the path that has
been running all along. That is checked against the value in the
committed H0 fixture — bytes from git, written before the host existed —
rather than against a number computed in this session.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from planbench_plugin_sdk import parse_manifest

from planbench_benchmark.contexts import build_evaluation_contexts
from planbench_benchmark.episode import scenario_for
from planbench_benchmark.fingerprint import (
    HostConditions,
    execution_conditions_fingerprint,
)
from planbench_benchmark.selection import load_profile, load_task_map
from planbench_simulator.host.channel_bundle import CapabilitySpec
from planbench_simulator.host.compatibility import (
    HostSupport,
    ProviderOwnership,
    resolve_compatibility,
)
from planbench_simulator.host.fairness_policy import FairnessPolicy
from planbench_simulator.host.provider_graph import ProviderGraph
from planbench_simulator.host.providers import (
    HUMAN_STATE_ESTIMATES,
    LIDAR_2D,
    builtin_providers,
    builtin_registry,
)
from planbench_simulator.host.providers.base import Provider

REPO_ROOT = Path(__file__).resolve().parents[1]
PROFILE = REPO_ROOT / "profiles" / "warehouse_crossing_v1.yaml"
HOST_PARITY_FIXTURE = Path(__file__).parent / "golden" / "host_parity.json"


@pytest.fixture(scope="module")
def deployment():
    profile = load_profile(PROFILE)
    map_data = load_task_map(profile, base_dir=REPO_ROOT)
    context = build_evaluation_contexts(profile, seed_count=1)[0]
    return profile, map_data, scenario_for(profile, context)


def _manifest(**overrides):
    data = {
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
        "requirements": {"all_of": [LIDAR_2D]},
        "supports": {
            "action_types": ["continuous-velocity@1"],
            "robot_dynamics": ["differential-drive@1"],
            "execution_models": ["synchronous-step@1"],
        },
        "requires_global_path": True,
    }
    data.update(overrides)
    return parse_manifest(data)


def _unbuilt_lane() -> dict:
    """A runtime lane the plan names as post-MVP and nobody has built."""
    return {
        "supported_lanes": ["ros2_node"],
        "production_lane": "ros2_node",
        "profiles": {
            "ros2_node": {
                "protocol": "planbench-ros2/v1",
                "codec": "ros-msg-v1",
                "deadline_policy": "control-period",
            }
        },
    }


class _CandidateProvider(Provider):
    """A provider the candidate ships — part of what is being measured."""

    capability = "org.lab://channel/social-costmap@1"
    cadence = "per_tick"
    provenance = "candidate"

    def advance(self, tick, now, view, inputs) -> None:
        del tick, now, view, inputs

    def read(self) -> str:
        return "COSTMAP"


class TestTheLegacyFingerprintHasNotMoved:
    """§7.1's hard requirement, checked against committed bytes."""

    def test_the_committed_value_is_still_produced(self, deployment) -> None:
        profile, map_data, scenario = deployment
        fixture = json.loads(HOST_PARITY_FIXTURE.read_text(encoding="utf-8"))
        expected = fixture["astar_dwa_seed0"]["execution_conditions_fingerprint"]
        assert execution_conditions_fingerprint(map_data, scenario, profile) == expected

    def test_absent_host_conditions_change_nothing(self, deployment) -> None:
        profile, map_data, scenario = deployment
        without = execution_conditions_fingerprint(map_data, scenario, profile)
        assert execution_conditions_fingerprint(map_data, scenario, profile, None) == without

    def test_empty_host_conditions_change_nothing(self, deployment) -> None:
        """A host that adds no condition must hash like no host at all —
        otherwise wrapping the legacy path in bookkeeping would orphan
        every trace on disk for a change that altered no metre driven."""
        profile, map_data, scenario = deployment
        without = execution_conditions_fingerprint(map_data, scenario, profile)
        with_empty = execution_conditions_fingerprint(map_data, scenario, profile, HostConditions())
        assert with_empty == without


class TestTheHostConditionsCannotGrowUnhashed:
    """The guard for the door ``CONDITION_ARGUMENTS`` does not watch.

    ``run_stack``'s condition arguments have a guard; host conditions
    arrive by another path entirely, so they need their own. The defence
    is the same one the module was built on — derive the payload from the
    object, never from a hand-maintained list — and this pins it, because
    a later hand-built dict would silently stop hashing a new field.
    """

    def test_every_declared_field_reaches_the_payload(self, deployment) -> None:
        profile, map_data, scenario = deployment
        baseline = execution_conditions_fingerprint(map_data, scenario, profile)
        populated = {
            "providers": (("cap", "Prov"),),
            "adapter_chain": ("adapter@1",),
            "runtime_profile": {"lane": "subprocess"},
        }
        assert set(populated) == set(HostConditions.model_fields), (
            "HostConditions grew a field; decide whether it is an execution condition, "
            "then add it here so this guard keeps proving every field is hashed"
        )
        for name, value in populated.items():
            conditions = HostConditions(**{name: value})
            assert (
                execution_conditions_fingerprint(map_data, scenario, profile, conditions)
                != baseline
            ), f"{name} does not reach the fingerprint payload"


class TestNewConditionsDoChangeIt:
    def test_a_deployment_owned_provider_changes_it(self, deployment) -> None:
        profile, map_data, scenario = deployment
        baseline = execution_conditions_fingerprint(map_data, scenario, profile)
        with_tracker = execution_conditions_fingerprint(
            map_data,
            scenario,
            profile,
            HostConditions(providers=((HUMAN_STATE_ESTIMATES, "DeploymentTracker"),)),
        )
        assert with_tracker != baseline

    def test_the_runtime_profile_changes_it_not_only_the_lane_name(self, deployment) -> None:
        """A lane whose codec changed is a different execution condition
        under the same word (§5.9 rule 4)."""
        profile, map_data, scenario = deployment
        first = execution_conditions_fingerprint(
            map_data,
            scenario,
            profile,
            HostConditions(runtime_profile={"lane": "subprocess", "codec": "protobuf-v1"}),
        )
        second = execution_conditions_fingerprint(
            map_data,
            scenario,
            profile,
            HostConditions(runtime_profile={"lane": "subprocess", "codec": "json-v1"}),
        )
        assert first != second

    def test_an_adapter_chain_changes_it(self, deployment) -> None:
        profile, map_data, scenario = deployment
        baseline = execution_conditions_fingerprint(map_data, scenario, profile)
        adapted = execution_conditions_fingerprint(
            map_data,
            scenario,
            profile,
            HostConditions(adapter_chain=("trajectory-to-velocity@1",)),
        )
        assert adapted != baseline

    def test_provider_declaration_order_does_not(self, deployment) -> None:
        """Two spellings of one set must hash equal — the same rule the
        observation tokens follow."""
        profile, map_data, scenario = deployment
        pair = (("a", "A"), ("b", "B"))
        assert execution_conditions_fingerprint(
            map_data, scenario, profile, HostConditions(providers=pair)
        ) == execution_conditions_fingerprint(
            map_data, scenario, profile, HostConditions(providers=pair[::-1])
        )


class TestOwnershipDecidesWhatChanges:
    """§7.1's three-way split, as accounting rather than prose."""

    def _graph(self) -> ProviderGraph:
        registry = builtin_registry()
        registry.register(
            CapabilitySpec(capability=_CandidateProvider.capability, cadence="per_tick")
        )
        return ProviderGraph(
            (*builtin_providers(include_oracle=True), _CandidateProvider()), registry
        )

    def test_each_provider_lands_in_its_own_bucket(self) -> None:
        ownership = ProviderOwnership.from_graph(self._graph())
        assert [cap for cap, _ in ownership.candidate_owned] == [_CandidateProvider.capability]
        assert [cap for cap, _ in ownership.oracle_owned] == [HUMAN_STATE_ESTIMATES]
        assert LIDAR_2D in [cap for cap, _ in ownership.deployment_owned]

    def test_a_candidate_owned_provider_stays_out_of_the_fingerprint(self) -> None:
        """It is already in ``candidate_id``; hashing it here as well
        would split one candidate's episodes across two fingerprints for
        a change its identity already records."""
        hashable = dict(ProviderOwnership.from_graph(self._graph()).hashable())
        assert _CandidateProvider.capability not in hashable
        assert HUMAN_STATE_ESTIMATES in hashable
        assert LIDAR_2D in hashable


class TestPreflightAnswersBeforeTheEpisode:
    def _graph(self, **kwargs) -> ProviderGraph:
        return ProviderGraph(builtin_providers(**kwargs), builtin_registry())

    def test_a_satisfied_plugin_is_runnable(self) -> None:
        report = resolve_compatibility(
            _manifest(), available_capabilities=frozenset(), graph=self._graph()
        )
        assert report.runnable
        assert report.state == "registered_and_runnable"
        assert report.explain() == "runnable"
        assert LIDAR_2D in report.provider_order

    def test_a_missing_capability_is_named(self) -> None:
        report = resolve_compatibility(
            _manifest(requirements={"all_of": [HUMAN_STATE_ESTIMATES]}),
            available_capabilities=frozenset(),
            graph=self._graph(),
        )
        assert report.state == "registered_but_missing_provider"
        assert report.missing_capabilities == (HUMAN_STATE_ESTIMATES,)
        assert "capabilities not offered" in report.explain()

    def test_an_unavailable_runtime_lane_is_its_own_state(self) -> None:
        """``ros2_node`` rather than ``subprocess``: this test used the
        subprocess lane until H7 built it, and a test asserting a lane is
        unavailable has to name one that actually is — otherwise it
        passes for a while and then reports the platform's own progress
        as a failure."""
        report = resolve_compatibility(
            _manifest(runtime=_unbuilt_lane()),
            available_capabilities=frozenset(),
            graph=self._graph(),
        )
        assert report.state == "registered_but_missing_runtime"
        assert report.missing_runtime == ("ros2_node",)

    def test_unbuilt_dynamics_register_as_incompatible(self) -> None:
        """The plan's own example: an Ackermann plugin registers and is
        marked incompatible; the physics is not opened to avoid a correct
        refusal."""
        report = resolve_compatibility(
            _manifest(
                supports={
                    "action_types": ["continuous-velocity@1"],
                    "robot_dynamics": ["ackermann@1"],
                    "execution_models": ["synchronous-step@1"],
                }
            ),
            available_capabilities=frozenset(),
            graph=self._graph(),
        )
        assert report.state == "registered_but_incompatible"
        assert report.incompatible_dynamics == ("ackermann@1",)

    def test_incompatibility_outranks_a_missing_provider(self) -> None:
        """Installing the provider would not make an Ackermann plugin
        runnable here, and sending someone to install it wastes an
        afternoon."""
        report = resolve_compatibility(
            _manifest(
                requirements={"all_of": [HUMAN_STATE_ESTIMATES]},
                supports={
                    "action_types": ["continuous-velocity@1"],
                    "robot_dynamics": ["ackermann@1"],
                    "execution_models": ["synchronous-step@1"],
                },
            ),
            available_capabilities=frozenset(),
            graph=self._graph(),
        )
        assert report.state == "registered_but_incompatible"
        assert report.missing_capabilities  # still reported, just not the headline

    def test_several_alternatives_count_as_compatible(self) -> None:
        """Listing several action types says "any of these will do", so
        refusing over the unsupported ones would be a refusal built from
        alternatives the plugin offered."""
        report = resolve_compatibility(
            _manifest(
                supports={
                    "action_types": ["trajectory@1", "continuous-velocity@1"],
                    "robot_dynamics": ["differential-drive@1"],
                    "execution_models": ["synchronous-step@1"],
                }
            ),
            available_capabilities=frozenset(),
            graph=self._graph(),
        )
        assert report.incompatible_action_types == ()
        assert report.runnable

    def test_every_blocker_is_reported_in_one_pass(self) -> None:
        """Fixing one, re-running, and discovering the next is the cost
        this report exists to avoid."""
        report = resolve_compatibility(
            _manifest(
                requirements={"all_of": [HUMAN_STATE_ESTIMATES]},
                runtime=_unbuilt_lane(),
            ),
            available_capabilities=frozenset(),
            graph=self._graph(),
        )
        explanation = report.explain()
        assert "capabilities not offered" in explanation
        assert "runtime lane unavailable" in explanation

    def test_an_unrunnable_graph_blocks_and_is_explained(self) -> None:
        graph = ProviderGraph((builtin_providers()[0], builtin_providers()[0]), builtin_registry())
        report = resolve_compatibility(
            _manifest(), available_capabilities=frozenset({LIDAR_2D}), graph=graph
        )
        assert not report.runnable
        assert "ambiguous" in report.explain()


class TestFairnessReachesPreflight:
    def test_a_production_policy_refuses_an_oracle_graph(self) -> None:
        graph = ProviderGraph(builtin_providers(include_oracle=True), builtin_registry())
        report = resolve_compatibility(
            _manifest(),
            available_capabilities=frozenset(),
            graph=graph,
            policy=FairnessPolicy.production(),
        )
        assert not report.runnable
        assert report.fairness_refusals == ("oracle",)

    def test_a_research_policy_admits_it_and_records_the_evidence_class(self) -> None:
        graph = ProviderGraph(builtin_providers(include_oracle=True), builtin_registry())
        report = resolve_compatibility(
            _manifest(),
            available_capabilities=frozenset(),
            graph=graph,
            policy=FairnessPolicy.research(),
        )
        assert report.runnable
        assert report.evidence_class == "oracle"


class TestTheReportFeedsTheOneFingerprint:
    def test_host_conditions_carry_the_resolved_profile_and_providers(self) -> None:
        graph = ProviderGraph(builtin_providers(), builtin_registry())
        report = resolve_compatibility(_manifest(), available_capabilities=frozenset(), graph=graph)
        conditions = report.host_conditions()
        assert conditions.runtime_profile["codec"] == "python-object/v1"
        assert (LIDAR_2D, "Lidar2DProvider") in conditions.providers

    def test_a_host_supporting_nothing_refuses_everything_it_should(self) -> None:
        report = resolve_compatibility(
            _manifest(),
            available_capabilities=frozenset(),
            support=HostSupport(
                action_types=frozenset(),
                robot_dynamics=frozenset(),
                execution_models=frozenset(),
                runtime_lanes=frozenset(),
            ),
        )
        assert report.state == "registered_but_incompatible"
        assert report.incompatible_action_types
        assert report.incompatible_dynamics
        assert report.incompatible_execution_models
