"""Which stored maps and scenarios nothing can reach any more.

**The counting is the whole problem, and one level of it is not enough.**
On the database this was written against, 198 maps carried 41 distinct
checksums and exactly 5 of them had nothing pointing at them. Sweeping
those 5 would have looked like a working feature and left the shelf as
full as it was. The other 193 were held alive by a scenario row — and
176 of the 208 scenarios were themselves pointed at by nothing. 165 maps
were being kept by a scenario that was already dead.

So reachability is transitive: a scenario keeps its map only while
something keeps the scenario. That is the one rule here that is easy to
write down and easy to get wrong, and it is why this module is plain
functions over plain sets rather than a query buried in a router.

**What counts as an anchor.** A simulation or a benchmark is a run —
something that happened, with results filed against the ids it names.
Those ids must keep working, so anything they reference is reachable.
A scenario is not an anchor: it is a description, and a description
nobody ran is exactly what this sweep is for.

**Pinning is not reachability and is deliberately kept separate.**
`kept` says a person wants this map regardless of what points at it.
Folding it into the reachable set would have been shorter and would have
made "why is this map still here" unanswerable — the caller could no
longer tell "a benchmark needs it" from "somebody pinned it". They are
different answers to a reader and they stay different here.

**Nothing in this module deletes.** It reports. The deleting lives in
the service, behind a flag, because a function that computes a set and
also destroys it is a function nobody can test the interesting half of.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class StoreShape:
    """The id graph, with no rows in it.

    Passed in rather than queried here so the rule can be tested against
    a hand-written graph — the cases worth testing (a map kept alive by a
    dead scenario, a pinned map nothing points at) are three-row
    situations that are miserable to build through a repository.
    """

    map_ids: frozenset[str]
    kept_map_ids: frozenset[str]
    #: scenario id -> the map it names.
    scenario_maps: dict[str, str]
    #: Ids named by a simulation or a benchmark: a run happened against
    #: these, so they have to keep resolving.
    anchored_map_ids: frozenset[str] = field(default_factory=frozenset)
    anchored_scenario_ids: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class Sweep:
    """What is unreachable, named rather than counted.

    Ids rather than a total, because the caller shows them before it
    deletes anything: "delete 165 maps?" is a question nobody can answer
    and "delete 165 maps, including static-obstacles ×117?" is one they
    can.
    """

    map_ids: tuple[str, ...]
    scenario_ids: tuple[str, ...]

    @property
    def is_empty(self) -> bool:
        return not self.map_ids and not self.scenario_ids


def sweep(shape: StoreShape) -> Sweep:
    """Everything nothing can reach, in deletion order.

    Scenarios first in the returned tuples, and that ordering is not
    cosmetic: a caller deleting maps before the scenarios that name them
    would, for a moment, have scenario rows pointing at maps that are
    gone. There is no foreign key stopping it — `ScenarioRow.map_id`
    carries none on purpose, so that deleting a map cannot silently erase
    benchmark provenance — which means the ordering is the only thing
    keeping the store consistent through the middle of a sweep.
    """
    dead_scenarios = tuple(
        sorted(
            scenario_id
            for scenario_id in shape.scenario_maps
            if scenario_id not in shape.anchored_scenario_ids
        )
    )

    live_scenarios = set(shape.scenario_maps) - set(dead_scenarios)
    reachable_maps = (
        set(shape.anchored_map_ids)
        | {shape.scenario_maps[scenario_id] for scenario_id in live_scenarios}
        | set(shape.kept_map_ids)
    )

    dead_maps = tuple(sorted(shape.map_ids - reachable_maps))
    return Sweep(map_ids=dead_maps, scenario_ids=dead_scenarios)


def shape_from_rows(
    *,
    maps: Iterable[tuple[str, bool]],
    scenarios: Iterable[tuple[str, str]],
    simulation_map_ids: Iterable[str],
    simulation_scenario_ids: Iterable[str],
    benchmark_map_ids: Iterable[str],
    benchmark_scenario_ids: Iterable[str],
) -> StoreShape:
    """Assemble the graph from what a repository can list.

    Keyword-only, because six iterables of strings in a row is a call
    nobody can read and two of them are one transposition away from
    swapping maps for scenarios silently.
    """
    map_rows = list(maps)
    return StoreShape(
        map_ids=frozenset(map_id for map_id, _ in map_rows),
        kept_map_ids=frozenset(map_id for map_id, kept in map_rows if kept),
        scenario_maps=dict(scenarios),
        anchored_map_ids=frozenset(simulation_map_ids) | frozenset(benchmark_map_ids),
        anchored_scenario_ids=(
            frozenset(simulation_scenario_ids) | frozenset(benchmark_scenario_ids)
        ),
    )
