"""The static plugin manifest: readable without importing anything.

A manifest is JSON on disk (``.planbench-plugin/plugin.json``). Parsing
it must never execute plugin code — an ImportError, a CUDA load or a
crash in one plugin must not take discovery down (plan §5.1) — so this
module works on parsed JSON and file paths only, and the tests prove it
by parking a booby-trapped module next to a manifest.

What is enforced here, at parse time:

- schema shape (unknown fields refused);
- ``plugin_api`` major compatibility;
- ``runtime.production_lane ∈ supported_lanes``, profile keys likewise —
  the lane a candidate declares is part of its identity (§5.1), so a
  manifest whose declared lane cannot exist is not registrable-but-sick,
  it is malformed;
- every requirement resolves: a v1 token, a built-in channel, or a
  capability **this manifest itself declares** in ``capability_schemas``
  (§5.2 rule 2 with its round-4 exception). Anything else fails loud
  with close matches, because "registered_but_missing_provider" must
  mean missing infrastructure, never a typo;
- a monolithic plugin may not claim to require a global path.

What is deliberately *not* here: provider graphs, runtime availability,
compatibility verdicts. Those need a host and a deployment; this file
only decides whether the text describes a plugin.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from planbench_plugin_sdk.capabilities import (
    CapabilityRef,
    _close_matches,
    is_builtin,
)
from planbench_plugin_sdk.errors import (
    DuplicatePluginError,
    IncompatibleProtocolError,
    ManifestError,
    UnknownCapabilityError,
)
from planbench_plugin_sdk.protocol_version import is_compatible
from planbench_plugin_sdk.requirements import RequirementSet

#: Where a plugin bundle keeps its manifest, by convention.
MANIFEST_FILENAME = "plugin.json"

PluginRole = Literal["global", "local", "monolithic"]

_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_.-]*$")
_DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


class RuntimeProfile(BaseModel):
    """How one lane runs this plugin. Hashed into the resolved runtime
    profile, which is why codec and deadline policy are stated rather
    than assumed (§5.9 rule 4)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    protocol: str = Field(min_length=1)
    codec: str = Field(min_length=1)
    deadline_policy: str = Field(min_length=1)
    #: ``package.module:Attribute`` — what to load **after** preflight
    #: says this plugin may run. A string here, deliberately: discovery
    #: reads it and does not resolve it, which is what keeps a plugin
    #: whose import raises from taking discovery down with it.
    entry_point: str = ""
    #: Top-level modules this lane needs. Checked with ``find_spec``,
    #: which locates without executing — the same trick ``_build_ppo``
    #: already uses to keep torch optional. A missing one leaves the
    #: plugin registered and not runnable, never crashed.
    python_dependencies: tuple[str, ...] = ()


class RuntimeSpec(BaseModel):
    """Which lanes exist for this plugin, and which one production uses."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    supported_lanes: tuple[str, ...] = Field(min_length=1)
    production_lane: str = Field(min_length=1)
    profiles: dict[str, RuntimeProfile] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _lanes_are_consistent(self) -> RuntimeSpec:
        if self.production_lane not in self.supported_lanes:
            raise ValueError(
                f"production_lane {self.production_lane!r} is not in supported_lanes "
                f"{list(self.supported_lanes)}; the lane a candidate is measured in is "
                "part of its identity, so it cannot be a lane the plugin does not have"
            )
        unknown = sorted(set(self.profiles) - set(self.supported_lanes))
        if unknown:
            raise ValueError(
                f"runtime profile(s) {unknown} describe lanes not in supported_lanes "
                f"{list(self.supported_lanes)}"
            )
        return self


class CapabilitySchemaDeclaration(BaseModel):
    """A capability this plugin bundle itself defines (plan §5.1 round 4).

    ``schema_digest`` pins the payload schema: two bundles declaring one
    URI with different digests are two incompatible claims to one name,
    and the registry quarantines rather than picking a winner (H5)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    uri: str
    schema_path: str = Field(alias="schema", min_length=1)
    schema_digest: str
    codecs: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate(self) -> CapabilitySchemaDeclaration:
        CapabilityRef.parse(self.uri)  # syntax, with suggestions on failure
        if is_builtin(self.uri):
            raise ValueError(
                f"{self.uri} is a built-in capability; a plugin cannot redeclare its "
                "schema, only require it"
            )
        if not _DIGEST_PATTERN.match(self.schema_digest):
            raise ValueError(f"schema_digest must be 'sha256:<64 hex>', got {self.schema_digest!r}")
        return self


class BundledManifestRef(BaseModel):
    """A provider or adapter manifest shipped in the bundle — a path,
    never code, so discovery stays import-free."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    manifest: str = Field(min_length=1)


class SupportsSpec(BaseModel):
    """What the plugin can execute against (§5.6). References, open by
    design: an unsupported value registers as incompatible, it does not
    fail parsing."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    action_types: tuple[str, ...] = Field(min_length=1)
    robot_dynamics: tuple[str, ...] = Field(min_length=1)
    execution_models: tuple[str, ...] = Field(min_length=1)


class PluginManifest(BaseModel):
    """One plugin, as its static declaration."""

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    plugin_api: str = Field(min_length=1)
    id: str
    version: str = Field(min_length=1)
    role: PluginRole
    runtime: RuntimeSpec
    requirements: RequirementSet = Field(default_factory=RequirementSet)
    capability_schemas: tuple[CapabilitySchemaDeclaration, ...] = ()
    providers: tuple[BundledManifestRef, ...] = ()
    action_adapters: tuple[BundledManifestRef, ...] = ()
    supports: SupportsSpec
    config_schema: dict[str, Any] = Field(default_factory=dict)
    requires_global_path: bool | None = None

    @model_validator(mode="after")
    def _validate(self) -> PluginManifest:
        if not _ID_PATTERN.match(self.id):
            raise ValueError(
                f"plugin id {self.id!r} must be lowercase [a-z0-9_.-], starting with "
                "a letter or digit — it becomes part of candidate identity"
            )
        if self.role == "monolithic" and self.requires_global_path:
            raise ValueError(
                "a monolithic plugin cannot require a global path: it is one layer "
                "by definition (HĐ-1.2), and the loop hands it none"
            )
        return self

    def declared_capability_uris(self) -> frozenset[str]:
        return frozenset(entry.uri for entry in self.capability_schemas)


def parse_manifest(data: Mapping[str, Any], *, source: str = "<memory>") -> PluginManifest:
    """Dict → manifest, with every H1a refusal applied.

    Split from :func:`load_manifest` so discovery (H5) can parse entries
    it found by other means, and so tests can hit each refusal without a
    filesystem.
    """
    try:
        manifest = PluginManifest.model_validate(data)
    except ValidationError as error:
        raise ManifestError(f"{source}: not a plugin manifest: {error}") from error
    if not is_compatible(manifest.plugin_api):
        raise IncompatibleProtocolError(
            f"{source}: plugin_api {manifest.plugin_api!r} is not this SDK's major; "
            "the manifest cannot be interpreted, not even to quarantine it"
        )
    _check_requirements_resolve(manifest, source)
    return manifest


def _check_requirements_resolve(manifest: PluginManifest, source: str) -> None:
    """§5.2 rule 2, with its one exception.

    A requirement must name a v1 token, a built-in channel, or a
    capability this manifest itself declares. Everything else is
    presumed a typo and refused with close matches — the distinction
    from "declared but no provider in this deployment" is exactly what
    keeps preflight reports readable.
    """
    declared = manifest.declared_capability_uris()
    for reference in manifest.requirements.mentioned():
        if is_builtin(reference) or reference in declared:
            continue
        raise UnknownCapabilityError(
            f"{source}: requirement {reference!r} names a capability that is neither "
            "built in nor declared in this manifest's capability_schemas. If it is "
            "yours, declare its schema; if it is core's, check the spelling.",
            suggestions=_close_matches(reference) + tuple(sorted(declared)),
        )


def manifest_checksum(data: Mapping[str, Any]) -> str:
    """Content identity of a manifest, for duplicate detection.

    Canonical JSON, so key order and whitespace cannot make one manifest
    look like two."""
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def load_manifest(path: Path | str) -> tuple[PluginManifest, str]:
    """Read one manifest file. Returns (manifest, checksum).

    Reads bytes and parses JSON — nothing here imports, executes or even
    globs next to the manifest. A bundle whose Python would crash on
    import parses exactly as well as a healthy one; *running* it is a
    later phase's decision, made after preflight.
    """
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ManifestError(f"{path}: cannot read manifest: {error}") from error
    if not isinstance(data, dict):
        raise ManifestError(f"{path}: a manifest must be a JSON object")
    return parse_manifest(data, source=str(path)), manifest_checksum(data)


class ManifestIndex:
    """Manifests seen so far, keyed by (id, version).

    Re-adding the identical manifest is a no-op — discovery scans
    overlapping directories and must be idempotent. Two *different*
    manifests under one (id, version) fail loud: silently keeping either
    one would make "which code ran" unanswerable, and that question is
    the whole point of candidate identity.
    """

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str], tuple[PluginManifest, str]] = {}

    def add(self, manifest: PluginManifest, checksum: str) -> PluginManifest:
        key = (manifest.id, manifest.version)
        existing = self._entries.get(key)
        if existing is None:
            self._entries[key] = (manifest, checksum)
            return manifest
        if existing[1] == checksum:
            return existing[0]
        raise DuplicatePluginError(
            f"plugin {manifest.id!r} version {manifest.version!r} is claimed by two "
            f"different manifests (checksums {existing[1][:18]}… and {checksum[:18]}…); "
            "bump the version or reconcile the bundles"
        )

    def get(self, plugin_id: str, version: str) -> PluginManifest | None:
        entry = self._entries.get((plugin_id, version))
        return entry[0] if entry else None

    def __len__(self) -> int:
        return len(self._entries)

    def manifests(self) -> tuple[PluginManifest, ...]:
        return tuple(entry[0] for entry in self._entries.values())
