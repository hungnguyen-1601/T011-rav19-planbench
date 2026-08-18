"""``planbench plugins`` — what is installed, and why it will not run.

    python -m planbench_simulator.host.cli list
    python -m planbench_simulator.host.cli check <plugin-id>

The plan's H8 asks for a surface that shows registration state and the
compatibility report, and the reason is in the ADR's consequences: a
plugin may be *registered but not runnable*, so the platform has to be
able to explain that rather than leaving an operator to infer it from
absence.

**Absence is what this exists to prevent.** Without it the only signal
that a plugin is not running is that it is not in the results, and a
missing row looks identical whether the deployment lacks a provider, the
bundle is quarantined, a dependency is uninstalled, or nobody ever
installed the plugin. Those are four different afternoons.

So both commands print the *reason*, and the exit code is usable in CI:
zero when everything asked about can run, one when something cannot.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from planbench_simulator.host.compatibility import HostSupport, resolve_compatibility
from planbench_simulator.host.discovery import PluginRegistry
from planbench_simulator.host.fairness_policy import FairnessPolicy
from planbench_simulator.host.provider_graph import ProviderGraph
from planbench_simulator.host.providers import builtin_providers, builtin_registry


def _registry(bundle_root: str | None, *, entry_points: bool) -> PluginRegistry:
    """Built-ins plus whatever the operator pointed at.

    The built-in manifests come through the benchmark package, imported
    here rather than at module scope so that ``--help`` does not load the
    registry: a command that cannot print its own usage without importing
    the world is a command people stop running.
    """
    from planbench_benchmark.legacy_plugins import discover_all

    return discover_all(bundle_root=bundle_root, include_entry_points=entry_points)


def _graph(*, oracle: bool) -> ProviderGraph:
    return ProviderGraph(builtin_providers(include_oracle=oracle), builtin_registry())


def command_list(args: argparse.Namespace) -> int:
    registry = _registry(args.bundles, entry_points=not args.no_entry_points)
    print(registry.roster() or "no plugins found")
    quarantined = registry.quarantined()
    unrunnable = [p for p in registry.plugins() if not p.runnable_runtime]
    if quarantined or unrunnable:
        print(
            f"\n{len(registry.plugins())} registered, {len(unrunnable)} missing dependencies, "
            f"{len(quarantined)} quarantined"
        )
        return 1
    return 0


def command_check(args: argparse.Namespace) -> int:
    registry = _registry(args.bundles, entry_points=not args.no_entry_points)
    matches = [p for p in registry.plugins() if p.manifest.id == args.plugin_id]
    if not matches:
        known = sorted(p.manifest.id for p in registry.plugins())
        print(f"no plugin {args.plugin_id!r}; discovered: {known}", file=sys.stderr)
        for entry in registry.quarantined():
            print(f"  quarantined {entry.source}: {entry.reason}", file=sys.stderr)
        return 1

    policy = FairnessPolicy.research() if args.research else FairnessPolicy.production()
    graph = _graph(oracle=args.research)
    failed = False
    for plugin in matches:
        report = resolve_compatibility(
            plugin.manifest,
            available_capabilities=frozenset(args.offers),
            graph=graph,
            policy=policy,
            support=HostSupport(),
            # One verdict, not two. Discovery is the only layer that
            # probes the interpreter, so its findings go *into* the
            # state rather than being printed beside a state that
            # contradicts them.
            missing_dependencies=plugin.missing_dependencies,
        )
        print(f"{plugin.manifest.id}@{plugin.manifest.version}")
        print(f"  source            : {plugin.source}")
        print(f"  registration      : {report.state}")
        print(f"  evidence class    : {report.evidence_class}")
        print(f"  runtime lane      : {report.resolved_runtime_profile.get('lane', '?')}")
        if plugin.missing_dependencies:
            print(f"  missing modules   : {list(plugin.missing_dependencies)}")
        print(f"  provider graph    : {list(report.provider_order) or '(none resolved)'}")
        if report.ownership.oracle_owned:
            print(f"  oracle providers  : {[c for c, _ in report.ownership.oracle_owned]}")
        print(f"  why               : {report.explain()}")
        failed = failed or not report.runnable
    return 1 if failed else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="planbench-plugins",
        description="Show which algorithm plugins exist and whether they can run.",
    )
    parser.add_argument(
        "--bundles",
        default=None,
        help="directory of plugin bundles to scan, alongside the built-ins",
    )
    parser.add_argument(
        "--no-entry-points",
        action="store_true",
        help="skip installed distributions (useful when reproducing a report)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    listing = subparsers.add_parser("list", help="every plugin found, runnable or not")
    listing.set_defaults(handler=command_list)

    check = subparsers.add_parser("check", help="the compatibility report for one plugin")
    check.add_argument("plugin_id")
    check.add_argument(
        "--offers",
        nargs="*",
        default=(),
        metavar="CAPABILITY",
        help="capabilities the deployment provides beyond the built-in graph",
    )
    check.add_argument(
        "--research",
        action="store_true",
        help="admit oracle sources; the report says so in its evidence class",
    )
    check.set_defaults(handler=command_check)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.bundles is not None and not Path(args.bundles).is_dir():
        print(f"--bundles {args.bundles!r} is not a directory", file=sys.stderr)
        return 2
    return args.handler(args)


if __name__ == "__main__":  # pragma: no cover - exercised through main()
    raise SystemExit(main())
