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


def constructor_kwargs(config: BaseModel) -> dict[str, Any]:
    """What to hand the plugin's own constructor.

    **Absent means absent, and ``None`` is how absence survives a round
    trip.** ``exclude_unset`` looks like the right filter and is not: a
    candidate stores its parameters as ``model_dump(mode="json")``, which
    materialises every optional field as ``null``. Replaying those makes
    the fields *set* — to ``None`` — so the filter passes them through
    and the plugin is constructed with ``mu_heading=None``. That is the
    `TypeError: unsupported operand type(s) for +: 'NoneType' and
    'NoneType'` a decision run died on: the controller ran fine from the
    Test Bench, which does not round-trip through stored parameters, and
    only failed once one did.

    Filtering by value instead is not a workaround. A ``config_schema``
    declares JSON types — number, integer, boolean, string — and none of
    them has ``null`` as a meaningful value, so ``null`` can only mean
    "not specified". The plugin's own default is then the right answer,
    and it is the only place that default exists: reading it would mean
    importing plugin code, which discovery may not do.
    """
    return {name: value for name, value in config.model_dump().items() if value is not None}


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
        settings = constructor_kwargs(config)
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


def controller_configs_for(plugin_id: str, config_schema: dict[str, Any]) -> dict[str, dict]:
    """The one named configuration an imported controller starts with.

    **A configuration has to exist or the controller cannot be run at
    all.** Registration takes a *name*, not a parameter dict, because a
    name is what a report quotes and what two runs are compared under —
    so a controller with no named configuration is one the Test Bench
    offers and then refuses to start, which is exactly what an imported
    plugin did until this existed.

    The name is prefixed with the plugin's id because names are unique
    across controllers, not within them: two imported plugins would
    otherwise both want to be called ``defaults``.

    **The parameters are whatever the manifest declares as defaults, and
    nothing more.** The real defaults live in the plugin's constructor,
    and reading them would mean importing plugin code — the one thing
    discovery may not do. So a schema that declares no ``default`` yields
    an empty parameter set: honest, and it hashes as what it is. An
    author who wants their parameters recorded in the report declares
    them in ``config_schema``, which is the only surface the platform
    reads.
    """
    declared = {
        name: spec["default"]
        for name, spec in (config_schema.get("properties") or {}).items()
        if isinstance(spec, dict) and "default" in spec
    }
    return {f"{plugin_id}_defaults": declared}


def stack_id_for(plugin_id: str, global_planner: str) -> str:
    """The id this pairing is measured and recorded under.

    ``<global>+<local>`` like every other stack, and the plugin's own id
    on the right of the ``+`` rather than a prettier alias: it is what
    the candidate hashes on, so a display name here would be a second
    identity nobody could resolve later.
    """
    return f"{global_planner}+{plugin_id}"


def offerable_global_planners() -> tuple[str, ...]:
    """The global planners an imported controller can be paired with.

    Read from the **built-in** registry rather than from
    ``list_algorithms()``: the latter now includes imported stacks, and a
    plugin whose own pairing widened the set it is being paired against
    would be deciding its own catalogue.

    A planner qualifies when some offerable built-in stack uses it *and*
    that planner has a ``+dwa`` pairing to borrow the global half from —
    the second condition is not pedantry, it is where the global factory
    and the observation class come from.
    """
    from planbench_benchmark.registry import ALGORITHMS

    planners = {
        entry.info.global_planner
        for entry in ALGORITHMS.values()
        if entry.info.benchmarkable
    }
    return tuple(sorted(p for p in planners if f"{p}+dwa" in ALGORITHMS))


def build_plugin_entries(
    manifest_data: dict[str, Any],
    *,
    directory: Path,
    description: str = "",
    controller_version: str = "",
) -> list:
    """One entry per global planner this controller can be paired with.

    **A local controller is not tied to a global planner, and the
    manifest does not claim otherwise.** It declares
    ``requires_global_path``, which says "I follow a path somebody
    else planned" — not who planned it. Registering against one planner
    was a default this module invented, and it showed: an imported
    controller was absent from the picker the moment somebody chose
    RRT*, with nothing on screen to say why.

    Each pairing is its own stack and therefore its own candidate, which
    is correct: the same controller behind A* and behind RRT* is two
    experiments, and the platform has always modelled that by making
    ``astar+dwa`` and ``rrtstar+dwa`` separate entries.
    """
    return [
        build_plugin_entry(
            manifest_data,
            directory=directory,
            description=description,
            global_planner=planner,
            controller_version=controller_version,
        )
        for planner in offerable_global_planners()
    ]


def build_plugin_entry(
    manifest_data: dict[str, Any],
    *,
    directory: Path,
    description: str = "",
    global_planner: str = "astar",
    controller_version: str = "",
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
        # The uploaded bytes, so re-importing a fixed bundle produces a
        # different candidate rather than overwriting the old one's
        # identity. Falls back to the manifest's own version only when a
        # caller has no checksum to give: a number a person maintains is
        # a number a person forgets, and the failure is silent.
        controller_version=controller_version or f"v{manifest.version}",
        controller_configs=controller_configs_for(manifest.id, manifest.config_schema),
    )


__all__ = [
    "CLASS_FOR_REQUIREMENTS",
    "DEFAULT_CONTROL_PERIOD_S",
    "NEUTRAL_REQUIREMENTS",
    "PluginStackError",
    "build_local_factory",
    "build_plugin_entries",
    "build_plugin_entry",
    "config_model_for",
    "constructor_kwargs",
    "controller_configs_for",
    "observation_class_for",
    "offerable_global_planners",
    "stack_id_for",
]
