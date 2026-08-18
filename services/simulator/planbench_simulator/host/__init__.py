"""AlgorithmHost (H2): mediation between the loop and the algorithms.

The simulation loop keeps calling the two ABCs it has always called;
behind them a facade turns each call into an SDK request, the host
applies its guardrails (crash → safe outcome, invalid output → safe
stop, deadline bookkeeping), and a legacy adapter hands the request to
the unchanged planner. Byte-level parity with the pre-host runtime is
pinned by ``tests/test_host_parity_golden.py``.
"""

from planbench_simulator.host.algorithm_host import (
    AlgorithmHost,
    HostPluginError,
    HostStats,
)
from planbench_simulator.host.channel_bundle import (
    AuthorizedChannelBundle,
    CadenceMonitor,
    CapabilityRegistry,
    CapabilitySpec,
    ChannelContractError,
    UndeclaredChannelError,
)
from planbench_simulator.host.compatibility import (
    CompatibilityReport,
    HostSupport,
    ProviderOwnership,
    RegistrationState,
    resolve_compatibility,
)
from planbench_simulator.host.discovery import (
    ENTRY_POINT_GROUP,
    DiscoveredPlugin,
    PluginRegistry,
    QuarantinedPlugin,
)
from planbench_simulator.host.facades import (
    HostBackedGlobalPlanner,
    HostBackedLocalPlanner,
    host_backed_planners,
    host_backed_policy,
)
from planbench_simulator.host.fairness_policy import (
    EvidenceClass,
    FairnessPolicy,
    FairnessViolation,
    meet,
    provenance_class,
)
from planbench_simulator.host.freshness import (
    FreshnessFilter,
    FreshnessPolicy,
    StaleChannelError,
)
from planbench_simulator.host.graph_source import (
    GraphBackedLocalPlanner,
    GraphChannelSource,
)
from planbench_simulator.host.latency import (
    HOST_MEASURED,
    LATENCY_LAYERS,
    PLUGIN_REPORTED,
    LatencyLedger,
)
from planbench_simulator.host.legacy_global import LegacyGlobalPlugin
from planbench_simulator.host.legacy_local import LegacyLocalPlugin
from planbench_simulator.host.legacy_policy import LegacyPolicyPlugin
from planbench_simulator.host.lifecycle import (
    GRID_CHANNEL,
    OBSERVATION_CHANNEL,
    HostedGlobalPlugin,
    HostedLocalPlugin,
    channel_payload,
)
from planbench_simulator.host.provider_graph import (
    GraphResolution,
    ProviderGraph,
    ProviderGraphError,
)
from planbench_simulator.host.providers import (
    Provider,
    ProviderError,
    builtin_providers,
    builtin_registry,
)
from planbench_simulator.host.runtime_view import (
    OracleAccessDenied,
    ProviderRuntimeView,
    register_trusted_oracle,
)
from planbench_simulator.host.runtimes import (
    RuntimeLoadError,
    SubprocessPlugin,
    SubprocessRuntime,
    TrustedPythonRuntime,
    UnencodableRequest,
)

__all__ = [
    "ENTRY_POINT_GROUP",
    "GRID_CHANNEL",
    "OBSERVATION_CHANNEL",
    "AlgorithmHost",
    "DiscoveredPlugin",
    "HOST_MEASURED",
    "LATENCY_LAYERS",
    "PLUGIN_REPORTED",
    "FreshnessFilter",
    "FreshnessPolicy",
    "LatencyLedger",
    "PluginRegistry",
    "QuarantinedPlugin",
    "RuntimeLoadError",
    "StaleChannelError",
    "SubprocessPlugin",
    "SubprocessRuntime",
    "TrustedPythonRuntime",
    "UnencodableRequest",
    "AuthorizedChannelBundle",
    "CadenceMonitor",
    "CapabilityRegistry",
    "CapabilitySpec",
    "ChannelContractError",
    "CompatibilityReport",
    "EvidenceClass",
    "FairnessPolicy",
    "FairnessViolation",
    "GraphBackedLocalPlanner",
    "GraphChannelSource",
    "GraphResolution",
    "HostBackedGlobalPlanner",
    "HostBackedLocalPlanner",
    "HostPluginError",
    "HostStats",
    "HostSupport",
    "HostedGlobalPlugin",
    "HostedLocalPlugin",
    "LegacyGlobalPlugin",
    "LegacyLocalPlugin",
    "LegacyPolicyPlugin",
    "OracleAccessDenied",
    "Provider",
    "ProviderError",
    "ProviderGraph",
    "ProviderGraphError",
    "ProviderOwnership",
    "ProviderRuntimeView",
    "RegistrationState",
    "UndeclaredChannelError",
    "builtin_providers",
    "builtin_registry",
    "channel_payload",
    "host_backed_planners",
    "host_backed_policy",
    "meet",
    "provenance_class",
    "register_trusted_oracle",
    "resolve_compatibility",
]
