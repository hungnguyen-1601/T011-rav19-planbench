"""What the orphan sweep may and may not take.

Three-row graphs, built by hand. The cases that matter here are shapes
rather than volumes — a map kept alive by a dead scenario, a pinned map
nothing points at — and building those through repositories would bury
the one line under fixtures.
"""

from __future__ import annotations

from planbench_api.retention import StoreShape, dedupe, shape_from_rows, sweep


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


class TestKeepingOneOfEach:
    """`dedupe`, which answers a different question from `sweep`.

    `sweep` takes everything unreachable, and on a real store that meant
    every copy of thirteen grids — correct for "delete what is unused"
    and wrong for a person looking at a list who wants one row per map
    rather than a hundred and seventeen.
    """

    def dup(self, **over) -> StoreShape:
        base = dict(
            map_ids=frozenset({"old", "new"}),
            kept_map_ids=frozenset(),
            scenario_maps={},
            map_checksums={"old": "same", "new": "same"},
            map_created_at={"old": "2026-01-01", "new": "2026-06-01"},
        )
        base.update(over)
        return StoreShape(**base)

    def test_keeps_one_copy_and_takes_the_rest(self) -> None:
        assert dedupe(self.dup()).map_ids == ("new",)

    def test_keeps_the_oldest_copy(self) -> None:
        """Oldest, because its id has had the longest chance to be
        written down somewhere this database cannot see."""
        assert "old" not in dedupe(self.dup()).map_ids

    def test_never_empties_a_checksum(self) -> None:
        """The difference from `sweep` in one line: no copy of this grid
        is reachable, and one still survives."""
        result = dedupe(self.dup())
        survivors = set(self.dup().map_ids) - set(result.map_ids)
        assert survivors

    def test_collapses_around_a_referenced_copy_rather_than_through_it(self) -> None:
        """A benchmark pointing at a map other than the one it ran on is
        the claim this platform exists to prevent, so a referenced copy
        is never the one deleted — even when it is the newer."""
        result = dedupe(self.dup(anchored_map_ids=frozenset({"new"})))
        assert result.map_ids == ("old",)

    def test_keeps_every_referenced_copy(self) -> None:
        """Two runs on two copies of one grid. Neither id may stop
        resolving, so neither row goes."""
        assert dedupe(self.dup(anchored_map_ids=frozenset({"old", "new"}))).map_ids == ()

    def test_a_pin_decides_which_copy_stands_in(self) -> None:
        assert dedupe(self.dup(kept_map_ids=frozenset({"new"}))).map_ids == ("old",)

    def test_a_live_scenario_protects_the_copy_it_names(self) -> None:
        result = dedupe(
            self.dup(
                scenario_maps={"s1": "new"},
                anchored_scenario_ids=frozenset({"s1"}),
            )
        )
        assert result.map_ids == ("old",)

    def test_leaves_distinct_grids_alone(self) -> None:
        result = dedupe(self.dup(map_checksums={"old": "a", "new": "b"}))
        assert result.map_ids == ()

    def test_deletes_no_scenarios(self) -> None:
        """Two scenarios on identical grids are not interchangeable the
        way the grids are: the poses are an author's choice."""
        result = dedupe(self.dup(scenario_maps={"s1": "old", "s2": "new"}))
        assert result.scenario_ids == ()

    def test_spares_a_row_whose_checksum_is_unknown(self) -> None:
        """Guessing that an unlabelled row duplicates something would
        delete a map on no evidence."""
        result = dedupe(self.dup(map_checksums={"old": "same"}))
        assert "new" not in result.map_ids


class TestTheImportStopsStoringCopies:
    """The source of the duplicates, and where it was fixed.

    The deployment form calls `POST /scenario-library/{name}/import`
    simply by *opening* — it needs a map to draw before anybody has
    typed anything — and that endpoint stored a fresh map and scenario
    on every call. The row counts were a usage histogram of a dropdown:
    117 `static-obstacles`, the default it opens on, then 29
    `sudden-stop`, 7 `crossing`, and so on down the library.
    """

    def test_adopting_the_same_grid_twice_stores_one_map(self) -> None:
        from planbench_api.repositories import MapRepository
        from planbench_schemas.map import MapData

        repo = MapRepository()
        grid = MapData(name="hall", width=2, height=2, resolution=0.5, origin={"x": 0.0, "y": 0.0}, cells=[0, 0, 0, 0])
        first = repo.create(grid)
        found = repo.find_by_checksum(grid.checksum())
        assert found is not None
        assert found.id == first.id

    def test_a_different_grid_is_not_adopted(self) -> None:
        from planbench_api.repositories import MapRepository
        from planbench_schemas.map import MapData

        repo = MapRepository()
        repo.create(MapData(name="a", width=2, height=2, resolution=0.5, origin={"x": 0.0, "y": 0.0}, cells=[0, 0, 0, 0]))
        other = MapData(name="b", width=2, height=2, resolution=0.5, origin={"x": 0.0, "y": 0.0}, cells=[0, 0, 0, 100])
        assert repo.find_by_checksum(other.checksum()) is None

    def test_the_lookup_is_stable_across_calls(self) -> None:
        """Oldest-first, so a caller that repeats the import keeps
        getting the same id. A newest-first tiebreak would hand back a
        different map the moment anything else stored the same grid —
        the kind of instability that surfaces months later in somebody's
        bookmark."""
        from planbench_api.repositories import MapRepository
        from planbench_schemas.map import MapData

        repo = MapRepository()
        grid = MapData(name="hall", width=2, height=2, resolution=0.5, origin={"x": 0.0, "y": 0.0}, cells=[0, 0, 0, 0])
        first = repo.create(grid)
        repo.create(grid)
        assert repo.find_by_checksum(grid.checksum()).id == first.id

    def test_a_pin_survives_an_edit(self) -> None:
        """A pin belongs to the map, not to a revision of it."""
        from dataclasses import replace

        from planbench_api.repositories import MapRepository
        from planbench_schemas.map import MapData

        repo = MapRepository()
        grid = MapData(name="hall", width=2, height=2, resolution=0.5, origin={"x": 0.0, "y": 0.0}, cells=[0, 0, 0, 0])
        stored = repo.create(grid)
        repo._items[stored.id] = replace(stored, kept=True)
        edited = repo.update(stored.id, MapData(**{**grid.model_dump(), "name": "hall two"}))
        assert edited.kept is True


class TestTheSocketSendsEveryPlannedRoute:
    """The test bench drew one plan for a whole replanning episode.

    The socket sent `plan_path` at `start` and nothing after it, so a
    dashed line sat still while the robot drove somewhere else — which
    reads as a controller ignoring its plan rather than as a plan that
    was replaced.
    """

    def routes(self, plans, replan_times):
        from types import SimpleNamespace

        from planbench_api.routers.ws import _planned_routes

        point = lambda x, y: SimpleNamespace(x=x, y=y)  # noqa: E731
        run = SimpleNamespace(
            plans=tuple(SimpleNamespace(path=[point(*p) for p in path]) for path in plans),
            result=SimpleNamespace(
                events=[
                    SimpleNamespace(time=t, type="replan") for t in replan_times
                ]
                + [SimpleNamespace(time=99.0, type="success")],
            ),
        )
        return _planned_routes(run)

    def test_pairs_each_plan_with_the_replan_that_brought_it_in(self) -> None:
        routes = self.routes([[(0, 0), (1, 1)], [(1, 1), (2, 2)]], [4.5])
        assert [route["from_time"] for route in routes] == [0.0, 4.5]
        assert [route["attempt"] for route in routes] == [1, 2]

    def test_the_first_plan_is_in_force_from_zero(self) -> None:
        """It is the route the episode set out on, not one that replaced
        something."""
        assert self.routes([[(0, 0), (1, 1)]], [])[0]["from_time"] == 0.0

    def test_says_nothing_when_the_counts_do_not_line_up(self) -> None:
        """A refused replan is an event with no plan behind it, and a
        route drawn at the wrong moment is a picture of a decision nobody
        made. The client keeps the opening plan instead."""
        assert self.routes([[(0, 0), (1, 1)]], [4.5, 9.0]) == []

    def test_says_nothing_for_an_episode_stored_before_plans_existed(self) -> None:
        """Empty means not recorded, never 'it did not replan'."""
        assert self.routes([], []) == []

    def test_counts_only_replan_events(self) -> None:
        """A success or a collision is a verdict, not a handover."""
        routes = self.routes([[(0, 0)], [(1, 1)]], [3.0])
        assert len(routes) == 2

