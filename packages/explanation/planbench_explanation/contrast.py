"""Reading a pattern across the candidate lattice — E3.

The lattice is free evidence. If A\\* + DWA and RRT\\* + DWA both stall in
the same corridor, that costs no new run to notice and it *rules out*
"A\\*'s global planner does this" — the two do not share a global
planner. Cross-reading what already ran is the cheapest causal leverage
the platform has.

It is also the easiest place to over-read, so this module produces four
verdicts and three of them are refusals:

``rules_out_component_specific_attribution``
    the pattern is on both sides of a swap, so the component that
    differs is not what produces it. **Not** proof that the component
    they share is: task geometry, the costmap, the shared providers and
    the interaction between layers all produce shared patterns too.
``supports_component_specific_attribution``
    a swap that holds *everything else* fixed, and the pattern follows
    the component that changed.
``insufficient_contrast``
    no pair in this lattice differs in exactly one component.
``interaction_not_isolated``
    a pair differs in one component and the pattern moved, but another
    pair contradicts it — the evidence reaches an interaction and cannot
    separate the layers.

**Comparisons are between candidates that differ in exactly one place.**
Two stacks differing in both planner and controller say nothing about
either, and treating them as a swap is how a lattice reading turns into
a coin flip with a citation.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from planbench_explanation.detectors import DetectionType
from planbench_explanation.subjects import Subject

ContrastVerdict = Literal[
    "rules_out_component_specific_attribution",
    "supports_component_specific_attribution",
    "insufficient_contrast",
    "interaction_not_isolated",
]

#: Which stack component each comparable field names. Only these are
#: swappable: two candidates differing anywhere else are two experiments.
COMPONENT_SUBJECTS: dict[str, Subject] = {
    "global_planner": "global_planner",
    "local_controller": "local_controller",
    "local_controller_config": "local_controller",
}


class ContrastRefusal(ValueError):
    """The lattice on hand cannot support the reading requested."""


class CandidateComponents(BaseModel):
    """One candidate's stack, as the fields a swap can differ in.

    Typed rather than parsed out of a label. ``stack_label`` reads
    ``"astar+dwa"`` and splitting it on ``+`` works right up until a
    stack has a hyphenated name or three parts, at which point the
    lattice reading silently compares the wrong things.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_id: str = Field(min_length=1)
    global_planner: str = Field(min_length=1)
    local_controller: str = Field(min_length=1)
    local_controller_config: str = Field(min_length=1)

    def differs_in(self, other: CandidateComponents) -> tuple[str, ...]:
        return tuple(
            field for field in COMPONENT_SUBJECTS if getattr(self, field) != getattr(other, field)
        )


class ContrastFinding(BaseModel):
    """What the lattice says about one pattern, and how far that goes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    detection_type: DetectionType
    verdict: ContrastVerdict
    #: The component the evidence is about, when there is one. ``None``
    #: for the two refusals that name no component.
    subject: Subject | None = None
    #: The pairs the verdict rests on, as ``(candidate, candidate)``.
    pairs: tuple[tuple[str, str], ...] = ()
    #: Said in full, because the verdict names are compressed and the
    #: distinction between "rules out" and "proves the other one" is the
    #: whole reason this module is careful.
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self) -> ContrastFinding:
        needs_subject = self.verdict in (
            "rules_out_component_specific_attribution",
            "supports_component_specific_attribution",
        )
        if needs_subject and self.subject is None:
            raise ContrastRefusal(f"verdict {self.verdict!r} is about a component but names none")
        if not needs_subject and self.subject is not None:
            raise ContrastRefusal(
                f"verdict {self.verdict!r} names component {self.subject!r}, but it is a "
                "statement about the lattice rather than about a component"
            )
        return self


def read_lattice(
    components: Sequence[CandidateComponents],
    present: Mapping[str, bool],
    *,
    detection_type: DetectionType,
) -> ContrastFinding:
    """What the candidates that already ran say about one pattern.

    ``present`` is ``candidate_id → did this pattern appear``. A
    candidate missing from it is one the pattern was never looked for
    in, and it takes no part: absence of a lookup is not absence of a
    pattern.
    """
    known = [item for item in components if item.candidate_id in present]
    if len(known) < 2:
        return ContrastFinding(
            detection_type=detection_type,
            verdict="insufficient_contrast",
            reason=(
                "fewer than two candidates were checked for this pattern, so there is "
                "nothing to contrast"
            ),
        )

    swaps: list[tuple[CandidateComponents, CandidateComponents, str]] = []
    for index, left in enumerate(known):
        for right in known[index + 1 :]:
            difference = left.differs_in(right)
            if len(difference) == 1:
                swaps.append((left, right, difference[0]))

    if not swaps:
        return ContrastFinding(
            detection_type=detection_type,
            verdict="insufficient_contrast",
            reason=(
                "no two candidates in this run differ in exactly one component, so no "
                "swap holds everything else fixed and nothing can be attributed"
            ),
        )

    shared: list[tuple[CandidateComponents, CandidateComponents, str]] = []
    moved: list[tuple[CandidateComponents, CandidateComponents, str]] = []
    for left, right, field in swaps:
        if present[left.candidate_id] and present[right.candidate_id]:
            shared.append((left, right, field))
        elif present[left.candidate_id] != present[right.candidate_id]:
            moved.append((left, right, field))

    by_field: dict[str, list[tuple[CandidateComponents, CandidateComponents, str]]] = {}
    for swap in moved:
        by_field.setdefault(swap[2], []).append(swap)
    contradicted = {
        field for field, group in by_field.items() if any(s[2] == field for s in shared) and group
    }

    if contradicted:
        field = sorted(contradicted)[0]
        return ContrastFinding(
            detection_type=detection_type,
            verdict="interaction_not_isolated",
            pairs=_pairs(by_field[field] + [s for s in shared if s[2] == field]),
            reason=(
                f"swapping {field} moved the pattern in one pair and left it in place in "
                "another; the evidence reaches an interaction and cannot separate the layers"
            ),
        )

    # **Two axes that both "explain" it explain nothing on their own.**
    # An earlier version took the alphabetically first field here, which
    # attributed a pattern to the global planner because "g" sorts before
    # "l" — a coin flip wearing a component name. When the pattern moves
    # with more than one component, the honest reading is that the
    # evidence has not separated them.
    if len(by_field) > 1:
        return ContrastFinding(
            detection_type=detection_type,
            verdict="interaction_not_isolated",
            pairs=_pairs([swap for group in by_field.values() for swap in group]),
            reason=(
                f"the pattern moves with more than one component ({', '.join(sorted(by_field))}); "
                "each looks sufficient on its own pair, so this evidence does not separate "
                "them and attributing it to either would be a choice, not a finding"
            ),
        )

    if moved:
        field = next(iter(by_field))
        return ContrastFinding(
            detection_type=detection_type,
            verdict="supports_component_specific_attribution",
            subject=COMPONENT_SUBJECTS[field],
            pairs=_pairs(by_field[field]),
            reason=(
                f"the pattern follows {field} across every pair that changes only that "
                "component, it is the only component it follows, and every other part of "
                "the stack was held fixed"
            ),
        )

    if shared:
        field = sorted({swap[2] for swap in shared})[0]
        return ContrastFinding(
            detection_type=detection_type,
            verdict="rules_out_component_specific_attribution",
            subject=COMPONENT_SUBJECTS[field],
            pairs=_pairs([swap for swap in shared if swap[2] == field]),
            reason=(
                f"the pattern is present on both sides of a {field} swap, so that "
                "component is not what produces it. This does not show that the "
                "component they share does: task geometry, the costmap, the shared "
                "providers and the interaction between layers all produce shared patterns"
            ),
        )

    return ContrastFinding(
        detection_type=detection_type,
        verdict="insufficient_contrast",
        reason="the pattern appeared in no candidate that a swap could compare",
    )


def _pairs(
    swaps: Sequence[tuple[CandidateComponents, CandidateComponents, str]],
) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((left.candidate_id, right.candidate_id)) for left, right, _ in swaps)  # type: ignore[misc]


def components_from_report(report: Mapping[str, object]) -> tuple[CandidateComponents, ...]:
    """The lattice as the scoring run recorded it.

    Reads the typed ``components`` block. A run that predates it has no
    lattice here rather than a guessed one: splitting ``stack_label`` on
    a plus sign would produce comparisons nobody checked.
    """
    found = []
    for entry in report.get("candidates") or []:  # type: ignore[union-attr]
        block = entry.get("components")  # type: ignore[union-attr]
        if not isinstance(block, Mapping):
            continue
        found.append(
            CandidateComponents(
                candidate_id=str(entry.get("candidate_id")),  # type: ignore[union-attr]
                global_planner=str(block.get("global_planner") or ""),
                local_controller=str(block.get("local_controller") or ""),
                local_controller_config=str(block.get("local_controller_config") or ""),
            )
        )
    return tuple(found)
