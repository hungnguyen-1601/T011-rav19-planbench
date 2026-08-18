"""The evidence ladder a claim is placed on, and the words it may use.

Four levels, and *no fifth level for ignorance*. "Not enough evidence"
is the absence of a claim, not a weak one — a fifth rung would let an
empty investigation render as a row on the panel, which is how a reader
learns to read blank space as a finding.

+--------------------------+-------------------------------------------+
| level                    | what had to be true                       |
+==========================+===========================================+
| ``observed``             | it was measured, from recorded data       |
| ``associated``           | a pattern is consistent with a mechanism  |
| ``mechanism_verified``   | a checker reproduced the narrow condition |
| ``intervention_supported``| the world was changed and the effect moved|
+--------------------------+-------------------------------------------+

The level is a property of the **evidence**, never of the pipeline that
produced the sentence. An LLM-written sentence and a template-written
sentence backed by the same record sit on the same rung.

**Qualifiers are orthogonal.** They say where a number came from, and
they never move a claim up or down: ``profile_weighted`` (the
decomposition depends on the preference profile, so the profile must be
named or a preference is being read as a measurement), ``estimated`` (a
tool's estimate, not a raw measurement), ``reconstructed_input`` (inputs
were rebuilt and not verified) and ``research_lane`` (evidence from a
diagnostic run outside the evaluation distribution).

**Why a phrase whitelist exists at all.** The failure this blocks is not
a fabricated number — the ledger already stops those. It is
``"stuck *because of* a local minimum [fact:oscillation_B7]"``: real
citation, real observation, invented causality. That is a *lexical*
defect and can be caught lexically, so it is, at render time (E4) and in
review, using the same table the promotion matrix uses.

The phrases below are English because the platform's exported report is
English. A locale is a :class:`PhrasePolicy`, not a fork of this module:
E4 adds one for the Vietnamese UI and the rules stay in one place.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Literal

from pydantic import BaseModel, ConfigDict

ClaimLevel = Literal["observed", "associated", "mechanism_verified", "intervention_supported"]

#: Weakest to strongest. Index in this tuple is the only ordering.
CLAIM_LEVEL_ORDER: tuple[ClaimLevel, ...] = (
    "observed",
    "associated",
    "mechanism_verified",
    "intervention_supported",
)

Qualifier = Literal[
    "profile_weighted",
    "estimated",
    "reconstructed_input",
    "research_lane",
]

KNOWN_QUALIFIERS: tuple[Qualifier, ...] = (
    "profile_weighted",
    "estimated",
    "reconstructed_input",
    "research_lane",
)


class UnknownClaimLevelError(ValueError):
    """A level outside :data:`CLAIM_LEVEL_ORDER`."""


def level_rank(level: ClaimLevel) -> int:
    """Position on the ladder; higher is a stronger statement."""
    try:
        return CLAIM_LEVEL_ORDER.index(level)
    except ValueError as exc:
        raise UnknownClaimLevelError(
            f"{level!r} is not a claim level; known levels are {list(CLAIM_LEVEL_ORDER)}"
        ) from exc


def weakest(*levels: ClaimLevel) -> ClaimLevel:
    """The least of the given levels — every ceiling composes this way.

    A tool card's maximum, an input provenance ceiling and a subject
    ceiling are three independent caps, and a claim may not exceed any
    of them. Taking the minimum here rather than at each call site is
    what stops one of the three being forgotten in one branch.
    """
    if not levels:
        raise ValueError("weakest() needs at least one level")
    return min(levels, key=level_rank)


class PhrasePolicy(BaseModel):
    """Which wordings each level may use, in one language."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    locale: str
    #: Phrases permitted *at* a level. A phrase belonging to a stronger
    #: level is forbidden at every weaker one — that is derived below,
    #: not listed, so the two halves cannot drift apart.
    allowed: dict[ClaimLevel, tuple[str, ...]]
    #: Wordings forbidden everywhere below ``intervention_supported``
    #: regardless of the table — the causal vocabulary readers weigh
    #: most heavily.
    causal: tuple[str, ...] = ()

    def forbidden_at(self, level: ClaimLevel) -> tuple[str, ...]:
        """Phrases that may not appear in a sentence carrying ``level``."""
        rank = level_rank(level)
        stronger = {
            phrase
            for other, phrases in self.allowed.items()
            if level_rank(other) > rank
            for phrase in phrases
        }
        if rank < level_rank("intervention_supported"):
            stronger.update(self.causal)
        return tuple(sorted(stronger))

    def violations(self, text: str, level: ClaimLevel) -> tuple[str, ...]:
        """Forbidden phrases present in ``text``, as written.

        Word-boundary matching, case-insensitive: ``"caused"`` must not
        fire on ``"because"`` and must fire on ``"Caused"``.
        """
        lowered = text.lower()
        return tuple(
            phrase
            for phrase in self.forbidden_at(level)
            if re.search(rf"(?<!\w){re.escape(phrase.lower())}(?!\w)", lowered)
        )


#: The English policy, matching the level table in the design note.
ENGLISH_PHRASES = PhrasePolicy(
    locale="en",
    allowed={
        "observed": ("measured", "recorded", "observed"),
        "associated": ("consistent with", "matches the pattern of", "co-occurs with"),
        "mechanism_verified": ("verified", "reproduced", "confirmed by replay"),
        "intervention_supported": ("caused", "is the primary cause", "eliminates"),
    },
    causal=("because of", "due to", "causes", "caused by", "responsible for"),
)


def check_phrases(
    text: str,
    level: ClaimLevel,
    *,
    policy: PhrasePolicy = ENGLISH_PHRASES,
) -> tuple[str, ...]:
    """Convenience wrapper over :meth:`PhrasePolicy.violations`."""
    return policy.violations(text, level)


def canonical_qualifiers(values: Iterable[str]) -> tuple[Qualifier, ...]:
    """Validate, deduplicate and sort qualifiers.

    Closed vocabulary for the same reason the observation tokens are
    closed (``planbench_schemas.observations``): a qualifier compared by
    string is a qualifier a typo turns off.
    """
    cleaned = {value.strip() for value in values}
    unknown = sorted(cleaned - set(KNOWN_QUALIFIERS))
    if unknown:
        raise ValueError(
            f"unknown qualifier(s) {unknown}; known qualifiers are {list(KNOWN_QUALIFIERS)}"
        )
    return tuple(sorted(cleaned))  # type: ignore[arg-type]
