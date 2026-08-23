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
    #: map id -> content checksum. Two maps sharing one are the same
    #: grid stored twice, which is what `dedupe` collapses.
    map_checksums: dict[str, str] = field(default_factory=dict)
    #: When each map was stored, for picking which copy of a duplicate
    #: stands in for the rest. Absent ids sort last.
    map_created_at: dict[str, str] = field(default_factory=dict)
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


def dedupe(shape: StoreShape) -> Sweep:
    """Duplicate copies of a map, keeping one of each.

    **A gentler rule than `sweep`, and a different question.** `sweep`
    asks what nothing can reach and takes all of it — which on a real
    store deleted every copy of thirteen grids, because no copy of them
    was reachable. That is correct for "delete what is unused" and wrong
    for what a person looking at the list actually wants, which is one
    row per map instead of a hundred and seventeen.

    So the rule here keeps at least one row for every distinct checksum,
    always:

    - **Every protected copy stays.** A map a simulation or benchmark
      names has results filed against that id; collapsing two of them
      into one would need those references rewritten, and a benchmark
      pointing at a map other than the one it ran on is exactly the
      claim this platform exists to prevent. So duplicates are collapsed
      *around* the protected copies rather than through them.
    - **Where no copy is protected, the oldest stands in.** Oldest
      rather than newest because it is the one whose id has had the
      longest chance to be written down somewhere this database cannot
      see — a bookmark, a ticket, a notebook.
    - **A pinned copy is never deleted**, and never fails to count as a
      survivor either.

    Scenarios are not touched. A scenario carries its own poses, and two
    scenarios on identical grids are not interchangeable the way the
    grids are.
    """
    protected = set(shape.anchored_map_ids) | set(shape.kept_map_ids)
    # A map kept alive by a live scenario is protected too: the scenario
    # names it, and that name has to keep resolving.
    live_scenarios = {
        scenario_id
        for scenario_id in shape.scenario_maps
        if scenario_id in shape.anchored_scenario_ids
    }
    protected |= {shape.scenario_maps[scenario_id] for scenario_id in live_scenarios}

    by_checksum: dict[str, list[str]] = {}
    for map_id in shape.map_ids:
        checksum = shape.map_checksums.get(map_id)
        # A row with no checksum is not known to duplicate anything, and
        # guessing that it does would delete a map on no evidence.
        if checksum is None:
            continue
        by_checksum.setdefault(checksum, []).append(map_id)

    doomed: list[str] = []
    for copies in by_checksum.values():
        survivors = {map_id for map_id in copies if map_id in protected}
        if not survivors:
            survivors = {min(copies, key=lambda m: (shape.map_created_at.get(m, "~"), m))}
        doomed += [map_id for map_id in copies if map_id not in survivors]

    return Sweep(map_ids=tuple(sorted(doomed)), scenario_ids=())


def shape_from_rows(
    *,
    maps: Iterable[tuple[str, bool]],
    scenarios: Iterable[tuple[str, str]],
    checksums: dict[str, str] | None = None,
    created_at: dict[str, str] | None = None,
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
        map_checksums=dict(checksums or {}),
        map_created_at=dict(created_at or {}),
        scenario_maps=dict(scenarios),
        anchored_map_ids=frozenset(simulation_map_ids) | frozenset(benchmark_map_ids),
        anchored_scenario_ids=(
            frozenset(simulation_scenario_ids) | frozenset(benchmark_scenario_ids)
        ),
    )
