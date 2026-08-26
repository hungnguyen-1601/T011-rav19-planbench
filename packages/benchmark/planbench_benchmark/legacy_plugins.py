"""Built-in algorithms exposed as plugin manifests, and the loader (H1b).

The first real consumer of the plugin SDK: every registry algorithm gets
a **synthetic manifest** — derived from the registry facts, never
hand-written — and ``LegacyPluginLoader`` resolves those manifests back
to the exact factories the platform has always run. Nothing new
executes; the point is that the SDK contract is now chewed by real
registry data before H2 freezes anything (plan H1a/H1b, round 4).

**One manifest per component, not per stack.** The plugin contracts of
§5.5 are global / local / monolithic; a stack is a *pairing*, and the
registry keeps being the authority on which pairings exist
(``rrtstar+ppo`` is not one). So the loader answers two different
questions with two different methods: "what components exist?" from the
manifests, "which pairs may run?" from the registry.

**Identity is delegated, not re-derived.** ``candidate()`` calls
``candidate_from_stack`` — the same function every measured candidate
came from — so a candidate assembled via manifests hashes identically to
one assembled directly. The H0 golden fixture pins this across commits.

Synthetic manifests only cover what may still be offered: withdrawn
stacks and D12 reference stacks contribute no component manifests. The
monolithic side comes from the policy registry (``policies.py``), which
is debt A5's home.
"""

from __future__ import annotations

from typing import Any

from planbench_plugin_sdk import (
    PLUGIN_API_VERSION,
    ManifestIndex,
    PluginManifest,
    manifest_checksum,
    parse_manifest,
)

from planbench_benchmark.candidates import candidate_from_stack
from planbench_benchmark.policies import build_policy, list_policies
from planbench_benchmark.registry import (
    AlgorithmInfo,
    UnknownAlgorithmError,
    build_global_planner,
    build_local_planner,
    list_algorithms,
)
from planbench_decision.candidate import Candidate
from planbench_planning.common.base import GlobalPlanner
from planbench_planning.common.local_base import LocalPlanner

#: Built-in components all run in-process today; the manifest says so
#: explicitly because the lane is part of what H2 must preserve.
_RUNTIME: dict[str, Any] = {
    "supported_lanes": ["python_in_process"],
    "production_lane": "python_in_process",
    "profiles": {
        "python_in_process": {
            "protocol": "planbench-inproc/v1",
            "codec": "python-object/v1",
            "deadline_policy": "control-period",
        }
    },
}

#: §5.6 references for the built-ins. A global planner's "action" is the
#: path it emits; everything else matches the MVP triple the plan names.
_SUPPORTS: dict[str, dict[str, list[str]]] = {
    "global": {
        "action_types": ["global-path@1"],
        "robot_dynamics": ["differential-drive@1"],
        "execution_models": ["synchronous-step@1"],
    },
    "local": {
        "action_types": ["continuous-velocity@1"],
        "robot_dynamics": ["differential-drive@1"],
        "execution_models": ["synchronous-step@1"],
    },
}
_SUPPORTS["monolithic"] = _SUPPORTS["local"]

#: What each P02 observation class implies at runtime — the same mapping
#: ``candidates._REQUIREMENTS`` uses for G6, restated here as manifest
#: requirement lists. ``full_static_map`` maps to nothing for the same
#: reason it maps to no G6 token: the deployment ships the map.
_CLASS_REQUIREMENTS: dict[str, list[str]] = {
    "full_static_map": [],
    "lidar_only": ["lidar_2d"],
    "human_states": ["human_state_estimates"],
    "lidar+human_states": ["lidar_2d", "human_state_estimates"],
    "full_static_map+human_states": ["human_state_estimates"],
}

#: Version every synthetic manifest carries. "v1" on purpose: it is the
#: default ``StackComponent.version``, so the manifest layer introduces
#: no version the identity layer does not already have.
SYNTHETIC_VERSION = "v1"


def _offerable(info: AlgorithmInfo) -> bool:
    """Stacks that may still be offered: not withdrawn, not D12 reference."""
    return info.benchmarkable


def _manifest(
    component_id: str,
    role: str,
    requirements: list[str],
    config_schema: dict[str, Any],
    requires_global_path: bool | None,
) -> dict[str, Any]:
    return {
        "plugin_api": PLUGIN_API_VERSION,
        "id": component_id,
        "version": SYNTHETIC_VERSION,
        "role": role,
        "runtime": _RUNTIME,
        "requirements": {"all_of": requirements},
        "supports": _SUPPORTS[role],
        "config_schema": config_schema,
        "requires_global_path": requires_global_path,
    }


def synthetic_manifests() -> tuple[dict[str, Any], ...]:
    """One manifest dict per offerable component, from registry facts.

    Derived on every call rather than stored, the fingerprint lesson
    applied to metadata: a hand-maintained list beside the registry
    would drift from it, and a withdrawn stack would keep a manifest
    nobody remembered to delete.
    """
    globals_seen: dict[str, dict[str, Any]] = {}
    locals_seen: dict[str, dict[str, Any]] = {}
    for info in list_algorithms():
        if not _offerable(info):
            continue
        if info.global_planner not in globals_seen:
            globals_seen[info.global_planner] = _manifest(
                info.global_planner,
                "global",
                _CLASS_REQUIREMENTS[info.global_observation_class],
                {},
                None,
            )
        if info.local_controller not in locals_seen:
            locals_seen[info.local_controller] = _manifest(
                info.local_controller,
                "local",
                _CLASS_REQUIREMENTS[info.local_observation_class],
                info.config_schema,
                info.requires_global_path,
            )
    policies = tuple(
        _manifest(entry.name, "monolithic", ["lidar_2d"], {}, False) for entry in list_policies()
    )
    ordered = [*globals_seen.values(), *locals_seen.values(), *policies]
    return tuple(ordered)


def discover_all(
    *,
    bundle_root: str | None = None,
    include_entry_points: bool = True,
):
    """The whole roster: built-ins, bundles on disk, installed plugins.

    H5's "one discovery path". The built-in stacks enter the same
    registry as everything else rather than being listed beside it — a
    roster assembled from two mechanisms drifts, and the first symptom
    is a report naming stacks the runner cannot run.

    Imported here rather than at module scope: this module is on the
    identity path (``candidate_from_stack``), and pulling the simulator
    in to answer a question about hashes would make an API process load
    the engine to validate a form.
    """
    from planbench_simulator.host.discovery import PluginRegistry

    registry = PluginRegistry()
    registry.add_manifests(synthetic_manifests(), source="builtin")
    if bundle_root is not None:
        registry.discover_directory(bundle_root)
    if include_entry_points:
        registry.discover_entry_points()
    return registry


class LegacyPluginLoader:
    """Manifests in, the platform's own factories out.

    Every build method delegates to the registry the moment the manifest
    has answered "does this component exist" — validation, lazy PPO
    imports and seed plumbing all stay where they were, which is what
    makes the H0 parity claim cheap to keep.
    """

    def __init__(self) -> None:
        self._index = ManifestIndex()
        for data in synthetic_manifests():
            manifest = parse_manifest(data, source=f"synthetic:{data['id']}")
            self._index.add(manifest, manifest_checksum(data))
        # Which pairs the registry actually has, and which stack id backs
        # a lone component. sorted() so the backing stack for "astar" is
        # deterministic (astar+dwa, not whichever dict order offered).
        self._pairs: dict[tuple[str, str], str] = {}
        self._global_backing: dict[str, str] = {}
        self._local_backing: dict[str, str] = {}
        for info in sorted(list_algorithms(), key=lambda entry: entry.id):
            if not _offerable(info):
                continue
            self._pairs[(info.global_planner, info.local_controller)] = info.id
            self._global_backing.setdefault(info.global_planner, info.id)
            self._local_backing.setdefault(info.local_controller, info.id)

    # -- what exists ---------------------------------------------------

    def manifests(self) -> tuple[PluginManifest, ...]:
        return self._index.manifests()

    def manifest(self, component_id: str) -> PluginManifest:
        manifest = self._index.get(component_id, SYNTHETIC_VERSION)
        if manifest is None:
            known = sorted(entry.id for entry in self._index.manifests())
            raise UnknownAlgorithmError(
                f"no built-in component {component_id!r}; components: {known}"
            )
        return manifest

    # -- which pairs may run -------------------------------------------

    def stack_id(self, global_id: str, local_id: str) -> str:
        """The registry stack behind a pairing, or the registry's refusal.

        The manifests say the components exist; only the registry says
        the pair does. ``rrtstar+ppo`` has two valid manifests and no
        stack, and offering it anyway would benchmark a configuration
        nobody registered.
        """
        self.manifest(global_id)
        self.manifest(local_id)
        stack = self._pairs.get((global_id, local_id))
        if stack is None:
            pairs = sorted(f"{left}+{right}" for left, right in self._pairs)
            raise UnknownAlgorithmError(
                f"components {global_id!r} and {local_id!r} both exist, but the "
                f"registry pairs no stack {global_id}+{local_id}; registered pairs: "
                f"{pairs}"
            )
        return stack

    # -- factories, unchanged ------------------------------------------

    def build_global(self, global_id: str, *, episode_seed: int) -> GlobalPlanner:
        self.manifest(global_id)
        return build_global_planner(self._global_backing[global_id], episode_seed=episode_seed)

    def build_local(self, local_id: str, config: dict[str, Any] | None = None) -> LocalPlanner:
        self.manifest(local_id)
        return build_local_planner(self._local_backing[local_id], config)

    def candidate(
        self,
        global_id: str,
        local_id: str,
        *,
        params: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Candidate:
        """The same candidate ``candidate_from_stack`` would build.

        Delegation is the whole point: identity comes from the one
        function every stored candidate_id came from, so the manifest
        path cannot mint a second identity for a known configuration.
        """
        return candidate_from_stack(self.stack_id(global_id, local_id), params=params, **kwargs)

    def build_policy(self, candidate: Candidate, **kwargs: Any):
        """The monolithic door, delegated to the policy registry (A5)."""
        return build_policy(candidate, **kwargs)
