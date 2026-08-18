"""Finding plugins without running them (H5).

Three sources, one registry: manifests handed in (the built-in stacks,
as synthetic manifests from H1b), bundle directories on disk, and Python
entry points. All three end in the same place, because "which plugins
exist" must have one answer — a built-in that were discovered by a
different mechanism than an installed one would drift from it, and the
first symptom would be a report that lists different things than the
runner can run.

**Nothing here imports plugin code, and that is the load-bearing
property** (§5.1). Entry points are read as *strings*: ``importlib
.metadata`` knows a distribution's declared entry points without
importing the module they name, and this module never resolves them.
Dependencies are checked with ``find_spec``, which locates a module
without executing it — the same trick the PPO factory has always used to
keep torch optional.

So a bundle whose Python raises on import is discovered exactly as well
as a healthy one, and the failure surfaces where it can be reported:
against that plugin, at load time, after preflight said it was allowed
to run at all.

**A bad manifest is quarantined, never fatal.** One malformed plugin in
a directory of ten must not cost the other nine — and the reason travels
with the entry, because "eleven plugins found, one unusable, here is
why" is an answer, while a discovery that died is not.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from importlib.util import find_spec
from pathlib import Path
from typing import Any

from planbench_plugin_sdk import (
    MANIFEST_FILENAME,
    DuplicatePluginError,
    ManifestIndex,
    PluginManifest,
    PluginSDKError,
    load_manifest,
    manifest_checksum,
    parse_manifest,
)

#: Where a bundle keeps its manifest inside its own directory.
BUNDLE_DIRNAME = ".planbench-plugin"

#: The entry-point group a distribution advertises a plugin under.
ENTRY_POINT_GROUP = "planbench.plugins"


@dataclass(frozen=True)
class DiscoveredPlugin:
    """One plugin found, with where it came from and whether it can run.

    ``runnable_runtime`` answers only the *runtime* half of the question
    — are this lane's dependencies importable. Whether the deployment
    provides its capabilities is preflight's half
    (``resolve_compatibility``), and the two are kept apart because they
    send whoever reads them to different fixes: ``pip install`` versus
    declaring a provider.
    """

    manifest: PluginManifest
    checksum: str
    source: str
    runnable_runtime: bool = True
    missing_dependencies: tuple[str, ...] = ()


@dataclass(frozen=True)
class QuarantinedPlugin:
    """Something that claimed to be a plugin and could not be read."""

    source: str
    reason: str


class PluginRegistry:
    """Everything discovered, quarantine included."""

    def __init__(self, *, dependency_probe: Callable[[str], bool] | None = None) -> None:
        #: Injected so a test can describe an environment without
        #: installing packages into it. Defaults to ``find_spec``, which
        #: locates a module without executing it.
        self._has_module = dependency_probe or _module_is_available
        self._index = ManifestIndex()
        self._found: dict[tuple[str, str], DiscoveredPlugin] = {}
        self._quarantined: list[QuarantinedPlugin] = []

    # -- sources -------------------------------------------------------

    def add_manifests(self, manifests: Iterable[Mapping[str, Any]], *, source: str) -> None:
        """Register manifests already in hand — the built-in synthetic
        ones, which reach the same registry as everything else so the
        roster has one shape."""
        for data in manifests:
            self._admit(data, source=f"{source}:{data.get('id', '?')}")

    def discover_directory(self, root: Path | str) -> None:
        """Every ``<bundle>/.planbench-plugin/plugin.json`` under ``root``.

        Sorted, so two machines scanning one directory agree on order and
        therefore on which duplicate is reported against which.
        """
        root = Path(root)
        if not root.is_dir():
            return
        for path in sorted(root.glob(f"*/{BUNDLE_DIRNAME}/{MANIFEST_FILENAME}")):
            try:
                manifest, checksum = load_manifest(path)
            except PluginSDKError as error:
                self._quarantined.append(QuarantinedPlugin(source=str(path), reason=str(error)))
                continue
            self._record(manifest, checksum, source=str(path))

    def discover_entry_points(self, entry_points: Iterable[Any] | None = None) -> None:
        """Plugins advertised by installed distributions.

        The entry point's *value* is read, never resolved: an entry point
        names a module, and importing it to find out what it declares is
        exactly the thing §5.1 forbids. The manifest is located inside
        the distribution's own files instead.
        """
        for entry in entry_points if entry_points is not None else _entry_points():
            source = f"entry-point:{getattr(entry, 'name', '?')}"
            try:
                path = _manifest_path_for(entry)
            except Exception as error:  # noqa: BLE001 - a broken install must not be fatal
                self._quarantined.append(
                    QuarantinedPlugin(source=source, reason=f"cannot locate manifest: {error!r}")
                )
                continue
            if path is None:
                self._quarantined.append(
                    QuarantinedPlugin(
                        source=source,
                        reason=(
                            f"advertises {ENTRY_POINT_GROUP} but ships no "
                            f"{BUNDLE_DIRNAME}/{MANIFEST_FILENAME}"
                        ),
                    )
                )
                continue
            try:
                manifest, checksum = load_manifest(path)
            except PluginSDKError as error:
                self._quarantined.append(QuarantinedPlugin(source=source, reason=str(error)))
                continue
            self._record(manifest, checksum, source=source)

    # -- admission -----------------------------------------------------

    def _admit(self, data: Mapping[str, Any], *, source: str) -> None:
        try:
            manifest = parse_manifest(data, source=source)
        except PluginSDKError as error:
            self._quarantined.append(QuarantinedPlugin(source=source, reason=str(error)))
            return
        self._record(manifest, manifest_checksum(data), source=source)

    def _record(self, manifest: PluginManifest, checksum: str, *, source: str) -> None:
        try:
            self._index.add(manifest, checksum)
        except DuplicatePluginError as error:
            self._quarantined.append(QuarantinedPlugin(source=source, reason=str(error)))
            return
        key = (manifest.id, manifest.version)
        if key in self._found:
            return  # the identical manifest, seen through two sources
        missing = self._missing_dependencies(manifest)
        self._found[key] = DiscoveredPlugin(
            manifest=manifest,
            checksum=checksum,
            source=source,
            runnable_runtime=not missing,
            missing_dependencies=missing,
        )

    def _missing_dependencies(self, manifest: PluginManifest) -> tuple[str, ...]:
        """What the production lane needs and this interpreter lacks.

        Only the production lane is checked. A plugin that also supports
        a subprocess lane it will not be measured in should not be marked
        unrunnable because that lane's dependencies are absent.
        """
        profile = manifest.runtime.profiles.get(manifest.runtime.production_lane)
        if profile is None:
            return ()
        return tuple(
            module for module in profile.python_dependencies if not self._has_module(module)
        )

    # -- reading -------------------------------------------------------

    def plugins(self) -> tuple[DiscoveredPlugin, ...]:
        return tuple(self._found[key] for key in sorted(self._found))

    def runnable(self) -> tuple[DiscoveredPlugin, ...]:
        return tuple(plugin for plugin in self.plugins() if plugin.runnable_runtime)

    def quarantined(self) -> tuple[QuarantinedPlugin, ...]:
        return tuple(self._quarantined)

    def get(self, plugin_id: str, version: str) -> DiscoveredPlugin | None:
        return self._found.get((plugin_id, version))

    def roster(self) -> str:
        """One line per plugin, for the operator-facing view of H8.

        Quarantined entries are listed too. A roster that showed only
        what worked would answer "what can I run" while hiding "what did
        I install that is not working", and the second question is the
        one somebody is asking when they read this.
        """
        lines = []
        for plugin in self.plugins():
            status = (
                "runnable"
                if plugin.runnable_runtime
                else f"missing {list(plugin.missing_dependencies)}"
            )
            lines.append(
                f"{plugin.manifest.id}@{plugin.manifest.version} [{status}] via {plugin.source}"
            )
        lines += [f"QUARANTINED {entry.source}: {entry.reason}" for entry in self._quarantined]
        return "\n".join(lines)


def _module_is_available(module: str) -> bool:
    """Is this module importable, without importing it.

    ``find_spec`` raises rather than returning None when a *parent*
    package is itself missing, which is a "no" wearing an exception.
    """
    try:
        return find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def _entry_points() -> tuple[Any, ...]:
    from importlib.metadata import entry_points

    return tuple(entry_points(group=ENTRY_POINT_GROUP))


def _manifest_path_for(entry: Any) -> Path | None:
    """Where an entry point's distribution keeps its manifest.

    Resolved through the distribution's file list rather than by
    importing the package: ``importlib.resources`` would import it, and
    an import is the one thing discovery may not do.
    """
    dist = getattr(entry, "dist", None)
    if dist is None:
        return None
    package = entry.value.split(":")[0].split(".")[0]
    candidate = dist.locate_file(f"{package}/{BUNDLE_DIRNAME}/{MANIFEST_FILENAME}")
    path = Path(str(candidate))
    return path if path.is_file() else None
