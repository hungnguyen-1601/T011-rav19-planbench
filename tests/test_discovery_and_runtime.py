"""H5: discovery that runs nothing, and a runtime that runs it late.

DoD lines pinned here: the built-in stacks enter the same registry as
everything else, entry-point discovery works, a plugin whose
dependencies are absent stays registered and not runnable, and discovery
never executes plugin code — proved with a bundle whose every module
raises on import.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from planbench_plugin_sdk import PLUGIN_API_VERSION, is_compatible, parse_manifest

from planbench_benchmark.legacy_plugins import discover_all, synthetic_manifests
from planbench_simulator.host.compatibility import CompatibilityReport, resolve_compatibility
from planbench_simulator.host.discovery import (
    BUNDLE_DIRNAME,
    PluginRegistry,
)
from planbench_simulator.host.provider_graph import ProviderGraph
from planbench_simulator.host.providers import (
    LIDAR_2D,
    builtin_providers,
    builtin_registry,
)
from planbench_simulator.host.runtimes import RuntimeLoadError, TrustedPythonRuntime

EXPLODING = 'raise RuntimeError("discovery executed plugin code")'


def manifest_data(**overrides):
    data = {
        "plugin_api": PLUGIN_API_VERSION,
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
                    "entry_point": "social_nav:SocialNavPlanner",
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
    return data


def write_bundle(root: Path, name: str, data: dict | str) -> Path:
    """A bundle whose Python explodes on import, every time."""
    bundle = root / name
    (bundle / BUNDLE_DIRNAME).mkdir(parents=True)
    (bundle / "__init__.py").write_text(EXPLODING, encoding="utf-8")
    (bundle / "planner.py").write_text(EXPLODING, encoding="utf-8")
    text = data if isinstance(data, str) else json.dumps(data)
    (bundle / BUNDLE_DIRNAME / "plugin.json").write_text(text, encoding="utf-8")
    return bundle


class _FakeDist:
    def __init__(self, root: Path) -> None:
        self._root = root

    def locate_file(self, relative: str) -> Path:
        return self._root / relative


class _FakeEntryPoint:
    """Enough of an ``EntryPoint`` to be read without being resolved."""

    def __init__(self, name: str, value: str, root: Path) -> None:
        self.name = name
        self.value = value
        self.dist = _FakeDist(root)


class TestDiscoveryRunsNothing:
    """§5.1's load-bearing property, proved rather than asserted."""

    def test_a_bundle_that_explodes_on_import_is_discovered(self, tmp_path) -> None:
        write_bundle(tmp_path, "social_nav", manifest_data())
        registry = PluginRegistry()
        registry.discover_directory(tmp_path)

        assert [p.manifest.id for p in registry.plugins()] == ["org.lab.social-nav"]
        assert "social_nav" not in sys.modules

    def test_one_broken_manifest_does_not_cost_the_others(self, tmp_path) -> None:
        """Ten plugins, one malformed: the other nine must survive, and
        the reason must travel with the entry."""
        write_bundle(tmp_path, "good_a", manifest_data(id="org.lab.a"))
        write_bundle(tmp_path, "good_b", manifest_data(id="org.lab.b"))
        write_bundle(tmp_path, "broken", "{ this is not json")

        registry = PluginRegistry()
        registry.discover_directory(tmp_path)

        assert sorted(p.manifest.id for p in registry.plugins()) == ["org.lab.a", "org.lab.b"]
        assert len(registry.quarantined()) == 1
        assert "cannot read manifest" in registry.quarantined()[0].reason

    def test_a_manifest_that_fails_validation_is_quarantined_with_why(self, tmp_path) -> None:
        write_bundle(tmp_path, "typo", manifest_data(requirements={"all_of": ["lidar2d"]}))
        registry = PluginRegistry()
        registry.discover_directory(tmp_path)

        assert registry.plugins() == ()
        assert "lidar_2d" in registry.quarantined()[0].reason  # the suggestion survives

    def test_a_missing_directory_is_not_an_error(self, tmp_path) -> None:
        """A deployment with no bundle directory has no plugins, which is
        a normal state and not a misconfiguration."""
        registry = PluginRegistry()
        registry.discover_directory(tmp_path / "nowhere")
        assert registry.plugins() == ()
        assert registry.quarantined() == ()


class TestEntryPointDiscovery:
    def test_an_installed_distribution_is_found_without_importing_it(self, tmp_path) -> None:
        write_bundle(tmp_path, "social_nav", manifest_data())
        registry = PluginRegistry()
        registry.discover_entry_points(
            [_FakeEntryPoint("social-nav", "social_nav:SocialNavPlanner", tmp_path)]
        )
        assert [p.manifest.id for p in registry.plugins()] == ["org.lab.social-nav"]
        assert registry.plugins()[0].source.startswith("entry-point:")
        assert "social_nav" not in sys.modules

    def test_a_distribution_shipping_no_manifest_is_quarantined(self, tmp_path) -> None:
        """Advertising the group and shipping no manifest is a packaging
        mistake; naming it is what lets the author fix it."""
        registry = PluginRegistry()
        registry.discover_entry_points([_FakeEntryPoint("ghost", "ghost:Thing", tmp_path)])
        assert registry.plugins() == ()
        assert "ships no" in registry.quarantined()[0].reason

    def test_the_same_plugin_through_two_sources_is_one_entry(self, tmp_path) -> None:
        """Scanning a directory and reading an entry point that points at
        it must not double-count — discovery has to be idempotent across
        overlapping sources."""
        write_bundle(tmp_path, "social_nav", manifest_data())
        registry = PluginRegistry()
        registry.discover_directory(tmp_path)
        registry.discover_entry_points(
            [_FakeEntryPoint("social-nav", "social_nav:SocialNavPlanner", tmp_path)]
        )
        assert len(registry.plugins()) == 1
        assert registry.quarantined() == ()

    def test_two_different_bodies_for_one_id_are_quarantined(self, tmp_path) -> None:
        other = tmp_path / "other"
        other.mkdir()
        write_bundle(tmp_path, "social_nav", manifest_data())
        write_bundle(other, "social_nav", manifest_data(config_schema={"x": 1}))
        registry = PluginRegistry()
        registry.discover_directory(tmp_path)
        registry.discover_directory(other)
        assert len(registry.plugins()) == 1
        assert "two different manifests" in registry.quarantined()[0].reason


class TestMissingDependenciesLeaveItRegistered:
    """DoD: registered, and not runnable, and the difference is stated."""

    def _registry(self, available: set[str], **overrides) -> PluginRegistry:
        registry = PluginRegistry(dependency_probe=lambda module: module in available)
        registry.add_manifests([manifest_data(**overrides)], source="test")
        return registry

    def _with_deps(self, *modules: str) -> dict:
        runtime = manifest_data()["runtime"]
        runtime["profiles"]["python_in_process"]["python_dependencies"] = list(modules)
        return {"runtime": runtime}

    def test_an_absent_dependency_does_not_hide_the_plugin(self) -> None:
        registry = self._registry(set(), **self._with_deps("torch"))
        plugin = registry.plugins()[0]
        assert plugin.manifest.id == "org.lab.social-nav"
        assert not plugin.runnable_runtime
        assert plugin.missing_dependencies == ("torch",)
        assert registry.runnable() == ()

    def test_a_present_dependency_makes_it_runnable(self) -> None:
        registry = self._registry({"torch"}, **self._with_deps("torch"))
        assert registry.runnable()[0].missing_dependencies == ()

    def test_only_the_production_lane_is_checked(self) -> None:
        """A lane the plugin will not be measured in must not mark it
        unrunnable — the deps of a subprocess lane are that lane's
        problem, on the day it is used."""
        runtime = manifest_data()["runtime"]
        runtime["supported_lanes"] = ["python_in_process", "subprocess"]
        runtime["profiles"]["subprocess"] = {
            "protocol": "planbench-subprocess/v1",
            "codec": "protobuf-v1",
            "deadline_policy": "control-period",
            "python_dependencies": ["grpcio"],
        }
        registry = self._registry(set(), runtime=runtime)
        assert registry.runnable()[0].manifest.id == "org.lab.social-nav"

    def test_the_roster_says_both_what_runs_and_what_does_not(self) -> None:
        registry = self._registry(set(), **self._with_deps("torch"))
        registry.add_manifests([{"nonsense": True}], source="bad")
        roster = registry.roster()
        assert "missing ['torch']" in roster
        assert "QUARANTINED" in roster


class TestBuiltinsShareTheOnePath:
    def test_the_built_in_stacks_enter_the_same_registry(self) -> None:
        registry = discover_all(include_entry_points=False)
        ids = sorted(plugin.manifest.id for plugin in registry.plugins())
        assert ids == ["astar", "dwa", "greedy_reference_policy", "ppo", "rrtstar"]
        assert all(plugin.source.startswith("builtin") for plugin in registry.plugins())

    def test_a_bundle_joins_them_in_one_roster(self, tmp_path) -> None:
        write_bundle(tmp_path, "social_nav", manifest_data())
        registry = discover_all(bundle_root=tmp_path, include_entry_points=False)
        ids = sorted(plugin.manifest.id for plugin in registry.plugins())
        assert "org.lab.social-nav" in ids
        assert "astar" in ids

    def test_the_synthetic_manifests_declare_this_sdk_version(self) -> None:
        for data in synthetic_manifests():
            assert is_compatible(data["plugin_api"])


class TestTheRuntimeLoadsLateAndRefusesEarly:
    def _runnable_report(self) -> CompatibilityReport:
        graph = ProviderGraph(builtin_providers(), builtin_registry())
        return resolve_compatibility(
            parse_manifest(manifest_data()), available_capabilities=frozenset(), graph=graph
        )

    def test_a_plugin_preflight_refused_is_never_imported(self) -> None:
        """The ordering the class exists to enforce: importing it to find
        out would run code the host has already decided may not run."""
        manifest = parse_manifest(manifest_data())
        refused = resolve_compatibility(
            manifest,
            available_capabilities=frozenset(),
            graph=ProviderGraph((), builtin_registry()),
        )
        assert not refused.runnable
        with pytest.raises(RuntimeLoadError, match="refusing to load"):
            TrustedPythonRuntime().load(manifest, refused)

    def test_a_broken_import_fails_against_the_plugin_not_the_roster(self, tmp_path) -> None:
        """Discovery deliberately did not import; the failure therefore
        lands here, named, instead of taking discovery down."""
        (tmp_path / "exploding_plugin.py").write_text(EXPLODING, encoding="utf-8")
        sys.path.insert(0, str(tmp_path))
        try:
            runtime = manifest_data()["runtime"]
            runtime["profiles"]["python_in_process"]["entry_point"] = "exploding_plugin:Thing"
            manifest = parse_manifest(manifest_data(runtime=runtime))
            with pytest.raises(RuntimeLoadError, match="could not be imported"):
                runtime_lane = TrustedPythonRuntime()
                runtime_lane.load(manifest, self._runnable_report())
        finally:
            sys.path.remove(str(tmp_path))

    def test_a_plugin_without_an_entry_point_says_so(self) -> None:
        runtime = manifest_data()["runtime"]
        runtime["profiles"]["python_in_process"].pop("entry_point")
        manifest = parse_manifest(manifest_data(runtime=runtime))
        with pytest.raises(RuntimeLoadError, match="no entry_point"):
            TrustedPythonRuntime().load(manifest, self._runnable_report())

    def test_a_lane_mismatch_is_refused(self) -> None:
        """Loading a subprocess-lane plugin in-process would measure a
        lane the plugin did not declare (§5.9 rule 4)."""
        runtime = {
            "supported_lanes": ["subprocess"],
            "production_lane": "subprocess",
            "profiles": {
                "subprocess": {
                    "protocol": "planbench-subprocess/v1",
                    "codec": "protobuf-v1",
                    "deadline_policy": "control-period",
                    "entry_point": "whatever:Thing",
                }
            },
        }
        manifest = parse_manifest(manifest_data(runtime=runtime))
        report = self._runnable_report()
        with pytest.raises(RuntimeLoadError, match="this runtime is"):
            TrustedPythonRuntime().load(manifest, report)

    def test_a_loaded_plugin_must_present_its_role(self, tmp_path) -> None:
        """Structural conformance, not behavioural: a missing ``step``
        would otherwise surface as an AttributeError mid-episode."""
        (tmp_path / "half_plugin.py").write_text(
            "class Half:\n    name = 'half'\n    def reset(self, request):\n        pass\n",
            encoding="utf-8",
        )
        sys.path.insert(0, str(tmp_path))
        try:
            runtime = manifest_data()["runtime"]
            runtime["profiles"]["python_in_process"]["entry_point"] = "half_plugin:Half"
            manifest = parse_manifest(manifest_data(runtime=runtime))
            with pytest.raises(RuntimeLoadError, match=r"has no \['step'\]"):
                TrustedPythonRuntime().load(manifest, self._runnable_report())
        finally:
            sys.path.remove(str(tmp_path))

    def test_a_conforming_plugin_loads(self, tmp_path) -> None:
        (tmp_path / "whole_plugin.py").write_text(
            "class Whole:\n"
            "    name = 'whole'\n"
            "    control_period = None\n"
            "    def reset(self, request):\n        pass\n"
            "    def step(self, request):\n        pass\n",
            encoding="utf-8",
        )
        sys.path.insert(0, str(tmp_path))
        try:
            runtime = manifest_data()["runtime"]
            runtime["profiles"]["python_in_process"]["entry_point"] = "whole_plugin:Whole"
            manifest = parse_manifest(manifest_data(runtime=runtime))
            plugin = TrustedPythonRuntime().load(manifest, self._runnable_report())
            assert plugin.name == "whole"
        finally:
            sys.path.remove(str(tmp_path))
