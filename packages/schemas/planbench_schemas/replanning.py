"""Replanning policy: when a stack is allowed to ask for a new global path.

This is a property of the *evaluation conditions*, not of any algorithm.
Every stack in a benchmark replans under the same rule, with the same
budget, triggered by the same engine states — otherwise a comparison
measures which planner was given more retries rather than which planner
navigates better.

Why it lives here and not on :class:`~planbench_schemas.scenario.Scenario`:
adding a field to ``Scenario`` changes ``_scenario_checksum`` for every
scenario ever stored, which would invalidate the conditions checksum of
every existing benchmark report and stale the whole difficulty
calibration (P03) — a schema change masquerading as a change of physics.
Replanning is a rule the benchmark applies *to* a scenario, so it is
carried by :class:`~planbench_benchmark.spec.BenchmarkSpec` and hashed
into the fairness record separately.

Disabled by default. A run with the default config behaves exactly as
the engine did before replanning existed, down to the checksum.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReplanningConfig(BaseModel):
    """Whether a stack may replan, and — if anybody insists — how often.

    The trigger itself is not configurable, and deliberately so: the
    engine terminates an episode as ``STUCK`` or ``NO_PROGRESS``, and
    those two states are what replanning intervenes on. Making the
    trigger tunable would reopen exactly the door this config closes —
    one stack replanning on a hair trigger while another waits.

    **The budget defaults to unlimited, and that is a reversal.** It used
    to be a required cap, on the reasoning that an unbounded budget turns
    "did the planner recover?" into "did the timeout arrive first?". The
    reasoning was sound and the cure was worse: a shared ``max_replans``
    is a number *somebody chose*, it binds differently for different
    stacks, and under a budget of three a stack that would have escaped
    on its fourth try is scored as a failure of the budget rather than of
    the planner. That is the same class of artifact the replan
    information privilege was (HĐ-4.1) — an evaluation condition quietly
    deciding the result.

    What replaces the cap is a price. Every replan now records its own
    control-step row carrying the global planner's latency, so G4 pools
    it with the rest: p99 cuts at the 99th percentile, so one or two
    replans in four hundred steps sit above the cut and cost nothing,
    while habitual replanning walks into the latency gate on its own. The
    ceiling grows out of the physics rather than being declared, and it
    is the same ceiling for every candidate because the deployment
    declares one ``control_period`` and one ``episode_timeout_s``.
    """

    model_config = ConfigDict(frozen=True)

    enabled: bool = False
    #: ``None`` means unlimited. An integer still caps, because the
    #: retiring benchmark flow stores specs that name one and a stored
    #: run must keep describing the conditions it actually ran under.
    #:
    #: **The declared default stays 0, and that is not the same as the
    #: effective one.** ``NO_REPLANNING`` is ``ReplanningConfig()``, its
    #: ``checksum_payload`` spells ``max_replans=0``, and that string is
    #: mixed into every stored conditions checksum — changing the
    #: declared default to ``None`` would rewrite the checksum of every
    #: benchmark ever run and tell its reader their old results became
    #: incomparable, which is false. So the promotion below happens only
    #: when replanning is switched on *and* nobody named a budget.
    max_replans: int | None = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _promote_unset_budget(self) -> ReplanningConfig:
        """Enabled with no budget named means unlimited.

        Keyed on ``model_fields_set`` rather than on the value, because
        an explicit ``max_replans=0`` is a different statement from
        leaving it out: the first is somebody asking for a budget that
        does nothing, which the check below refuses, and the second is
        somebody not capping at all.
        """
        if self.enabled and "max_replans" not in self.model_fields_set:
            object.__setattr__(self, "max_replans", None)
        return self

    @model_validator(mode="after")
    def _validate(self) -> ReplanningConfig:
        if self.enabled and self.max_replans is not None and self.max_replans < 1:
            raise ValueError(
                "replanning is enabled with a budget of 0 replans, which does nothing; "
                "leave max_replans unset for unlimited, set it >= 1 to cap, or leave "
                "replanning disabled"
            )
        return self

    def allows(self, replans_so_far: int) -> bool:
        """May the stack replan once more?

        A method rather than a comparison at the call site: ``None``
        means unlimited, and a bare ``<=`` against it raises. One place
        that knows what ``None`` means is one place to get it wrong.
        """
        if not self.enabled:
            return False
        return self.max_replans is None or replans_so_far <= self.max_replans

    @property
    def is_default(self) -> bool:
        """True when this config is the historical no-replanning behaviour.

        Used to keep the conditions checksum of pre-replanning benchmarks
        byte-identical: a field that changes every stored checksum the
        day it is added tells the reader that all their old results
        became incomparable, which is false.
        """
        return not self.enabled and self.max_replans == 0

    def checksum_payload(self) -> str:
        """Canonical string mixed into the conditions checksum."""
        return f"replanning:enabled={self.enabled},max_replans={self.max_replans}"


#: The behaviour every benchmark had before this feature existed.
NO_REPLANNING = ReplanningConfig()
