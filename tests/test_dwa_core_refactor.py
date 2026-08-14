"""Golden trajectories: the shared DWA core must change nothing.

P2 pulls the parts of :mod:`planbench_planning.dwa.planner` that
``dwa_predictive`` will also need into
``planbench_planning.common.dwa_core`` — the sample grid, the rollout,
the point cloud, the polyline distance. It is a **pure refactor**, and
this file is the only thing standing between "pure refactor" as an
intention and "pure refactor" as a fact.

**Why a golden file and not a unit test per function.** Unit tests on the
extracted helpers would prove each one still returns what it used to
return *for the inputs somebody thought to write down*. The risk here is
different in kind: an argument silently reordered, a default that moves,
a ``float`` that becomes an ``int``, a rollout that starts one step
earlier. Those change the **commands** without breaking any function's
contract, and every stored measurement on this platform is downstream of
the commands. So the check is end-to-end and exact.

**Exact means exact**, and it is checked at two levels because one of
them is not enough.

The per-case assertions compare values parsed back out of the fixture.
That catches a shifted float — a refactor moving the last bit of a
velocity has not "changed nothing", it has changed something too small
for *this* scene to show, and the next scene may not be so kind — but
Python's ``==`` is forgiving in two ways a refactor can actually trip:
``0 == 0.0`` hides a type change, and ``-0.0 == 0.0`` hides a sign flip
that reordering a subtraction can produce.

So :meth:`TestTheSharedCoreChangedNothing.test_the_serialised_form_is_byte_identical`
compares the **text**: the fresh result serialised exactly as the fixture
was written, against the bytes on disk. ``repr`` renders ``0``, ``0.0``
and ``-0.0`` as three different strings, so neither gap survives it. The
per-case assertions stay because a byte diff over a quarter-megabyte file
says only *something moved*, and the case name says where.

**What is stored, and why both.** Each case keeps the controller's
**command sequence** — the thing the extracted code actually produces —
and the resulting **trajectory**. The commands localise a failure to the
controller; the trajectory proves the episode as a whole came out the
same, including the parts of the stack that only react to commands
(replanning triggers, recovery ladders, termination). A change that
somehow preserved every command but moved the robot would be a change in
the simulator, and this file should notice that too.

To regenerate — only ever with a reason, and the reason is never "the
test went red"::

    PLANBENCH_REGEN_GOLDEN=1 python -m pytest tests/test_dwa_core_refactor.py

The fixture in this repository was generated **before** the extraction,
from the implementation that produced every measurement recorded up to
2026-08-14. Regenerating it after a change under test destroys the only
evidence that the change was neutral.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any

import pytest

from planbench_benchmark.candidates import LOCAL_CONTROLLER_CONFIGS
from planbench_benchmark.registry import build_global_planner, build_local_planner
from planbench_benchmark.scenarios import build_scenario
from planbench_schemas.replanning import ReplanningConfig
from planbench_schemas.sensor import SensorNoise
from planbench_simulator.nav_stack import run_stack

GOLDEN_PATH = Path(__file__).parent / "golden" / "dwa_trajectories.json"

#: Episodes chosen to touch every line being moved, not to look thorough.
#:
#: Each was checked for what it actually does before being kept — the
#: first draft of this list held ``crossing_obstacle``, which sounds like
#: a traffic case and is not: the robot passes the pedestrian at 1.29 m
#: without altering course, and the whole episode holds **three** distinct
#: headings. A golden case that drives in a straight line pins a straight
#: line.
#:
#: * ``doorway`` — tight alignment: the heading term, the polyline
#:   distance and the goal lookahead all bite at once.
#: * ``narrow_corridor`` under **RRT\*** — a global path with many short
#:   segments and reversing bearings, which is where a polyline distance
#:   rewritten "equivalently" goes wrong.
#: * ``bidirectional_corridor`` — oncoming traffic in a 2 m corridor, met
#:   at **0.000 m** of clearance across 90 distinct headings. This is the
#:   traffic case ``crossing_obstacle`` pretended to be.
#: * ``dynamic_warehouse`` — **three** moving obstacles, so the point
#:   cloud carries several clusters at once, and the episode ends in a
#:   **collision**: a terminal path none of the others take.
#: * ``sudden_stop`` with **noise and replanning** — the believed pose
#:   reaches the point cloud while the true pose drives the rollout, and
#:   replans re-enter ``reset``.
#: * ``sudden_stop`` with a **declared closing speed** — the P1 branch
#:   through the dynamic window, which is the newest code in the file and
#:   the least protected by habit.
#: * ``static_obstacles`` at the **coarse** sampling density with
#:   ``allow_reverse`` on — a pillar field the robot has to weave
#:   through. The reverse flag is here to execute the branch in
#:   ``_dynamic_window`` that widens the sampled window, **not** because
#:   the robot reverses: measured, it never does, and the run is
#:   byte-identical to the same scene with the flag off. That identity is
#:   itself pinned, below.
CASES: tuple[dict[str, Any], ...] = (
    {"name": "doorway_astar", "scenario": "doorway", "stack": "astar+dwa"},
    {"name": "corridor_rrtstar", "scenario": "narrow_corridor", "stack": "rrtstar+dwa"},
    {
        "name": "oncoming_traffic_astar",
        "scenario": "bidirectional_corridor",
        "stack": "astar+dwa",
    },
    {"name": "warehouse_three_movers", "scenario": "dynamic_warehouse", "stack": "astar+dwa"},
    {
        "name": "sudden_stop_noisy_replanning",
        "scenario": "sudden_stop",
        "stack": "astar+dwa",
        "noise": {
            "lidar_range_sigma_m": 0.02,
            "wheel_slip_fraction": 0.02,
            "localization_drift_m": 0.1,
            "localization_jump_probability": 0.02,
            "lidar_dropout_probability": 0.02,
            "odometry_bias_fraction": 0.01,
            "command_latency_steps": 2,
        },
        "replanning": True,
    },
    {
        "name": "sudden_stop_declared_bound",
        "scenario": "sudden_stop",
        "stack": "astar+dwa",
        "obstacle_speed": 1.0,
    },
    {
        "name": "pillars_coarse",
        "scenario": "static_obstacles",
        "stack": "astar+dwa",
        "config": "dwa_coarse",
        "overrides": {"allow_reverse": True},
    },
)

#: Cases whose point is that the robot had to deal with moving traffic.
#: Named here so the assertion below cannot drift out of step with the
#: list above by somebody renaming a case.
TRAFFIC_CASES = ("oncoming_traffic_astar", "warehouse_three_movers")

#: Long enough for each case to reach its interesting part, short enough
#: that the guard runs in the time somebody will actually spend on it.
GOLDEN_TIMEOUT_S = 25.0


def _run_case(case: dict[str, Any]) -> dict[str, Any]:
    """Drive one episode and reduce it to the numbers that must not move."""
    map_data, scenario = build_scenario(case["scenario"])
    updates: dict[str, Any] = {"timeout_seconds": GOLDEN_TIMEOUT_S}
    if "noise" in case:
        # Built, not handed over as a mapping: ``model_copy`` does not
        # validate, so a dict here would sail through and only surface
        # deep inside ``SafetyEnvelope.for_noise``.
        updates["sensor_noise"] = SensorNoise(**case["noise"])
    scenario = scenario.model_copy(update=updates)

    config = {
        **LOCAL_CONTROLLER_CONFIGS[case.get("config", "dwa_balanced")],
        **case.get("overrides", {}),
    }
    run = run_stack(
        map_data,
        scenario,
        build_local_planner(case["stack"], config),
        build_global_planner(case["stack"], episode_seed=scenario.random_seed),
        ReplanningConfig(enabled=True) if case.get("replanning") else None,
        obstacle_speed=case.get("obstacle_speed"),
    )
    gaps = [
        math.hypot(point.x - obstacle.x, point.y - obstacle.y)
        - obstacle.radius
        - scenario.robot.radius
        for point in run.result.trajectory
        for obstacle in point.obstacles
    ]
    return {
        "status": run.result.status.value,
        "steps": run.result.steps,
        # Closest the robot's surface came to any moving obstacle. Not
        # part of what the refactor may change — it is here so the claim
        # that a case exercises traffic is checkable rather than asserted
        # in a comment.
        "min_dynamic_gap": min(gaps) if gaps else None,
        # The controller's own output, and the first place a moved line
        # shows up.
        "commands": [
            [point.linear_velocity, point.angular_velocity] for point in run.result.trajectory
        ],
        "trajectory": [
            [point.time, point.x, point.y, point.theta] for point in run.result.trajectory
        ],
        # Global planning is not part of this refactor, but a path that
        # moved would make every command below it incomparable — so it is
        # recorded to tell "the controller changed" from "the controller
        # was asked something different".
        "plans": [[[p.x, p.y] for p in plan.path] for plan in run.plans],
    }


def _generate() -> dict[str, Any]:
    return {case["name"]: _run_case(case) for case in CASES}


@pytest.fixture(scope="module")
def golden() -> dict[str, Any]:
    if os.environ.get("PLANBENCH_REGEN_GOLDEN"):
        GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN_PATH.write_text(json.dumps(_generate(), indent=1), encoding="utf-8")
        pytest.skip("regenerated the golden fixture; re-run without the flag to check it")
    if not GOLDEN_PATH.exists():
        raise AssertionError(
            f"{GOLDEN_PATH} is missing. It is the record of how the controller behaved "
            "before the shared core was extracted, so it cannot be rebuilt from the "
            "code it exists to check. Restore it from git rather than regenerating it"
        )
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def measured() -> dict[str, Any]:
    """Every case, run once. Six episodes is enough to be worth reusing."""
    return _generate()


class TestTheSharedCoreChangedNothing:
    """One assertion per case, and the case name is the diagnostic."""

    def test_the_serialised_form_is_byte_identical(self, measured: dict[str, Any]) -> None:
        """The whole fixture, as text, against the text on disk.

        **This is the assertion the rest of the class only approximates.**
        Everything below compares values parsed back out of JSON, and
        Python's ``==`` is deliberately forgiving in two ways that matter
        to a refactor:

        * ``0 == 0.0`` — an ``int`` where a ``float`` used to be passes,
          and the next thing to touch that value may not be so relaxed;
        * ``-0.0 == 0.0`` — a sign flip on zero passes, and a negative
          zero angular velocity is a real thing to produce by reordering
          a subtraction.

        Serialising the new result *the same way the fixture was written*
        and comparing the strings catches both, because ``repr`` writes
        ``0`` and ``0.0`` and ``-0.0`` as three different things.

        Note what this does **not** do: it does not regenerate anything.
        It formats the freshly measured result and compares it to bytes
        that have been on disk since before the extraction.
        """
        assert json.dumps(measured, indent=1) == GOLDEN_PATH.read_text(encoding="utf-8")

    @pytest.mark.parametrize("name", [case["name"] for case in CASES])
    def test_the_commands_are_identical(
        self, name: str, golden: dict[str, Any], measured: dict[str, Any]
    ) -> None:
        """The controller's output, float for float.

        Checked before the trajectory on purpose: if the commands moved,
        the trajectory moved for a reason this file can name, and saying
        "the robot ended up elsewhere" first would bury it.
        """
        assert name in golden, f"no golden record for {name}; the case list grew"
        assert measured[name]["commands"] == golden[name]["commands"]

    @pytest.mark.parametrize("name", [case["name"] for case in CASES])
    def test_the_episode_is_identical(
        self, name: str, golden: dict[str, Any], measured: dict[str, Any]
    ) -> None:
        assert measured[name]["plans"] == golden[name]["plans"]
        assert measured[name]["trajectory"] == golden[name]["trajectory"]
        assert measured[name]["status"] == golden[name]["status"]
        assert measured[name]["steps"] == golden[name]["steps"]

    def test_the_fixture_covers_every_case(self, golden: dict[str, Any]) -> None:
        """A case added to ``CASES`` without regenerating would otherwise
        be silently unchecked — the parametrised tests above would ask for
        a record that is not there, and ``assert name in golden`` is a
        clearer failure than a ``KeyError`` three frames down."""
        assert sorted(golden) == sorted(case["name"] for case in CASES)

    def test_the_episodes_actually_did_something(self, golden: dict[str, Any]) -> None:
        """A golden file of six robots that never moved would pass every
        assertion above and protect nothing."""
        for name, record in golden.items():
            assert record["steps"] > 50, f"{name} barely ran"
            moved = {tuple(point[1:3]) for point in record["trajectory"]}
            assert len(moved) > 20, f"{name} did not go anywhere"

    def test_the_traffic_cases_really_had_to_deal_with_traffic(
        self, golden: dict[str, Any]
    ) -> None:
        """The point-cloud path is the largest thing being moved, so the
        cases meant to exercise it must not be quietly empty scenes.

        Measured, not asserted in a comment: this is the check that
        retired ``crossing_obstacle``, which sailed past its pedestrian at
        1.29 m and held three distinct headings for the whole episode.
        """
        for name in TRAFFIC_CASES:
            record = golden[name]
            assert record["min_dynamic_gap"] is not None, f"{name} has no moving obstacle"
            assert record["min_dynamic_gap"] < 0.2, (
                f"{name} never came near its traffic (closest "
                f"{record['min_dynamic_gap']:.3f} m), so it does not exercise the "
                "point cloud under load"
            )
            headings = {round(point[3], 6) for point in record["trajectory"]}
            assert len(headings) > 10, f"{name} drove in a straight line"

    def test_the_cases_between_them_cover_the_branches(self, golden: dict[str, Any]) -> None:
        """Coverage stated as a property of the fixture, so a case list
        edited down to save time fails here rather than silently narrowing
        what the refactor is checked against."""
        statuses = {record["status"] for record in golden.values()}
        assert {"success", "collision"} <= statuses, "no terminal variety"
        assert any(len(record["plans"]) > 1 for record in golden.values()), "nothing replanned"
        assert any(record["min_dynamic_gap"] is None for record in golden.values()), (
            "every case has moving traffic, so the empty-point-cloud path is unexercised"
        )

    def test_allowing_reverse_changes_nothing_it_should_not(self) -> None:
        """The ``allow_reverse`` branch, pinned by what it does **not** do.

        Turning the flag on widens the sampled velocity window downwards.
        On every shipped scene the controller still never picks a negative
        velocity — ``weight_velocity`` prefers forward motion and nothing
        outbids it — so the two runs come out byte-identical.

        That equality is the assertion, and it is a stronger guard than
        "some case drove in reverse" would have been: a refactor that
        mangles the ``-max_linear_velocity if allow_reverse else 0.0``
        clamp changes the window's floor, and a changed floor changes the
        sample grid, and a changed grid shows up here immediately. The
        first version of this file asserted that some case *did* reverse;
        it was simply false, which is the same failure as keeping a
        "traffic" case that never met traffic.
        """
        base = dict(CASES[-1])
        assert base["name"] == "pillars_coarse", "this test reads the coarse pillar case"
        forward_only = {**base, "overrides": {**base["overrides"], "allow_reverse": False}}
        assert _run_case(base)["commands"] == _run_case(forward_only)["commands"]
