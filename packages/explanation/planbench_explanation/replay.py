"""Re-running a recorded planning attempt, without knowing what a planner is — E6b.

The check this module performs needs a planner. The explanation layer
must not *contain* one: it reads artifacts a run produced, and a package
that imported the simulator would be a package that can only explain
runs from this repository, on this version, with this planner registry.
That constraint is the reason
:func:`~planbench_explanation.sidecar_writer.costmap_checksum` takes
cells rather than an ``OccupancyGrid``, and it holds here too.

So the planner arrives as an argument. :class:`ReplayPlanner` is the
whole of what this layer knows about one: hand it a
:class:`ReplayRequest` — a grid as numbers, a query as coordinates, a
planner name with its parameters and seed — and get back a
:class:`ReplayPlan`. The adapter that turns that into an actual
``OccupancyGrid`` and an actual ``AStarPlanner`` lives on the simulator
side, where both already exist.

**What a successful replay establishes, and what it does not.** If every
recorded input matches and the planner returns no path where the run
recorded no path, the query really is infeasible for this stack: that is
``geometric_infeasibility``, at the card's ceiling, because the inputs
were recorded rather than rebuilt. If the planner *finds* a path where
the run found none, the proposition is **refuted** — and that is a real
answer, not a failure of the check.

**``rrt_convergence`` is a sweep, not a replay, and that is why it took
longer.** Reproducing one attempt answers "was this query impossible".
The sampling question is different: *at the configured budget, does this
planner find the corridor only sometimes?* Answering it means running
the same recorded query across the run's **seeds** at more than one
budget and looking at the rate. The seeds come from the run — they are
the episode contexts' own — and the budgets are a preregistered
constant here, because a budget chosen after seeing the first sweep is
a budget chosen to produce an answer.

**Everything else is ``not_checkable``, on purpose.** A different build,
a different costmap, a different fingerprint, a refusal for a different
reason — each means the thing that ran is not the thing being asked
about. :func:`~planbench_explanation.planning_input_evidence.admit_replay_with_sidecar`
decides that, and this module does not second-guess it: a replay that
disagrees with the record in any field is evidence about the harness,
not about the run.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from planbench_explanation.checkers import CheckerRefusal, CheckOutcome
from planbench_explanation.planning_input_evidence import (
    PlanningInputEvidence,
    PlanningOutcome,
    ReplayObservation,
    admit_replay_with_sidecar,
)
from planbench_explanation.sidecar_writer import PlanningSnapshot


class ReplayUnavailable(RuntimeError):
    """The harness cannot reproduce the attempt it was given.

    Distinct from "the replay disagreed with the record": that is a
    finding about the run, and this is the harness saying it is not
    equipped — an unknown planner, a sampling planner whose seed was
    never recorded. Defined here rather than in the adapter so the host
    can catch it without importing the simulator, which is the whole
    point of this module.
    """

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}")


class ReplayRequest(BaseModel):
    """One recorded planning attempt, as numbers a planner can be given.

    Flat and primitive on purpose. An adapter on the other side rebuilds
    whatever grid type its planner wants; passing a grid *object* would
    mean this module had an opinion about which one.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    cells: tuple[int, ...]
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    resolution: float = Field(gt=0)
    origin_x: float
    origin_y: float
    start_x: float
    start_y: float
    goal_x: float
    goal_y: float
    planner_name: str = Field(min_length=1)
    planner_parameters: dict[str, float | int | str | bool] = Field(default_factory=dict)
    #: ``None`` for a deterministic planner. An adapter handed ``None``
    #: for a sampling planner should refuse rather than pick one.
    seed: int | None = None

    @classmethod
    def from_snapshot(cls, snapshot: PlanningSnapshot) -> ReplayRequest:
        grid = snapshot.grid
        return cls(
            cells=grid.cells,
            width=grid.width,
            height=grid.height,
            resolution=grid.resolution,
            origin_x=grid.origin_x,
            origin_y=grid.origin_y,
            start_x=snapshot.start_x,
            start_y=snapshot.start_y,
            goal_x=snapshot.goal_x,
            goal_y=snapshot.goal_y,
            planner_name=snapshot.planner_name,
            planner_parameters=dict(snapshot.planner_parameters),
            seed=snapshot.seed,
        )


class ReplayPlan(BaseModel):
    """What the harness got back, in the terms the admission rules use.

    The harness reports its **own** fingerprint and build rather than
    echoing the record's. Echoing would make the two always agree, and
    the comparison exists precisely to catch a replay run under a
    different configuration or a different commit.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    outcome: PlanningOutcome
    output_plan_checksum: str | None = None
    failure_code: str | None = None
    planner_fingerprint: str = Field(min_length=1)
    execution_environment_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self) -> ReplayPlan:
        if self.outcome == "path" and not self.output_plan_checksum:
            raise CheckerRefusal(
                "replay_harness_incomplete",
                "a replay that found a path must hash it, or there is nothing to "
                "compare against the recorded plan",
            )
        if self.outcome != "path" and self.output_plan_checksum is not None:
            raise CheckerRefusal(
                "replay_harness_incomplete",
                f"outcome={self.outcome!r} carries a plan checksum",
            )
        if self.outcome != "path" and not self.failure_code:
            raise CheckerRefusal(
                "replay_harness_incomplete",
                "a replay that found no path must say why: 'no path' and 'timed out' "
                "are different mechanisms, and the mechanism is the subject of the "
                "claim being checked",
            )
        return self


class ReplayPlanner(Protocol):
    """A planner, as far as this layer needs to know.

    One method. Everything that makes a planner a planner — grids,
    footprints, sampling strategies — belongs on the other side of this
    boundary.
    """

    def replay(self, request: ReplayRequest) -> ReplayPlan: ...


class ReplayEvidence(BaseModel):
    """A recorded attempt and the snapshot it points at, already resolved.

    Resolved by the host rather than here: loading a file is the host's
    job and a checker is a pure function of its evidence, the same rule
    the other two checkers follow.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    record: PlanningInputEvidence
    snapshot: PlanningSnapshot
    #: True when the harness was handed the recorded grid directly, false
    #: when it rebuilt one and every fingerprint matched. Both may reach
    #: ``mechanism_verified``; the distinction is recorded because they
    #: are different claims about where the inputs came from.
    inputs_loaded_from_record: bool = True

    @model_validator(mode="after")
    def _check(self) -> ReplayEvidence:
        if self.snapshot.checksum != self.record.snapshot_checksum:
            raise CheckerRefusal(
                "replay_inputs_mismatched",
                "the snapshot handed to the checker is not the one the record pins; "
                "resolve it with sidecar_writer.snapshot_for so the mismatch is "
                "reported as a file problem rather than as a failed replay",
            )
        return self


def check_replay_global_plan(evidence: ReplayEvidence, *, planner: ReplayPlanner) -> CheckOutcome:
    """Re-run the recorded query and see whether the stack still refuses.

    The verdict follows the **recorded** outcome, once the replay has
    reproduced it exactly:

    ``no_path`` reproduced
        ``supported`` — the query is infeasible for this stack, on the
        costmap it was actually given.
    ``path`` reproduced
        ``refuted`` — the planner does find a route here, so whatever
        went wrong in the episode was not the query being impossible.

    Anything the admission rules will not accept raises, and the host
    turns that into ``not_checkable``. That is the honest shape: a
    replay that diverged has told us something about the harness.
    """
    request = ReplayRequest.from_snapshot(evidence.snapshot)
    plan = planner.replay(request)

    admission = admit_replay_with_sidecar(
        evidence.record,
        ReplayObservation(
            costmap_checksum=evidence.record.costmap_checksum,
            query=evidence.record.query,
            planner_fingerprint=plan.planner_fingerprint,
            execution_environment_ref=plan.execution_environment_ref,
            outcome=plan.outcome,
            output_plan_checksum=plan.output_plan_checksum,
            failure_code=plan.failure_code,
        ),
        inputs_loaded_from_record=evidence.inputs_loaded_from_record,
    )
    if admission.execution_status != "completed":
        raise CheckerRefusal(
            "replay_did_not_reproduce",
            f"attempt {evidence.record.planning_attempt} of "
            f"{evidence.record.episode_context_id}: {list(admission.reasons)}. A "
            "replay that diverges from the record is evidence about the harness, "
            "not about the run.",
        )

    reproduced = evidence.record.outcome
    measurements = {
        "attempts_replayed": 1.0,
        "attempts_recorded": float(evidence.record.planning_attempt),
        "paths_found": 1.0 if reproduced == "path" else 0.0,
    }
    if reproduced == "path":
        return CheckOutcome(
            proposition_type="geometric_infeasibility",
            verdict="refuted",
            measurements=measurements,
            note=(
                f"re-run on the recorded inputs, the planner returns a path of "
                f"checksum {str(plan.output_plan_checksum)[:12]}; the query is not "
                "infeasible for this stack"
            ),
        )
    return CheckOutcome(
        proposition_type="geometric_infeasibility",
        verdict="supported",
        measurements=measurements,
        note=(
            f"re-run on the recorded costmap, start and goal, the planner refuses "
            f"again with {evidence.record.failure_code!r} — the query is infeasible "
            "for this stack as configured"
        ),
    )


#: Budgets the convergence sweep runs at, as multiples of the configured
#: one. **Preregistered**: written down before any sweep, because a
#: second budget picked after seeing the first result is a budget picked
#: to make a rate rise. Two points is the minimum that can show a trend
#: and the most that is cheap enough to run per hypothesis.
BUDGET_MULTIPLIERS: tuple[float, ...] = (1.0, 4.0)

#: A rate at or above this at the configured budget means the planner
#: finds the corridor reliably, and the hypothesis is refuted rather
#: than unproven.
RELIABLE_AT_BUDGET = 0.9

#: How much the rate must rise at the larger budget before the shortfall
#: is attributed to sampling rather than to the query. Below this the
#: verdict is ``refuted``: a rate that does not move with the budget is
#: pointing at the geometry.
BUDGET_SENSITIVITY = 0.2

#: Seeds below this and a rate is the shape a handful of draws makes.
MINIMUM_SEEDS_FOR_CONVERGENCE = 8


class ConvergenceEvidence(BaseModel):
    """One recorded query, plus the seeds the run actually used.

    The seeds are **not** in the sidecar and should not be: a record
    describes the attempt that happened, and this check is about the
    attempts that did not. They come from the run's episode contexts,
    which is where the deployment's seed set lives.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    record: PlanningInputEvidence
    snapshot: PlanningSnapshot
    #: The run's own seeds. Deduplicated by the validator: one seed
    #: counted twice moves a rate without adding a draw.
    seeds: tuple[int, ...]
    #: Which parameter carries the sample budget on this planner.
    budget_parameter: str = "max_iterations"

    @model_validator(mode="after")
    def _check(self) -> ConvergenceEvidence:
        if self.snapshot.checksum != self.record.snapshot_checksum:
            raise CheckerRefusal(
                "replay_inputs_mismatched",
                "the snapshot handed to the checker is not the one the record pins",
            )
        repeated = sorted({seed for seed in self.seeds if self.seeds.count(seed) > 1})
        if repeated:
            raise CheckerRefusal(
                "seed_counted_twice",
                f"seed(s) {repeated} appear twice; one draw counted twice moves the "
                "rate without adding a sample",
            )
        if self.budget_parameter not in self.snapshot.planner_parameters:
            raise CheckerRefusal(
                "budget_parameter_not_recorded",
                f"the snapshot records no {self.budget_parameter!r}, so there is no "
                "configured budget to be a multiple of — and a sweep against a "
                "guessed baseline measures the guess",
            )
        return self


def check_rrt_convergence(evidence: ConvergenceEvidence, *, planner: ReplayPlanner) -> CheckOutcome:
    """Does this planner reach the corridor by design, or by sampling luck.

    Runs the recorded query at every seed, at each preregistered budget,
    and compares the rates. Three outcomes and only one of them is the
    mechanism:

    reliable at the configured budget
        ``refuted``. The planner finds it; whatever went wrong was not
        the sample budget.
    intermittent, and the rate rises with the budget
        ``supported``. The corridor is being found by luck, which is the
        claim.
    intermittent, and the rate does not move
        ``refuted``. A rate flat in the budget points at the geometry,
        not at the sampling — and reporting it as "not enough samples"
        would send somebody to tune the wrong knob.

    Too few seeds raises instead of guessing. A rate over four draws is
    the shape four draws happen to make.
    """
    if len(evidence.seeds) < MINIMUM_SEEDS_FOR_CONVERGENCE:
        raise CheckerRefusal(
            "insufficient_seeds",
            f"{len(evidence.seeds)} seed(s); a success rate needs at least "
            f"{MINIMUM_SEEDS_FOR_CONVERGENCE} draws to be a rate rather than an "
            "anecdote about the draws that happened",
        )

    base = ReplayRequest.from_snapshot(evidence.snapshot)
    configured = float(evidence.snapshot.planner_parameters[evidence.budget_parameter])
    rates: dict[float, float] = {}
    for multiplier in BUDGET_MULTIPLIERS:
        parameters = dict(base.planner_parameters)
        parameters[evidence.budget_parameter] = int(round(configured * multiplier))
        reached = 0
        for seed in evidence.seeds:
            plan = planner.replay(
                base.model_copy(update={"planner_parameters": parameters, "seed": seed})
            )
            reached += 1 if plan.outcome == "path" else 0
        rates[multiplier] = reached / len(evidence.seeds)

    at_budget = rates[BUDGET_MULTIPLIERS[0]]
    at_high = rates[BUDGET_MULTIPLIERS[-1]]
    measurements = {
        "seeds_run": float(len(evidence.seeds)),
        "seeds_reaching_corridor": at_budget * len(evidence.seeds),
        "success_rate_at_budget": at_budget,
        "success_rate_at_high_budget": at_high,
        "budget_multiplier": float(BUDGET_MULTIPLIERS[-1]),
    }

    if at_budget >= RELIABLE_AT_BUDGET:
        return CheckOutcome(
            proposition_type="sampling_budget_insufficiency",
            verdict="refuted",
            measurements=measurements,
            note=(
                f"at the configured budget the corridor is reached on "
                f"{at_budget:.0%} of {len(evidence.seeds)} seeds; the planner finds "
                "it reliably and the budget is not what failed"
            ),
        )
    if at_high - at_budget < BUDGET_SENSITIVITY:
        return CheckOutcome(
            proposition_type="sampling_budget_insufficiency",
            verdict="refuted",
            measurements=measurements,
            note=(
                f"the rate is {at_budget:.0%} at the configured budget and "
                f"{at_high:.0%} at {BUDGET_MULTIPLIERS[-1]:g}x; a rate that does not "
                "move with the budget points at the geometry rather than at sampling"
            ),
        )
    return CheckOutcome(
        proposition_type="sampling_budget_insufficiency",
        verdict="supported",
        measurements=measurements,
        note=(
            f"the corridor is reached on {at_budget:.0%} of seeds at the configured "
            f"budget and {at_high:.0%} at {BUDGET_MULTIPLIERS[-1]:g}x — it is being "
            "found by sampling luck rather than by the planner's design"
        ),
    )
