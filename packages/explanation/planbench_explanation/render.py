"""Turning a claim into a sentence, without letting the sentence grow — E4.

The ledger decides what may be said; this decides how. Two rules do all
the work.

**One template per rung.** The verbs are the ones the evidence ladder
licenses — "measured" at ``observed``, "consistent with" at
``associated``, "verified" at ``mechanism_verified``, "caused" only at
``intervention_supported`` — and the rendered sentence is run back
through the same lexical check the promotion matrix uses. A template is
a promise about wording; checking the output is what keeps the promise
after somebody edits the template.

**The impact sentence says which kind of impact it is.** These two are
different claims and read almost identically if nobody is careful:

``observed_contribution``
    *"the mechanism appears in the episodes where time efficiency is
    down"* — the objective moved, and this mechanism was present. It
    does **not** say the mechanism moved it.
``attributable_effect_estimate``
    *"estimated to account for part of the shortfall in time
    efficiency, by <method>"* — a model of how much, with assumptions
    and an uncertainty, and it renders with the ``estimated``
    qualifier attached.

**No number the ledger does not hold.** ``ImpactRef`` deliberately
carries no float, so these sentences name the objective, the kind and
the method, and point at the artifact for the figures. A renderer that
printed a number would be printing one it made up.

Nothing here renders a model's prose. E4 ships templates only; the
optional LLM phrasing station of the design note sits behind the same
claim ledger and the same lexical gate, and it is not part of this.
"""

from __future__ import annotations

from planbench_explanation.ledger import Claim, ImpactRef
from planbench_explanation.levels import ClaimLevel, PhrasePolicy, check_phrases

#: One frame per rung. ``{subject}`` and ``{statement}`` are filled from
#: the claim; the verb is fixed by the frame, which is the point.
LEVEL_TEMPLATES: dict[ClaimLevel, str] = {
    "observed": "Measured: {statement}.",
    "associated": "Consistent with {subject}: {statement}.",
    "mechanism_verified": "Verified for {subject}: {statement}.",
    "intervention_supported": "Caused by {subject}: {statement}. Scope: {scope}.",
}

#: How each impact kind is allowed to be worded. Separate from the level
#: frames because a claim can be verified and still only carry an
#: observed contribution — the two say different things and both have to
#: survive on the same line.
IMPACT_TEMPLATES: dict[str, str] = {
    "observed_contribution": (
        " The mechanism appears in the episodes where {objective} is unfavourable; "
        "how much of that it accounts for is not established. Figures: {artifact}."
    ),
    "attributable_effect_estimate": (
        " Estimated to account for part of the shortfall in {objective}, by {method}. "
        "Figures, assumptions and uncertainty: {artifact}."
    ),
}

#: What the panel prints where a claim would have gone. The design's
#: fifth state is the absence of a claim, and it needs its own words so
#: an empty panel is not read as "nothing was wrong".
NO_CLAIM_SENTENCE = (
    "Not enough evidence for a claim here. The observations below are symptoms, not causes."
)


class RenderRefusal(ValueError):
    """A claim that cannot be rendered without saying more than it has."""


def render_claim(claim: Claim, *, phrase_policy: PhrasePolicy | None = None) -> str:
    """One claim as one sentence, at the strength its evidence earned.

    Re-checks its own output against the level's phrase whitelist. That
    looks redundant — the templates are written to comply — and it is
    exactly the check that survives somebody rewording a template two
    months from now, or a claim whose ``statement`` carries a causal
    verb the promotion matrix let through in a language it does not
    police.
    """
    frame = LEVEL_TEMPLATES[claim.level]
    sentence = frame.format(
        subject=claim.subject.replace("_", " "),
        statement=claim.statement.rstrip("."),
        scope=claim.scope,
    )
    if claim.impact_ref is not None:
        sentence += _impact_clause(claim.impact_ref)
    if claim.qualifiers:
        sentence += f" [{', '.join(qualifier.replace('_', ' ') for qualifier in claim.qualifiers)}]"

    kwargs = {"policy": phrase_policy} if phrase_policy else {}
    violations = check_phrases(sentence, claim.level, **kwargs)  # type: ignore[arg-type]
    if violations:
        raise RenderRefusal(
            f"the rendered sentence uses {list(violations)}, which {claim.level} does not "
            f"license: {sentence!r}. Either the claim's statement overreaches or a "
            "template was edited into saying more than its rung allows"
        )
    return sentence


def _impact_clause(impact: ImpactRef) -> str:
    clause = IMPACT_TEMPLATES[impact.impact_kind].format(
        objective=impact.objective.replace("_", " "),
        method=impact.method.replace("_", " "),
        artifact=impact.artifact_ref,
    )
    if impact.profile_weighted:
        # The decomposition depends on the deployment's weights, so the
        # profile has to be on the same line as the number it produced —
        # otherwise a preference reads as a measurement. Named, not
        # merely flagged: "weighted by the preference profile" renders
        # identically for two runs that weighted things differently.
        clause += f" Weighted by preference profile {impact.profile_ref}."
    return clause


def render_no_claim(reason: str | None = None) -> str:
    """What goes where a claim would have been.

    ``reason`` is the promotion matrix's own words when there is one. An
    empty explanation panel is read as "nothing to see"; a panel saying
    a check refuted the hypothesis is read correctly, and the difference
    is one string.
    """
    if not reason:
        return NO_CLAIM_SENTENCE
    return f"{NO_CLAIM_SENTENCE} ({reason})"
