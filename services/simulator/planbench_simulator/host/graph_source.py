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
from planbench_simulator.host.freshness import FreshnessFilter, FreshnessPolicy
from planbench_simulator.host.provider_graph import ProviderGraph
from planbench_simulator.host.runtime_view import ProviderRuntimeView


class GraphChannelSource:
    """The loop's channel seam, backed by a provider graph.

    Also where the freshness policy is *applied* rather than merely
    defined. A policy with unit tests and no caller is a description of
    what the host would do, and the first person to read the export list
    would reasonably conclude lateness was handled. Every bundle handed
    to a plugin now passes through :class:`FreshnessFilter`, so stale
    reuse, dropping, out-of-order rejection and skew tolerance are
    properties of episodes rather than of a test file.

    **The policy is an execution condition, and it is declared as one.**
    Switching ``reuse`` to ``drop`` changes what a plugin sees on a late
    tick, which changes the command, which changes the trajectory — so
    :meth:`host_conditions` folds it into the fingerprint alongside the
    provider graph. Two runs under different freshness policies are two
    experiments and must not share a trace.
    """

    def __init__(
        self,
        graph: ProviderGraph,
        *,
        grant_truth: bool = False,
        freshness: FreshnessPolicy | None = None,
    ) -> None:
        self._graph = graph
        self._grant_truth = grant_truth
        self._freshness = FreshnessFilter(freshness or FreshnessPolicy())
        self._view: ProviderRuntimeView | None = None
        #: The seed of the episode about to run, kept because the plugin
        #: is entitled to it and this is the only object on the plugin's
        #: side of the seam that the loop hands it to.
        self.episode_seed = 0

    def bind(self, engine: Any, planning_grid: Any, episode_seed: int) -> None:
        self.episode_seed = episode_seed
        self._view = ProviderRuntimeView.over_engine(
            engine,
            planning_grid,
            episode_seed=episode_seed,
            grant_truth=self._grant_truth,
        )
        # Providers drop episode state here, not in their constructors:
        # one graph may run many episodes, and perception carried across
        # them would leak one episode into the next. The freshness filter
        # is history too — a revision carried over would make this
        # episode's first channel look like a regression.
        self._graph.reset()
        self._freshness.reset()

    def advance(self) -> None:
        view = self._require_view()
        self._graph.advance(view.tick(), view.now(), view)

    def bundle(self, granted: tuple[str, ...]) -> AuthorizedChannelBundle:
        """The granted channels, after the freshness policy has spoken.

        A channel the policy withholds is **absent** from the bundle, not
        present-and-empty: the plugin's own ``LookupError`` then says a
        capability it declared did not arrive, which is the truth, and
        the host turns that into a safe stop. Substituting a blank
        payload would let it compute on nothing and call the result a
        measurement.
        """
        view = self._require_view()
        now = view.now()
        raw = self._graph.bundle_for(granted, now=now)
        admitted = [
            envelope
            for envelope in (self._freshness.admit(entry, now) for entry in raw.envelopes())
            if envelope is not None
        ]
        return AuthorizedChannelBundle(tuple(admitted))

    def host_conditions(self) -> dict[str, object]:
        """The freshness policy as an execution condition (§5.9, §7.1)."""
        policy = self._freshness.policy
        return {
            "freshness_on_stale": policy.on_stale,
            "freshness_max_age_s": dict(sorted(policy.max_age_s.items())),
            "freshness_clock_skew_s": policy.clock_skew_tolerance_s,
        }

    @property
    def freshness_stats(self) -> dict[str, int]:
        """How much of this episode ran on reused or withheld data.

        An episode where a third of the ticks ran on stale channels is a
        different measurement from one where none did, and no other
        column in the trace would show it.
        """
        return dict(self._freshness.stats)

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
    def emits_latency_layers(self) -> bool:
        """Whether this controller's results carry the six §5.9 layers.

        **Asked before the first tick, because a Parquet file has one
        schema.** The recorder fixes its columns at construction and
        refuses a row carrying layers it was not built for — correctly,
        since it cannot grow a column after taking rows.

        Only the subprocess lane measures them: it times encode, write,
        wait, read and decode because a plugin behind a pipe pays a
        transport cost an in-process one does not. So the answer is a
        fact about the lane, and the lane is the thing asked.
        """
        from planbench_simulator.host.runtimes.subprocess_lane import SubprocessPlugin

        return isinstance(getattr(self._host, "_local", None), SubprocessPlugin)

    @property
    def channel_source(self):
        """The seam this controller needs bound before it can step.

        Exposed so a caller that only asked for a controller does not
        also have to know that this one is channel-native. ``run_stack``
        reads it when no source was passed explicitly.
        """
        return self._source

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
                # The seed the episode is actually running under.
                #
                # It was missing until 2026-08-24, and the omission was
                # silent in the way that matters: `episode_seed` defaults
                # to 0, so every plugin on this path drew from the same
                # seed in every episode. A stochastic controller would
                # not fail — it would repeat one sample across the whole
                # sweep while the paired statistics went on assuming
                # independent draws. `HostBackedLocalPlanner` passed it
                # from the start; this facade did not, and nothing
                # compared the two.
                episode_seed=self._source.episode_seed,
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
