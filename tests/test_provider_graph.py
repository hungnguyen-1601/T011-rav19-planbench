"""H3: the provider graph, the channel contract, and the fairness lane.

Each class pins one DoD line: DAG resolution (with cycles, gaps and
ambiguity reported as themselves), undeclared channels refused, the
cadence invariant written per cadence rather than as one equality,
schema/codec/frame checked before a channel enters a bundle, the oracle
provider gated and always ``sim_only``, and the round-3 provider
lifecycle — ``advance`` once per tick, ``read`` pure, randomness
addressable, state cleared between episodes.
"""

from __future__ import annotations

from typing import Any

import pytest
from planbench_plugin_sdk import ChannelEnvelope

from planbench_simulator.host.channel_bundle import (
    AuthorizedChannelBundle,
    CadenceMonitor,
    CapabilityRegistry,
    CapabilitySpec,
    ChannelContractError,
    UndeclaredChannelError,
    validate_channel,
)
from planbench_simulator.host.fairness_policy import (
    FairnessPolicy,
    FairnessViolation,
    meet,
    provenance_class,
)
from planbench_simulator.host.provider_graph import ProviderGraph, ProviderGraphError
from planbench_simulator.host.providers import (
    HUMAN_STATE_ESTIMATES,
    LEGACY_OBSERVATION,
    LIDAR_2D,
    ROBOT_STATE,
    STATIC_COSTMAP,
    GroundTruthTrackProvider,
    Provider,
    ProviderError,
    builtin_providers,
    builtin_registry,
)
from planbench_simulator.host.runtime_view import (
    TRUSTED_ORACLE_PROVIDERS,
    OracleAccessDenied,
    ProviderRuntimeView,
)


class _Counting(Provider):
    """Stateful on purpose: a tracker is the case the contract is for."""

    cadence = "per_tick"
    provenance = "deployment"

    def __init__(self, capability: str, depends_on: tuple[str, ...] = ()) -> None:
        self.capability = capability
        self.depends_on = depends_on
        self.advances = 0
        self.seen: list[dict[str, Any]] = []

    def reset(self) -> None:
        self.advances = 0
        self.seen = []

    def advance(self, tick, now, view, inputs) -> None:
        del tick, now, view
        self.advances += 1
        self.seen.append(dict(inputs))

    def read(self) -> int:
        return self.advances


#: Test capabilities are real URIs, because an envelope refuses anything
#: else — the SDK's canonical-spelling rule applies to the host's own
#: channels too, and a test that dodged it would test a laxer contract
#: than production runs under.
ALPHA = "org.test://channel/alpha@1"
BETA = "org.test://channel/beta@1"
GAMMA = "org.test://channel/gamma@1"


def _spec(capability: str, cadence: str = "per_tick") -> CapabilitySpec:
    return CapabilitySpec(capability=capability, cadence=cadence)  # type: ignore[arg-type]


class _StubObservation:
    """Enough of an ``Observation`` for the derived channels."""

    def __init__(self, ranges: tuple[float, ...] = (1.0, 2.0)) -> None:
        self.lidar_ranges = ranges


def _view(now: float = 0.0, tick: int = 0, truth=()) -> ProviderRuntimeView:
    return ProviderRuntimeView(
        now=lambda: now,
        tick=lambda: tick,
        robot_state=lambda: "STATE",
        measured_observation=_StubObservation,
        planning_grid=lambda: "GRID",
        episode_seed=11,
        _truth=lambda: truth,
    )


class TestDagResolution:
    def test_a_chain_resolves_in_dependency_order(self) -> None:
        registry = CapabilityRegistry((_spec("a"), _spec("b"), _spec("c")))
        graph = ProviderGraph(
            (_Counting("c", ("b",)), _Counting("a"), _Counting("b", ("a",))),
            registry,
        )
        assert graph.resolution.runnable
        assert graph.resolution.order == ("a", "b", "c")

    def test_a_missing_dependency_is_named_with_its_dependant(self) -> None:
        graph = ProviderGraph((_Counting("b", ("a",)),), CapabilityRegistry((_spec("b"),)))
        assert not graph.resolution.runnable
        assert graph.resolution.missing == ("a",)
        assert "missing providers for ['a']" in graph.resolution.explain()

    def test_a_cycle_is_reported_as_the_cycle(self) -> None:
        """ "maximum recursion depth" names the symptom; the two
        capabilities waiting on each other name the defect."""
        graph = ProviderGraph(
            (_Counting("a", ("b",)), _Counting("b", ("a",))),
            CapabilityRegistry((_spec("a"), _spec("b"))),
        )
        assert set(graph.resolution.cycles) == {"a", "b"}

    def test_two_providers_for_one_capability_are_ambiguous(self) -> None:
        """The host never picks the better source: ``human_state_estimates``
        from a tracker and from ground truth are different experiments."""
        graph = ProviderGraph((_Counting("a"), _Counting("a")), CapabilityRegistry((_spec("a"),)))
        assert graph.resolution.ambiguous == ("a",)
        assert not graph.resolution.runnable

    def test_an_explicit_selection_resolves_the_tie(self) -> None:
        class _Other(_Counting):
            pass

        graph = ProviderGraph(
            (_Counting("a"), _Other("a")),
            CapabilityRegistry((_spec("a"),)),
            selection={"a": "_Other"},
        )
        assert graph.resolution.runnable
        assert graph.resolution.sources["a"] == "_Other"

    def test_an_unrunnable_graph_refuses_to_advance(self) -> None:
        graph = ProviderGraph((_Counting("b", ("a",)),), CapabilityRegistry((_spec("b"),)))
        with pytest.raises(ProviderGraphError, match="not runnable"):
            graph.advance(0, 0.0, _view())


class TestTheLifecycleContract:
    def test_advance_runs_exactly_once_per_tick(self) -> None:
        """A tracker advanced twice for one tick has stepped its state
        through a world that only moved once."""
        registry = CapabilityRegistry((_spec("a"),))
        provider = _Counting("a")
        graph = ProviderGraph((provider,), registry)
        graph.advance(0, 0.0, _view())
        with pytest.raises(ProviderError, match="already advanced"):
            graph.advance(0, 0.0, _view())
        assert provider.advances == 1

    def test_read_is_pure_without_the_cache(self) -> None:
        """Called straight on the provider, bypassing the graph's cache:
        the cache is a cost optimisation, never what makes reads agree."""
        provider = _Counting("a")
        graph = ProviderGraph((provider,), CapabilityRegistry((_spec("a"),)))
        graph.advance(0, 0.0, _view())
        assert provider.read() == provider.read() == 1

    def test_inputs_arrive_from_declared_dependencies_only(self) -> None:
        upstream, downstream = _Counting("a"), _Counting("b", ("a",))
        graph = ProviderGraph((downstream, upstream), CapabilityRegistry((_spec("a"), _spec("b"))))
        graph.advance(0, 0.0, _view())
        assert downstream.seen == [{"a": 1}]

    def test_reset_clears_state_between_episodes(self) -> None:
        """State may live within an episode; carrying it across would leak
        one episode's perception into the next, and every paired
        comparison assumes it does not."""
        provider = _Counting("a")
        graph = ProviderGraph((provider,), CapabilityRegistry((_spec("a"),)))
        graph.advance(0, 0.0, _view())
        graph.reset()
        assert provider.advances == 0
        graph.advance(0, 0.0, _view())  # the same tick is legal after a reset

    def test_randomness_is_addressable_not_sequential(self) -> None:
        """Two reads of one address agree; a different tick differs. This
        is what makes a provider's output independent of how many times
        anything drew before it."""
        view = _view()
        first = view.rng(stream_id=3, tick=7).random()
        again = view.rng(stream_id=3, tick=7).random()
        other_tick = view.rng(stream_id=3, tick=8).random()
        other_stream = view.rng(stream_id=4, tick=7).random()
        assert first == again
        assert first != other_tick
        assert first != other_stream


class TestTheCadenceInvariant:
    """Per cadence, not one equality — the round-4 fix. A global path
    consumed for three hundred ticks is old and valid, and a rule that
    forced it to look current would teach providers to re-stamp."""

    def test_per_tick_must_carry_this_tick(self) -> None:
        registry = CapabilityRegistry((_spec(ALPHA),))
        stale = ChannelEnvelope(
            capability=ALPHA, cadence="per_tick", produced_at=0.9, provenance="deployment"
        )
        with pytest.raises(ChannelContractError, match="must carry this tick's time"):
            validate_channel(stale, registry, CadenceMonitor(), now=1.0)

    def test_on_change_may_be_older_than_now(self) -> None:
        """A global path consumed for three hundred ticks is old and
        valid; this is the case one equality rule would have broken."""
        registry = CapabilityRegistry((_spec(BETA, "on_change"),))
        envelope = ChannelEnvelope(
            capability=BETA,
            cadence="on_change",
            revision=4,
            produced_at=0.5,
            provenance="deployment",
        )
        validate_channel(envelope, registry, CadenceMonitor(), now=9.0)

    def test_a_revision_may_not_go_backwards(self) -> None:
        registry = CapabilityRegistry((_spec(BETA, "on_change"),))
        monitor = CadenceMonitor()
        newer = ChannelEnvelope(
            capability=BETA,
            cadence="on_change",
            revision=4,
            produced_at=0.5,
            provenance="deployment",
        )
        validate_channel(newer, registry, monitor, now=9.0)
        older = newer.model_copy(update={"revision": 3, "produced_at": 0.6})
        with pytest.raises(ChannelContractError, match="went backwards"):
            validate_channel(older, registry, monitor, now=9.0)

    def test_unchanged_data_may_not_be_restamped(self) -> None:
        """The clause that carries the rule: without it, freshness is
        whatever a provider says it is, and no later async policy can see
        through the lie."""
        registry = CapabilityRegistry((_spec(BETA, "on_change"),))
        monitor = CadenceMonitor()
        first = ChannelEnvelope(
            capability=BETA,
            cadence="on_change",
            revision=1,
            produced_at=0.5,
            provenance="deployment",
        )
        validate_channel(first, registry, monitor, now=1.0)
        restamped = first.model_copy(update={"produced_at": 2.0})
        with pytest.raises(ChannelContractError, match="fresh stamp"):
            validate_channel(restamped, registry, monitor, now=2.0)

    def test_a_static_channel_may_not_change_revision(self) -> None:
        registry = CapabilityRegistry((_spec(GAMMA, "static"),))
        monitor = CadenceMonitor()
        first = ChannelEnvelope(
            capability=GAMMA,
            cadence="static",
            revision=1,
            produced_at=0.0,
            provenance="deployment",
        )
        validate_channel(first, registry, monitor, now=0.0)
        with pytest.raises(ChannelContractError, match="changed revision"):
            validate_channel(first.model_copy(update={"revision": 2}), registry, monitor, now=1.0)

    def test_the_declared_cadence_is_not_the_providers_to_choose(self) -> None:
        registry = CapabilityRegistry((_spec(ALPHA, "per_tick"),))
        envelope = ChannelEnvelope(
            capability=ALPHA,
            cadence="static",
            revision=1,
            produced_at=0.0,
            provenance="deployment",
        )
        with pytest.raises(ChannelContractError, match="registered as per_tick"):
            validate_channel(envelope, registry, CadenceMonitor(), now=0.0)


class TestChannelContractBeforeTheBundle:
    """DoD: schema digest, codec, frame and cadence — not just the DAG."""

    def test_an_unregistered_capability_cannot_be_validated(self) -> None:
        with pytest.raises(ChannelContractError, match="no registered spec"):
            validate_channel(
                ChannelEnvelope(
                    capability="planbench://channel/mystery@1",
                    cadence="per_tick",
                    produced_at=0.0,
                    provenance="deployment",
                ),
                CapabilityRegistry(),
                CadenceMonitor(),
                now=0.0,
            )

    def test_a_foreign_codec_is_refused(self) -> None:
        registry = CapabilityRegistry((_spec(ALPHA),))
        envelope = ChannelEnvelope(
            capability=ALPHA,
            cadence="per_tick",
            produced_at=0.0,
            provenance="deployment",
            payload_encoding="protobuf-v1",
        )
        with pytest.raises(ChannelContractError, match="codec"):
            validate_channel(envelope, registry, CadenceMonitor(), now=0.0)

    def test_a_wrong_frame_is_refused(self) -> None:
        """A payload read in the wrong frame is wrong silently — the same
        defect shape as the 180-degree LiDAR sweep (L20)."""
        registry = CapabilityRegistry((_spec(ALPHA),))
        envelope = ChannelEnvelope(
            capability=ALPHA,
            cadence="per_tick",
            produced_at=0.0,
            provenance="deployment",
            frame_id="robot",
        )
        with pytest.raises(ChannelContractError, match="frame"):
            validate_channel(envelope, registry, CadenceMonitor(), now=0.0)


class TestUndeclaredChannelsNeverReachAPlugin:
    def test_reading_an_ungranted_capability_raises(self) -> None:
        """Not None: a plugin that quietly gets nothing behaves differently
        from one that gets data, and nobody can interpret "differently"."""
        bundle = AuthorizedChannelBundle(
            (
                ChannelEnvelope(
                    capability="lidar_2d",
                    cadence="per_tick",
                    produced_at=0.0,
                    provenance="deployment",
                    payload=(1.0,),
                ),
            )
        )
        assert bundle.payload("lidar_2d") == (1.0,)
        with pytest.raises(UndeclaredChannelError, match="was not granted"):
            bundle.payload(HUMAN_STATE_ESTIMATES)

    def test_a_bundle_only_offers_what_was_granted(self) -> None:
        graph = ProviderGraph(builtin_providers(), builtin_registry())
        graph.advance(0, 0.0, _view())
        bundle = graph.bundle_for((LIDAR_2D,), now=0.0)
        assert bundle.capabilities() == (LIDAR_2D,)
        assert ROBOT_STATE not in bundle

    def test_granting_something_nothing_produced_is_a_wiring_error(self) -> None:
        graph = ProviderGraph(builtin_providers(), builtin_registry())
        graph.advance(0, 0.0, _view())
        with pytest.raises(ProviderGraphError, match="nothing produced it"):
            graph.bundle_for((HUMAN_STATE_ESTIMATES,), now=0.0)


class TestTheBuiltinGraph:
    def test_the_default_set_resolves_and_excludes_the_oracle(self) -> None:
        graph = ProviderGraph(builtin_providers(), builtin_registry())
        assert graph.resolution.runnable
        assert HUMAN_STATE_ESTIMATES not in graph.resolution.sources
        assert graph.provenances() == ("deployment",)

    def test_lidar_is_derived_from_the_one_measurement_taken(self) -> None:
        """Two independent reads of the sensor in one tick would draw
        noise twice and hand two consumers two different worlds."""
        observations = []

        def measure():
            observations.append(1)

            class _Obs:
                lidar_ranges = (1.0, 2.0)

            return _Obs()

        view = ProviderRuntimeView(
            now=lambda: 0.0,
            tick=lambda: 0,
            robot_state=lambda: "STATE",
            measured_observation=measure,
            planning_grid=lambda: "GRID",
        )
        graph = ProviderGraph(builtin_providers(), builtin_registry())
        graph.advance(0, 0.0, view)
        assert graph.bundle_for((LIDAR_2D,), now=0.0).payload(LIDAR_2D) == (1.0, 2.0)
        assert len(observations) == 1

    def test_the_static_costmap_keeps_its_stamp_across_ticks(self) -> None:
        """The case the per-cadence rule exists for: a grid that never
        changes must not have to re-stamp itself to stay legal."""
        graph = ProviderGraph(builtin_providers(), builtin_registry())
        graph.advance(0, 0.0, _view())
        first = graph.bundle_for((STATIC_COSTMAP,), now=0.0).envelope(STATIC_COSTMAP)
        graph.advance(1, 0.05, _view(now=0.05, tick=1))
        later = graph.bundle_for((STATIC_COSTMAP,), now=0.05).envelope(STATIC_COSTMAP)
        assert first.produced_at == later.produced_at == 0.0
        assert first.revision == later.revision == 1

    def test_the_observation_channel_carries_the_engine_object(self) -> None:
        graph = ProviderGraph(builtin_providers(), builtin_registry())
        graph.advance(0, 0.0, _view())
        payload = graph.bundle_for((LEGACY_OBSERVATION,), now=0.0).payload(LEGACY_OBSERVATION)
        assert isinstance(payload, _StubObservation)


class TestTheSeamOverARealEngine:
    """DoD: the host receives closures, never the engine or the scenario."""

    @staticmethod
    def _engine():
        from planbench_benchmark.scenarios import build_scenario
        from planbench_simulator.engine import SimulationEngine

        map_data, scenario = build_scenario("doorway")
        engine = SimulationEngine()
        engine.load_map(map_data)
        engine.load_scenario(scenario)
        engine.reset()
        return engine

    def test_the_view_exposes_no_route_back_to_the_engine(self) -> None:
        engine = self._engine()
        view = ProviderRuntimeView.over_engine(engine, "GRID")
        reachable = [
            name
            for name in vars(view)
            if getattr(view, name) is engine or getattr(view, name) is None
        ]
        assert reachable == ["_truth"]  # and that one is None: truth was not granted
        assert view.now() == engine.time
        assert view.tick() == engine.steps

    def test_truth_is_absent_unless_the_deployment_grants_it(self) -> None:
        """Two gates, not one: the deployment decides whether an oracle
        lane exists at all, and the allowlist decides who may use it."""
        view = ProviderRuntimeView.over_engine(self._engine(), "GRID")
        with pytest.raises(OracleAccessDenied, match="carries no truth closure"):
            view.private_truth(GroundTruthTrackProvider())

    def test_a_granted_view_feeds_the_oracle_provider(self) -> None:
        view = ProviderRuntimeView.over_engine(self._engine(), "GRID", grant_truth=True)
        assert isinstance(view.private_truth(GroundTruthTrackProvider()), tuple)

    def test_the_builtin_graph_runs_against_the_real_engine(self) -> None:
        engine = self._engine()
        view = ProviderRuntimeView.over_engine(engine, "GRID")
        graph = ProviderGraph(builtin_providers(), builtin_registry())
        graph.reset()
        graph.advance(engine.steps, engine.time, view)
        bundle = graph.bundle_for((LIDAR_2D, ROBOT_STATE), now=engine.time)
        assert len(bundle.payload(LIDAR_2D)) == len(engine.get_observation().lidar_ranges)
        assert bundle.payload(ROBOT_STATE).pose == engine.get_state().pose


class TestTheOracleIsGatedAndMarked:
    def test_only_the_allowlisted_class_may_read_truth(self) -> None:
        assert (GroundTruthTrackProvider,) == TRUSTED_ORACLE_PROVIDERS

    def test_an_impostor_cannot_reach_truth_by_renaming_itself(self) -> None:
        """The check is on the class object, so declaring a convenient
        capability or provenance buys nothing."""

        class _Impostor(_Counting):
            provenance = "oracle"

            def advance(self, tick, now, view, inputs) -> None:
                view.private_truth(self)

        graph = ProviderGraph(
            (_Impostor(HUMAN_STATE_ESTIMATES),),
            CapabilityRegistry((_spec(HUMAN_STATE_ESTIMATES),)),
        )
        with pytest.raises(OracleAccessDenied, match="not an allowlisted oracle"):
            graph.advance(0, 0.0, _view(truth=()))

    def test_the_oracle_differentiates_backwards_never_forwards(self) -> None:
        """An oracle that knew the future would measure something no
        estimator could approach even in principle — P4's rule."""

        # The real schema, not a stub shaped like one. An earlier draft
        # of this test used an object with bare ``x``/``y`` attributes,
        # and ``CircleObstacle`` keeps its position in ``center`` — so
        # the test passed while the provider could not have read a single
        # real obstacle. A stub that is easier to write than the type it
        # stands in for is a test agreeing with itself.
        from planbench_schemas.geometry import Point2D
        from planbench_schemas.scenario import CircleObstacle

        def _obstacle(x: float) -> CircleObstacle:
            return CircleObstacle(center=Point2D(x=x, y=0.0), radius=0.3)

        positions = [(_obstacle(0.0),), (_obstacle(0.1),)]
        graph = ProviderGraph(builtin_providers(include_oracle=True), builtin_registry())
        graph.advance(0, 0.0, _view(truth=positions[0]))
        first = graph.bundle_for((HUMAN_STATE_ESTIMATES,), now=0.0).payload(HUMAN_STATE_ESTIMATES)
        assert first[0]["vx"] == 0.0  # nothing earlier to difference against
        graph.advance(1, 0.5, _view(now=0.5, tick=1, truth=positions[1]))
        second = graph.bundle_for((HUMAN_STATE_ESTIMATES,), now=0.5).payload(HUMAN_STATE_ESTIMATES)
        assert second[0]["vx"] == pytest.approx(0.2)

    def test_an_oracle_channel_is_sim_only(self) -> None:
        policy = FairnessPolicy.research()
        graph = ProviderGraph(builtin_providers(include_oracle=True), builtin_registry())
        graph.advance(0, 0.0, _view(truth=()))
        bundle = graph.bundle_for((HUMAN_STATE_ESTIMATES,), now=0.0)
        assert policy.is_sim_only(bundle.provenance_of(HUMAN_STATE_ESTIMATES))


class TestTheFairnessPolicy:
    def test_a_production_run_refuses_an_oracle_source_at_admission(self) -> None:
        graph = ProviderGraph(builtin_providers(include_oracle=True), builtin_registry())
        with pytest.raises(FairnessViolation, match="does not admit"):
            FairnessPolicy.production().admit(graph.provenances())

    def test_a_research_run_admits_it_and_carries_the_consequence(self) -> None:
        graph = ProviderGraph(builtin_providers(include_oracle=True), builtin_registry())
        policy = FairnessPolicy.research()
        policy.admit(graph.provenances())
        assert policy.evidence_class(graph.provenances()) == "oracle"

    def test_one_oracle_channel_demotes_a_production_entry(self) -> None:
        """The meet rule: nobody has to remember to say so."""
        assert meet("production", "oracle") == "oracle"
        assert meet("production", "reference") == "reference"
        assert meet("production", "production") == "production"

    def test_deployment_and_candidate_sources_are_both_production(self) -> None:
        """Ownership decides whose identity changes and who is charged
        (§5.9, §7.1); it does not decide what may be concluded."""
        assert provenance_class(("deployment", "candidate")) == "production"

    def test_a_reference_entry_stays_reference_on_a_clean_graph(self) -> None:
        policy = FairnessPolicy.production(entry_class="reference")
        assert policy.evidence_class(("deployment",)) == "reference"
