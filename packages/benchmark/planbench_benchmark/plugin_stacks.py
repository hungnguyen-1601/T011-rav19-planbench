"""Imported plugins, as stacks the rest of the platform can name.

``ALGORITHMS`` is a dict written in source, and every stack in it exists
because somebody added a line to it. A plugin arrives after the process
has started, so it cannot. This module is the second source: it builds
the same ``_Entry`` the registry stores, from a manifest instead of from
a literal, and registers it beside the built-ins.

**Two sources, said out loud.** The alternative was to make the built-ins
plugins too, so there would be one path — architecturally the right
answer, and a refactor that touches every stack currently running. This
takes the smaller step and is honest about the shape it leaves: a
catalogue that is the union of a dict and a registry, with one lookup
consulting both.

**Nothing here is guessed from a plugin id.** The observation class, the
config schema, whether a global path is required — each comes from the
manifest or the entry is refused. The one thing a manifest cannot state
is which built-in global planner it should be paired with, and that is a
caller's choice rather than a default this module invents.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, create_model

from planbench_planning.common.local_base import LocalPlanner

#: Requirement tokens that carry no observation-class meaning: every
#: stack consumes them implicitly, so a plugin naming one is not thereby
#: seeing more than a built-in does. Kept as an explicit list rather than
#: "anything with a URI" so that a new channel has to be classified by a
#: person before a candidate can declare it.
NEUTRAL_REQUIREMENTS = frozenset(
    {
        "planbench://channel/robot-state@1",
        "planbench://channel/global-path@1",
        "planbench://channel/legacy-observation@1",
    }
)

#: The inverse of ``legacy_plugins._CLASS_REQUIREMENTS``. Stated as its
#: own mapping and pinned by a test against that one: deriving it at
#: import time would make a typo in either look like agreement.
CLASS_FOR_REQUIREMENTS: dict[frozenset[str], str] = {
    frozenset(): "full_static_map",
    frozenset({"lidar_2d"}): "lidar_only",
    frozenset({"human_state_estimates"}): "human_states",
    frozenset({"lidar_2d", "human_state_estimates"}): "lidar+human_states",
}

#: The deployment's cycle time, used as the lane's deadline. Matches the
#: value every built-in controller config carries; a plugin measured
#: against a different one would be measured against a different robot.
DEFAULT_CONTROL_PERIOD_S = 0.05


class PluginStackError(ValueError):
    """A manifest that cannot be turned into a stack this platform runs."""


def observation_class_for(requirements: tuple[str, ...]) -> str:
    """What a plugin declaring these requirements is allowed to see.

    Refuses rather than defaults. ``AlgorithmInfo`` deliberately gives
    the observation classes no default, and the reason applies twice as
    hard here: the worst outcome is not an unlabelled candidate but a
    wrongly labelled one, where a leaderboard looks fair while comparing
    a sensing planner against one reading ground truth.
    """
    graded = frozenset(requirements) - NEUTRAL_REQUIREMENTS
    try:
        return CLASS_FOR_REQUIREMENTS[graded]
    except KeyError:
        raise PluginStackError(
            f"requirements {sorted(graded)} do not map to an observation class. "
            "P02 prices what a candidate may see, and a stack whose sensing cannot be "
            "stated cannot be compared with one whose can"
        ) from None


def config_model_for(plugin_id: str, config_schema: dict[str, Any]) -> type[BaseModel]:
    """A validation model from the manifest's own ``config_schema``.

    Every field is optional and unset fields are never forwarded, so a
    plugin's constructor defaults stay the plugin's. ``extra='forbid'``
    because a key the manifest does not declare is a typo, and forwarding
    it would reach the constructor as an unexpected keyword — a crash at
    the first episode instead of a refusal at configuration time.
    """
    types: dict[str, Any] = {
        "number": float,
        "integer": int,
        "boolean": bool,
        "string": str,
    }
    fields: dict[str, Any] = {}
    for name, spec in (config_schema.get("properties") or {}).items():
        declared = spec.get("type") if isinstance(spec, dict) else None
        fields[name] = (types.get(declared, Any) | None, None)
    fields["control_period"] = (
        float,
        Field(
            default=DEFAULT_CONTROL_PERIOD_S,
            gt=0,
            description=(
                "The deployment's cycle time. The lane enforces it as a deadline, so it "
                "belongs to the robot being modelled rather than to the plugin."
            ),
        ),
    )
    return create_model(
        f"PluginConfig_{plugin_id.replace('.', '_').replace('-', '_')}",
        __config__=ConfigDict(extra="forbid"),
        **fields,
    )


def build_local_factory(manifest_data: dict[str, Any], directory: Path):
    """A factory that starts the plugin in a subprocess when called.

    The whole chain is built here rather than at registration time
    because it must be per-episode: a worker process is episode state,
    and one shared across a sweep would carry a controller's memory from
    one episode into the next.
    """

    def factory(config: BaseModel) -> LocalPlanner:
        from planbench_plugin_sdk import parse_manifest

        from planbench_simulator.host.algorithm_host import AlgorithmHost
        from planbench_simulator.host.compatibility import HostSupport, resolve_compatibility
        from planbench_simulator.host.fairness_policy import FairnessPolicy
        from planbench_simulator.host.graph_source import (
            GraphBackedLocalPlanner,
            GraphChannelSource,
        )
        from planbench_simulator.host.provider_graph import ProviderGraph
        from planbench_simulator.host.providers import builtin_providers, builtin_registry
        from planbench_simulator.host.runtimes.subprocess_lane import SubprocessRuntime

        manifest = parse_manifest(manifest_data, source=str(directory))
        settings = config.model_dump(exclude_unset=True)
        control_period = float(
            settings.pop("control_period", None) or DEFAULT_CONTROL_PERIOD_S
        )

        graph = ProviderGraph(builtin_providers(include_oracle=False), builtin_registry())
        report = resolve_compatibility(
            manifest,
            available_capabilities=frozenset(),
            graph=graph,
            policy=FairnessPolicy.production(),
            support=HostSupport(),
        )
        if not report.runnable:
            raise PluginStackError(
                f"{manifest.id!r} cannot run on this deployment: {report.explain()}"
            )
        plugin = SubprocessRuntime(search_paths=(str(directory),)).load(
            manifest, report, settings, control_period_s=control_period
        )
        source = GraphChannelSource(graph)
        return GraphBackedLocalPlanner(
            AlgorithmHost(local_plugin=plugin),
            source,
            granted=tuple(manifest.requirements.all_of) + tuple(manifest.requirements.optional),
        )

    return factory


def stack_id_for(plugin_id: str, global_planner: str) -> str:
    """The id this pairing is measured and recorded under.

    ``<global>+<local>`` like every other stack, and the plugin's own id
    on the right of the ``+`` rather than a prettier alias: it is what
    the candidate hashes on, so a display name here would be a second
    identity nobody could resolve later.
    """
    return f"{global_planner}+{plugin_id}"


def build_plugin_entry(
    manifest_data: dict[str, Any],
    *,
    directory: Path,
    description: str = "",
    global_planner: str = "astar",
):
    """One registry entry for one imported plugin, paired with a global.

    Returns the same ``_Entry`` shape the built-ins use, so everything
    downstream — identity, preflight, the runner — keeps one code path.
    """
    from planbench_plugin_sdk import parse_manifest

    from planbench_benchmark.registry import ALGORITHMS, AlgorithmInfo, _Entry

    manifest = parse_manifest(manifest_data, source=str(directory))
    if manifest.role not in {"local", "monolithic"}:
        raise PluginStackError(
            f"role {manifest.role!r} is not a controller; only a local or monolithic "
            "plugin can be paired with a global planner"
        )
    backing = ALGORITHMS.get(f"{global_planner}+dwa")
    if backing is None:
        raise PluginStackError(
            f"no built-in stack uses global planner {global_planner!r} to borrow it from"
        )

    requirements = tuple(manifest.requirements.all_of) + tuple(manifest.requirements.optional)
    info = AlgorithmInfo(
        id=stack_id_for(manifest.id, global_planner),
        kind="stack",
        description=description
        or f"Imported plugin {manifest.id}@{manifest.version}, run in the subprocess lane.",
        config_schema=manifest.config_schema,
        global_planner=global_planner,
        local_controller=manifest.id,
        stochastic_global_planner=backing.info.stochastic_global_planner,
        requires_model=False,
        global_observation_class=backing.info.global_observation_class,
        local_observation_class=observation_class_for(requirements),
        requires_global_path=bool(manifest.requires_global_path),
    )
    return _Entry(
        info=info,
        config_model=config_model_for(manifest.id, manifest.config_schema),
        factory=build_local_factory(manifest_data, directory),
        # The global half is the built-in's, unchanged: pairing an
        # imported controller with A* must measure the same A* every
        # other candidate ran, or the comparison is between two things
        # at once.
        global_factory=backing.global_factory,
    )


__all__ = [
    "CLASS_FOR_REQUIREMENTS",
    "DEFAULT_CONTROL_PERIOD_S",
    "NEUTRAL_REQUIREMENTS",
    "PluginStackError",
    "build_local_factory",
    "build_plugin_entry",
    "config_model_for",
    "observation_class_for",
    "stack_id_for",
]
