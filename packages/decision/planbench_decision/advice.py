"""Tell a reader what to do next, and what not to do.

Every gate in this codebase answers pass or fail. That is the right shape
for a decision and the wrong shape for a person: "G3 fail, 0.71 < 0.85"
is true, checkable, and leaves the reader to work out on their own
whether the fix is a better candidate, a different scenario split, or —
the move that quietly destroys the whole point — a looser threshold.

This module is the shape for the second half. An :class:`Advice` is a
:class:`~planbench_decision.self_check.Finding` with two more fields:
what a reader can legitimately do, and what they must not. The second
one is the one that earns the module. Every gate in this platform has an
illegitimate remedy that makes it pass, most of them are one edit away,
and a reader who was told only "this failed" is being invited to find
them.

Three rules, inherited from :mod:`planbench_decision.self_check` and
extended by one:

**Every piece of advice cites a field that exists.** ``field_path``
resolves against the source data through
:func:`~planbench_decision.self_check.resolve`. Advice that cannot point
at its own evidence reads as verified and is not, and the same check is
what keeps an LLM layer honest — it may rank and rephrase, it may not
invent a citation.

**Advice never acts.** These objects are text. Nothing here launches a
run, edits a deployment or approves a result; those are human acts on
the decisions page, and the agent's published
``FORBIDDEN_CAPABILITIES`` says so where a caller can check it.

**A forbidden remedy is named, not implied.** ``do_not`` is empty only
when there genuinely is no tempting wrong move. Leaving it empty because
the wrong move is "obvious" is how it gets taken.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from planbench_decision.self_check import Severity, exists, resolve

__all__ = [
    "Advice",
    "AdviceKind",
    "Severity",
    "keep_resolvable",
    "order",
    "resolve",
]

#: Which half of the lifecycle a piece of advice belongs to. Carried so a
#: caller can render "before you spend the compute" separately from
#: "now that you have the numbers" without parsing the code strings.
AdviceKind = Literal["preflight", "diagnosis", "reproduction", "reporting"]

#: Severity ordering used for display. `blocking` first, because a reader
#: who stops after the first line should have read the one that changes
#: what they do next.
_SEVERITY_RANK: dict[str, int] = {"blocking": 0, "material": 1, "disclosure": 2}


class Advice(BaseModel):
    """One thing a reader should do, grounded in one field they can check."""

    model_config = ConfigDict(frozen=True)

    #: Stable identifier. Lets a rule be tracked across runs, scored by an
    #: evaluation harness, and silenced by a reader who disagrees with it
    #: without silencing everything.
    code: str
    kind: AdviceKind
    severity: Severity
    #: The situation, stated as something checkable against `field_path`.
    claim: str
    #: Why it is the case, in one sentence. Not persuasion — the sentence
    #: a reader compares against the field to decide whether to believe
    #: the advice at all.
    ground: str
    #: Dotted path into the source data. Always resolvable; see
    #: :func:`keep_resolvable`, which is what enforces it.
    field_path: str
    #: The legitimate next step. Concrete enough to act on: "register a
    #: candidate with a smaller lookahead" rather than "improve the
    #: configuration".
    do: str
    #: The move that would make the symptom disappear without making the
    #: conclusion true. Empty only when there is genuinely no such move.
    do_not: str = ""
    #: What this advice is about — a candidate id, a gate name, an
    #: episode. Empty when it concerns the run as a whole.
    #:
    #: Carried beside ``field_path`` rather than parsed out of it: a
    #: reader grouping advice by candidate would otherwise have to
    #: reverse-engineer ``candidates[1].stack`` into "the second one",
    #: and an index is not a name.
    subject: str = ""


def keep_resolvable(items: tuple[Advice, ...], source: dict[str, Any]) -> tuple[Advice, ...]:
    """Drop advice whose ``field_path`` does not resolve against ``source``.

    Applied to rule output as well as model output, deliberately. A rule
    that points at a field a particular report happens not to carry is
    making the same unverifiable claim a hallucinating model would, and
    the reader has no way to tell the two apart. Better to lose the
    advice than to publish one that cannot be checked.

    Presence is the test, not truthiness: this uses
    :func:`~planbench_decision.self_check.exists`, so advice may cite a
    field that is present and null. That case is not an edge — "this run
    recorded no effect size" is advice *about* a null, and testing with
    ``resolve() is not None`` would delete precisely the advice that
    exists to point at one.

    Two silent-drop traps this cannot catch, and which a rule author has
    to avoid by hand: a ``@property`` (``constraints.n_min_evaluation_episodes``,
    ``robot.t_cycle_ms``, ``sensor_noise.active``) is readable in Python
    and absent from ``model_dump()``, so citing one drops here; and a
    dotted path with no index into a list never resolves. Both are why
    every rule's citation is asserted against a real dict in the tests.
    """
    return tuple(item for item in items if exists(source, item.field_path))


def order(items: tuple[Advice, ...]) -> tuple[Advice, ...]:
    """Sort by severity, then by code, so two runs of one input agree.

    The secondary key is not decoration: rules fire in whatever order
    their module happens to evaluate them, and a list that reshuffles
    between identical runs is one a reader cannot diff.
    """
    return tuple(sorted(items, key=lambda a: (_SEVERITY_RANK.get(a.severity, 9), a.code)))
