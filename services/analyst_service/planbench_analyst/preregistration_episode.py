"""The bar for the episode scope, written down before any run moves it.

A second constant beside the run scope's rather than an edit to it. That
one is what a frozen bundle was calibrated against, and rewriting it to
describe a different experiment would silently redefine what an existing
calibration meant.

**This experiment cannot produce a deployment decision, and says so
here rather than in a footnote.** Three things are missing and each on
its own is enough:

* the golden fixtures carry no per-episode utility, so the only episodes
  with a real verdict come from **recorded runs nobody planted an
  answer into** — correctness is read by a human against a rubric, not
  computed against a label;
* there are **three clusters**, one of which recorded no trace, and a
  cluster is a run: episodes inside one share a map, a pair, a build and
  a task. Twelve episodes is twelve observations of three things;
* nothing is held out. Every arm is read on the same twelve.

What it can do is compare arms on the same episodes under one rubric,
and say which of them is worth paying for on a larger set later.
"""

from __future__ import annotations

from dataclasses import dataclass

from planbench_explanation.versioning import artifact_checksum

__all__ = [
    "EPISODE_PREREGISTRATION",
    "EpisodePreregistration",
    "episode_preregistration_checksum",
]


@dataclass(frozen=True)
class EpisodePreregistration:
    """The bar for one episode's explanation, as data. Frozen and hashed."""

    #: The margin below which two episode utilities are one answer.
    #:
    #: Fixed **before** any episode was scored with it, which is the only
    #: property that matters: a margin chosen after the distribution is
    #: visible is a margin chosen to produce a winner. Half a percent of
    #: the [0, 1] utility range.
    tie_epsilon: float = 0.005

    #: Vetoes. A configuration that violates one is not compared on
    #: anything else, however well it reads.
    hard_constraints: tuple[tuple[str, float], ...] = (
        # A statement handing the episode to the side the platform did
        # not name. Rule 9 drops these; a count above zero means the
        # guard is off, not that the model is bold.
        ("verdict_contradictions", 0.0),
        # A hypothesis presented as bearing on the outcome without the
        # four things the contract asks of one. Rule 10 demotes these,
        # so a non-zero count in the *final* answer means the demotion
        # did not happen.
        ("contrast_contract_unmet_in_final", 0.0),
        # A number in a statement. Rule 2, and scope-blind.
        ("quantities_in_statements", 0.0),
    )

    #: The one number the conclusion is about.
    #:
    #: Not "mechanism correctness": these episodes have no planted
    #: mechanism to be correct about. What is read is whether a
    #: hypothesis offered as bearing on the outcome **holds up** against
    #: the packet a human reads beside it — the rubric's R1 and R2 taken
    #: together, on the findings the platform let through.
    primary_endpoint: str = "contrast_holds_up_rate_cluster_level"
    #: Read per cluster and reported per cluster. A rate over twelve
    #: episodes from three runs is not a rate over twelve trials.
    primary_unit: str = "cluster"
    #: Reported as counts. Twelve episodes across three clusters is far
    #: below anything a proportion should be quoted from, and the run
    #: scope's own preregistration draws that line at twelve **cases**.
    report_as: str = "counts"

    secondary_endpoints: tuple[str, ...] = (
        # Was the register the model claimed the one the platform kept?
        "bearing_agreement",
        # Of what it offered as a contrast, how much survived rule 10?
        "contrast_survival_rate",
        # Did it decline where the episode gave it nothing?
        "abstention_correctness",
        # Every citation resolves and speaks about what was claimed.
        "evidence_relevance",
        "cost_median_tokens",
        "latency_median_s",
    )

    #: How the twelve were chosen, fixed before they were looked at.
    #:
    #: The exemplar recipe rather than a hand-picked dozen: it is
    #: preregistered, deterministic, and already used by the replay page,
    #: so the episodes an arm is read on are the episodes a reader would
    #: have opened anyway.
    case_selection: str = "four_exemplar_roles_per_cluster"
    clusters: tuple[str, ...] = (
        "sudden_stop_v5_local_controller_selection",
        "sudden_stop_v6_full_stack_selection",
        "demo_hall_global_planner_selection",
    )
    cases_per_cluster: int = 4

    #: Stage one reads every arm once; stage two repeats the two that
    #: survive. Written down because "which arms went through to stage
    #: two" is a decision, and a decision taken after the numbers are in
    #: is the flattering one.
    stage_one_repeats: int = 1
    stage_two_repeats: int = 3
    stage_two_arms: int = 2
    #: What lets an arm through: it violated no hard constraint, and it
    #: did not drop more of its own proposals than the baseline did.
    stage_two_rule: str = "no_hard_constraint_violated_and_guard_drops_not_worse_than_b1"

    #: Judged blind, by one person, against the rubric fixed on 26-08.
    rubric: str = "r0.1.0"
    scoring: str = "blind_to_arm_single_scorer"

    #: The ceiling on this experiment, stated as data so a report cannot
    #: quietly omit it.
    holdout: bool = False
    conclusion_class: str = "exploratory"

    #: What the whole thing may cost. Read by the runner, which stops
    #: rather than continuing past it.
    max_usd: float = 3.0
    model: str = "o4-mini"

    def as_dict(self) -> dict[str, object]:
        return {
            "tie_epsilon": self.tie_epsilon,
            "hard_constraints": [list(item) for item in self.hard_constraints],
            "primary_endpoint": self.primary_endpoint,
            "primary_unit": self.primary_unit,
            "report_as": self.report_as,
            "secondary_endpoints": list(self.secondary_endpoints),
            "case_selection": self.case_selection,
            "clusters": list(self.clusters),
            "cases_per_cluster": self.cases_per_cluster,
            "stage_one_repeats": self.stage_one_repeats,
            "stage_two_repeats": self.stage_two_repeats,
            "stage_two_arms": self.stage_two_arms,
            "stage_two_rule": self.stage_two_rule,
            "rubric": self.rubric,
            "scoring": self.scoring,
            "holdout": self.holdout,
            "conclusion_class": self.conclusion_class,
            "max_usd": self.max_usd,
            "model": self.model,
        }


EPISODE_PREREGISTRATION = EpisodePreregistration()


def episode_preregistration_checksum() -> str:
    """Goes on every artifact this experiment writes."""
    return artifact_checksum(EPISODE_PREREGISTRATION.as_dict())
