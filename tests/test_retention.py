"""What the orphan sweep may and may not take.

Three-row graphs, built by hand. The cases that matter here are shapes
rather than volumes — a map kept alive by a dead scenario, a pinned map
nothing points at — and building those through repositories would bury
the one line under fixtures.
"""

from __future__ import annotations

from planbench_api.retention import StoreShape, shape_from_rows, sweep


def shape(**over) -> StoreShape:
    base = dict(
        map_ids=frozenset({"m1"}),
        kept_map_ids=frozenset(),
        scenario_maps={},
        anchored_map_ids=frozenset(),
        anchored_scenario_ids=frozenset(),
    )
    base.update(over)
    return StoreShape(**base)


class TestWhatTheSweepTakes:
    def test_a_map_nothing_points_at_is_swept(self) -> None:
        assert sweep(shape()).map_ids == ("m1",)

    def test_a_map_a_run_names_is_kept(self) -> None:
        """A simulation happened against this id, so the id has to keep
        resolving. Deleting it turns a stored result into a record of
        nothing."""
        assert sweep(shape(anchored_map_ids=frozenset({"m1"}))).is_empty

    def test_a_live_scenario_keeps_its_map(self) -> None:
        result = sweep(
            shape(
                scenario_maps={"s1": "m1"},
                anchored_scenario_ids=frozenset({"s1"}),
            )
        )
        assert result.is_empty

    def test_a_dead_scenario_does_not_keep_its_map(self) -> None:
        """**The rule this module exists for.** Counting one level deep,
        193 of 198 maps looked reachable; 165 of them were held by a
        scenario that nothing had ever run."""
        result = sweep(shape(scenario_maps={"s1": "m1"}))
        assert result.scenario_ids == ("s1",)
        assert result.map_ids == ("m1",)

    def test_one_live_scenario_is_enough_to_keep_a_shared_map(self) -> None:
        """Two scenarios on one map, one of them still anchored. The map
        stays; only the dead scenario goes."""
        result = sweep(
            shape(
                scenario_maps={"live": "m1", "dead": "m1"},
                anchored_scenario_ids=frozenset({"live"}),
            )
        )
        assert result.scenario_ids == ("dead",)
        assert result.map_ids == ()

    def test_a_pinned_map_survives_with_nothing_pointing_at_it(self) -> None:
        """The entire point of the column: unreachable and unwanted are
        different claims."""
        assert sweep(shape(kept_map_ids=frozenset({"m1"}))).map_ids == ()

    def test_pinning_a_map_does_not_rescue_the_scenario_on_it(self) -> None:
        """Pinning says "keep this map", not "keep everything that ever
        named it". A scenario nobody ran is what the sweep is for, and a
        pin on its map must not quietly become a pin on it."""
        result = sweep(
            shape(
                map_ids=frozenset({"m1"}),
                kept_map_ids=frozenset({"m1"}),
                scenario_maps={"s1": "m1"},
            )
        )
        assert result.scenario_ids == ("s1",)
        assert result.map_ids == ()

    def test_scenarios_come_back_alongside_maps_not_instead_of_them(self) -> None:
        """A caller deleting maps first would, for a moment, hold
        scenario rows naming maps that are gone — and no foreign key
        would stop it, because `ScenarioRow.map_id` deliberately carries
        none."""
        result = sweep(shape(map_ids=frozenset({"m1"}), scenario_maps={"s1": "m1"}))
        assert result.scenario_ids and result.map_ids


class TestAssemblingTheGraph:
    def test_reads_pins_off_the_map_rows(self) -> None:
        built = shape_from_rows(
            maps=[("m1", False), ("m2", True)],
            scenarios=[("s1", "m1")],
            simulation_map_ids=[],
            simulation_scenario_ids=[],
            benchmark_map_ids=["m9"],
            benchmark_scenario_ids=["s9"],
        )
        assert built.kept_map_ids == frozenset({"m2"})
        assert built.anchored_map_ids == frozenset({"m9"})
        assert built.anchored_scenario_ids == frozenset({"s9"})

    def test_takes_anchors_from_both_simulations_and_benchmarks(self) -> None:
        """Either is a run that happened. Reading only one of them would
        sweep ids the other still needs."""
        built = shape_from_rows(
            maps=[("m1", False), ("m2", False)],
            scenarios=[],
            simulation_map_ids=["m1"],
            simulation_scenario_ids=["s1"],
            benchmark_map_ids=["m2"],
            benchmark_scenario_ids=["s2"],
        )
        assert sweep(built).is_empty
