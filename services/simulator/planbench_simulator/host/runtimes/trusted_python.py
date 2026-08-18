"""The trusted in-process lane: import late, and only when allowed.

**Loading is the first moment plugin code runs**, and everything before
it — discovery, preflight — is arranged so that moment can be refused.
This class enforces the ordering rather than trusting callers to observe
it: :meth:`load` demands a compatibility report that says runnable, so
"we imported it and then found out it could not run" is not reachable.

**Trusted is a policy word, not a security word** (§5.7). Code imported
into this process can reach anything this process can: monkeypatch the
engine, walk ``gc`` for a runtime view, read the truth closure a
provider was refused. The guard rails here are conformance checks, not
a sandbox, and the honest name for what they buy is *a wrong plugin
fails loudly instead of silently*. A plugin nobody trusts does not run
in this lane; that is what H7's subprocess is for, and no amount of
checking here substitutes for it.

The conformance check is deliberately structural rather than
behavioural: does the loaded object present the methods its declared
role needs. Whether it *navigates* is what the benchmark measures, and a
loader that tried to pre-judge that would be running episodes at import
time.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

from planbench_plugin_sdk import PluginManifest

from planbench_simulator.host.compatibility import CompatibilityReport

#: What each role must present to be driven by the host.
_REQUIRED_METHODS: dict[str, tuple[str, ...]] = {
    "global": ("plan",),
    "local": ("reset", "step"),
    "monolithic": ("reset", "step"),
}


class RuntimeLoadError(RuntimeError):
    """A plugin could not be turned into a running object."""


class TrustedPythonRuntime:
    """Loads a plugin into this process, once preflight has allowed it."""

    lane = "python_in_process"

    def load(
        self,
        manifest: PluginManifest,
        report: CompatibilityReport,
        config: dict[str, Any] | None = None,
    ) -> Any:
        """Import the entry point and build the plugin.

        Raises rather than returning a broken object: a caller that got
        ``None`` back would discover the failure at the first control
        tick, inside an episode that has already started recording.
        """
        if not report.runnable:
            raise RuntimeLoadError(
                f"refusing to load {manifest.id!r}: preflight says {report.state} "
                f"({report.explain()}). Importing it to find out would run plugin code "
                "the host has already decided may not run"
            )
        if manifest.runtime.production_lane != self.lane:
            raise RuntimeLoadError(
                f"{manifest.id!r} declares production lane "
                f"{manifest.runtime.production_lane!r}; this runtime is {self.lane!r}, "
                "and loading it here would measure a lane the plugin did not declare"
            )

        target = self._entry_point(manifest)
        factory = self._resolve(manifest, target)
        try:
            plugin = factory(**(config or {}))
        except Exception as error:  # noqa: BLE001 - the plugin's constructor is foreign code
            raise RuntimeLoadError(
                f"{manifest.id!r} raised while being constructed: {error!r}"
            ) from error
        self._check_conformance(manifest, plugin)
        return plugin

    # -- internals -----------------------------------------------------

    def _entry_point(self, manifest: PluginManifest) -> str:
        profile = manifest.runtime.profiles.get(self.lane)
        target = profile.entry_point if profile else ""
        if not target:
            raise RuntimeLoadError(
                f"{manifest.id!r} declares no entry_point for the {self.lane!r} lane; "
                "discovery reads that string and this runtime is the only thing that "
                "resolves it, so without it there is nothing to load"
            )
        return target

    def _resolve(self, manifest: PluginManifest, target: str) -> Any:
        module_name, _, attribute = target.partition(":")
        if not attribute:
            raise RuntimeLoadError(
                f"{manifest.id!r} entry_point {target!r} must be 'module:Attribute'"
            )
        try:
            module = import_module(module_name)
        except Exception as error:  # noqa: BLE001 - foreign import, any exception is possible
            raise RuntimeLoadError(
                f"{manifest.id!r} could not be imported ({module_name!r}): {error!r}. "
                "Discovery deliberately did not do this, so the failure lands here, "
                "against this plugin, instead of taking the roster down"
            ) from error
        try:
            return getattr(module, attribute)
        except AttributeError as error:
            raise RuntimeLoadError(
                f"{manifest.id!r} names {attribute!r} in {module_name!r}, which has no "
                "such attribute"
            ) from error

    def _check_conformance(self, manifest: PluginManifest, plugin: Any) -> None:
        missing = [
            name
            for name in _REQUIRED_METHODS[manifest.role]
            if not callable(getattr(plugin, name, None))
        ]
        if missing:
            raise RuntimeLoadError(
                f"{manifest.id!r} declares role {manifest.role!r} but the loaded object "
                f"has no {missing}; the host drives a role through those methods, and a "
                "missing one would surface as an AttributeError mid-episode"
            )
        if not getattr(plugin, "name", None):
            raise RuntimeLoadError(
                f"{manifest.id!r} loaded an object with no ``name``; every trace and "
                "report identifies a candidate by it"
            )
