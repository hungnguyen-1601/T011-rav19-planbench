"""H7: a plugin in its own process, and lateness handled at last.

DoD lines: the host starts a plugin out of process; a timeout and a
crash are isolated; latency is measured in layers with the trust
semantics of §5.9 rule 6; and the asynchronous freshness policy H3
deliberately did not build arrives now that lateness is real.
"""

from __future__ import annotations

import pytest
from planbench_plugin_sdk import (
    ChannelEnvelope,
    LocalResetRequest,
    LocalStepRequest,
    load_manifest,
)

from planbench_benchmark.scenarios import build_scenario
from planbench_simulator.host import AlgorithmHost, HostBackedLocalPlanner
from planbench_simulator.host.compatibility import resolve_compatibility
from planbench_simulator.host.freshness import (
    FreshnessFilter,
    FreshnessPolicy,
    StaleChannelError,
)
from planbench_simulator.host.provider_graph import ProviderGraph
from planbench_simulator.host.providers import (
    LEGACY_OBSERVATION,
    builtin_providers,
    builtin_registry,
)
from planbench_simulator.host.runtimes import (
    LATENCY_LAYERS,
    PLUGIN_REPORTED,
    RuntimeLoadError,
    SubprocessRuntime,
)
from planbench_simulator.nav_stack import run_stack
from tests.test_proof_plugins import EXAMPLES  # noqa: F401 - path constant only

BUNDLE = EXAMPLES / "remote_wanderer"

#: **The deployment's control period**, not a number picked for comfort.
#: Every test uses it, so "the plugin answers in time" means in time for
#: this robot rather than eventually — the distinction G4 rests on.
DEPLOYMENT_PERIOD_S = 0.05


@pytest.fixture(scope="module")
def manifest():
    parsed, _ = load_manifest(BUNDLE / ".planbench-plugin" / "plugin.json")
    return parsed


@pytest.fixture(scope="module")
def report(manifest):
    return resolve_compatibility(
        manifest,
        available_capabilities=frozenset({LEGACY_OBSERVATION}),
        graph=ProviderGraph(builtin_providers(), builtin_registry()),
    )


def _runtime() -> SubprocessRuntime:
    return SubprocessRuntime(search_paths=(str(EXAMPLES),))


def _observation_request(now: float = 0.0) -> LocalStepRequest:
    from planbench_schemas.episode import Observation
    from planbench_schemas.geometry import Pose2D

    observation = Observation(
        time=now,
        pose=Pose2D(x=1.0, y=1.0, theta=0.0),
        linear_velocity=0.0,
        angular_velocity=0.0,
        goal_distance=4.0,
        goal_bearing=0.3,
        lidar_ranges=(3.0,) * 72,
    )
    return LocalStepRequest(
        state={"robot_state": None},
        channels=(
            ChannelEnvelope(
                capability=LEGACY_OBSERVATION,
                cadence="per_tick",
                produced_at=now,
                provenance="deployment",
                payload=observation,
            ),
        ),
    )


class TestThePluginRunsOutOfProcess:
    def test_it_starts_and_answers(self, manifest, report) -> None:
        plugin = _runtime().load(manifest, report, control_period_s=DEPLOYMENT_PERIOD_S)
        try:
            plugin.reset(LocalResetRequest(robot={}, declared={}))
            result = plugin.step(_observation_request())
            assert result.failure_reason == ""
            assert result.action.linear_velocity > 0.0
        finally:
            plugin.close()

    def test_it_imports_nothing_from_this_process(self, manifest, report) -> None:
        """The plugin runs in another interpreter, so the host's modules
        being loaded here proves nothing about it — but its *own* module
        must not appear in this process, or the lane is in-process
        wearing a subprocess label."""
        import sys

        plugin = _runtime().load(manifest, report, control_period_s=DEPLOYMENT_PERIOD_S)
        try:
            assert "remote_wanderer" not in sys.modules
        finally:
            plugin.close()

    def test_preflight_still_gates_the_start(self, manifest) -> None:
        refused = resolve_compatibility(
            manifest,
            available_capabilities=frozenset(),  # the channel it needs is absent
            graph=ProviderGraph((), builtin_registry()),
        )
        with pytest.raises(RuntimeLoadError, match="refusing to start"):
            _runtime().load(manifest, refused, control_period_s=DEPLOYMENT_PERIOD_S)


class TestTimeoutAndCrashAreIsolated:
    def test_a_slow_plugin_is_killed_and_becomes_a_safe_stop(self, manifest, report) -> None:
        """The difference from the in-process lane, in one test: there the
        deadline is observed, here it is enforced."""
        plugin = _runtime().load(
            manifest, report, {"stall_ms": 400.0}, control_period_s=DEPLOYMENT_PERIOD_S
        )
        try:
            plugin.reset(LocalResetRequest(robot={}, declared={}))
            result = plugin.step(_observation_request())
            assert result.action.linear_velocity == 0.0
            assert "deadline" in result.failure_reason
        finally:
            plugin.close()

    def test_a_dead_worker_is_not_respawned(self, manifest, report) -> None:
        """A fresh worker mid-episode would answer the next tick with a
        fresh internal state under one episode id, and no reader could
        see the seam."""
        plugin = _runtime().load(
            manifest, report, {"stall_ms": 400.0}, control_period_s=DEPLOYMENT_PERIOD_S
        )
        try:
            plugin.reset(LocalResetRequest(robot={}, declared={}))
            plugin.step(_observation_request())
            again = plugin.step(_observation_request())
            assert "not running" in again.failure_reason
            assert again.action.linear_velocity == 0.0
        finally:
            plugin.close()

    def test_the_host_survives_a_worker_that_never_loads(self, manifest, report) -> None:
        broken = manifest.model_copy(
            update={
                "runtime": manifest.runtime.model_copy(
                    update={
                        "profiles": {
                            "subprocess": manifest.runtime.profiles["subprocess"].model_copy(
                                update={"entry_point": "no_such_module:Thing"}
                            )
                        }
                    }
                )
            }
        )
        with pytest.raises(RuntimeLoadError, match="failed to load"):
            _runtime().load(broken, report, control_period_s=DEPLOYMENT_PERIOD_S)


class TestTheOtherWaysAWorkerCanDie:
    """The half of "crash is isolated" the first pass did not prove."""

    def _plugin(self, manifest, report, config=None):
        return _runtime().load(manifest, report, config or {}, control_period_s=DEPLOYMENT_PERIOD_S)

    def test_an_exception_inside_step_is_a_safe_stop(self, manifest, report) -> None:
        """The plugin raises; the worker survives and reports it as data,
        so the episode records a refusal rather than losing the process."""
        plugin = self._plugin(manifest, report)
        try:
            plugin.reset(LocalResetRequest(robot={}, declared={}))
            # No channels: the plugin's own LookupError fires inside step.
            result = plugin.step(LocalStepRequest(state={"robot_state": None}, channels=()))
            assert result.action.linear_velocity == 0.0
            assert "not granted" in result.failure_reason
        finally:
            plugin.close()

    def test_the_worker_survives_that_exception_and_answers_again(self, manifest, report) -> None:
        """An error is not a death: a plugin that raised on one tick must
        still be asked the next, or one bad channel would end an episode
        the robot could have finished."""
        plugin = self._plugin(manifest, report)
        try:
            plugin.reset(LocalResetRequest(robot={}, declared={}))
            plugin.step(LocalStepRequest(state={"robot_state": None}, channels=()))
            recovered = plugin.step(_observation_request())
            assert recovered.failure_reason == ""
            assert recovered.action.linear_velocity > 0.0
        finally:
            plugin.close()

    def test_a_worker_that_exits_mid_episode_is_a_safe_stop(self, manifest, report) -> None:
        """``os._exit`` from outside: no unwinding, no farewell — the
        shape a native crash has, and the one a try/except cannot fake."""
        plugin = self._plugin(manifest, report)
        try:
            plugin.reset(LocalResetRequest(robot={}, declared={}))
            assert plugin.step(_observation_request()).failure_reason == ""
            plugin._process.kill()
            plugin._process.wait(timeout=5.0)
            result = plugin.step(_observation_request())
            assert result.action.linear_velocity == 0.0
            assert result.failure_reason
        finally:
            plugin.close()

    def test_an_unencodable_payload_fails_loudly(self, manifest, report) -> None:
        """No ``__unencodable__`` placeholder: a plugin computing on a
        marker would report results derived from data it never got."""
        from planbench_simulator.host.runtimes import UnencodableRequest

        plugin = self._plugin(manifest, report)
        try:
            plugin.reset(LocalResetRequest(robot={}, declared={}))
            request = LocalStepRequest(
                state={"robot_state": None},
                channels=(
                    ChannelEnvelope(
                        capability=LEGACY_OBSERVATION,
                        cadence="per_tick",
                        produced_at=0.0,
                        provenance="deployment",
                        payload=object(),  # nothing this codec can carry
                    ),
                ),
            )
            with pytest.raises(UnencodableRequest, match="cannot carry"):
                plugin.step(request)
        finally:
            plugin.close()


class TestTheContractSurvivesTheCodec:
    def test_the_robot_reaches_the_far_side(self, manifest, report) -> None:
        """It did not, in the first version. A controller that cannot read
        its own velocity limits is running a different experiment from the
        in-process one, which would make a lane comparison meaningless."""
        from planbench_simulator.host.runtimes.subprocess_lane import _encode_reset

        encoded = _encode_reset(
            LocalResetRequest(robot={"robot_config": {"max_linear_velocity": 1.0}}, declared={})
        )
        assert encoded["robot"] == {"robot_config": {"max_linear_velocity": 1.0}}

    def test_every_channel_states_its_encoding(self, manifest, report) -> None:
        from planbench_simulator.host.runtimes.subprocess_lane import _encode_step

        encoded = _encode_step(_observation_request())
        assert encoded["channels"][0]["payload_encoding"] == "json-v1"


class TestLatencyLayersAndWhoMeasuredThem:
    def test_the_layers_are_recorded_per_tick(self, manifest, report) -> None:
        plugin = _runtime().load(manifest, report, control_period_s=DEPLOYMENT_PERIOD_S)
        try:
            plugin.reset(LocalResetRequest(robot={}, declared={}))
            plugin.step(_observation_request())
            row = plugin.last_latency.as_trace_row()
            assert set(row) == {*LATENCY_LAYERS, "compute_measured_by"}
            assert plugin.last_latency.end_to_end_control_ms > 0.0
            assert row["transport_ms"] >= 0.0
            assert row["algorithm_compute_ms"] > 0.0
        finally:
            plugin.close()

    def test_compute_is_marked_plugin_reported(self, manifest, report) -> None:
        """§5.9 rule 6: the host cannot see the plugin's own clock, so
        that number is diagnostic and a gate must not read it."""
        plugin = _runtime().load(manifest, report, control_period_s=DEPLOYMENT_PERIOD_S)
        try:
            plugin.reset(LocalResetRequest(robot={}, declared={}))
            plugin.step(_observation_request())
            assert plugin.last_latency.compute_measured_by == PLUGIN_REPORTED
        finally:
            plugin.close()

    def test_end_to_end_covers_the_reported_compute(self, manifest, report) -> None:
        """The host-measured figure is the outer bound: a plugin claiming
        more compute than the whole round trip took is claiming something
        impossible, and transport is clamped rather than going negative."""
        plugin = _runtime().load(
            manifest, report, {"stall_ms": 10.0}, control_period_s=DEPLOYMENT_PERIOD_S
        )
        try:
            plugin.reset(LocalResetRequest(robot={}, declared={}))
            plugin.step(_observation_request())
            latency = plugin.last_latency
            assert latency.end_to_end_control_ms >= latency.algorithm_compute_ms
            assert latency.transport_ms >= 0.0
        finally:
            plugin.close()


class TestTheLaneDrivesARealEpisode:
    def test_an_out_of_process_controller_completes_an_episode(self, manifest, report) -> None:
        """At the deployment's own period. An episode that passed only
        because the lane was handed two comfortable seconds would prove
        the plugin answers eventually, which is not what G4 asks."""
        plugin = _runtime().load(manifest, report, control_period_s=DEPLOYMENT_PERIOD_S)
        try:
            hosted = HostBackedLocalPlanner(AlgorithmHost(local_plugin=plugin))
            map_data, scenario = build_scenario("doorway")
            scenario = scenario.model_copy(update={"timeout_seconds": 4.0})
            run = run_stack(map_data, scenario, hosted)
            assert run.algorithm == "astar+remote_wanderer"
            assert run.result.steps > 0
        finally:
            plugin.close()


class TestTheFreshnessPolicy:
    """The half H3 deliberately left: tolerance, once lateness is real."""

    def _envelope(self, produced_at: float, revision: int | None = None) -> ChannelEnvelope:
        return ChannelEnvelope(
            capability="lidar_2d",
            cadence="per_tick",
            produced_at=produced_at,
            revision=revision,
            provenance="deployment",
            payload=(1.0,),
        )

    def test_a_fresh_channel_is_delivered(self) -> None:
        filt = FreshnessFilter()
        assert filt.admit(self._envelope(1.0), now=1.0) is not None
        assert filt.stats["delivered"] == 1

    def test_a_stale_channel_is_reused_with_its_original_stamp(self) -> None:
        """Reuse is honest only if the plugin can tell: the previous
        envelope goes through unmodified, so an age computed from it is
        the true one."""
        filt = FreshnessFilter()
        first = self._envelope(1.0)
        filt.admit(first, now=1.0)
        delivered = filt.admit(self._envelope(1.0), now=5.0)
        assert delivered is first
        assert delivered.produced_at == 1.0
        assert filt.stats["reused"] == 1

    def test_dropping_hands_the_plugin_nothing(self) -> None:
        """Correct for a plugin that would rather brake than act on a
        guess — which is why ``drop`` is not ``reuse`` with an expiry."""
        filt = FreshnessFilter(FreshnessPolicy(on_stale="drop"))
        filt.admit(self._envelope(1.0), now=1.0)
        assert filt.admit(self._envelope(1.0), now=5.0) is None
        assert filt.stats["dropped"] == 1

    def test_a_refusing_policy_says_so(self) -> None:
        filt = FreshnessFilter(FreshnessPolicy(on_stale="fail"))
        with pytest.raises(StaleChannelError, match="does not substitute"):
            filt.admit(self._envelope(0.0), now=9.0)

    def test_an_out_of_order_revision_is_never_delivered(self) -> None:
        """Feeding a plugin a regression in a quantity it was told is
        monotonic is worse than feeding it nothing."""
        filt = FreshnessFilter()
        newer = ChannelEnvelope(
            capability="planbench://channel/global-path@1",
            cadence="on_change",
            revision=5,
            produced_at=1.0,
            provenance="deployment",
        )
        filt.admit(newer, now=1.0)
        older = newer.model_copy(update={"revision": 3})
        assert filt.admit(older, now=1.0) is newer
        assert filt.stats["out_of_order"] == 1

    def test_small_clock_skew_is_tolerated_and_large_is_a_fault(self) -> None:
        """A timestamp slightly ahead is a clock difference; rejecting it
        would make a working system look broken."""
        filt = FreshnessFilter()
        assert filt.admit(self._envelope(1.005), now=1.0) is not None
        with pytest.raises(StaleChannelError, match="ahead of the clock"):
            filt.admit(self._envelope(2.0), now=1.0)

    def test_static_channels_have_no_age_limit(self) -> None:
        """The costmap built at episode start is not stale at minute
        three, and a policy saying otherwise would force re-stamping."""
        filt = FreshnessFilter()
        static = ChannelEnvelope(
            capability="planbench://channel/static-costmap@1",
            cadence="static",
            revision=1,
            produced_at=0.0,
            provenance="deployment",
        )
        assert filt.admit(static, now=180.0) is static

    def test_reset_clears_the_history_between_episodes(self) -> None:
        filt = FreshnessFilter()
        filt.admit(self._envelope(1.0), now=1.0)
        filt.reset()
        assert filt.stats["delivered"] == 0
        assert filt.admit(self._envelope(0.0), now=0.0) is not None
