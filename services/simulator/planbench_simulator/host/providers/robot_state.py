"""``robot-state@1`` — where the robot is, as the loop already grants it."""

from __future__ import annotations

from typing import Any

from planbench_schemas.robot import RobotState
from planbench_simulator.host.providers.base import Provider
from planbench_simulator.host.runtime_view import ProviderRuntimeView

ROBOT_STATE = "planbench://channel/robot-state@1"


class RobotStateProvider(Provider):
    """The state the simulator hands every controller today.

    True pose, not believed: this is the ``RobotState`` the loop passes
    to ``compute`` and has always passed. The *believed* pose reaches a
    controller through the observation channel, which is where the
    localisation error is modelled — keeping the two apart is what makes
    "the robot does not know where it is" a real experiment rather than
    a change of world.
    """

    capability = ROBOT_STATE
    cadence = "per_tick"
    provenance = "deployment"
    stream_id = 1

    def __init__(self) -> None:
        self._state: RobotState | None = None

    def reset(self) -> None:
        self._state = None

    def advance(
        self, tick: int, now: float, view: ProviderRuntimeView, inputs: dict[str, Any]
    ) -> None:
        del tick, now, inputs
        self._state = view.robot_state()

    def read(self) -> RobotState | None:
        return self._state
