"""The shortlist a model chooses from, built by the platform — W2.

The analyst's hardest job is not "which mechanism" so much as "which of
the mechanisms this platform can actually argue about". Left to invent
the space itself, a model reaches for whatever a packet's prose suggests
and the guard drops the result — which measures the guard, not the
model. So the platform proposes the space and the model does what a
model is good at: choosing among stated options, picking evidence for
one, and writing the sentence afterwards.

Four rules, and each one is a way this could go wrong instead:

**A candidate carries no evidence refs.** The refs are the model's to
choose out of the fact index, and the guard scores that choice. A
shortlist that arrived with the citations attached would score the
generator's reading while looking like the model's.

**``verification_options`` is a separate variable.** The shortlist is a
prior over *mechanisms*; the options are a hint about *how to check
one*. They move under their own flag because E4a and E4b measure them
apart — bundled, a gain in either would be reported as a gain in both.

**Three sources, merged, never doubled.** The detector mapping, the
knowledge entries retrieval offered, and the algorithm natures. Deduped
on ``(mechanism_id, subject)``: the same mechanism reached two ways is
one candidate with two reasons, and listing it twice would read as two
mechanisms agreeing.

A trait is the third source and it behaves differently on purpose. It
says what an algorithm is *like*, not what happened in this run, so it
can raise a mechanism the run already suggests and it cannot invent one.
A nature that could conjure a candidate out of nothing would be the
model's folklore arriving through the platform's own door.

**``unknown`` is always on the list.** A shortlist with no way to say
"none of these" is a forced choice, and a forced choice is what makes an
analyst confidently wrong.

Distractors live here too, and they are **eval only** — see
:func:`inject_distractors`, which refuses anything but a development
partition. The scorer's labels never reach this module: a distractor is
drawn from the mechanisms the platform knows, not from the answer.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass, replace

from planbench_analyst.knowledge_provider import TraitOffer
from planbench_explanation.case_packet import CasePacket
from planbench_explanation.integration import DETECTION_HYPOTHESES
from planbench_explanation.knowledge_contract import ResolvedReference
from planbench_explanation.propositions import ASSERTABLE_PROPOSITIONS
from planbench_explanation.tools import ToolCatalog

__all__ = [
    "CandidateRefusal",
    "MechanismCandidate",
    "VerificationOption",
    "generate_candidates",
    "generator_recall_at_k",
    "inject_distractors",
    "render_candidates",
]

#: The mechanism a shortlist always offers, and the one no source can
#: remove. Its subject is ``None``: "something else was going on" is not
#: a statement about a component.
UNKNOWN = "unknown"


class CandidateRefusal(ValueError):
    """A shortlist this platform will not build or serve."""


@dataclass(frozen=True)
class VerificationOption:
    """One way this mechanism could be checked, and what the call needs."""

    tool_id: str
    required_arguments: tuple[str, ...]


@dataclass(frozen=True)
class MechanismCandidate:
    """One mechanism the platform is willing to have argued about.

    Deliberately **without** supporting refs: the model picks those from
    the fact index, and that choice is what the guard scores.
    """

    mechanism_id: str
    subject: str | None
    #: Why this is on the list — detection types, entry ids, trait refs.
    #: Plural because three sources can reach one mechanism, and a
    #: reader is owed all of the reasons rather than the first.
    triggered_by: tuple[str, ...] = ()
    verification_options: tuple[VerificationOption, ...] = ()
    #: ``detector`` | ``knowledge`` | ``traits`` | ``unknown`` |
    #: ``distractor``. Recorded so ``generator_recall@K`` can be read per
    #: source, and so an eval run can be told from a production one.
    sources: tuple[str, ...] = ()

    @property
    def key(self) -> tuple[str, str]:
        """What two candidates are the same candidate by."""
        return (self.mechanism_id, self.subject or "")


def generate_candidates(
    packet: CasePacket,
    *,
    catalog: ToolCatalog,
    available_evidence: frozenset[str] = frozenset(),
    knowledge: Sequence[ResolvedReference] = (),
    traits: Sequence[TraitOffer] = (),
    verification_options: bool = True,
) -> tuple[MechanismCandidate, ...]:
    """The shortlist for one packet, in the order the platform ranks it.

    Ordered by how many sources reached a mechanism and then by id, so
    two runs of one packet produce one list. ``unknown`` is last and
    always present.
    """
    found: dict[tuple[str, str], MechanismCandidate] = {}

    for observation in packet.observations:
        mapped = DETECTION_HYPOTHESES.get(observation.type)
        if mapped is None:
            continue
        mechanism, subject, _tool = mapped
        _merge(found, mechanism, subject, f"detection:{observation.type}", "detector")

    for reference in knowledge:
        _merge(
            found,
            reference.proposition_type,
            reference.subject,
            reference.entry.citation,
            "knowledge",
        )

    for offer in traits:
        # A nature raises what the run already suggests and cannot
        # invent a mechanism: it describes the algorithm, not the
        # episode. Every candidate about this component gains the
        # reason; a component with no candidate gains nothing.
        subject = _subject_of(offer)
        if subject is None:
            continue
        for key, candidate in list(found.items()):
            if candidate.subject == subject:
                found[key] = replace(
                    candidate,
                    triggered_by=_add(candidate.triggered_by, offer.ref),
                    sources=_add(candidate.sources, "traits"),
                )

    ranked = sorted(
        found.values(),
        key=lambda item: (-len(item.sources), -len(item.triggered_by), item.mechanism_id),
    )
    shortlist = [
        replace(
            candidate,
            verification_options=(
                _options_for(candidate, catalog, available_evidence) if verification_options else ()
            ),
        )
        for candidate in ranked
    ]
    shortlist.append(
        MechanismCandidate(
            mechanism_id=UNKNOWN,
            subject=None,
            triggered_by=(),
            # The fallback menu, when it is offered at all: a round that
            # ends at ``unknown`` still has to be able to look.
            verification_options=(
                _fallback_options(catalog, available_evidence) if verification_options else ()
            ),
            sources=(UNKNOWN,),
        )
    )
    return tuple(shortlist)


def render_candidates(shortlist: Sequence[MechanismCandidate]) -> str:
    """The shortlist as the model is shown it.

    One line per candidate and one per option. No prose about why a
    mechanism is plausible: the reasons are ids the model can look up,
    and a paragraph arguing for a candidate is the platform doing the
    analyst's job and then grading it.
    """
    lines: list[str] = []
    for candidate in shortlist:
        subject = candidate.subject or "no component"
        reasons = ", ".join(candidate.triggered_by) or "always offered"
        lines.append(f"- {candidate.mechanism_id} ({subject}); raised by: {reasons}")
        for option in candidate.verification_options:
            arguments = ", ".join(option.required_arguments) or "no arguments"
            lines.append(f"    · check with {option.tool_id} — needs {arguments}")
    return "\n".join(lines)


def generator_recall_at_k(
    shortlist: Sequence[MechanismCandidate],
    *,
    expected_mechanism: str,
    expected_subject: str | None = None,
    k: int = 5,
) -> bool:
    """Whether the planted mechanism is in the first ``k`` candidates.

    Scored on the generator's **own** output, before any harness
    intervention: a recall measured after distractors were injected or
    the gold candidate was dropped is a measurement of the harness.
    """
    for candidate in list(shortlist)[:k]:
        if candidate.mechanism_id != expected_mechanism:
            continue
        if expected_subject is None or candidate.subject == expected_subject:
            return True
    return False


def inject_distractors(
    shortlist: Sequence[MechanismCandidate],
    *,
    partition: str,
    seed: int,
    rate: float,
    drop_gold: bool = False,
    gold: tuple[str, str | None] | None = None,
) -> tuple[MechanismCandidate, ...]:
    """Eval-only: add plausible wrong mechanisms, optionally remove the right one.

    **Fail-closed on the partition.** Anything but ``development`` is
    refused: this mode exists to measure whether the model is choosing
    or agreeing, and a production round whose shortlist carried invented
    mechanisms would be a platform lying to its own analyst. The official
    gate reads the same rule.

    The distractors are drawn from the propositions this platform knows,
    never from the scorer's labels — nothing here needs to be told the
    answer. ``drop_gold`` is the one exception and takes it explicitly,
    which is why it is a separate argument a caller has to pass rather
    than a rate somebody could raise by accident.
    """
    if partition != "development":
        raise CandidateRefusal(
            f"distractor mode is development-only and this run is {partition!r}. A "
            "production shortlist carrying invented mechanisms is the platform "
            "lying to its own analyst, and the official gate reads this same rule."
        )
    if not 0.0 <= rate <= 1.0:
        raise CandidateRefusal(f"distractor rate {rate} is not a fraction")

    working = list(shortlist)
    if drop_gold:
        if gold is None:
            raise CandidateRefusal(
                "dropping the gold candidate needs to be told which one it is; a "
                "harness that guessed would be scoring its own guess"
            )
        working = [item for item in working if item.key != (gold[0], gold[1] or "")]

    present = {item.mechanism_id for item in working}
    # Assertable ones only. An inference-only proposition is one the
    # platform forbids outright, so offering it as a distractor would
    # test whether the model can be led into a sentence the guard
    # drops anyway — a different experiment, and not this one.
    pool = sorted(set(ASSERTABLE_PROPOSITIONS) - present - {UNKNOWN})
    if not pool or rate == 0.0:
        return tuple(working)

    generator = random.Random(seed)
    wanted = max(1, round(len(working) * rate))
    chosen = generator.sample(pool, k=min(wanted, len(pool)))
    injected = [
        MechanismCandidate(
            mechanism_id=mechanism,
            subject=None,
            triggered_by=("eval:distractor",),
            sources=("distractor",),
        )
        for mechanism in chosen
    ]
    # Before ``unknown``, which stays last: its position is part of what
    # the model is told, and moving it would be a second change nobody
    # declared.
    tail = [item for item in working if item.mechanism_id == UNKNOWN]
    head = [item for item in working if item.mechanism_id != UNKNOWN]
    return tuple(head + injected + tail)


# --------------------------------------------------------------------------


def _merge(
    found: dict[tuple[str, str], MechanismCandidate],
    mechanism: str,
    subject: str | None,
    reason: str,
    source: str,
) -> None:
    key = (mechanism, subject or "")
    existing = found.get(key)
    if existing is None:
        found[key] = MechanismCandidate(
            mechanism_id=mechanism,
            subject=subject,
            triggered_by=(reason,),
            sources=(source,),
        )
        return
    found[key] = replace(
        existing,
        triggered_by=_add(existing.triggered_by, reason),
        sources=_add(existing.sources, source),
    )


def _add(values: tuple[str, ...], value: str) -> tuple[str, ...]:
    return values if value in values else (*values, value)


def _subject_of(offer: TraitOffer) -> str | None:
    if offer.kind == "global":
        return "global_planner"
    if offer.kind == "local":
        return "local_controller"
    return None


def _options_for(
    candidate: MechanismCandidate,
    catalog: ToolCatalog,
    available_evidence: frozenset[str],
) -> tuple[VerificationOption, ...]:
    """The checks that could support this mechanism **and** could run.

    A card whose required evidence this run does not hold is left off:
    naming it would send the analyst at a tool the host will refuse at
    admission, and the refusal reads to a model as the platform being
    broken.
    """
    options: list[VerificationOption] = []
    for card in catalog.cards:
        supported = card.proposition_policy.supported_proposition_types
        if candidate.mechanism_id not in supported:
            continue
        if not set(card.required_evidence) <= set(available_evidence):
            continue
        options.append(
            VerificationOption(
                tool_id=card.tool_id,
                required_arguments=tuple(
                    argument.name for argument in card.io.arguments if argument.required
                ),
            )
        )
    return tuple(options)


def _fallback_options(
    catalog: ToolCatalog, available_evidence: frozenset[str]
) -> tuple[VerificationOption, ...]:
    """What ``unknown`` may still look at: the evidence-capable menu.

    A round that cannot name a mechanism is exactly the round that needs
    to go and read something, so the fallback is the tools this run can
    serve rather than nothing at all.
    """
    return tuple(
        VerificationOption(
            tool_id=card.tool_id,
            required_arguments=tuple(
                argument.name for argument in card.io.arguments if argument.required
            ),
        )
        for card in catalog.cards
        if card.tool_class in ("fact_query", "evidence_navigation")
        and set(card.required_evidence) <= set(available_evidence)
    )
