"""A legal way for an analyst to put a number in a sentence.

Rule 2 forbids a quantity written out, and it is right to: a number a
reader cannot open is a number they have to take on trust, while a ref
opens onto the fact the platform measured. What the rule never gave the
analyst was somewhere else to put one. So it wrote them anyway and lost
whole sentences: across a scored hold-out, sixty per cent of rounds
ended blank and every one of them was a sentence removed for carrying a
figure the packet already held.

The way out is neither to relax the rule nor to let the platform rewrite
what the model said. It is a **placeholder**: the analyst writes
``{obs:stuck_cluster:C1@ep-1/stopped_seconds}`` where it wants the
number, and the value is filled in from the packet when somebody reads
it. The sentence stays the analyst's — it chose the words and it chose
which fact to point at — and the figure stays the platform's, resolved
from its own index at the moment of reading.

Two properties this buys that a rewrite would not:

* **the number cannot drift from the fact.** Nothing copies it, so
  nothing can copy it wrong or go stale against a re-scored run;
* **a reader can tell who said what.** The words are the model's and the
  digits are the platform's, and neither is disguised as the other.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

#: What a placeholder looks like in a statement.
#:
#: Braces because they cannot occur in a ref and read as a slot rather
#: than as punctuation. The ref inside is matched loosely and validated
#: against the packet afterwards: a pattern strict enough to encode
#: every ref shape would have to be updated in step with every new one,
#: and would fail closed in the wrong direction — silently treating an
#: unrecognised ref as prose.
PLACEHOLDER = re.compile(r"\{([^{}\s]+)\}")


class MagnitudeRefusal(ValueError):
    """A placeholder that cannot be filled, and why."""


def placeholders_in(statement: str) -> tuple[str, ...]:
    """Every ref a statement asks to have filled in."""
    return tuple(match.group(1) for match in PLACEHOLDER.finditer(statement))


def unresolvable(statement: str, facts: Mapping[str, object]) -> tuple[str, ...]:
    """Placeholders this packet cannot fill, in the order written.

    Two ways to fail and both matter. A ref the packet does not carry is
    the citation problem in miniature — a figure attributed to a
    measurement nobody made. A ref that resolves to something that is
    not a number is worse in a quieter way: it would render, and read as
    a quantity, while naming a detector or a candidate label.
    """
    missing: list[str] = []
    for ref in placeholders_in(statement):
        value = facts.get(ref)
        if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
            missing.append(ref)
    return tuple(missing)


def render(statement: str, facts: Mapping[str, object], *, digits: int = 2) -> str:
    """The statement as a reader sees it, with the figures filled in.

    Refuses rather than leaving a slot on screen: a sentence that says
    "stopped for {obs:...}" in front of somebody is worse than either
    version it was meant to be, and the check that would have caught it
    belongs before this is called.
    """
    unfilled = unresolvable(statement, facts)
    if unfilled:
        raise MagnitudeRefusal(
            f"this packet cannot fill {list(unfilled)}; a statement is rendered "
            "only after the guard has agreed every placeholder resolves to a number"
        )

    def fill(match: re.Match[str]) -> str:
        value = float(facts[match.group(1)])  # type: ignore[arg-type]
        if abs(value - round(value)) < 1e-9:
            return str(int(round(value)))
        return f"{value:.{digits}f}".rstrip("0").rstrip(".")

    return PLACEHOLDER.sub(fill, statement)
