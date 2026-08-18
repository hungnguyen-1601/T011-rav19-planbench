"""Runtime lanes: how a discovered plugin becomes a running object.

H5 builds the second of the three MVP lanes (§5.7). The first — legacy
in-process Python — is the adapter set of H2, which needs no loading
because the registry already holds factories. This package is the lane
for plugins the platform did not write.
"""

from planbench_simulator.host.latency import (
    HOST_MEASURED,
    LATENCY_LAYERS,
    PLUGIN_REPORTED,
    LatencyLedger,
)
from planbench_simulator.host.runtimes.subprocess_lane import (
    SubprocessPlugin,
    SubprocessRuntime,
    UnencodableRequest,
    WorkerDied,
)
from planbench_simulator.host.runtimes.trusted_python import (
    RuntimeLoadError,
    TrustedPythonRuntime,
)

__all__ = [
    "HOST_MEASURED",
    "LATENCY_LAYERS",
    "PLUGIN_REPORTED",
    "LatencyLedger",
    "RuntimeLoadError",
    "SubprocessPlugin",
    "SubprocessRuntime",
    "TrustedPythonRuntime",
    "UnencodableRequest",
    "WorkerDied",
]
