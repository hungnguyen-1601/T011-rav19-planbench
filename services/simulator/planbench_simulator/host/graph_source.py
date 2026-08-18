"""Driving the provider graph from the loop's clock, and feeding plugins.

The two halves that make a channel-native plugin run inside the existing
loop without the loop learning anything about it:

:class:`GraphChannelSource` implements the loop's one seam. It builds a
:class:`~planbench_simulator.host.runtime_view.ProviderRuntimeView` over
the episode's engine — closures, never the engine — and advances the
graph once per control decision, which is exactly the ``advance`` once
per tick the provider contract promises.

:class:`GraphBackedLocalPlanner` is the facade a channel-native plugin
wears. Same ABC as every controller, same loop; what differs is where
its inputs come from — an authorized bundle rather than the single
``Observation`` the legacy facade wraps.

**The grant list is fixed at construction, from the plugin's manifest.**
A plugin receives what it declared and was granted, and asking the
bundle for anything else raises rather than returning empty. That is the
difference between a data plane and a global: a plugin cannot widen its
own access by looking harder.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from planbench_plugin_sdk import LocalResetRequest, LocalStepRequest

from planbench_planning.common.local_base import LocalPlanner, LocalPlanResult
from planbench_schemas.episode import Observation
from planbench_schemas.geometry import Point2D
from planbench_schemas.robot import RobotConfig, RobotState
from planbench_simulator.host.algorithm_host import AlgorithmHost
from planbench_simulator.host.channel_bundle import AuthorizedChannelBundle
from planbench_simulator.host.provider_graph import ProviderGraph
from planbench_simulator.host.runtime_view import ProviderRuntimeView


class GraphChannelSource:
    """The loop's channel seam, backed by a provider graph."""

    def __init__(self, graph: ProviderGraph, *, grant_truth: bool = False) -> None:
        self._graph = graph
        self._grant_truth = grant_truth
        self._view: ProviderRuntimeView | None = None

    def bind(self, engine: Any, planning_grid: Any, episode_seed: int) -> None:
        self._view = ProviderRuntimeView.over_engine(
            engine,
            planning_grid,
            episode_seed=episode_seed,
            grant_truth=self._grant_truth,
        )
        # Providers drop episode state here, not in their constructors:
        # one graph may run many episodes, and perception carried across
        # them would leak one episode into the next.
        self._graph.reset()

    def advance(self) -> None:
        view = self._require_view()
        self._graph.advance(view.tick(), view.now(), view)

    def bundle(self, granted: tuple[str, ...]) -> AuthorizedChannelBundle:
        view = self._require_view()
        return self._graph.bundle_for(granted, now=view.now())

    def _require_view(self) -> ProviderRuntimeView:
        if self._view is None:
            raise RuntimeError(
                "this channel source was never bound to an episode; the loop binds it "
                "before the first control tick, so reaching here means it was driven "
                "outside one"
            )
        return self._view


class GraphBackedLocalPlanner(LocalPlanner):
    """``LocalPlanner`` outside; declared channels and a host inside."""

    def __init__(
        self,
        host: AlgorithmHost,
        source: GraphChannelSource,
        granted: tuple[str, ...],
    ) -> None:
        self._host = host
        self._source = source
        self._granted = granted

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
                declared={
                    "envelope": envelope,
                    "obstacle_speed": obstacle_speed,
                    "sensor_noise": sensor_noise,
                },
            )
        )

    def compute(self, state: RobotState, observation: Observation) -> LocalPlanResult:
        # ``observation`` is deliberately unused: a channel-native plugin
        # reads the observation channel if it declared it, and taking the
        # loop's copy would hand it data it never asked for — the exact
        # undeclared access the bundle exists to prevent.
        del observation
        bundle = self._source.bundle(self._granted)
        return self._host.step_local(
            LocalStepRequest(
                state={"robot_state": state},
                channels=bundle.envelopes(),
            )
        )
