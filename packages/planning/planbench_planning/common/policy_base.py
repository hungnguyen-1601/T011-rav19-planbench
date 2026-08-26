"""End-to-end policies: HĐ-4's second candidate shape.

A **monolithic** candidate is one layer, not two. It reads
``Observation`` and emits a command, with no global planner ahead of it
and no global path to follow — which is the whole difference from the
modular stacks this platform has run until now (HĐ-1.2).

**Why it is a ``LocalPlanner`` rather than a new interface.** The
simulator drives every candidate through the same loop, and it must:
whoever is being measured has to meet the same clock, the same
``Observation``, and the same termination rules, or the comparison is
between two harnesses instead of two navigators. So a policy differs in
exactly one place — it is handed no path — and that difference is a
default here rather than a branch in the driving loop.

**What this does not do.** It does not price the observation
requirements a policy declares (G6), and it does not load weights. A
policy that needs a camera and one that needs a planar scan are not the
same candidate, and HĐ-6 charges for the difference; that charge is
computed from ``Candidate.observation_requirements``, which the policy
author declares and the registry checks — not from this class.
"""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Sequence

from planbench_planning.common.local_base import LocalPlanner, LocalPlanResult
from planbench_schemas.episode import Observation
from planbench_schemas.geometry import Point2D
from planbench_schemas.robot import RobotConfig, RobotState

__all__ = ["MonolithicPolicy"]


class MonolithicPolicy(LocalPlanner):
    """A candidate that navigates from ``Observation`` alone.

    Subclasses implement :meth:`decide`. The two things they inherit are
    the two things that must not vary between candidates: the reset
    contract, and the fact that no global path is available even if one
    was computed.
    """

    def reset(self, global_path: Sequence[Point2D], robot: RobotConfig) -> None:
        """Prepare for a new episode. **The path is deliberately dropped.**

        Not ignored by oversight, and not merely unused: accepting it
        would make a policy that peeked at a global path indistinguishable
        from one that did not, and the first is a modular stack wearing a
        policy's label. The signature keeps the parameter because the
        simulator's loop is shared, and sharing that loop is what makes
        the comparison a comparison.
        """
        del global_path
        self._robot = robot
        self.prepare(robot)

    def prepare(self, robot: RobotConfig) -> None:
        """Hook for subclasses that need per-episode setup. Optional."""

    def compute(self, state: RobotState, observation: Observation) -> LocalPlanResult:
        return self.decide(state, observation)

    @abstractmethod
    def decide(self, state: RobotState, observation: Observation) -> LocalPlanResult:
        """The command for the next step, from the observation alone."""
