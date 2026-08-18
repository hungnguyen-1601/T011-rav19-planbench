"""planbench_plugin_sdk — the contract a plugin author writes against.

H1a of the Algorithm Host plan: static manifests, capability references
with the v1 alias bridge, requirement sets, channel envelopes and the
versioned request/response shapes. No host, no engine, no I/O beyond
reading a JSON file — a plugin depends on this package and nothing else
in the repository.
"""

from planbench_plugin_sdk.capabilities import (
    BUILTIN_CHANNEL_URIS,
    V1_TOKEN_TO_URI,
    CapabilityRef,
    canonical_requirement,
    canonical_requirements,
    is_builtin,
)
from planbench_plugin_sdk.channels import Cadence, ChannelEnvelope, Provenance
from planbench_plugin_sdk.conformance import (
    ConformanceReport,
    Finding,
    check_declarations,
    check_global_plugin,
    check_local_plugin,
)
from planbench_plugin_sdk.errors import (
    DuplicatePluginError,
    IncompatibleProtocolError,
    ManifestError,
    PluginSDKError,
    UnknownCapabilityError,
)
from planbench_plugin_sdk.manifest import (
    MANIFEST_FILENAME,
    ManifestIndex,
    PluginManifest,
    load_manifest,
    manifest_checksum,
    parse_manifest,
)
from planbench_plugin_sdk.protocol_version import PLUGIN_API_VERSION, is_compatible
from planbench_plugin_sdk.requests import (
    GlobalPlanRequest,
    LocalResetRequest,
    LocalStepRequest,
)
from planbench_plugin_sdk.requirements import RequirementSet
from planbench_plugin_sdk.responses import GlobalPlanResponse, LocalStepResponse

__all__ = [
    "BUILTIN_CHANNEL_URIS",
    "MANIFEST_FILENAME",
    "PLUGIN_API_VERSION",
    "V1_TOKEN_TO_URI",
    "Cadence",
    "CapabilityRef",
    "ChannelEnvelope",
    "ConformanceReport",
    "DuplicatePluginError",
    "Finding",
    "GlobalPlanRequest",
    "GlobalPlanResponse",
    "IncompatibleProtocolError",
    "LocalResetRequest",
    "LocalStepRequest",
    "LocalStepResponse",
    "ManifestError",
    "ManifestIndex",
    "PluginManifest",
    "PluginSDKError",
    "Provenance",
    "RequirementSet",
    "UnknownCapabilityError",
    "canonical_requirement",
    "canonical_requirements",
    "check_declarations",
    "check_global_plugin",
    "check_local_plugin",
    "is_builtin",
    "is_compatible",
    "load_manifest",
    "manifest_checksum",
    "parse_manifest",
]
