"""H11: a deployment can finally say it owns a capability.

The plugin side has been able to declare custom capabilities since H1a;
the deployment side could only ever say ``lidar_2d`` or
``human_state_estimates``. So a real deployment running its own tracker
had no way to answer a plugin that required one — "custom capability" was
half a feature.

**The condition every test here exists around: a profile that declares
none must be unchanged.** Every stored profile predates this field, and
runs are addressed by a conditions hash derived from the profile — so a
field that moved that hash for profiles which do not use it would orphan
the runs it describes. That is checked against the value in the committed
H0 fixture, not against a number computed in this session.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from task_profile_fakes import make_profile

from planbench_benchmark.contexts import build_evaluation_contexts
from planbench_benchmark.episode import scenario_for
from planbench_benchmark.fingerprint import execution_conditions_fingerprint
from planbench_benchmark.selection import load_profile, load_task_map
from planbench_schemas.task_profile import CapabilityGrant, TaskProfile

REPO_ROOT = Path(__file__).resolve().parents[1]
PROFILE = REPO_ROOT / "profiles" / "warehouse_crossing_v1.yaml"
HOST_PARITY_FIXTURE = Path(__file__).parent / "golden" / "host_parity.json"

TRACKER = {
    "capability": "human_state_estimates",
    "provider_id": "org.lab.pedestrian-tracker",
    "provider_version": "2.1.0",
    "provider_config": {"max_range_m": 8.0, "min_confidence": 0.4},
}


@pytest.fixture(scope="module")
def deployment():
    profile = load_profile(PROFILE)
    return profile, load_task_map(profile, base_dir=REPO_ROOT)


def _fingerprint(profile, map_data) -> str:
    context = build_evaluation_contexts(profile, seed_count=1)[0]
    return execution_conditions_fingerprint(map_data, scenario_for(profile, context), profile)


class TestAProfileThatDeclaresNoneIsUnchanged:
    """The precondition. Everything else is worthless without it."""

    def test_the_committed_fingerprint_still_comes_out(self, deployment) -> None:
        profile, map_data = deployment
        fixture = json.loads(HOST_PARITY_FIXTURE.read_text(encoding="utf-8"))
        expected = fixture["astar_dwa_seed0"]["execution_conditions_fingerprint"]
        assert _fingerprint(profile, map_data) == expected

    def test_an_empty_tuple_is_not_hashed_as_an_empty_list(self, deployment) -> None:
        """Belt and braces on the same guarantee: the key must be absent,
        not present-and-empty. If the payload ever grew ``[]`` the test
        above would still pass only by luck of JSON ordering."""
        profile, map_data = deployment
        assert profile.capability_grants == ()
        explicit = profile.model_copy(update={"capability_grants": ()})
        assert _fingerprint(explicit, map_data) == _fingerprint(profile, map_data)

    def test_an_old_document_round_trips_without_drift(self) -> None:
        """Load, dump, load again. A stored profile that came back
        different would make every run filed under it unreproducible from
        its own record."""
        profile = load_profile(PROFILE)
        again = TaskProfile.model_validate(profile.model_dump(mode="json"))
        assert again == profile
        assert "capability_grants" in again.model_dump(mode="json")


class TestGrantsAreExecutionConditions:
    def test_granting_a_provider_changes_the_fingerprint(self, deployment) -> None:
        """§7.1: a tracker the deployment runs changes what every
        candidate sees, so it is a condition rather than bookkeeping."""
        profile, map_data = deployment
        granted = profile.model_copy(update={"capability_grants": (CapabilityGrant(**TRACKER),)})
        assert _fingerprint(granted, map_data) != _fingerprint(profile, map_data)

    def test_retuning_that_provider_changes_it_again(self, deployment) -> None:
        """The config is the deployment's, and a tracker retuned between
        two sweeps is a different experimental condition whatever the
        candidates did."""
        profile, map_data = deployment
        first = profile.model_copy(update={"capability_grants": (CapabilityGrant(**TRACKER),)})
        retuned = dict(TRACKER, provider_config={"max_range_m": 12.0, "min_confidence": 0.4})
        second = profile.model_copy(update={"capability_grants": (CapabilityGrant(**retuned),)})
        assert _fingerprint(second, map_data) != _fingerprint(first, map_data)

    def test_declaration_order_does_not(self, deployment) -> None:
        profile, map_data = deployment
        other = dict(TRACKER, capability="org.lab://channel/social-costmap@1")
        forwards = profile.model_copy(update={"capability_grants": (CapabilityGrant(**TRACKER), CapabilityGrant(**other))})
        backwards = profile.model_copy(update={"capability_grants": (CapabilityGrant(**other), CapabilityGrant(**TRACKER))})
        assert _fingerprint(forwards, map_data) == _fingerprint(backwards, map_data)


class TestTheTwoVocabulariesMergeIntoOne:
    def test_granted_capabilities_unions_both_sides(self) -> None:
        profile = make_profile(
            capability_grants=[dict(TRACKER, capability="org.lab://channel/social-costmap@1")]
        )
        assert profile.granted_capabilities() == (
            "lidar_2d",
            "org.lab://channel/social-costmap@1",
        )

    def test_a_grant_is_canonicalised_through_the_alias_bridge(self) -> None:
        """A deployment writing the URI and a plugin writing the token
        must meet, and they only meet if both reduce to one form first."""
        profile = make_profile(
            available_observations=["lidar_2d"],
            capability_grants=[
                dict(TRACKER, capability="planbench://channel/human-state-estimates@1")
            ],
        )
        assert profile.capability_grants[0].capability == "human_state_estimates"

    def test_the_deployment_side_reaches_preflight(self) -> None:
        """The point of the whole feature: a plugin requiring a capability
        no built-in provider produces now runs when the deployment grants
        it."""
        from planbench_plugin_sdk import parse_manifest

        from planbench_simulator.host.compatibility import resolve_compatibility
        from planbench_simulator.host.provider_graph import ProviderGraph
        from planbench_simulator.host.providers import builtin_providers, builtin_registry

        manifest = parse_manifest(
            {
                "plugin_api": "1.2.0",
                "id": "org.lab.needs-tracker",
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
                            "entry_point": "x:Y",
                        }
                    },
                },
                "requirements": {"all_of": ["human_state_estimates"]},
                "supports": {
                    "action_types": ["continuous-velocity@1"],
                    "robot_dynamics": ["differential-drive@1"],
                    "execution_models": ["synchronous-step@1"],
                },
                "requires_global_path": True,
            }
        )
        graph = ProviderGraph(builtin_providers(), builtin_registry())

        without = resolve_compatibility(
            manifest, available_capabilities=frozenset(), graph=graph
        )
        assert without.state == "registered_but_missing_provider"

        profile = make_profile(capability_grants=[TRACKER])
        withgrant = resolve_compatibility(
            manifest,
            available_capabilities=frozenset(),
            graph=graph,
            deployment_grants=profile.granted_capabilities(),
        )
        assert withgrant.runnable


class TestAmbiguityIsRefusedWhenTheProfileIsWritten:
    def test_two_providers_for_one_capability_are_refused(self) -> None:
        """The host does not choose: a tracker and a ground-truth source
        both produce ``human_state_estimates`` and they are different
        experiments (§5.4)."""
        with pytest.raises(ValidationError, match="does not say which"):
            make_profile(
                capability_grants=[
                    TRACKER,
                    dict(TRACKER, provider_id="org.lab.other-tracker"),
                ]
            )

    def test_the_same_provider_twice_is_not_ambiguous(self) -> None:
        """Repetition is untidy, not contradictory — refusing it would
        turn a duplicated line into an outage."""
        profile = make_profile(capability_grants=[TRACKER, dict(TRACKER)])
        assert profile.granted_capabilities() == ("human_state_estimates", "lidar_2d")

    def test_declaring_a_capability_on_both_sides_is_refused(self) -> None:
        """``available_observations`` says the deployment simply has it;
        a grant names a provider for it. A resolver reading both would
        have to guess which the deployment meant."""
        with pytest.raises(ValidationError, match="appear both in"):
            make_profile(
                available_observations=["lidar_2d", "human_state_estimates"],
                capability_grants=[TRACKER],
            )

    def test_the_refusal_happens_before_any_episode(self) -> None:
        """Written into the profile validator rather than into resolution:
        the deployment is wrong before a sweep starts, and finding out
        three hours in costs the sweep."""
        with pytest.raises(ValidationError):
            TaskProfile.model_validate(
                {
                    **make_profile().model_dump(mode="json"),
                    "capability_grants": [
                        TRACKER,
                        dict(TRACKER, provider_id="org.lab.other"),
                    ],
                }
            )
