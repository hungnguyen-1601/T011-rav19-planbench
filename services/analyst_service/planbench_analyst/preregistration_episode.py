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

    #: The margin below which two episodes that both reached the goal
    #: are one answer, as a fraction of the slower one's travel time.
    #:
    #: **Written down here on 2026-08-29, after the distribution was
    #: visible, and that has to be said rather than hidden.** The branch
    #: it feeds exists because a candidate gated out at run level is
    #: scored on no episode at all, so every pairing with a gated side
    #: fell through to "undecidable" — including episodes where the two
    #: differed by a third of the journey, which then read downstream as
    #: "these were alike".
    #:
    #: A tenth is not the number that separates this data; the gaps in
    #: hand are 20-46% on one side and 1-10% on the other, and anything
    #: from 0.11 to 0.19 would split them identically. It is a tenth
    #: because a tenth of a journey is the smallest difference this
    #: deployment's own efficiency objective would notice, and because a
    #: round number nobody can tune is worth more here than a fitted one.
    #: The honest reading is that this margin is **not validated**: it is
    #: declared, and the first set it is applied to is the set it was
    #: declared after seeing.
    outcome_margin: float = 0.10

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
    #: What the rewording arm runs at instead, and why it is not three.
    #:
    #: **Two, because the budget left is 1.39 USD and three repeats
    #: estimate at 0.93 with a seven per cent error already observed on
    #: the last estimate.** Written before the arm ran rather than after,
    #: and the reason is money rather than results: nothing about this
    #: arm has been measured yet, so there is no result it could be
    #: chosen to flatter.
    #:
    #: Two is enough for what this arm asks, because it carries its own
    #: control: a round where every proposal was removed over wording is
    #: the baseline, and the second turn is the intervention, so the
    #: comparison is inside each round rather than against another arm.
    #: A paired arm would also have been the wrong control - the packets
    #: changed under `outcome_margin`, so nothing run today compares with
    #: the sweeps run before it.
    reword_arm_repeats: int = 2
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

    #: The hold-out cluster, and how its episodes are chosen.
    #:
    #: **Every episode of it, and one pass over each.** Not the exemplar
    #: recipe: that yields four episodes from one run, and four is too
    #: few to say whether anything generalises. Not more repeats either —
    #: repeats measure how much one model varies on one episode, which
    #: stages two and three already measured, while what is missing is
    #: whether the numbers survive episodes nobody tuned against.
    #:
    #: Taking all of them is also the only selection with nothing to
    #: choose: any subset of a cluster whose contents are already visible
    #: is a subset somebody picked.
    #:
    #: What this cluster does **not** hold out, said here rather than in
    #: a footnote: it is the same map and the same deployment as
    #: `sudden_stop_custom_v2`, so it tests the prompt, the rewording
    #: rules and the rubric against a new pairing, and tests neither the
    #: map's geometry nor the `outcome_margin` threshold. Every one of
    #: its thirty episodes decides on utility, so the threshold is not
    #: exercised at all — which is the honest position for a number
    #: declared after its own distribution was visible.
    holdout_case_selection: str = "every_episode_of_the_cluster_once"
    holdout_arm: str = "ep_b1"

    #: How many times the hold-out cluster is read per arm.
    #:
    #: **Raised from the one implied by ``holdout_case_selection`` to
    #: three on 2026-08-30, and the reason is that one reading turned out
    #: not to measure what it was read as.** Two arms scored under r0.2.0
    #: each landed six episodes at `explains` out of the eighteen whose
    #: packet could answer — and they were not the same six. Four of the
    #: six differ. A count that holds still while its membership turns
    #: over is a count whose run-to-run variation is at least as large as
    #: the difference between the arms, and nothing run at one reading
    #: per episode can separate the two.
    #:
    #: Three is the smallest number that says anything about that: it
    #: gives every episode a majority, so "this episode is explained" and
    #: "this episode is sometimes explained" stop being the same
    #: observation. It is not enough for an interval and is not claimed
    #: to be.
    #:
    #: **The cluster is still read whole.** Reading only the eighteen
    #: episodes that carry a supported contrast would cost a third less
    #: of the scorer's afternoon and would have been defensible — the
    #: property is the packet's and is computed before any output is
    #: seen — but it would end comparison with the three arms already
    #: scored, whose `describes_only` and `silent_correctly` counts are
    #: over all thirty.
    holdout_repeats: int = 3

    #: What counts as an episode the packet could have explained.
    #:
    #: The denominator for the one number this scope is about — the
    #: share of episodes where an arm said why one side beat the other —
    #: and it is computed rather than judged, so a scorer is not also
    #: deciding which episodes had an answer available.
    #:
    #: **Narrowed on 2026-08-31, and the direction has to be declared
    #: because it flatters the result.** A contrast is graded `support`
    #: by kind, and the two detection kinds qualify because a detector
    #: firing on one side and not the other is evidence about a
    #: mechanism — except where the registry names no mechanism.
    #: `near_miss_cluster` has no entry, so its contrasts arrived with
    #: no proposition and no owner while still counting as `support`;
    #: two of the three statements a scorer marked `wrong` on the last
    #: sweep rested on one, blaming two different components. Demoting
    #: those to `context` removes one episode from the eighteen.
    #:
    #: That episode scored `describes_only`, `describes_only`, `wrong`
    #: across its three readings — no `explains` at all — so the
    #: measured rate moves from 10/18 to 10/17, from 0.56 to 0.59,
    #: **upward, on a change to the platform rather than to the arm.**
    #: Both are to be reported wherever either is. The reasoning stands
    #: on its own — a detection with no mechanism behind it cannot
    #: license a claim about a component — and it was written down
    #: before the arithmetic was run, but neither fact makes a rate that
    #: rose after a guard change safe to quote alone.
    holdout_denominator: str = "episodes_with_a_supported_contrast"

    #: Judged blind, by one person, against the rubric fixed on 26-08.
    #:
    #: **Amended to r0.2.0 on 2026-08-30, and the amendment makes the
    #: bar harder rather than easier.** r0.1.0 scores statements: of the
    #: sentences an arm wrote, how many hold against the packet and cite
    #: it. That is a precision measure, and it is maxed by saying
    #: nothing — which is what happened. On `holdout-b1` the arm
    #: abstained on nineteen of thirty-seven blocks, every abstention
    #: was marked `should_have`, and none of that reaches the headline,
    #: because r0.1.0 has no denominator for a sentence never written.
    #: Half the sample was invisible to the number reported for it.
    #:
    #: R6 adds the question the experiment was for: on this episode, did
    #: the arm say **why one side beat the other**. It is scored per
    #: episode rather than per statement, over the episodes whose packet
    #: carries a `support`-strength contrast — a denominator the sheet
    #: computes, so a scorer is not also deciding which episodes had an
    #: answer available.
    #:
    #: Amending a rubric after seeing results is the move this project
    #: forbids, so the direction matters: nothing that scored under
    #: r0.1.0 is rescored more leniently, r0.1.0's marks are kept as
    #: they were, and the new axis can only lower an arm's standing.
    #: Artifacts already written keep their own `preregistration_checksum`
    #: and are not restated under the new id.
    rubric: str = "r0.2.0"
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
            "outcome_margin": self.outcome_margin,
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
            "reword_arm_repeats": self.reword_arm_repeats,
            "stage_two_arms": self.stage_two_arms,
            "stage_two_rule": self.stage_two_rule,
            "stage_two_tiebreak": self.stage_two_tiebreak,
            "rubric": self.rubric,
            "scoring": self.scoring,
            "holdout": self.holdout,
            "holdout_case_selection": self.holdout_case_selection,
            "holdout_repeats": self.holdout_repeats,
            "holdout_denominator": self.holdout_denominator,
            "holdout_arm": self.holdout_arm,
            "conclusion_class": self.conclusion_class,
            "max_usd": self.max_usd,
            "model": self.model,
        }


EPISODE_PREREGISTRATION = EpisodePreregistration()


def episode_preregistration_checksum() -> str:
    """Goes on every artifact this experiment writes."""
    return artifact_checksum(EPISODE_PREREGISTRATION.as_dict())
