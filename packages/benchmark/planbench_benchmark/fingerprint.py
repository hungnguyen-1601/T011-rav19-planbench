"""What an episode was actually simulated under, as one hash.

**The hole this closes, with the artefact that proved it.** A trace is
addressed by ``(candidate_id, episode_context_id)`` and nothing else:
``--reuse-traces`` checks that the file exists and skips the simulation,
``--score-only`` looks the file up by the same two ids, and
``TraceMetadata`` records neither the map nor the traffic nor the noise.
Meanwhile HĐ-3.1 freezes ``episode_context_id`` at *(task profile,
mission, variant, seed)* — the **environment is not in it**.

So the two halves fit together badly. Re-running a deployment after
changing its world produces episodes that hash to the same ids, and the
machinery happily reuses the old ones. Measured, not feared: re-running
``warehouse_crossing_v1`` after withdrawing ``v_obstacle_max`` left a
``run_journal.jsonl`` with **120 records** — sixty ``stuck`` followed by
sixty ``success``, under the *same* ``episode_context_id b408516ece7f``.
Two different worlds, one identity, one file. A reader diffing that
journal would conclude the episode was flaky.

**Why this is derived from objects rather than from a list of fields.**
The first draft of this was a hand-written list of profile fields to
hash, and in a single sitting it managed both possible mistakes: it
omitted ``clearance_preference``, which changes the planning grid and so
the trajectory, and it included ``clearance_warning_m``, which only the
Metrics Engine reads when scoring a trace that already exists. A list
maintained beside the thing it describes drifts from it. So the payload
here is built from **exactly the arguments the simulator is handed** —
add a field to ``Scenario`` and it is covered without anybody
remembering, and :func:`condition_arguments` states the rest so a test
can check the set has not grown.

The classification rule, for whoever extends this: **in, if changing it
could change the trajectory or the contents of the trace; out, if it
only changes how a finished trace is judged.** Gate thresholds,
``hardware`` and the preference profile are all firmly out — a
deployment may retune what counts as success without re-simulating
anything.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from planbench_schemas.map import MapData
from planbench_schemas.scenario import Scenario
from planbench_schemas.task_profile import TaskProfile

#: Scenario fields deliberately left out of the hash.
#:
#: ``name`` and ``description`` are labels — renaming a scenario does not
#: change one metre of what happens in it. ``description`` is the subtler
#: of the two and was missed on the first pass: ``scenario_for`` builds
#: it as ``"<profile> · <mission> · seed <n>"``, so leaving it in
#: smuggled the seed back into a hash that had deliberately excluded it,
#: and every episode of one deployment came out with different
#: conditions.
#:
#: ``random_seed`` is left out because the seed is already the ``s`` in
#: ``episode_context_id``, which the trace path is keyed by: hashing it
#: here would make the fingerprint say "different episode" when the ids
#: beside it have said that already. The question this answers is
#: narrower — *were the conditions the same?*
_IGNORED_SCENARIO_FIELDS = frozenset({"name", "description", "random_seed"})

#: Everything ``run_contract_episode`` hands the simulator that describes
#: the **conditions** rather than the candidate or the plumbing.
#:
#: Named here so :mod:`tests.test_execution_fingerprint` can assert that
#: ``run_stack`` has not quietly grown a sixth one. A condition the
#: simulator reads and this module does not hash is a trace that can be
#: reused across a change nobody sees.
CONDITION_ARGUMENTS: tuple[str, ...] = (
    "map_data",
    "scenario",
    "replanning",
    "recovery",
    "obstacle_speed",
)


def _canonical(value: Any) -> Any:
    """A JSON-safe form with a stable ordering."""
    if hasattr(value, "model_dump"):
        return _canonical(value.model_dump(mode="json"))
    if isinstance(value, dict):
        return {key: _canonical(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    return value


def scenario_payload(scenario: Scenario) -> dict:
    """The scenario, minus the fields that name it rather than define it."""
    dumped = scenario.model_dump(mode="json")
    return _canonical(
        {key: dumped[key] for key in sorted(dumped) if key not in _IGNORED_SCENARIO_FIELDS}
    )


def execution_conditions_fingerprint(
    map_data: MapData,
    scenario: Scenario,
    profile: TaskProfile,
) -> str:
    """SHA-256 over everything the episode was simulated under.

    Two traces with the same fingerprint were produced by the same world
    under the same rules and may be compared; two with different ones may
    not, whatever their ids say.
    """
    payload = {
        "map": map_data.checksum(),
        "scenario": scenario_payload(scenario),
        "replanning": _canonical(profile.replanning),
        "recovery": _canonical(profile.recovery),
        "obstacle_speed": profile.environment.v_obstacle_max,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]
