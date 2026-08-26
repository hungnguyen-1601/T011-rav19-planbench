"""H1b: the SDK's first real consumer, and the monolithic loader (A5).

Pipeline under test: registry entry → synthetic manifest → manifest
parser → ``LegacyPluginLoader`` → the exact factories the platform has
always run. Plus the policy registry that finally turns a declared
``Candidate(type="monolithic")`` into something ``run_policy`` drives.

The candidate-identity assertions compare against the **committed H0
golden fixture**, not against a value computed in this session — the
claim is "unchanged across the H1b commit", and only bytes from git can
witness that.
"""

from __future__ import annotations

import json
from importlib.util import find_spec
from pathlib import Path

import pytest
from planbench_plugin_sdk import parse_manifest

from planbench_benchmark.candidates import (
    LOCAL_CONTROLLER_CONFIGS,
    UnknownParameterError,
    candidate_from_stack,
)
from planbench_benchmark.legacy_plugins import LegacyPluginLoader, synthetic_manifests
from planbench_benchmark.policies import (
    BUILTIN_CHECKPOINT,
    PolicyCheckpointError,
    PolicyEntry,
    UnknownPolicyError,
    build_policy,
    register_policy,
)
from planbench_benchmark.registry import AlgorithmConfigError, UnknownAlgorithmError
from planbench_benchmark.scenarios import build_scenario
from planbench_decision.candidate import Candidate
from planbench_planning.common.reference_policy import GreedyReferencePolicy
from planbench_simulator.nav_stack import run_policy

HOST_PARITY_FIXTURE = Path(__file__).parent / "golden" / "host_parity.json"


@pytest.fixture(scope="module")
def loader() -> LegacyPluginLoader:
    return LegacyPluginLoader()


def _monolithic(name: str, checkpoint: str) -> Candidate:
    return Candidate(
        type="monolithic",
        policy={"name": name, "checkpoint": checkpoint},  # type: ignore[arg-type]
        observation_requirements=("lidar_2d",),
        resource_profile={  # type: ignore[arg-type]
            "kind": "artifact",
            "model_artifact_mb": 0.1,
            "runtime_footprint_mb": 1.0,
        },
    )


class TestSyntheticManifestsAreRealManifests:
    """Derived from the registry, validated by the same parser any
    external bundle goes through — the SDK chewing real data."""

    def test_every_manifest_parses_under_the_sdk(self) -> None:
        for data in synthetic_manifests():
            manifest = parse_manifest(data, source=f"synthetic:{data['id']}")
            assert manifest.runtime.production_lane == "python_in_process"

    def test_the_offerable_components_are_exactly_these(self, loader) -> None:
        """Exact set, the guard style that caught two undecided stacks in
        the P6 session: a component appearing here without a decision is
        a red test, not a silent offer."""
        ids = sorted(manifest.id for manifest in loader.manifests())
        assert ids == ["astar", "dwa", "greedy_reference_policy", "ppo", "rrtstar"]

    def test_withdrawn_and_reference_stacks_contribute_nothing(self, loader) -> None:
        """dwa_predictive was withdrawn on measured evidence and
        pure_pursuit is a D12 reference; a manifest for either would be
        the platform offering what its own registry refuses."""
        ids = {manifest.id for manifest in loader.manifests()}
        assert "dwa_predictive" not in ids
        assert "pure_pursuit" not in ids

    def test_roles_and_requirements_come_from_registry_facts(self, loader) -> None:
        dwa = loader.manifest("dwa")
        assert dwa.role == "local"
        assert dwa.requirements.all_of == ("lidar_2d",)
        assert dwa.requires_global_path is True
        astar = loader.manifest("astar")
        assert astar.role == "global"
        assert astar.requirements.all_of == ()

    def test_the_config_schema_travels_into_the_manifest(self, loader) -> None:
        assert "horizon_seconds" in loader.manifest("dwa").config_schema.get("properties", {})


class TestManifestsResolveToTheOldFactories:
    def test_astar_resolves_to_the_astar_factory(self, loader) -> None:
        assert loader.build_global("astar", episode_seed=7).name == "astar"

    def test_rrtstar_resolves_and_keeps_its_seed_plumbing(self, loader) -> None:
        assert loader.build_global("rrtstar", episode_seed=3).name == "rrtstar"

    def test_dwa_resolves_with_a_named_configuration(self, loader) -> None:
        local = loader.build_local("dwa", dict(LOCAL_CONTROLLER_CONFIGS["dwa_balanced"]))
        assert local.name == "dwa"

    def test_an_unknown_component_is_refused_with_the_roster(self, loader) -> None:
        with pytest.raises(UnknownAlgorithmError, match="components"):
            loader.build_global("teb", episode_seed=0)

    def test_two_valid_components_do_not_imply_a_stack(self, loader) -> None:
        """rrtstar and ppo both have manifests; the registry pairs no
        such stack, and the loader must relay that refusal rather than
        invent the pairing."""
        with pytest.raises(UnknownAlgorithmError, match="pairs no stack"):
            loader.stack_id("rrtstar", "ppo")


class TestCandidateIdentityIsUnchanged:
    def test_the_manifest_path_and_the_direct_path_agree(self, loader) -> None:
        params = dict(LOCAL_CONTROLLER_CONFIGS["dwa_balanced"])
        via_manifests = loader.candidate("astar", "dwa", params=params)
        direct = candidate_from_stack("astar+dwa", params=params)
        assert via_manifests.candidate_id == direct.candidate_id

    def test_the_id_matches_the_committed_h0_baseline(self, loader) -> None:
        """Bytes from git, not from this session: the H0 fixture recorded
        3b18dfbfa9e7 before any H1 code existed."""
        fixture = json.loads(HOST_PARITY_FIXTURE.read_text(encoding="utf-8"))
        params = dict(LOCAL_CONTROLLER_CONFIGS["dwa_balanced"])
        assert (
            loader.candidate("astar", "dwa", params=params).candidate_id
            == fixture["astar_dwa_seed0"]["candidate_id"]
        )
        assert (
            loader.candidate("rrtstar", "dwa", params=params).candidate_id
            == fixture["rrtstar_dwa_seed0"]["candidate_id"]
        )


class TestUnknownConfigFailsExactlyAsBefore:
    def test_an_unknown_parameter_is_refused(self, loader) -> None:
        with pytest.raises(UnknownParameterError, match="no parameter"):
            loader.candidate("astar", "dwa", params={"sim_time": 2.5})

    def test_an_invalid_value_is_refused(self, loader) -> None:
        with pytest.raises(AlgorithmConfigError):
            loader.candidate("astar", "dwa", params={"horizon_seconds": -1.0})


class TestPPOKeepsItsLazyPath:
    def test_a_ppo_candidate_still_demands_a_chosen_model(self, loader) -> None:
        with pytest.raises(AlgorithmConfigError, match="no PPO model was chosen"):
            loader.candidate("astar", "ppo", params={})

    @pytest.mark.skipif(
        find_spec("stable_baselines3") is not None,
        reason="RL extras installed; the lazy-import refusal cannot fire",
    )
    def test_building_the_controller_fails_on_the_missing_dependency(self, loader) -> None:
        """The find_spec check must stay ahead of any checkpoint read:
        pointing an operator at torch when the model file is fine (or
        vice versa) sends them fixing the wrong thing."""
        with pytest.raises(AlgorithmConfigError, match="dependencies are not installed"):
            loader.build_local("ppo", {"model_path": "weights.zip"})


class TestThePolicyRegistryPaysA5:
    """Candidate(type='monolithic') → policy object → run_policy."""

    def test_a_declared_monolithic_candidate_now_builds(self) -> None:
        policy = build_policy(_monolithic("greedy_reference_policy", BUILTIN_CHECKPOINT))
        assert isinstance(policy, GreedyReferencePolicy)

    def test_it_runs_through_the_shared_loop(self, loader) -> None:
        """The A5 claim end to end: same loop, one-layer name, no global
        search charged. A short doorway episode is enough — the DoD is
        that it *runs*, not that it succeeds."""
        candidate = _monolithic("greedy_reference_policy", BUILTIN_CHECKPOINT)
        map_data, scenario = build_scenario("doorway")
        scenario = scenario.model_copy(update={"timeout_seconds": 3.0})
        run = run_policy(map_data, scenario, loader.build_policy(candidate))
        assert run.algorithm == "greedy_reference_policy"
        assert run.plan.success and run.plan.path == ()
        assert run.plan.planning_time_seconds == 0.0

    def test_an_unknown_policy_lists_the_known_ones(self) -> None:
        with pytest.raises(UnknownPolicyError, match="greedy_reference_policy"):
            build_policy(_monolithic("ppo_navigation", "c1"))

    def test_a_weightless_policy_rejects_an_invented_checkpoint(self) -> None:
        """The checkpoint is hashed into candidate_id, so accepting an
        arbitrary string would mint distinct ids for configurations that
        cannot differ."""
        with pytest.raises(PolicyCheckpointError, match="builtin"):
            build_policy(_monolithic("greedy_reference_policy", "epoch-40"))

    def test_a_modular_candidate_is_redirected(self) -> None:
        with pytest.raises(UnknownPolicyError, match="build_planners"):
            build_policy(candidate_from_stack("astar+dwa"))

    def test_a_weighted_policy_requires_a_resolver_and_gets_the_path(self, tmp_path) -> None:
        """The checkpoint-resolution half of A5, exercised through a
        registered test double: this layer hands the *resolved file* to
        the builder and refuses to guess when no resolver is given."""
        from planbench_benchmark import policies as policies_module

        received: list[str | None] = []
        register_policy(
            PolicyEntry(
                name="test_weighted_policy",
                description="test double for the resolver contract",
                reference=True,
                requires_checkpoint=True,
                builder=lambda path: (received.append(path), GreedyReferencePolicy())[1],
            )
        )
        try:
            candidate = _monolithic("test_weighted_policy", "model-registry:m1")

            with pytest.raises(PolicyCheckpointError, match="resolve_checkpoint"):
                build_policy(candidate)

            weights = tmp_path / "m1.zip"
            build_policy(candidate, resolve_checkpoint=lambda checkpoint: str(weights))
            assert received == [str(weights)]
        finally:
            # The registry is process-global; leaving the double behind
            # would leak it into any loader built later in the session
            # (synthetic_manifests derives from this registry).
            policies_module._POLICIES.pop("test_weighted_policy", None)

    def test_registering_the_same_name_twice_fails_loud(self) -> None:
        with pytest.raises(ValueError, match="already registered"):
            register_policy(
                PolicyEntry(
                    name="greedy_reference_policy",
                    description="imposter",
                    reference=True,
                    requires_checkpoint=False,
                    builder=lambda _path: GreedyReferencePolicy(),
                )
            )
