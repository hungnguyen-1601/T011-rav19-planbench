"""What the explanation panel shows for each way a run can end — E4.

A run produces one of five outcomes, and four of them are not "here is
why A won". The panel has to say something different in each, because
the failure mode is uniform: an empty panel reads as *nothing to
report*, and three of these outcomes mean *there was nothing to
compare*, which is a different sentence and a different next action.

+-------------------+------------------------------------------------+
| outcome           | what the panel is for                          |
+===================+================================================+
| ``clear``         | why the recommendation won: waterfall, claims, |
|                   | exemplars                                      |
| ``near_equivalent``| the same evidence, under a headline saying    |
|                   | the difference is inside the noise and the     |
|                   | tie-break decided it                           |
| ``no_survivors``  | who failed which gate. No ΔU exists, so no     |
|                   | waterfall and no "why A beat B"                |
| ``gate_only``     | the *deployment* cannot rank anybody. Nothing  |
|                   | a candidate does changes it                    |
| ``interrupted``   | what did run is valid and smaller; the panel   |
|                   | says so beside every number                    |
+-------------------+------------------------------------------------+

**The three no-card outcomes are not one state.** Collapsing them into
"no recommendation" is what makes a gate table read like a failure:
`no_survivors` asks for a better candidate, `gate_only` asks for a
deployment whose threshold leaves room above it, and `interrupted` asks
for the rest of the episodes. Same blank card, three different jobs.

This module decides *what may be shown*, not how it looks. The flags are
data so the same decision serves the web panel, the exported report and
any future surface — three renderers each deciding for themselves when a
waterfall is meaningful is three chances to show one where ΔU does not
exist.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

RunOutcome = Literal[
    "clear",
    "near_equivalent",
    "no_survivors",
    "gate_only",
    "interrupted",
]

RUN_OUTCOMES: tuple[RunOutcome, ...] = (
    "clear",
    "near_equivalent",
    "no_survivors",
    "gate_only",
    "interrupted",
)


class PanelRefusal(ValueError):
    """A panel plan that would show something the run cannot support."""


class PanelPlan(BaseModel):
    """What the explanation surface may render for one run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    outcome: RunOutcome
    #: A ΔU decomposition only exists where a paired comparison ran.
    show_waterfall: bool
    #: Claims are about *why one candidate beat another*. Without a
    #: comparison there is no such question to answer.
    show_claims: bool
    #: The four preregistered episodes, which also need a pair.
    show_exemplars: bool
    #: The episode replays themselves. **True everywhere**, including
    #: the outcomes with no comparison: a candidate that failed a gate
    #: has traces, and they are exactly what somebody asking "why did it
    #: fail" needs to open. An earlier version gated the whole viewer on
    #: ``show_exemplars`` and so hid the evidence for the three outcomes
    #: whose only content is evidence.
    show_trace_evidence: bool = True
    #: Which gates eliminated whom. Useful in every outcome, and the
    #: entire content of three of them.
    show_gate_table: bool
    #: i18n key for the sentence at the top of the panel.
    headline_key: str = Field(min_length=1)
    #: i18n keys for caveats that must appear beside the numbers, not in
    #: a footnote nobody scrolls to.
    caveat_keys: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _check(self) -> PanelPlan:
        if self.show_exemplars and not self.show_trace_evidence:
            raise PanelRefusal(
                "exemplars are four episodes to open in the replay viewer, so hiding "
                "the viewer while offering them leaves four links to nowhere"
            )
        comparable = self.outcome in ("clear", "near_equivalent", "interrupted")
        if not comparable and (self.show_waterfall or self.show_claims or self.show_exemplars):
            raise PanelRefusal(
                f"outcome {self.outcome!r} has no paired comparison, so there is no ΔU to "
                "decompose, nobody to compare episodes between, and no 'why A won' to "
                "claim. Showing any of those would answer a question this run never asked"
            )
        return self


#: The five plans, written out rather than derived from a rule.
#:
#: A rule would be shorter and would hide the decision: the interesting
#: content here is *which caveat travels with which outcome*, and that is
#: five judgements, not one formula.
#:
#: ``interrupted`` appears twice, because it is two situations. A run
#: that stopped after ranking has a comparison and a caveat about its
#: size; one that stopped before ranking has no ΔU at all. The first
#: version of this module had one ``interrupted`` plan with the
#: comparison switched on, and ``outcome_of`` happily returned it for an
#: unranked run — each function correct alone, the pair producing a
#: panel that decomposes a difference nobody computed.
PANEL_PLANS: dict[tuple[RunOutcome, bool], PanelPlan] = {
    ("clear", True): PanelPlan(
        outcome="clear",
        show_waterfall=True,
        show_claims=True,
        show_exemplars=True,
        show_gate_table=True,
        headline_key="explain.headline.clear",
        caveat_keys=("explain.caveat.scope",),
    ),
    ("near_equivalent", True): PanelPlan(
        outcome="near_equivalent",
        show_waterfall=True,
        show_claims=True,
        show_exemplars=True,
        show_gate_table=True,
        headline_key="explain.headline.nearEquivalent",
        # The interval covers zero, so the ranking did not decide this —
        # the declared tie-break ladder did, and a reader who misses that
        # reads a coin flip as a measurement.
        caveat_keys=(
            "explain.caveat.insideTheNoise",
            "explain.caveat.tieBreak",
            "explain.caveat.scope",
        ),
    ),
    ("no_survivors", False): PanelPlan(
        outcome="no_survivors",
        show_waterfall=False,
        show_claims=False,
        show_exemplars=False,
        show_gate_table=True,
        headline_key="explain.headline.noSurvivors",
        caveat_keys=("explain.caveat.registerABetterCandidate",),
    ),
    ("gate_only", False): PanelPlan(
        outcome="gate_only",
        show_waterfall=False,
        show_claims=False,
        show_exemplars=False,
        show_gate_table=True,
        headline_key="explain.headline.gateOnly",
        # Never "try a softer deployment": the threshold is the
        # customer's requirement, and lowering it to get a ranking is
        # the one move this platform exists to make visible.
        caveat_keys=("explain.caveat.deploymentCannotRank",),
    ),
    ("interrupted", True): PanelPlan(
        outcome="interrupted",
        show_waterfall=True,
        show_claims=True,
        show_exemplars=True,
        show_gate_table=True,
        headline_key="explain.headline.interrupted",
        caveat_keys=("explain.caveat.fewerEpisodes", "explain.caveat.scope"),
    ),
    ("interrupted", False): PanelPlan(
        outcome="interrupted",
        show_waterfall=False,
        show_claims=False,
        show_exemplars=False,
        show_gate_table=True,
        headline_key="explain.headline.interruptedBeforeRanking",
        caveat_keys=(
            "explain.caveat.fewerEpisodes",
            "explain.caveat.noComparisonYet",
        ),
    ),
}


def plan_for(outcome: RunOutcome, *, has_comparison: bool) -> PanelPlan:
    """The panel plan for one outcome.

    ``has_comparison`` has no default on purpose. It is the fact that
    decides whether half the panel exists, and a default would let a
    caller who never thought about it get the answer that draws the most.
    """
    key = (outcome, has_comparison)
    if key in PANEL_PLANS:
        return PANEL_PLANS[key]
    if outcome in ("clear", "near_equivalent") and not has_comparison:
        raise PanelRefusal(
            f"outcome {outcome!r} is a statement about a paired comparison, so "
            "has_comparison=False contradicts it: a run that ranked its candidates "
            "has one by construction"
        )
    raise PanelRefusal(
        f"outcome {outcome!r} never has a paired comparison, so has_comparison=True "
        "asks for a decomposition of a difference that was never computed"
    )


def outcome_of(
    *,
    ranked: bool,
    status: str | None,
    interrupted: bool,
    gate_only: bool,
) -> RunOutcome:
    """Which of the five this run is, from what the report already says.

    Order matters and is the argument of the function. ``interrupted``
    is checked first among the no-card cases because a run that stopped
    early may *also* have had nobody survive — and "we did not finish"
    is the fact that makes the second one uninterpretable, so it is the
    one to lead with.

    Whether that interrupted run *has* a comparison is a separate
    question, answered by ``ranked`` and passed to :func:`plan_for`;
    see :func:`panel_for`.
    """
    if not ranked:
        if interrupted:
            return "interrupted"
        if gate_only:
            return "gate_only"
        return "no_survivors"
    if interrupted:
        return "interrupted"
    if status == "NEAR_EQUIVALENT":
        return "near_equivalent"
    return "clear"


def panel_for(
    *,
    ranked: bool,
    status: str | None,
    interrupted: bool,
    gate_only: bool,
) -> PanelPlan:
    """Outcome and plan in one call, so the two cannot be paired wrongly.

    The composition is the API. Calling ``outcome_of`` and ``plan_for``
    separately is what produced a waterfall on an unranked run: both
    calls were right, and nothing checked that they were about the same
    run.
    """
    outcome = outcome_of(ranked=ranked, status=status, interrupted=interrupted, gate_only=gate_only)
    return plan_for(outcome, has_comparison=ranked)
