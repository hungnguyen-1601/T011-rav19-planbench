"""What the host hands a plugin, as versioned data (plan §5.5, §7.2).

These models replace kwargs probing as the extension surface: a field a
controller needs travels here, declared and versioned, instead of being
discovered by name inside ``_reset_local`` — the mechanism that silently
lost ``sensor_noise`` once already.

Values are plain primitives (floats, tuples, dicts), not schema-package
models: a plugin outside this repository depends on the SDK alone, and
these payloads must survive a codec across a process boundary in H7.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from planbench_plugin_sdk.channels import ChannelEnvelope
from planbench_plugin_sdk.protocol_version import PLUGIN_API_VERSION


class GlobalPlanRequest(BaseModel):
    """One global planning call (episode start or replan)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    plugin_api: str = PLUGIN_API_VERSION
    start: tuple[float, float]
    goal: tuple[float, float]
    #: The deployment's robot declaration, as plain data.
    robot: dict[str, Any] = Field(default_factory=dict)
    channels: tuple[ChannelEnvelope, ...] = ()


class LocalResetRequest(BaseModel):
    """Start of an episode segment for a local or monolithic plugin.

    ``declared`` carries the deployment-declared values the legacy
    runtime probes for by name (envelope, obstacle_speed, sensor_noise).
    Keys a plugin does not understand are simply unused — but they are
    *present*, so nothing can go missing the way a probed kwarg can.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    plugin_api: str = PLUGIN_API_VERSION
    global_path: tuple[tuple[float, float], ...] = ()
    robot: dict[str, Any] = Field(default_factory=dict)
    declared: dict[str, Any] = Field(default_factory=dict)


class LocalStepRequest(BaseModel):
    """One control tick."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    plugin_api: str = PLUGIN_API_VERSION
    #: Robot state as the plugin may know it (believed pose, velocities).
    state: dict[str, Any] = Field(default_factory=dict)
    channels: tuple[ChannelEnvelope, ...] = ()
