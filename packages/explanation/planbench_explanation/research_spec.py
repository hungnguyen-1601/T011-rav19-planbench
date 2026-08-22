"""Experiments an analyst may describe and nobody may run — E5.

``intervention_supported`` is the top of the evidence ladder and the one
rung no amount of reading recorded data reaches: it needs a new run
where one thing was changed on purpose. An analyst that notices this
will, quite reasonably, want to propose one. Three tools let it — and
all three produce a **document**.

The specification is the deliverable. It names the axis to vary, what is
held constant, how many episodes and which seeds, and — before any of it
runs — what result would count as support and what would count as
refutation. Executing it is a person's decision in the research lane,
with a runner that enforces the policy end to end. Nothing here starts a
run, and :class:`~planbench_explanation.tools.ToolCard` refuses a
research-proposal card that claims otherwise.

**The preregistered outcome is required, not encouraged.** An
intervention whose success criterion is written after the numbers are in
is an intervention that succeeded. The field is mandatory and the
promotion matrix reads
:class:`~planbench_explanation.ledger.InterventionEvidence`, which
requires a preregistration reference, so a spec without one produces
evidence the matrix will not accept anyway.

**One axis at a time, and the schema counts.** Two components swapped
together produce a difference nobody can assign — the same
``interaction_not_isolated`` verdict the contrast lattice returns for a
multi-axis pair. Better refused when the experiment is designed than
discovered when it is analysed.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from planbench_explanation.propositions import PropositionType
from planbench_explanation.subjects import Subject

#: Which lane a specification may ever run in. One value: writing it
#: down as a Literal means a spec cannot describe itself as diagnostic
#: and slip past a host that filters on the lane.
ResearchLane = Literal["research"]

SpecKind = Literal["component_swap", "parameter_intervention", "task_perturbation"]


class ResearchSpecRefusal(ValueError):
    """A specification that could not answer the question it poses."""


class PreregisteredOutcome(BaseModel):
    """What would count as support, and what would count as refutation.

    Both, always. A criterion for success with none for failure is a
    criterion that cannot fail: every result short of success becomes
    "inconclusive, needs more episodes".
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    metric: str = Field(min_length=1)
    supports_if: str = Field(min_length=1)
    refutes_if: str = Field(min_length=1)
    #: How the difference will be tested. Named up front so the test is
    #: not chosen after seeing which one gives the answer.
    statistical_test: str = Field(min_length=1)
    minimum_effect_size: float | None = None


class ExperimentDesign(BaseModel):
    """The part that decides whether the answer will mean anything."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    #: Episodes per arm, paired on ``episode_context_id`` as everywhere
    #: else in this platform.
    episodes_per_arm: int = Field(ge=1)
    seeds: tuple[int, ...]
    #: What must not move. The list is the experiment: an axis missing
    #: from it is an axis free to explain the result.
    held_constant: tuple[str, ...]
    paired: bool = True

    @model_validator(mode="after")
    def _check(self) -> ExperimentDesign:
        if not self.seeds:
            raise ResearchSpecRefusal(
                "a specification with no seeds cannot be re-run by whoever reads it"
            )
        if len(set(self.seeds)) != len(self.seeds):
            raise ResearchSpecRefusal("repeated seeds inflate the sample without adding runs")
        if not self.held_constant:
            raise ResearchSpecRefusal(
                "nothing is held constant, so every difference in the result has "
                "several candidate causes and the experiment answers none of them"
            )
        return self


class ResearchSpecification(BaseModel):
    """A described experiment. Never an executed one."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    spec_id: str = Field(min_length=1)
    spec_kind: SpecKind
    #: Constant by type. A spec cannot describe itself as authorised.
    execution_authorized: Literal[False] = False
    required_lane: ResearchLane = "research"
    #: Which hypothesis this would settle, and about what.
    hypothesis_id: str = Field(min_length=1)
    proposition_type: PropositionType
    subject: Subject
    #: The single thing that varies, and its levels.
    axis: str = Field(min_length=1)
    levels: tuple[str, ...]
    baseline_candidate_id: str = Field(min_length=1)
    task_profile_id: str = Field(min_length=1)
    design: ExperimentDesign
    outcome: PreregisteredOutcome
    #: What this experiment would still not settle. Written by whoever
    #: designs it, because the reader who most needs it is the one who
    #: will quote the result out of context.
    does_not_settle: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _check(self) -> ResearchSpecification:
        if len(self.levels) < 2:
            raise ResearchSpecRefusal(
                f"axis {self.axis!r} has {len(self.levels)} level(s); an intervention "
                "with one level is the run that already happened"
            )
        if len(set(self.levels)) != len(self.levels):
            raise ResearchSpecRefusal(f"axis {self.axis!r} repeats a level")
        if self.axis in self.design.held_constant:
            raise ResearchSpecRefusal(
                f"{self.axis!r} is both the axis under test and held constant; one of "
                "the two is a mistake and the schema cannot tell which"
            )
        return self

    @property
    def summary(self) -> str:
        """One line for a panel that lists proposals. Says it has not run."""
        return (
            f"proposed experiment {self.spec_id}: vary {self.axis} across "
            f"{len(self.levels)} levels on {self.task_profile_id}, "
            f"{self.design.episodes_per_arm} paired episodes per arm — not executed"
        )


def component_swap(
    *,
    spec_id: str,
    hypothesis_id: str,
    proposition_type: PropositionType,
    subject: Subject,
    component: str,
    alternatives: tuple[str, ...],
    baseline_candidate_id: str,
    task_profile_id: str,
    design: ExperimentDesign,
    outcome: PreregisteredOutcome,
    does_not_settle: tuple[str, ...] = (),
) -> ResearchSpecification:
    """Swap one component of the stack, hold the rest."""
    return ResearchSpecification(
        spec_id=spec_id,
        spec_kind="component_swap",
        hypothesis_id=hypothesis_id,
        proposition_type=proposition_type,
        subject=subject,
        axis=component,
        levels=alternatives,
        baseline_candidate_id=baseline_candidate_id,
        task_profile_id=task_profile_id,
        design=design,
        outcome=outcome,
        does_not_settle=does_not_settle,
    )


def parameter_intervention(
    *,
    spec_id: str,
    hypothesis_id: str,
    proposition_type: PropositionType,
    subject: Subject,
    parameter: str,
    levels: tuple[str, ...],
    baseline_candidate_id: str,
    task_profile_id: str,
    design: ExperimentDesign,
    outcome: PreregisteredOutcome,
    does_not_settle: tuple[str, ...] = (),
) -> ResearchSpecification:
    """Vary one parameter across declared levels, hold the rest."""
    return ResearchSpecification(
        spec_id=spec_id,
        spec_kind="parameter_intervention",
        hypothesis_id=hypothesis_id,
        proposition_type=proposition_type,
        subject=subject,
        axis=parameter,
        levels=levels,
        baseline_candidate_id=baseline_candidate_id,
        task_profile_id=task_profile_id,
        design=design,
        outcome=outcome,
        does_not_settle=does_not_settle,
    )


def task_perturbation(
    *,
    spec_id: str,
    hypothesis_id: str,
    proposition_type: PropositionType,
    subject: Subject,
    feature: str,
    levels: tuple[str, ...],
    baseline_candidate_id: str,
    task_profile_id: str,
    design: ExperimentDesign,
    outcome: PreregisteredOutcome,
    does_not_settle: tuple[str, ...] = (),
) -> ResearchSpecification:
    """Change the task itself — which makes a new profile, and a new run."""
    return ResearchSpecification(
        spec_id=spec_id,
        spec_kind="task_perturbation",
        hypothesis_id=hypothesis_id,
        proposition_type=proposition_type,
        subject=subject,
        axis=feature,
        levels=levels,
        baseline_candidate_id=baseline_candidate_id,
        task_profile_id=task_profile_id,
        design=design,
        outcome=outcome,
        does_not_settle=does_not_settle,
    )
