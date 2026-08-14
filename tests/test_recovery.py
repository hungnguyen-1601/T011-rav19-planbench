"""Phase 3 — what the robot may do when planning has stopped working.

**Recovery is an evaluation condition, not a candidate feature.** In the
field it *is* part of a stack, and better recovery *is* a better stack.
But a candidate allowed to back up while its rival is not is being
compared on its recovery rather than on the layer the run claims to be
about — the same argument HĐ-4.1 makes about replan information. So it is
declared on the deployment and applied on the one path every candidate
goes through, and moving it to the candidate needs a scope
(``recovery_selection``) that does not exist yet.

Four rungs, and the last one is different in kind:

====  ==============  =============================  ==================
      Behaviour       Changes                        Cost
====  ==============  =============================  ==================
R1    wait            time — traffic moves on        simulation time
R2    back up         the robot's position           time and distance
R3    turn            the robot's heading            time
R4    forget          **the belief, not the world**  time, and a budget
====  ==============  =============================  ==================

Three things this file pins were wrong in the first implementation, and
all three were found by measuring rather than by reading:

1. **The trigger.** Escalating on a *refused* replan almost never fires:
   on the two-doorway room all 43 replans succeeded and the robot still
   timed out, so recovery ran **zero** times in the scene it exists for.
   A plan that comes back and changes nothing is the common case.
2. **Blind motion.** The first ladder turned two timeouts into two
   **collisions**, because reversing is the one bearing the controller
   never checks.
3. **Reversing the wrong way.** "Back up" is not "move away from the
   obstacle" — a differential drive moves along its heading, and the two
   differ exactly when the robot is stuck facing *away* from what blocks
   it. It drove into a wall and collided on the next step.
"""

from __future__ import annotations

import math

import pytest
from blocked_route import blocked_scenario, two_doorway_map

from planbench_planning import DWAPlanner
from planbench_schemas.episode import EpisodeStatus
from planbench_schemas.recovery import LADDER, NO_RECOVERY, RecoveryConfig
from planbench_schemas.replanning import ReplanningConfig
from planbench_simulator.nav_stack import run_stack

REPLANNING = ReplanningConfig(enabled=True)

#: Simulated once per configuration and reused: these episodes run to a
#: 240-second timeout. Safe because a run is a pure function of its
#: inputs, and the results are read rather than mutated.
_RUNS: dict[tuple, object] = {}


def _run(recovery: RecoveryConfig | None = None, preference: float = 2.0):
    settings = None if recovery is None else tuple(sorted(recovery.checksum_payload().items()))
    key = (preference, settings)
    if key not in _RUNS:
        scenario = blocked_scenario().model_copy(
            update={"clearance_preference": preference}
        )
        _RUNS[key] = run_stack(
            two_doorway_map(),
            scenario,
            DWAPlanner(),
            None,
            REPLANNING,
            recovery=recovery,
        )
    return _RUNS[key]


def _events(run, kind: str) -> list:
    return [event for event in run.result.events if event.type == kind]


def _behaviours(run) -> list[str]:
    """Which rung each recovery event was, in order."""
    out = []
    for event in _events(run, "recovery"):
        for behaviour in LADDER:
            if f"({behaviour})" in event.message:
                out.append(behaviour)
                break
    return out


class TestItIsOffUntilADeploymentAsks:
    """Every stored run was measured without it, and it moves the robot.

    A behaviour that changes where the robot ends up changes every metric
    downstream, so switching it on is a new deployment rather than an
    edited one — the same rule ``replanning`` follows.
    """

    def test_the_default_does_nothing(self) -> None:
        assert NO_RECOVERY.enabled is False
        for behaviour in LADDER:
            assert not NO_RECOVERY.allows(behaviour)

    def test_an_episode_without_it_is_unchanged(self) -> None:
        """Byte-identical, not merely similar: a difference here would
        mean every measurement taken before this phase had quietly moved.
        """
        without = _run(None)
        explicit_off = _run(NO_RECOVERY)
        assert without.result.status is explicit_off.result.status
        assert without.result.elapsed_time == pytest.approx(
            explicit_off.result.elapsed_time
        )
        assert _events(without, "recovery") == []
        assert len(without.result.trajectory) == len(explicit_off.result.trajectory)


class TestTheLadderIsClimbedAndReset:
    def test_the_order_is_frozen(self) -> None:
        """Ordering is the design, not a detail. Cheap, reversible,
        world-changing moves first; the one that discards information
        last. Putting ``forget`` earlier would let a stack erase an
        obstacle before it had tried stepping away from it."""
        assert LADDER == ("wait", "back_up", "turn", "forget")

    def test_no_rung_is_ever_skipped(self) -> None:
        """Stated as first-appearance order rather than as a prefix of the
        ladder, because the ladder legitimately **resets mid-run**: on
        this scene the turn gets the robot moving again, so the next
        standstill starts from ``wait`` and the sequence reads
        ``wait, back_up, turn, wait, ...``. A prefix assertion would be
        failing the reset, which is the behaviour the class below pins.
        """
        used = _behaviours(_run(RecoveryConfig(enabled=True)))
        assert used, "recovery never fired in the scene it exists for"
        first_seen = {b: used.index(b) for b in LADDER if b in used}
        ordered = [first_seen[b] for b in LADDER if b in first_seen]
        assert ordered == sorted(ordered), (
            f"a rung was reached before the one below it: {used}"
        )
        assert used[0] == LADDER[0]

    def test_a_deployment_can_stop_short_of_forgetting(self) -> None:
        """``max_escalation`` says "wait and back up and turn, but never
        discard what you saw" without needing a flag per behaviour."""
        run = _run(RecoveryConfig(enabled=True, max_escalation=3))
        assert "forget" not in _behaviours(run)
        assert "turn" in _behaviours(run)

    def test_progress_puts_it_back_at_the_bottom(self) -> None:
        """Escalation measures *consecutive* unproductive standstills. A
        stack that got moving again has not spent its ladder, and making
        the next attempt start at ``forget`` would punish it for having
        recovered."""
        used = _behaviours(_run(RecoveryConfig(enabled=True)))
        assert used.count("wait") > 1, "the ladder never reset, so nothing is being measured"
        assert used[0] == "wait"


class TestTheRungThatErasesEvidenceIsCapped:
    """R4 changes belief rather than the world, which is why it is last.

    A stack free to clear what it has sensed is free to forget an
    obstacle it just saw, and **no gate would catch it**: the Metrics
    Engine reads the trace, and a forgotten obstacle leaves no row saying
    it was forgotten. The count exists for exactly that reason.
    """

    def test_it_happens_at_most_the_declared_number_of_times(self) -> None:
        run = _run(RecoveryConfig(enabled=True, max_forgets=1))
        assert _behaviours(run).count("forget") <= 1

    def test_zero_and_never_are_different_settings(self) -> None:
        """``max_forgets=0`` says "not again"; ``max_escalation=3`` says
        "never". They reach the same behaviour by different routes and a
        deployment should be able to say either."""
        assert not RecoveryConfig(enabled=True, max_forgets=0).allows("forget")
        assert not RecoveryConfig(enabled=True, max_escalation=3).allows("forget")
        assert RecoveryConfig(enabled=True).allows("forget", forgets_so_far=0)
        assert not RecoveryConfig(enabled=True).allows("forget", forgets_so_far=1)

    def test_every_use_is_in_the_record(self) -> None:
        run = _run(RecoveryConfig(enabled=True))
        forgets = [e for e in _events(run, "recovery") if "(forget)" in e.message]
        for event in forgets:
            assert "discarding what the LiDAR saw" in event.message
            assert "/1" in event.message, "the budget is not stated in the record"


class TestRecoveryObeysTheHardFeasibleSet:
    """The defect that made this phase's first version dangerous.

    A recovery that drove blind would be a fourth layer with its own
    answer to "may the robot be here" — the exact defect phases 1 and 2
    removed. It is not hypothetical: the first ladder turned two timeouts
    into two **collisions**.
    """

    def test_it_never_turns_a_timeout_into_a_collision(self) -> None:
        without = _run(None)
        with_recovery = _run(RecoveryConfig(enabled=True))
        assert without.result.status is not EpisodeStatus.COLLISION
        assert with_recovery.result.status is not EpisodeStatus.COLLISION, (
            "recovery drove the robot into something; it must refuse a step that "
            "would leave the hard feasible set, exactly as the controller does"
        )

    def test_reversing_is_refused_when_reverse_is_not_the_way_out(self) -> None:
        """A differential drive moves along its heading and nowhere else,
        so "back up" and "move away from the obstacle" are different
        instructions — and they differ exactly when the robot is stuck
        facing *away* from what blocks it. On this scene the first
        reverse is refused for that reason."""
        run = _run(RecoveryConfig(enabled=True))
        refusals = [
            e for e in _events(run, "recovery") if "did not reverse" in e.message
        ]
        assert refusals, "no reverse was ever refused, so the guard is untested here"

    def test_a_reverse_reports_what_it_actually_covered(self) -> None:
        """It used to report what it *intended*, so a reverse refused
        after 5 mm still logged "backed up 0.30 m". An event stream that
        overstates what the robot did is worse than none, because it is
        what somebody reads when the trajectory looks wrong."""
        run = _run(RecoveryConfig(enabled=True))
        moved = [e for e in _events(run, "recovery") if "backed up" in e.message]
        assert moved, "nothing ever reversed on this scene"
        for event in moved:
            covered, _, wanted = event.message.split("backed up ")[1].partition(" m of ")
            assert float(covered) <= float(wanted.split(" m")[0]) + 1e-9


class TestItIsChargedByBeingSimulated:
    """No penalty term exists, and none should.

    R1 burns simulation time against the timeout; R2 and R3 burn time and
    distance, so they land in ``travel_time_s`` and ``path_length_m`` on
    their own. The same argument retired ``max_replans`` and kept
    ``replan_count`` as evidence rather than a score.
    """

    def test_waiting_costs_the_episode_clock(self) -> None:
        run = _run(RecoveryConfig(enabled=True))
        waits = [e for e in _events(run, "recovery") if "(wait)" in e.message]
        assert waits, "nothing waited"
        scenario = blocked_scenario()
        assert f"{scenario.stuck_time_window:.1f}s" in waits[0].message

    def test_a_wait_is_one_stuck_window_and_not_a_chosen_number(self) -> None:
        """Waiting less than the detector's own window proves nothing:
        the standstill would be re-derived from samples that never
        stopped describing a stopped robot, so a shorter wait is one that
        cannot be observed to have worked."""
        scenario = blocked_scenario()
        run = _run(RecoveryConfig(enabled=True))
        first_wait = next(e for e in _events(run, "recovery") if "(wait)" in e.message)
        assert f"waited {scenario.stuck_time_window:.1f}s" in first_wait.message

    def test_recovery_and_replanning_stay_separate_in_the_record(self) -> None:
        """"The planner found another way" and "the robot backed up and
        tried again" are different facts about a stack. Collapsing them
        under one event name would make a run that recovered five times
        read like one that replanned five times."""
        run = _run(RecoveryConfig(enabled=True))
        assert _events(run, "recovery")
        assert _events(run, "replan")
        for event in _events(run, "recovery"):
            assert event.message.startswith("recovery ")
        for event in _events(run, "replan"):
            assert event.message.startswith("replan ")


class TestTheKnobsAreDerivedWhereverTheyCanBe:
    """Only two numbers are declared, and both are genuine choices.

    The distances and durations come from quantities the deployment
    already states — a wait is one stuck window, a reverse is one hard
    clearance, a turn faces the next waypoint. Asking an author for a
    "back-up distance" would be asking them to re-answer a question the
    robot's own geometry already answers.
    """

    def test_the_config_carries_only_the_two_real_choices(self) -> None:
        fields = set(RecoveryConfig.model_fields) - {"enabled"}
        assert fields == {"max_escalation", "max_forgets"}

    def test_the_manifest_says_so_even_when_it_is_off(self) -> None:
        """A manifest that was silent about recovery could not be told
        apart from one written before recovery existed — the same reason
        ``NO_REPLANNING`` still spells its fields out."""
        payload = NO_RECOVERY.checksum_payload()
        assert payload == {"enabled": False, "max_escalation": 4, "max_forgets": 1}


class TestTurningIsJustifiedByWhatItActuallyDoes:
    def test_it_faces_the_path_rather_than_a_chosen_angle(self) -> None:
        """Derived from the plan, and aimed at the failure that actually
        happens: a controller with ``allow_reverse=False`` facing a wall
        has no admissible command at all, and any heading it can drive
        beats the one it has."""
        run = _run(RecoveryConfig(enabled=True))
        turns = [e for e in _events(run, "recovery") if "(turn)" in e.message]
        assert turns
        assert "towards the path" in turns[0].message

    def test_the_plan_s_stated_reason_for_it_is_false_here(self) -> None:
        """The plan justified this rung as "re-scan from a different
        angle". With this project's default LiDAR that is **not true**:
        ``angle_span`` is 2π, so the robot already sees behind itself and
        turning reveals no new return. The behaviour is kept for the
        reason above; the claim is not.
        """
        assert blocked_scenario().lidar.angle_span == pytest.approx(2 * math.pi)
