"""Recovery behaviours: what a stack may do when planning cannot help.

**Why this is an evaluation condition and not a candidate feature.** In
the field, recovery *is* part of a navigation stack, and a stack with
better recovery *is* a better stack. But if one candidate may back up and
its rival may not, the comparison measures **recovery** rather than the
layer the run claims to be about. The platform already has the vocabulary
for that distinction — ``experiment_scope`` (HĐ-1.4):

* ``global_planner_selection`` / ``local_controller_selection`` — recovery
  is **shared**: declared on the deployment, applied on the one path
  every candidate goes through. Same argument as HĐ-4.1's replan rule.
* ``recovery_selection`` — a scope where recovery is what is being
  compared, and only there does it belong to the candidate.

This module is the shared half. The scope that moves it to the candidate
does not exist yet, and inventing it before anybody wants to compare
recovery would be building the second thing first.

Four behaviours, in escalating order, and the last one is different in
kind from the first three
------------------------------------------------------------------------

===  ==================  =============================  ===================
     Behaviour           Changes                        Reached when
===  ==================  =============================  ===================
R1   Wait in place       time — traffic moves on        something is passing
R2   Back up             the robot's position           too close to manoeuvre
R3   Turn in place       the robot's heading            facing nowhere drivable
R4   Forget what it saw  **the belief, not the world**  perception is suspect
===  ==================  =============================  ===================

**R1–R3 change the world's state; R4 erases evidence.** That is why it is
last and why it is capped. A stack that may clear its costmap freely is a
stack that may forget an obstacle it has just seen, and in this project
that is a straight line to a collision **no gate would catch** — the
Metrics Engine reads the trace, and a forgotten obstacle leaves no trace
row saying it was forgotten. The count is recorded for exactly that
reason.

**Recovery is charged in the currency it actually spends, and no other.**
R1 burns simulation time against the episode timeout. R2 and R3 burn time
*and* distance, so they land in ``travel_time_s`` and ``path_length_m``
on their own. No penalty term is added, and none should be: the same
argument retired ``max_replans`` and kept ``replan_count`` as evidence
rather than a score. A stack that recovers twice as often pays twice, in
numbers a reader already knows how to interpret.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "NO_RECOVERY",
    "RecoveryBehaviour",
    "RecoveryConfig",
]

#: The ladder, in the order it is climbed. Ordering is the whole design:
#: the cheap, reversible, world-changing moves come first, and the one
#: that discards information comes last.
RecoveryBehaviour = Literal["wait", "back_up", "turn", "forget"]

#: Escalation order, frozen. A different order would be a different
#: policy, not a tidy-up: putting ``forget`` earlier would let a stack
#: erase an obstacle before it had tried stepping away from it.
LADDER: tuple[RecoveryBehaviour, ...] = ("wait", "back_up", "turn", "forget")


class RecoveryConfig(BaseModel):
    """Which recovery behaviours this deployment allows, and how far.

    Defaults to **off**, like ``ReplanningConfig``, and for the same
    reason: every stored run was measured without it, and a behaviour
    that changes the robot's position changes every metric downstream.
    Switching it on is a new deployment, not an edited one.

    Notice how few numbers are here. The distances and durations are
    **derived** at the point of use from quantities the deployment
    already declares — a wait is one stuck window, a reverse is one hard
    clearance, a turn faces the next waypoint. Asking an author for a
    "back-up distance" would be asking them to re-answer a question the
    robot's own geometry already answers, and every such knob is one more
    thing two deployments can differ on for no reason anybody recorded.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    enabled: bool = False

    #: How many rungs of the ladder may be used. ``4`` is all of them.
    #: Lower values stop the escalation early, which is how a deployment
    #: says "wait and back up, but never forget what you saw" without
    #: needing a flag per behaviour.
    max_escalation: int = Field(default=len(LADDER), ge=0, le=len(LADDER))

    #: How many times an episode may discard its sensed obstacles (R4).
    #:
    #: **A number somebody chooses, and the plan required it to exist.**
    #: One is the default because a second clear is forgetting twice: the
    #: first can be read as "the sensor was wrong once", and after that
    #: the stack is choosing not to believe its own returns. Zero removes
    #: the behaviour entirely, which is also what ``max_escalation < 4``
    #: does; both are here because they say different things — "never"
    #: versus "not again".
    max_forgets: int = Field(default=1, ge=0)

    def allows(self, behaviour: RecoveryBehaviour, forgets_so_far: int = 0) -> bool:
        """May this behaviour be used now?

        ``forgets_so_far`` is ignored for everything but ``forget``,
        which is the only behaviour with a budget of its own — because it
        is the only one that spends something other than time.
        """
        if not self.enabled:
            return False
        if behaviour not in LADDER[: self.max_escalation]:
            return False
        if behaviour == "forget":
            return forgets_so_far < self.max_forgets
        return True

    def next_behaviour(self, rung: int) -> RecoveryBehaviour | None:
        """The behaviour at this rung, or ``None`` past the end.

        The caller tracks the rung and resets it when a replan succeeds:
        a stack that got moving again has not spent its ladder, and
        making it start from ``forget`` next time would punish it for
        having recovered.
        """
        if rung < 0 or rung >= min(self.max_escalation, len(LADDER)):
            return None
        return LADDER[rung]

    def checksum_payload(self) -> dict:
        """Canonical form for the manifest (HĐ-13).

        Spelled out even when disabled, so a manifest says *recovery was
        off* rather than being silent about it — the same reason
        ``NO_REPLANNING`` still writes its fields.
        """
        return {
            "enabled": self.enabled,
            "max_escalation": self.max_escalation,
            "max_forgets": self.max_forgets,
        }


#: What every deployment gets unless it asks otherwise.
NO_RECOVERY = RecoveryConfig()
