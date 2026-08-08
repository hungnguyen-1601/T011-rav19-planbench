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
    """How many times, and whether at all, a stack may replan.

    The trigger itself is not configurable, and deliberately so: the
    engine terminates an episode as ``STUCK`` or ``NO_PROGRESS``, and
    those two states are what replanning intervenes on. Making the
    trigger tunable would reopen exactly the door this config closes —
    one stack replanning on a hair trigger while another waits.
    """

    model_config = ConfigDict(frozen=True)

    enabled: bool = False
    #: Upper bound on replans per episode. Bounded rather than unlimited
    #: because an unbounded budget turns "did the planner recover?" into
    #: "did the timeout arrive first?", and the two are different
    #: questions with different answers.
    max_replans: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _validate(self) -> ReplanningConfig:
        if self.enabled and self.max_replans < 1:
            raise ValueError(
                "replanning is enabled with a budget of 0 replans, which does nothing; "
                "set max_replans >= 1 or leave replanning disabled"
            )
        return self

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
