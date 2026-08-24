"""H6: two plugins from outside the registry, running for real.

The DoD is a negative — *adding or removing these must not touch
``run_stack()`` or ``engine.get_observation()``* — so the tests are
arranged to make the negative checkable rather than asserted: the
plugins are discovered from their own bundles, loaded through the
trusted runtime, and driven through the same loop every registry stack
uses, and a test reads the loop's source to confirm neither plugin is
named in it.

The local proof is oracle-fed, which is the other half of the design:
it runs, and it can never be a production candidate (§5.10).
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest
from planbench_plugin_sdk import load_manifest

from planbench_benchmark.scenarios import build_scenario
from planbench_simulator import engine as engine_module
from planbench_simulator import nav_stack as nav_stack_module
from planbench_simulator.host import (
    AlgorithmHost,
    GraphBackedLocalPlanner,
    GraphChannelSource,
    HostBackedGlobalPlanner,
)
from planbench_simulator.host.channel_bundle import CapabilitySpec
from planbench_simulator.host.compatibility import resolve_compatibility
from planbench_simulator.host.discovery import PluginRegistry
from planbench_simulator.host.fairness_policy import FairnessPolicy
from planbench_simulator.host.provider_graph import ProviderGraph
from planbench_simulator.host.providers import (
    HUMAN_STATE_ESTIMATES,
    LEGACY_OBSERVATION,
    builtin_providers,
    builtin_registry,
)
from planbench_simulator.host.runtimes import TrustedPythonRuntime
from planbench_simulator.nav_stack import run_stack

EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "plugins"
PLANNING_GRID = "planbench://channel/planning-grid@1"


@pytest.fixture(scope="module", autouse=True)
def _importable_examples():
    """Example plugins are installed the way an external one would be:
    on the path, not in the repository's packages."""
    sys.path.insert(0, str(EXAMPLES))
    try:
        yield
    finally:
        sys.path.remove(str(EXAMPLES))
        for name in ("social_nav", "social_nav.planner", "corridor_planner"):
            sys.modules.pop(name, None)


@pytest.fixture(scope="module")
def discovered() -> PluginRegistry:
    registry = PluginRegistry()
    registry.discover_directory(EXAMPLES)
    return registry


def _graph(*, oracle: bool) -> ProviderGraph:
    registry = builtin_registry()
    registry.register(CapabilitySpec(capability=PLANNING_GRID, cadence="static"))
    return ProviderGraph(builtin_providers(include_oracle=oracle), registry)


def _load(
    registry: PluginRegistry,
    plugin_id: str,
    graph: ProviderGraph,
    policy=None,
    available: frozenset[str] = frozenset(),
):
    plugin = registry.get(plugin_id, "0.1.0")
    assert plugin is not None, f"{plugin_id} was not discovered"
    report = resolve_compatibility(
        plugin.manifest,
        available_capabilities=available,
        graph=graph,
        policy=policy or FairnessPolicy.research(),
    )
    return TrustedPythonRuntime().load(plugin.manifest, report), report


class TestBothPluginsAreFoundOutsideTheRegistry:
    def test_neither_is_in_the_algorithm_registry(self) -> None:
        from planbench_benchmark.registry import ALGORITHMS

        assert "social_nav" not in ALGORITHMS
        assert "corridor" not in ALGORITHMS
        assert not any("corridor" in stack for stack in ALGORITHMS)

    def test_discovery_finds_them_from_their_own_bundles(self, discovered) -> None:
        found = sorted(plugin.manifest.id for plugin in discovered.plugins())
        assert found == [
            "org.planbench.example.corridor",
            "org.planbench.example.remote-wanderer",
            "org.planbench.example.social-nav",
        ]
        assert discovered.quarantined() == ()

    def test_the_local_proof_declares_a_requirement_nothing_else_ever_has(self) -> None:
        """The first candidate in this platform's life to ask for more
        than ``lidar_2d`` — which is what makes G6's pricing clause face
        a real difference at last."""
        manifest, _ = load_manifest(EXAMPLES / "social_nav" / ".planbench-plugin" / "plugin.json")
        assert HUMAN_STATE_ESTIMATES in manifest.requirements.all_of


class TestTheLoopKnowsNothingAboutThem:
    """The DoD, made checkable rather than claimed."""

    def test_run_stack_names_neither_plugin(self) -> None:
        """No plugin, no capability, no provider named. ``channel_source``
        appears and must: it is the *generic* seam, and a loop with no
        seam at all could only feed a plugin by branching on it.

        The names checked are **identifiers**, not English words. The
        first draft looked for ``"corridor"`` and failed on a comment
        about a two-metre corridor — a guard that cannot tell prose from
        a special case reports noise, and noise is what gets a guard
        deleted.
        """
        source = inspect.getsource(nav_stack_module.run_stack)
        for name in (
            "social_nav",
            "SocialNavPlanner",
            "corridor_planner",
            "CorridorPlanner",
            "org.planbench.example",
            "human_state_estimates",
            "ProviderGraph",
        ):
            assert name not in source, f"run_stack special-cases {name!r}"

    def test_get_observation_names_neither_plugin(self) -> None:
        source = inspect.getsource(engine_module.SimulationEngine.get_observation)
        for name in ("social_nav", "corridor", "channel", "provider"):
            assert name not in source

    def test_the_only_seam_is_plugin_agnostic(self) -> None:
        """One argument, one protocol, no plugin named — the difference
        between a data plane and a branch per algorithm."""
        parameters = inspect.signature(nav_stack_module.run_stack).parameters
        assert "channel_source" in parameters
        assert parameters["channel_source"].default is None


class TestTheGlobalProofPlansForReal:
    def test_it_produces_a_path_through_the_host(self, discovered) -> None:
        graph = _graph(oracle=False)
        plugin, report = _load(
            discovered,
            "org.planbench.example.corridor",
            graph,
            available=frozenset({PLANNING_GRID}),
        )
        assert report.runnable

        map_data, scenario = build_scenario("doorway")
        # No legacy adapter: this plugin already speaks the host's global
        # contract, so wrapping it in one would translate a request that
        # is already in the right shape.
        hosted = HostBackedGlobalPlanner(AlgorithmHost(global_plugin=plugin))
        from planbench_simulator.nav_stack import plan_global_path

        plan, _ = plan_global_path(map_data, scenario, hosted)
        assert plan.success
        assert len(plan.path) >= 2
        assert plan.path_length > 0.0

    def test_it_drives_an_episode_paired_with_a_registry_controller(self, discovered) -> None:
        """A plugin global planner and a built-in controller in one
        stack: the pairing the registry could not express before."""
        graph = _graph(oracle=False)
        plugin, _ = _load(
            discovered,
            "org.planbench.example.corridor",
            graph,
            available=frozenset({PLANNING_GRID}),
        )

        from planbench_benchmark.candidates import LOCAL_CONTROLLER_CONFIGS
        from planbench_benchmark.registry import build_local_planner

        map_data, scenario = build_scenario("doorway")
        scenario = scenario.model_copy(update={"timeout_seconds": 8.0})
        # No legacy adapter: this plugin already speaks the host's global
        # contract, so wrapping it in one would translate a request that
        # is already in the right shape.
        hosted = HostBackedGlobalPlanner(AlgorithmHost(global_plugin=plugin))
        run = run_stack(
            map_data,
            scenario,
            build_local_planner("astar+dwa", dict(LOCAL_CONTROLLER_CONFIGS["dwa_balanced"])),
            hosted,
        )
        assert run.algorithm == "corridor+dwa"
        assert run.result.steps > 0


class TestTheSeedReachesAChannelNativePlugin:
    def test_the_facade_forwards_the_episode_seed(self) -> None:
        """`GraphBackedLocalPlanner` used to build a `LocalResetRequest`
        without one, so the field took its default of 0 and every episode
        handed the plugin the same seed.

        Nothing failed when it did. A stochastic controller simply drew
        the same sample in every episode while the paired statistics went
        on treating the draws as independent — which is why this is a
        test rather than a comment.
        """
        from planbench_schemas.robot import RobotConfig

        recorded = {}

        class Recorder:
            name = "recorder"
            control_period = None

            def reset(self, request):
                recorded["seed"] = request.episode_seed

            def step(self, request):
                raise AssertionError("not reached")

        source = GraphChannelSource(_graph(oracle=False))
        source.episode_seed = 4321
        planner = GraphBackedLocalPlanner(
            AlgorithmHost(local_plugin=Recorder()), source, granted=()
        )
        planner.reset(
            (),
            RobotConfig(
                radius=0.3,
                max_linear_velocity=1.0,
                max_angular_velocity=1.0,
                max_linear_acceleration=1.0,
                max_angular_acceleration=1.0,
            ),
        )
        assert recorded["seed"] == 4321


class TestTheLocalProofRunsOnGrantedChannels:
    def test_it_drives_an_episode_through_the_provider_graph(self, discovered) -> None:
        graph = _graph(oracle=True)
        plugin, report = _load(discovered, "org.planbench.example.social-nav", graph)
        assert report.runnable
        assert report.evidence_class == "oracle"

        source = GraphChannelSource(graph, grant_truth=True)
        hosted = GraphBackedLocalPlanner(
            AlgorithmHost(local_plugin=plugin),
            source,
            granted=(LEGACY_OBSERVATION, HUMAN_STATE_ESTIMATES),
        )
        map_data, scenario = build_scenario("dynamic_warehouse")
        scenario = scenario.model_copy(update={"timeout_seconds": 6.0})
        run = run_stack(map_data, scenario, hosted, channel_source=source)

        assert run.algorithm == "astar+social_nav"
        assert run.result.steps > 0
        assert plugin.diagnostics["steps"] > 0

    def test_it_cannot_read_a_channel_it_was_not_granted(self, discovered) -> None:
        """The bundle is the boundary: a plugin cannot widen its own
        access by looking harder."""
        graph = _graph(oracle=True)
        plugin, _ = _load(discovered, "org.planbench.example.social-nav", graph)
        source = GraphChannelSource(graph, grant_truth=True)
        hosted = GraphBackedLocalPlanner(
            AlgorithmHost(local_plugin=plugin),
            source,
            granted=(LEGACY_OBSERVATION,),  # the oracle channel withheld
        )
        map_data, scenario = build_scenario("dynamic_warehouse")
        scenario = scenario.model_copy(update={"timeout_seconds": 2.0})
        run = run_stack(map_data, scenario, hosted, channel_source=source)

        # The host turns the plugin's LookupError into a safe stop, so
        # the episode records the refusal instead of crashing the run.
        assert any("was not granted" in event.message for event in run.result.events)


class TestTheOracleFedProofIsNeverAProductionCandidate:
    """§5.10's other half: it runs, and it can never be recommended."""

    def test_a_production_policy_refuses_it_at_preflight(self, discovered) -> None:
        graph = _graph(oracle=True)
        plugin = discovered.get("org.planbench.example.social-nav", "0.1.0")
        report = resolve_compatibility(
            plugin.manifest,
            available_capabilities=frozenset(),
            graph=graph,
            policy=FairnessPolicy.production(),
        )
        assert not report.runnable
        assert report.fairness_refusals == ("oracle",)

    def test_without_the_oracle_it_is_not_runnable_either(self, discovered) -> None:
        """Not a loophole: drop the oracle provider and the capability it
        required has no other source in this MVP, so the plugin is
        registered and missing a provider rather than quietly downgraded
        to something it can run on."""
        graph = _graph(oracle=False)
        plugin = discovered.get("org.planbench.example.social-nav", "0.1.0")
        report = resolve_compatibility(
            plugin.manifest,
            available_capabilities=frozenset(),
            graph=graph,
            policy=FairnessPolicy.production(),
        )
        assert report.state == "registered_but_missing_provider"
        assert HUMAN_STATE_ESTIMATES in report.missing_capabilities

    def test_the_evidence_class_travels_with_the_run(self, discovered) -> None:
        graph = _graph(oracle=True)
        plugin = discovered.get("org.planbench.example.social-nav", "0.1.0")
        report = resolve_compatibility(
            plugin.manifest,
            available_capabilities=frozenset(),
            graph=graph,
            policy=FairnessPolicy.research(),
        )
        assert report.evidence_class == "oracle"
        assert HUMAN_STATE_ESTIMATES in dict(report.ownership.oracle_owned)
        # And the oracle provider is in the fingerprint, so an oracle run
        # and a production one are addressed apart, not merely labelled.
        assert HUMAN_STATE_ESTIMATES in dict(report.host_conditions().providers)


class TestRemovingThemCostsNothing:
    def test_the_builtin_roster_is_unchanged_by_their_absence(self) -> None:
        """Removing a plugin is deleting its bundle. Nothing in the
        platform holds a reference that would go dangling."""
        from planbench_benchmark.legacy_plugins import discover_all

        registry = discover_all(include_entry_points=False)
        ids = sorted(plugin.manifest.id for plugin in registry.plugins())
        assert ids == ["astar", "dwa", "greedy_reference_policy", "ppo", "rrtstar"]
