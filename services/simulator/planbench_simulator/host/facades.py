"""The old ABCs on the outside, host requests on the inside (H2 DoD).

``run_stack`` and ``run_policy`` keep calling ``GlobalPlanner.plan`` and
``LocalPlanner.reset/compute`` — nothing in the loop changed. These
facades implement those ABCs and translate each call into an SDK
request; the host mediates; a legacy adapter runs the unchanged code.

**The facade's reset signature is load-bearing.** ``_reset_local``
probes *its callee's* signature, and its callee is now the facade — so
the facade declares all three deployment kwargs, always receives them,
and packs them into ``LocalResetRequest.declared``. Which controller
actually accepts which kwarg is the adapter's business, resolved on the
other side of the host.
"""

from __future__ import annotations

from collections.abc import Sequence

from planbench_plugin_sdk import (
    ChannelEnvelope,
    GlobalPlanRequest,
    LocalResetRequest,
    LocalStepRequest,
)

from planbench_planning.common.base import GlobalPlanner, PlanResult
from planbench_planning.common.local_base import LocalPlanner, LocalPlanResult
from planbench_schemas.episode import Observation
from planbench_schemas.geometry import Point2D
from planbench_schemas.robot import RobotConfig, RobotState
from planbench_simulator.grid import OccupancyGrid
from planbench_simulator.host.algorithm_host import AlgorithmHost
from planbench_simulator.host.legacy_global import LegacyGlobalPlugin
from planbench_simulator.host.legacy_local import LegacyLocalPlugin
from planbench_simulator.host.legacy_policy import LegacyPolicyPlugin
from planbench_simulator.host.lifecycle import GRID_CHANNEL, OBSERVATION_CHANNEL


class HostBackedGlobalPlanner(GlobalPlanner):
    """``GlobalPlanner`` outside, ``GlobalPlanRequest`` inside."""

    def __init__(self, host: AlgorithmHost) -> None:
        self._host = host
        #: Grid channel revision: bumped per planning call, because the
        #: grid is rebuilt per call (initial plan, each replan) — the
        #: cadence contract for an ``on_change`` channel.
        self._revision = 0

    @property
    def name(self) -> str:
        return self._host.global_name

    def plan(self, grid: OccupancyGrid, start: Point2D, goal: Point2D) -> PlanResult:
        self._revision += 1
        request = GlobalPlanRequest(
            start=(start.x, start.y),
            goal=(goal.x, goal.y),
            channels=(
                ChannelEnvelope(
                    capability=GRID_CHANNEL,
                    cadence="on_change",
                    revision=self._revision,
                    produced_at=0.0,
                    provenance="deployment",
                    payload=grid,
                ),
            ),
        )
        return self._host.plan_global(request)


class HostBackedLocalPlanner(LocalPlanner):
    """``LocalPlanner`` outside, reset/step requests inside."""

    def __init__(self, host: AlgorithmHost, *, episode_seed: int = 0) -> None:
        self._host = host
        #: Reaches the plugin through ``reset``. Carried on the facade
        #: because the ABC's ``reset`` does not take one and the loop
        #: has no reason to grow an argument for it: the seed is a
        #: property of the episode this facade was built for.
        self._episode_seed = episode_seed

    @property
    def name(self) -> str:
        return self._host.local_name

    @property
    def control_period(self) -> float | None:
        return self._host.local_control_period

    @property
    def diagnostics(self):
        return self._host.local_diagnostics

    def reset(
        self,
        global_path: Sequence[Point2D],
        robot: RobotConfig,
        *,
        envelope=None,
        obstacle_speed=None,
        sensor_noise=None,
    ) -> None:
        self._host.reset_local(
            LocalResetRequest(
                global_path=tuple((point.x, point.y) for point in global_path),
                robot={"robot_config": robot},
                episode_seed=self._episode_seed,
                declared={
                    "envelope": envelope,
                    "obstacle_speed": obstacle_speed,
                    "sensor_noise": sensor_noise,
                },
            )
        )

    def compute(self, state: RobotState, observation: Observation) -> LocalPlanResult:
        request = LocalStepRequest(
            state={"robot_state": state},
            channels=(
                ChannelEnvelope(
                    capability=OBSERVATION_CHANNEL,
                    cadence="per_tick",
                    produced_at=observation.time,
                    provenance="deployment",
                    payload=observation,
                ),
            ),
        )
        return self._host.step_local(request)


def host_backed_planners(
    global_planner: GlobalPlanner,
    local_planner: LocalPlanner,
    *,
    episode_seed: int = 0,
) -> tuple[HostBackedGlobalPlanner, HostBackedLocalPlanner]:
    """Wrap one episode's planners behind one host.

    The deadline handed to the host is the controller's own declared
    period — observed, never enforced, in this lane (see
    ``algorithm_host``).
    """
    host = AlgorithmHost(
        global_plugin=LegacyGlobalPlugin(global_planner),
        local_plugin=LegacyLocalPlugin(local_planner),
        control_deadline_s=local_planner.control_period,
    )
    return HostBackedGlobalPlanner(host), HostBackedLocalPlanner(host, episode_seed=episode_seed)


def host_backed_policy(policy: LocalPlanner) -> HostBackedLocalPlanner:
    """Wrap a monolithic policy for ``run_policy`` — same loop, same host."""
    host = AlgorithmHost(
        local_plugin=LegacyPolicyPlugin(policy),
        control_deadline_s=policy.control_period,
    )
    return HostBackedLocalPlanner(host)
