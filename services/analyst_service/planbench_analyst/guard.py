"""The last thing that runs before anything is submitted.

Seven rules, all deterministic, all applied to what the model actually
returned rather than to what it was asked for. The system prompt states
most of them too; that is for the hit rate, and this is the enforcement.
A rule that lived only in the prompt would be a rule with a good day and
a bad day.

1. **Every ref resolves.** A citation into a packet that does not hold it
   is not a citation.
2. **No quantity in a statement.** The renderer prints numbers out of the
   fact index; a sentence carrying its own is dropped whether or not the
   number was right, because the reader cannot tell those apart.
3. **No claim the packet blocks.** ``known_unknowns`` name claim types
   this run cannot support, and proposing one anyway is the blocked-claim
   leak the suite counts.
4. **A check the card can answer.** A mechanism check may only be asked
   for a proposition its card supports; a navigation or fact tool
   supports none and may not be attached to one.
5. **Wording no stronger than ``associated``.** A proposal is an
   *unchecked* hypothesis. Causal vocabulary belongs four rungs up, and
   only after an intervention.
6. **A citation that does not contradict the claim.** The advisor's live
   run produced the case this exists for: a citation that resolved, held
   the value it implied, and said nothing about the sentence attached to
   it. Where the packet attributes a fact to a component, a proposal
   about a *different* component may not lean on it.
7. **Something to lean on at all.** A proposal with no citation is a
   sentence. Dropping it is cheaper than keeping it: precision loses
   both a numerator and a denominator, and the reader loses nothing they
   could have checked.

**Blocked is not deleted.** Every drop comes back as a
:class:`Blocked` record with the rule that fired, because the rate at
which each rule fires is the measurement A6 needs. A guard that silently
filtered would make the model look like it never made the mistake.

**The critic never removes.** It reorders and flags, and the ablation at
A6 is what decides whether it earns its call. A critic that could delete
would be a second guard with no rules written down.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from planbench_analyst.packet_view import PacketView
from planbench_explanation.catalog import ToolCatalog
from planbench_explanation.ledger import HypothesisProposal
from planbench_explanation.levels import check_phrases
from planbench_explanation.protocol import AnalysisResponse

__all__ = [
    "Blocked",
    "GuardResult",
    "NUMBER_WORDS",
    "critique",
    "guard",
    "quantities_in",
]

#: Numbers spelled out, in both languages this platform is read in. A
#: statement that says "twice the budget" or "gấp đôi ngân sách" has put
#: a quantity in the sentence exactly as much as one that says "2×", and
#: the digit-based check alone would wave it through.
NUMBER_WORDS: frozenset[str] = frozenset(
    {
        # en
        "zero",
        "one",
        "two",
        "three",
        "four",
        "five",
        "six",
        "seven",
        "eight",
        "nine",
        "ten",
        "eleven",
        "twelve",
        "twenty",
        "thirty",
        "forty",
        "fifty",
        "hundred",
        "thousand",
        "half",
        "twice",
        "double",
        "triple",
        "percent",
        "per cent",
        # vi
        "không",
        "một",
        "hai",
        "ba",
        "bốn",
        "năm",
        "sáu",
        "bảy",
        "tám",
        "chín",
        "mười",
        "trăm",
        "nghìn",
        "ngàn",
        "nửa",
        "gấp đôi",
        "phần trăm",
    }
)

#: A token that is a bare number, a percentage, or scientific notation.
#: Deliberately greedy about digits: an identifier that happens to carry
#: one is rescued below by the packet's own list of names, which is the
#: only honest way to tell ``aisle_B7`` from ``0.74``.
_NUMERIC = re.compile(r"^[+-]?(?:\d+(?:[.,]\d+)?(?:[eE][+-]?\d+)?)\s*%?$")


def quantities_in(statement: str, identifiers: frozenset[str]) -> tuple[str, ...]:
    """Quantities the statement carries, as written.

    ``identifiers`` are the names this packet uses — candidate labels,
    region ids, episode ids, objectives. A token that is one of them is
    a name, whatever digits it contains.
    """
    found: list[str] = []
    lowered = statement.casefold()
    for phrase in NUMBER_WORDS:
        if " " in phrase:
            if phrase in lowered:
                found.append(phrase)
            continue
        if re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", lowered):
            found.append(phrase)
    known = {name.casefold() for name in identifiers}
    for token in re.findall(r"[^\s,;:()\[\]]+", statement):
        cleaned = token.strip(".;:,")
        if not cleaned or cleaned.casefold() in known:
            continue
        if any(character.isdigit() for character in cleaned) and _NUMERIC.match(cleaned):
            found.append(cleaned)
        elif any(character.isdigit() for character in cleaned) and cleaned.casefold() not in known:
            # A token with digits that is neither a known name nor a bare
            # number — ``0.74m``, ``30-episode``, ``2x``. Treated as a
            # quantity: the alternative is a rule that a unit suffix
            # turns off.
            found.append(cleaned)
    return tuple(sorted(set(found)))


@dataclass(frozen=True)
class Blocked:
    """One proposal the guard refused, and the rule that refused it."""

    hypothesis_id: str
    rule: str
    detail: str


@dataclass(frozen=True)
class GuardResult:
    """What survives, what did not, and what the critic thought."""

    response: AnalysisResponse
    blocked: tuple[Blocked, ...] = ()
    #: Advisory only. Order the critic would read them in.
    ranking: tuple[str, ...] = ()
    #: ``hypothesis_id -> one sentence``. Never a reason to drop.
    flags: tuple[tuple[str, str], ...] = ()

    @property
    def blocked_by_rule(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in self.blocked:
            counts[item.rule] = counts.get(item.rule, 0) + 1
        return counts


def _check_problem(proposal: HypothesisProposal, catalog: ToolCatalog) -> tuple[str, str] | None:
    for check in proposal.requested_checks:
        card = next((item for item in catalog.cards if item.tool_id == check.tool_id), None)
        if card is None:
            return ("check_not_on_catalog", f"{check.tool_id!r} is not a tool")
        if card.tool_version != check.tool_version:
            return (
                "check_version_mismatch",
                f"{check.tool_id} is served at {card.tool_version}, asked at {check.tool_version}",
            )
        supported = card.proposition_policy.supported_proposition_types
        if card.tool_class == "mechanism_check" and proposal.proposition_type not in supported:
            return (
                "check_cannot_answer",
                f"{card.tool_id} supports {list(supported)}, not {proposal.proposition_type}",
            )
        # A fact query or a navigation tool is **not** required to leave
        # ``supported_proposition_types`` empty, and an earlier version of
        # this rule refused every proposal that asked for one which does —
        # ``get_candidate_contrast`` declares
        # ``component_specific_attribution``. The rule that matters is the
        # one above: a *mechanism check* may only be asked a question its
        # card answers. Reading anything else off this list turned a
        # perfectly good request into a blocked-claim statistic.
        problems = card.io.check_arguments(check.arguments)
        if problems:
            return ("check_arguments_rejected", "; ".join(problems))
    return None


def _subject_conflict(proposal: HypothesisProposal, view: PacketView) -> tuple[str, str] | None:
    for ref in proposal.supports + proposal.contradicts:
        fact = view.fact(ref.ref)
        if fact is None or fact.subject is None:
            # ``None`` is "the packet attributes this to nobody", which
            # is most measurements. Rule 6 is a contradiction test, not
            # a relevance test — saying who is responsible is the
            # lattice's job, and a fact that guessed would make this
            # rule confidently wrong.
            continue
        if fact.subject != proposal.proposed_subject:
            return (
                "citation_contradicts_subject",
                f"{ref.ref} is about {fact.subject}, the claim is about "
                f"{proposal.proposed_subject}",
            )
    return None


def guard(
    response: AnalysisResponse,
    view: PacketView,
    *,
    catalog: ToolCatalog,
    critic: bool = True,
) -> GuardResult:
    """Apply the seven rules, and say what each drop cost.

    An abstention passes through untouched: there is nothing to check,
    and re-deriving a reason here would overwrite the model's.
    """
    if response.abstained:
        return GuardResult(response=response)

    blocked_types = set(view.packet.blocked_claim_types)
    identifiers = view.identifiers
    kept: list[HypothesisProposal] = []
    blocked: list[Blocked] = []

    for proposal in response.proposals:
        cited = proposal.supports + proposal.contradicts
        missing = [ref.ref for ref in cited if ref.ref not in view]
        if missing:
            blocked.append(
                Blocked(proposal.hypothesis_id, "ref_not_in_packet", f"{sorted(set(missing))}")
            )
            continue
        quantities = quantities_in(proposal.hypothesis_statement, identifiers)
        if quantities:
            blocked.append(
                Blocked(proposal.hypothesis_id, "quantity_in_statement", f"{list(quantities)}")
            )
            continue
        if proposal.proposition_type in blocked_types:
            blocked.append(
                Blocked(
                    proposal.hypothesis_id,
                    "claim_blocked_by_packet",
                    f"{proposal.proposition_type} is blocked by a declared gap",
                )
            )
            continue
        problem = _check_problem(proposal, catalog)
        if problem is not None:
            blocked.append(Blocked(proposal.hypothesis_id, problem[0], problem[1]))
            continue
        # Rule 8 (W4). A draft is written **before** its check runs, so
        # a draft that reports the check's outcome is reporting a result
        # that does not exist yet. The words are the same ones a real
        # verdict would use, which is exactly why nothing downstream
        # could tell the two apart afterwards.
        if proposal.requested_checks:
            claimed = [
                word
                for word in ("verified", "confirmed", "refuted", "the check shows")
                if word in proposal.hypothesis_statement.lower()
            ]
            if claimed:
                blocked.append(
                    Blocked(proposal.hypothesis_id, "draft_claims_a_verdict", f"{claimed}")
                )
                continue

        wording = check_phrases(proposal.hypothesis_statement, "associated")
        if wording:
            blocked.append(
                Blocked(proposal.hypothesis_id, "wording_above_associated", f"{list(wording)}")
            )
            continue
        conflict = _subject_conflict(proposal, view)
        if conflict is not None:
            blocked.append(Blocked(proposal.hypothesis_id, conflict[0], conflict[1]))
            continue
        if not proposal.supports and not proposal.contradicts:
            blocked.append(
                Blocked(
                    proposal.hypothesis_id,
                    "no_citation",
                    "a proposal with nothing to lean on is a sentence",
                )
            )
            continue
        kept.append(proposal)

    if not kept:
        reasons = sorted({item.rule for item in blocked})
        answer = AnalysisResponse(
            analysis_run_id=response.analysis_run_id,
            analyst_bundle_id=response.analyst_bundle_id,
            abstained=True,
            abstention_reason=(
                "every proposal was refused before submission ("
                + ", ".join(reasons)
                + "); an abstention with a reason beats a claim the platform would refuse"
            ),
        )
        return GuardResult(response=answer, blocked=tuple(blocked))

    # E7's arm. The critic ranks what survived and says what looks
    # thin; with it off the proposals come back in the order the model
    # sent them and nothing is flagged, which is what E7 compares
    # against — a critic nobody has shown is worth its place is a habit
    # rather than a component.
    ranking, flags = critique(tuple(kept), view) if critic else ((), ())
    answer = AnalysisResponse(
        analysis_run_id=response.analysis_run_id,
        analyst_bundle_id=response.analyst_bundle_id,
        proposals=tuple(kept),
    )
    return GuardResult(response=answer, blocked=tuple(blocked), ranking=ranking, flags=flags)


def critique(
    proposals: tuple[HypothesisProposal, ...], view: PacketView
) -> tuple[tuple[str, ...], tuple[tuple[str, str], ...]]:
    """Advisory: an order to read them in, and what looks thin.

    Deterministic on purpose at this phase. A model critic is a second
    call for an opinion nobody has yet shown is worth paying for, and
    the ablation at A6 has to be able to compare *something* against no
    critic at all. Whether this earns its place is a measurement, not a
    design decision made here.
    """
    flags: list[tuple[str, str]] = []
    scored: list[tuple[tuple[int, int, str], str]] = []
    for proposal in proposals:
        supporting = len(proposal.supports)
        checkable = 1 if proposal.requested_checks else 0
        if not checkable:
            flags.append(
                (
                    proposal.hypothesis_id,
                    "no check requested: this can reach `associated` and stop there",
                )
            )
        if supporting == 1 and proposal.missing_evidence:
            flags.append(
                (
                    proposal.hypothesis_id,
                    "one citation and a declared gap: thin, and honest about it",
                )
            )
        observation_backed = any(
            (fact := view.fact(ref.ref)) is not None and fact.kind == "observation"
            for ref in proposal.supports
        )
        if not observation_backed:
            flags.append(
                (
                    proposal.hypothesis_id,
                    "no observation among its citations: it leans on facts nobody saw happen",
                )
            )
        scored.append(((-checkable, -supporting, proposal.hypothesis_id), proposal.hypothesis_id))
    return tuple(item for _, item in sorted(scored)), tuple(flags)
