"""H9B: a provider the candidate ships is part of what it is.

§7.1 splits providers three ways and H4 built two thirds of it: a
deployment-owned provider changes the execution fingerprint, and a
candidate-owned one was kept *out* of the fingerprint with a test to
prove it. The other half — that it goes **into** ``candidate_id`` — was
never wired, and the H4 report claimed the pair was locked in both
directions. It was locked in one.

The consequence is quiet: two candidates differing only in the estimator
they ship share an id, so every trace, every ΔU and every card recorded
against that id describes two different things with no way to tell.

Both directions are pinned here, and so is the thing that makes the
guarantee usable: **a candidate with no providers keeps the id it was
measured under**, checked against ids committed to git before this
field existed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from planbench_benchmark.candidates import LOCAL_CONTROLLER_CONFIGS, candidate_from_stack
from planbench_benchmark.fingerprint import HostConditions
from planbench_decision.candidate import (
    Candidate,
    CandidateProviderBinding,
    provider_config_digest,
)

HOST_PARITY_FIXTURE = Path(__file__).parent / "golden" / "host_parity.json"

RESOURCE = {
    "kind": "structural",
    "target_implementation": "cpp_ros2",
    "bytes_per_search_node": 64,
    "bytes_per_tree_node": 64,
    "bytes_per_costmap_cell": 1,
    "costmap_layers": 1,
    "fixed_overhead_mb": 10.0,
}


def binding(**overrides) -> CandidateProviderBinding:
    payload = {
        "capability": "lidar_2d",
        "provider_id": "org.lab.tracker",
        "provider_version": "1.2.0",
        "manifest_checksum": "sha256:" + "ab" * 32,
        "config_digest": "",
        "schema_digest": "",
    }
    payload.update(overrides)
    return CandidateProviderBinding(**payload)


def candidate(**overrides) -> Candidate:
    payload = {
        "type": "modular",
        "global_planner": {"name": "astar"},
        "local_controller": {"name": "dwa"},
        "observation_requirements": ("lidar_2d",),
        "resource_profile": RESOURCE,
    }
    payload.update(overrides)
    return Candidate(**payload)


class TestLegacyIdentityDoesNotMove:
    """The precondition for everything else. A field that shifted every
    stored id would orphan three hundred episodes per candidate to record
    something none of them have."""

    def test_a_candidate_with_no_providers_keeps_its_committed_id(self) -> None:
        """Bytes from git, written before this field existed."""
        fixture = json.loads(HOST_PARITY_FIXTURE.read_text(encoding="utf-8"))
        params = dict(LOCAL_CONTROLLER_CONFIGS["dwa_balanced"])
        for stack, key in (
            ("astar+dwa", "astar_dwa_seed0"),
            ("rrtstar+dwa", "rrtstar_dwa_seed0"),
        ):
            built = candidate_from_stack(stack, params=params)
            assert built.candidate_id == fixture[key]["candidate_id"]

    def test_an_explicit_empty_tuple_is_the_same_as_absent(self) -> None:
        """``providers=()`` must not be a different declaration from not
        mentioning providers — otherwise the key is in the payload after
        all and the guarantee above holds only by accident."""
        assert candidate().candidate_id == candidate(providers=()).candidate_id


class TestAProviderTheCandidateShipsChangesItsIdentity:
    def test_adding_one_changes_the_id(self) -> None:
        assert candidate(providers=(binding(),)).candidate_id != candidate().candidate_id

    def test_a_new_version_of_the_same_provider_changes_it(self) -> None:
        first = candidate(providers=(binding(provider_version="1.2.0"),))
        second = candidate(providers=(binding(provider_version="1.3.0"),))
        assert first.candidate_id != second.candidate_id

    def test_a_rebuilt_bundle_changes_it(self) -> None:
        """**Why the class name was not enough.** Two builds of one
        provider share a name, so hashing the name would let a rewritten
        estimator keep the id of the results it invalidated."""
        first = candidate(providers=(binding(manifest_checksum="sha256:" + "aa" * 32),))
        second = candidate(providers=(binding(manifest_checksum="sha256:" + "bb" * 32),))
        assert first.candidate_id != second.candidate_id

    def test_a_retuned_provider_changes_it(self) -> None:
        first = candidate(providers=(binding(config_digest=provider_config_digest({"gain": 1.0})),))
        second = candidate(
            providers=(binding(config_digest=provider_config_digest({"gain": 2.0})),)
        )
        assert first.candidate_id != second.candidate_id

    def test_a_changed_payload_schema_changes_it(self) -> None:
        first = candidate(providers=(binding(schema_digest="sha256:" + "cc" * 32),))
        second = candidate(providers=(binding(schema_digest="sha256:" + "dd" * 32),))
        assert first.candidate_id != second.candidate_id


class TestTheCanonicalisationTraps:
    """Both were paid for once already, elsewhere in this platform."""

    def test_declaration_order_does_not_change_the_id(self) -> None:
        one, two = (
            binding(capability="lidar_2d"),
            binding(capability="human_state_estimates", provider_id="org.lab.other"),
        )
        assert (
            candidate(providers=(one, two)).candidate_id
            == candidate(providers=(two, one)).candidate_id
        )

    def test_two_spellings_of_a_capability_are_one_binding(self) -> None:
        """The guarantee H1a exists for: ``lidar_2d`` and its URI are the
        same capability, so a candidate declaring either must get one id.
        Without the alias bridge here, H9B would silently undo DoD 15."""
        token = candidate(providers=(binding(capability="lidar_2d"),))
        uri = candidate(providers=(binding(capability="planbench://channel/lidar-2d@1"),))
        assert token.candidate_id == uri.candidate_id

    def test_a_config_written_in_two_orders_is_one_config(self) -> None:
        """The defect a test found in ``HostConditions.providers``, in the
        one place it would have cost a candidate id."""
        assert provider_config_digest({"a": 1, "b": 2}) == provider_config_digest({"b": 2, "a": 1})

    def test_an_unconfigured_provider_does_not_digest_an_empty_dict(self) -> None:
        assert provider_config_digest(None) == provider_config_digest({}) == ""


class TestTheOtherDirectionStillHolds:
    """H4's half, re-checked here so the pair is locked from both ends
    rather than one end being asserted in a report."""

    def test_a_deployment_owned_provider_does_not_touch_the_candidate_id(self) -> None:
        before = candidate().candidate_id
        # A deployment provider is an execution condition; nothing about
        # the candidate changed, so its identity must not.
        HostConditions(providers=(("lidar_2d", "DeploymentTracker"),))
        assert candidate().candidate_id == before

    def test_a_candidate_owned_provider_stays_out_of_the_fingerprint(self) -> None:
        from planbench_simulator.host.compatibility import ProviderOwnership

        ownership = ProviderOwnership(
            candidate_owned=(("org.lab://channel/x@1", "Mine"),),
            deployment_owned=(("lidar_2d", "Theirs"),),
        )
        hashable = dict(ownership.hashable())
        assert "org.lab://channel/x@1" not in hashable
        assert "lidar_2d" in hashable


class TestPreflightRefusesAnUndeclaredProvider:
    """Static identity and the resolved graph must agree. The graph knows
    which providers are candidate-owned; only the candidate can say it
    declared them, so neither side can check this alone."""

    def _report(self, declared: tuple[str, ...]):
        from planbench_plugin_sdk import parse_manifest

        from planbench_simulator.host.channel_bundle import CapabilityRegistry, CapabilitySpec
        from planbench_simulator.host.compatibility import resolve_compatibility
        from planbench_simulator.host.provider_graph import ProviderGraph
        from planbench_simulator.host.providers.base import Provider

        class _CandidateProvider(Provider):
            capability = "org.lab://channel/social-costmap@1"
            cadence = "per_tick"
            provenance = "candidate"

            def advance(self, tick, now, view, inputs) -> None:
                del tick, now, view, inputs

            def read(self) -> str:
                return "X"

        registry = CapabilityRegistry(
            (CapabilitySpec(capability=_CandidateProvider.capability, cadence="per_tick"),)
        )
        manifest = parse_manifest(
            {
                "plugin_api": "1.2.0",
                "id": "org.lab.plugin",
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
                "requirements": {"all_of": []},
                "supports": {
                    "action_types": ["continuous-velocity@1"],
                    "robot_dynamics": ["differential-drive@1"],
                    "execution_models": ["synchronous-step@1"],
                },
            }
        )
        return resolve_compatibility(
            manifest,
            available_capabilities=frozenset(),
            graph=ProviderGraph((_CandidateProvider(),), registry),
            declared_candidate_providers=declared,
        )

    def test_an_undeclared_candidate_provider_blocks_the_run(self) -> None:
        report = self._report(declared=())
        assert not report.runnable
        assert report.undeclared_providers == ("org.lab://channel/social-costmap@1",)
        assert "missing from candidate_id" in report.explain()

    def test_declaring_it_lets_the_run_proceed(self) -> None:
        report = self._report(declared=("org.lab://channel/social-costmap@1",))
        assert report.undeclared_providers == ()
        assert report.runnable


class TestIdentityIsKnowableBeforeAnyDeployment:
    def test_a_binding_needs_nothing_from_a_resolved_graph(self) -> None:
        """A ``candidate_id`` has to exist before preflight has anything
        to resolve. A candidate whose identity came from the graph would
        have a different id per deployment — and the id is what every
        stored result is filed under."""
        built = candidate(providers=(binding(),))
        assert built.candidate_id
        assert len(built.candidate_id) == 12

    def test_a_binding_refuses_a_capability_that_is_not_one(self) -> None:
        with pytest.raises(Exception, match="capability URI|Did you mean"):
            binding(capability="lidar2d")
