"""Built-in providers, and the capability specs that describe them.

:func:`builtin_registry` is the single place the platform states what a
built-in channel *is* — cadence, codec, frame — so the graph can refuse
a provider whose output contradicts its own capability before a plugin
becomes the first thing to notice.
"""

from planbench_simulator.host.channel_bundle import CapabilityRegistry, CapabilitySpec
from planbench_simulator.host.providers.base import Provider, ProviderError
from planbench_simulator.host.providers.ground_truth_tracks import (
    HUMAN_STATE_ESTIMATES,
    GroundTruthTrackProvider,
)
from planbench_simulator.host.providers.legacy_observation import (
    LEGACY_OBSERVATION,
    LegacyObservationProvider,
)
from planbench_simulator.host.providers.lidar_2d import LIDAR_2D, Lidar2DProvider
from planbench_simulator.host.providers.robot_state import ROBOT_STATE, RobotStateProvider
from planbench_simulator.host.providers.static_costmap import (
    STATIC_COSTMAP,
    StaticCostmapProvider,
)

#: What each built-in capability is. Payload digests are empty because a
#: built-in payload *is* a validated platform model — see
#: ``CapabilitySpec.schema_digest``.
BUILTIN_SPECS: tuple[CapabilitySpec, ...] = (
    CapabilitySpec(capability=ROBOT_STATE, cadence="per_tick"),
    CapabilitySpec(capability=LEGACY_OBSERVATION, cadence="per_tick"),
    CapabilitySpec(capability=LIDAR_2D, cadence="per_tick", frame_id="robot"),
    CapabilitySpec(capability=STATIC_COSTMAP, cadence="static"),
    CapabilitySpec(capability=HUMAN_STATE_ESTIMATES, cadence="per_tick"),
)


def builtin_registry() -> CapabilityRegistry:
    """A registry holding every built-in capability spec."""
    return CapabilityRegistry(BUILTIN_SPECS)


def builtin_providers(*, include_oracle: bool = False) -> tuple[Provider, ...]:
    """The deployment-owned providers, and the oracle only if asked.

    ``include_oracle`` defaults to False so the ordinary path cannot
    acquire a ground-truth source by forgetting to exclude it — the
    fairness policy would refuse it at admission, but a default that
    needs a second gate to be safe is a default pointed the wrong way.
    """
    providers: list[Provider] = [
        RobotStateProvider(),
        LegacyObservationProvider(),
        Lidar2DProvider(),
        StaticCostmapProvider(),
    ]
    if include_oracle:
        providers.append(GroundTruthTrackProvider())
    return tuple(providers)


__all__ = [
    "BUILTIN_SPECS",
    "HUMAN_STATE_ESTIMATES",
    "LEGACY_OBSERVATION",
    "LIDAR_2D",
    "ROBOT_STATE",
    "STATIC_COSTMAP",
    "GroundTruthTrackProvider",
    "LegacyObservationProvider",
    "Lidar2DProvider",
    "Provider",
    "ProviderError",
    "RobotStateProvider",
    "StaticCostmapProvider",
    "builtin_providers",
    "builtin_registry",
]
