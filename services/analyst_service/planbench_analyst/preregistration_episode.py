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
    #:
    #: **Every one is read off the answer a person is handed, never off
    #: the guard's own activity.** Written as counts of firings in the
    #: first version, which the first real sweep exposed as meaningless:
    #: rule 2 fired 55 times across twelve episodes and every firing was
    #: a sentence the guard had already removed, so the arm scored 55
    #: violations of a ceiling of zero for behaving correctly. The
    #: definition was wrong on its own terms — it would have read the
    #: same way had the number been flattering — and the names below now
    #: carry ``_in_final`` so no later reader can mistake which is being
    #: counted. Corrected 2026-08-27, after data and before any arm was
    #: selected on it.
    hard_constraints: tuple[tuple[str, float], ...] = (
        # A surviving statement handing the episode to the side the
        # platform did not name. Rule 9 drops these, so a count above
        # zero means the guard is off, not that the model is bold.
        ("verdict_contradictions_in_final", 0.0),
        # A hypothesis still presented as bearing on the outcome without
        # the four things the contract asks of one. Rule 10 demotes
        # rather than drops, so a non-zero count means the demotion did
        # not happen.
        ("contrast_contract_unmet_in_final", 0.0),
        # A number in a surviving statement. Rule 2, and scope-blind.
        ("quantities_in_statements_in_final", 0.0),
        # A surviving statement naming the twelve-character hash of a
        # candidate. The model is shown labels and never an id, so an id
        # in an answer is either a guess or a leak from the view. Added
        # 2026-08-27 because the first sweep produced it, not because it
        # was foreseen: o4-mini wrote sentences about "the local
        # controller of e1251e42a20b" on every arm.
        ("candidate_ids_in_final", 0.0),
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
    case_selection: str = "four_exemplar_roles_per_cluster_or_cardless_rule"
    #: The cardless clusters do not use the exemplar recipe — three of
    #: its four roles are defined on ΔU, which a run with no card does
    #: not have on both sides — so they contribute every episode where
    #: the two sides disagree about reaching the goal plus a fixed
    #: sample of the rest. That makes cluster sizes unequal (nine
    #: against four), which is why the endpoint is read **per cluster**
    #: and reported as counts: an unequal cluster pooled into a rate
    #: would weigh one run more heavily than another for no reason but
    #: how many of its episodes were decidable.
    cardless_case_selection: str = "all_disagreements_plus_fixed_control_sample"
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
    #:
    #: The second half reads the ``*_blocked`` figures and **is meant
    #: to** — unlike a veto, it is comparative and against the baseline
    #: rather than against a ceiling of zero, so an arm whose sentences
    #: the guard has to remove more often than b1's is worse in the way
    #: this says it is. Left as written when the vetoes were corrected,
    #: because it is not the same error and rewriting a selection rule
    #: that is sound is what the preregistration exists to stop.
    stage_two_rule: str = "no_hard_constraint_violated_and_guard_drops_not_worse_than_b1"

    #: How four eligible arms become the two stage two has room for.
    #:
    #: **An amendment, added 2026-08-27 after stage one and before stage
    #: two ran**, because the rule above was silent on it: it says which
    #: arms are *eligible* and the field beside it says two go through,
    #: and stage one produced four eligible arms. Deciding the cut by
    #: eye at that point is the whole failure mode a preregistration
    #: exists to stop, so the cut is written as a rule instead:
    #:
    #: * the baseline always goes through — stage two compares arms, and
    #:   without b1 in it there is nothing the other arm is better *than*;
    #: * the other seat goes to the eligible arm with the fewest guard
    #:   drops, which is the same figure the eligibility rule already
    #:   reads, taken to its extreme rather than to its threshold;
    #: * ties broken by the arm name, so nothing is left to whoever runs
    #:   it.
    #:
    #: On stage one this selects **ep_no_union** (9 drops) beside b1 (12),
    #: over ep_shortlist (10) and ep_run_context (12).
    stage_two_tiebreak: str = "baseline_plus_fewest_guard_drops_then_by_name"

    #: Judged blind, by one person, against the rubric fixed on 26-08.
    rubric: str = "r0.1.0"
    scoring: str = "blind_to_arm_single_scorer"

    #: The ceiling on this experiment, stated as data so a report cannot
    #: quietly omit it.
    holdout: bool = False
    conclusion_class: str = "exploratory"

    #: What the whole thing may cost. Read by the runner, which stops
    #: rather than continuing past it.
    #:
    #: **Raised from 3.00 to 4.50 on 2026-08-29, with An's approval, and
    #: the reason is scope rather than results.** Three USD paid for the
    #: twelve cases of `case_selection`; the set is now seventeen,
    #: because a run the platform refused to write a decision card for
    #: turned out to be readable — a card needs two candidates through
    #: six gates, while `outcome_only` needs neither, and that cluster
    #: carries the five hardest explanations in the experiment plus the
    #: four undecided episodes an arm has to decline on. The ceiling
    #: covers a larger question, not a second attempt at the same one:
    #: nothing already measured is re-run, and no arm was selected on
    #: anything this buys.
    max_usd: float = 4.5
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
            "cardless_case_selection": self.cardless_case_selection,
            "clusters": list(self.clusters),
            "cases_per_cluster": self.cases_per_cluster,
            "stage_one_repeats": self.stage_one_repeats,
            "stage_two_repeats": self.stage_two_repeats,
            "stage_two_arms": self.stage_two_arms,
            "stage_two_rule": self.stage_two_rule,
            "stage_two_tiebreak": self.stage_two_tiebreak,
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
