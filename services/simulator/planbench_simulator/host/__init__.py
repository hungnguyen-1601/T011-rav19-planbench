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
from planbench_simulator.host.facades import (
    HostBackedGlobalPlanner,
    HostBackedLocalPlanner,
    host_backed_planners,
    host_backed_policy,
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

__all__ = [
    "GRID_CHANNEL",
    "OBSERVATION_CHANNEL",
    "AlgorithmHost",
    "HostBackedGlobalPlanner",
    "HostBackedLocalPlanner",
    "HostPluginError",
    "HostStats",
    "HostedGlobalPlugin",
    "HostedLocalPlugin",
    "LegacyGlobalPlugin",
    "LegacyLocalPlugin",
    "LegacyPolicyPlugin",
    "channel_payload",
    "host_backed_planners",
    "host_backed_policy",
]
