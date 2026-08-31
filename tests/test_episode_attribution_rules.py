"""Two ways an episode answer blamed something it had no grounds to.

Both came out of a hand-scored hold-out, and neither was visible to the
rubric that scored it, because both produce sentences that are *true
about something* and cite refs that open.

**A component blamed with nothing to lean on.** The packet grades its
own differences: `context` narrows the space, `support` carries a
mechanism. An episode whose contrasts are all `context` has nothing
that can carry one — and two arms attributed anyway, saying "the
global_planner component difference explains why C5 achieved higher min
clearance" and a path "causing C1 to traverse closer to obstacles and
slow down". Both rest on `component_differs`, which states in its own
words that a mechanism "has to live in one of those": it says where to
look, not what happened.

**A component the episode never observed.** Eight subjects exist in the
taxonomy; a comparison declares three per side, and the rest arrive only
when something measured them. One arm wrote "costmap_inflation refused
to maintain clearance above the minimum threshold 0.15" on a packet with
no robot block, no inflation margin, and no threshold at all — only
`min_clearance = 0.148568`, rounded up into a limit nobody set.

Measured before they were written, over the two recorded arms: together
they remove every statement a scorer marked `wrong` and leave every
`explains` standing.
"""

from __future__ import annotations

import pathlib

from test_explanation_episode_packet import (
    build_contrasts,
    build_diagnoses,
    components,
    outcome,
    verdict_for,
)
from test_explanation_episode_packet import build_packet as _packet

from planbench_analyst.episode_guard import (
    _compares_without_support,
    _subject_absent_from_episode,
    contract_terms_met,
    contradicts_verdict,
)
from planbench_analyst.episode_runner import REWORDABLE_RULES
from planbench_analyst.episode_view import build_episode_view
from planbench_analyst.guard import quantities_in
from planbench_explanation.episode_floor import episode_floor
from planbench_explanation.episode_packet import EpisodeContrast, EpisodePacket, RobotFacts
from planbench_explanation.ledger import EvidenceRef, HypothesisProposal

REPO = pathlib.Path(__file__).resolve().parents[1]


class _Proposal:
    """Only the field the rule reads.

    A whole `HypothesisProposal` would need a statement, a type and refs
    that pass six earlier rules, none of which this one looks at.
    """

    def __init__(self, subject: str) -> None:
        self.proposed_subject = subject


def _context_only_packet() -> EpisodePacket:
    """A packet whose every contrast is `context`.

    Built by giving the two sides no detection at all: `component_differs`
    and `outcome_differs` remain, and both are graded `context`.
    """
    scored_a = outcome("A", decision_utility=0.87)
    scored_b = outcome("B")
    result = verdict_for(scored_a, scored_b)
    contrasts, ruled_out = build_contrasts(
        verdict=result,
        outcomes={"A": scored_a, "B": scored_b},
        components={"A": components("A"), "B": components("B", global_planner="rrtstar")},
        detections=[],
    )
    return _packet(
        contrasts=contrasts,
        ruled_out=ruled_out,
        diagnoses=build_diagnoses(
            verdict=result, outcomes={"A": scored_a, "B": scored_b}, detections=[]
        ),
    )


class TestAComponentMayNotBeBlamedWithNothingToLeanOn:
    def test_a_packet_with_no_supported_contrast_forbids_attribution(self) -> None:
        packet = _context_only_packet()
        assert not any(contrast.strength == "support" for contrast in packet.contrasts)
        assert "component_specific_attribution" in packet.blocked_claim_types

    def test_a_supported_contrast_allows_it_again(self) -> None:
        """The default packet carries a detection, so one contrast earns
        `support` — and the type has to come back, or the rule would
        refuse the answers this scope exists to produce."""
        packet = _packet()
        assert any(contrast.strength == "support" for contrast in packet.contrasts)
        assert "component_specific_attribution" not in packet.blocked_claim_types

    def test_it_is_declared_by_the_packet_rather_than_refused_later(self) -> None:
        """Where the rule lives is the decision, not an implementation
        detail. Blocked types travel in the packet, so the model is told
        before it drafts; catching the same sentence in the guard would
        spend a round and hand back silence, which is the failure this
        scope is being measured on."""
        blocked = _context_only_packet().blocked_claim_types
        assert isinstance(blocked, tuple) and "component_specific_attribution" in blocked

    def test_the_other_claim_types_are_untouched(self) -> None:
        """A mechanism seen in this episode is still sayable. The rule
        withdraws the right to name a *responsible component*, not the
        right to report what happened."""
        blocked = _context_only_packet().blocked_claim_types
        assert "local_minimum_entrapment" not in blocked


class TestAComponentTheEpisodeNeverObserved:
    def test_a_subject_with_no_fact_and_no_declaration_is_refused(self) -> None:
        view = build_episode_view(_packet())
        assert _subject_absent_from_episode(_Proposal("costmap_inflation"), view) is not None

    def test_a_declared_component_is_always_in_scope(self) -> None:
        """`obs:` and `diag:` facts carry no subject, so a rule that
        demanded a subject-bearing fact would refuse ordinary findings
        about the local controller — it did, on thirteen of twenty-five
        proposals, until this was narrowed to the subjects a packet has
        to earn."""
        view = build_episode_view(_packet())
        for field in ("global_planner", "local_controller", "local_controller_config"):
            assert _subject_absent_from_episode(_Proposal(field), view) is None

    def test_a_measured_subject_is_in_scope_once_measured(self) -> None:
        """The rule is about this episode's recording, not about a
        blacklist: give the packet a robot and costmap inflation becomes
        a thing that was measured, so it may be named."""
        view = build_episode_view(_packet(robot=RobotFacts(radius_m=0.3, inflation_margin_m=0.25)))
        assert _subject_absent_from_episode(_Proposal("costmap_inflation"), view) is None

    def test_the_reason_names_the_subject_it_refused(self) -> None:
        """A blocked round is read by a person deciding whether the
        refusal was right. "this episode records nothing about X" says
        which X; a bare rule name would send them back to the packet."""
        view = build_episode_view(_packet())
        reason = _subject_absent_from_episode(_Proposal("task_geometry"), view)
        assert reason is not None and "task_geometry" in reason


class TestARewriteMayFixACitationButNotAClaim:
    """Which refusals earn a second attempt.

    A round that loses every proposal is asked once more only when
    everything it lost was lost over *how a sentence was written*. The
    line matters in both directions: too narrow and the analyst goes
    silent holding the right answer, too wide and a refusal becomes an
    invitation to say the same wrong thing in safer words.
    """

    def test_a_placeholder_that_resolves_to_nothing_is_a_citation_mistake(self) -> None:
        """`magnitude_not_in_packet` fires when the ref inside the braces
        holds no number. The finding may be exactly right and reachable
        by naming a ref that resolves, or by dropping the figure — so it
        is a citation chosen wrongly, not a claim held wrongly, and a
        hold-out episode with a supported contrast went silent on this
        alone."""
        assert "magnitude_not_in_packet" in REWORDABLE_RULES

    def test_a_claim_the_packet_withdrew_is_not_reworded(self) -> None:
        """`claim_blocked_by_packet` means the packet has taken away the
        right to make that kind of claim here. No wording restores it,
        and asking again would spend a call to be refused identically."""
        assert "claim_blocked_by_packet" not in REWORDABLE_RULES

    def test_a_statement_against_the_verdict_is_not_reworded(self) -> None:
        """Handing the episode to the side the platform did not name is
        not badly worded. It is wrong."""
        assert "contradicts_verdict" not in REWORDABLE_RULES

    def test_blaming_an_unobserved_component_is_not_reworded(self) -> None:
        """Rule 12 refuses a subject this episode records nothing about.
        A rewrite cannot make the episode have observed it."""
        assert "subject_absent_from_episode" not in REWORDABLE_RULES


class TestTheFloorKeepsSpeakingWhereTheModelWasRefused:
    """The fallback must not inherit a rule written for the model.

    Withdrawing `component_specific_attribution` on context-only
    episodes covers most of the episodes the floor exists for. If the
    floor's diagnosis loop ever starts consulting `blocked_claim_types`
    — the obvious way to "tidy" the two halves of that function into
    agreement — the fallback goes silent exactly where the model already
    did, and a reader who was owed "here is what fired" gets a blank.
    """

    def test_a_context_only_packet_still_gets_what_fired(self) -> None:
        packet = _context_only_packet()
        assert "component_specific_attribution" in packet.blocked_claim_types
        answer = episode_floor(_packet())
        assert answer.proposals, "the floor is the panel of last resort"

    def test_what_it_says_is_a_detection_and_not_an_attribution(self) -> None:
        """Why it is allowed to speak at all: the type is a carrier, the
        sentence reports a detector firing, and the subject is the task's
        geometry rather than either stack."""
        first = episode_floor(_packet()).proposals[0]
        assert "was detected on" in first.hypothesis_statement
        assert first.proposed_subject == "task_geometry"

    def test_it_never_reaches_the_guard(self) -> None:
        """`answer_from_floor` builds a response out of the floor's
        proposals directly. Rules 11 and 12 govern what a model may
        propose; the floor is the platform stating what it recorded."""
        source = (
            REPO / "services" / "analyst_service" / "planbench_analyst" / "episode_runner.py"
        ).read_text(encoding="utf-8")
        after = source.split("answer = episode_floor(view.packet)", 1)[1]
        assert "episode_guard(" not in after.split("def ", 1)[0]


class TestBothSidesWeighedWhereNothingReachedSupport:
    """Rule 11 withdrew a proposition type; the claim came back wearing
    another one.

    The deployment arm made the same comparison under
    `local_minimum_entrapment` with subject `global_planner`, citing
    `component_differs` — "global_planner of C5 triggered a replan during
    the stuck cluster while C1 did not". Both statements a scorer marked
    `wrong` on that arm are that shape. Blocking one type blocked a
    label, not a move, so this asks the packet instead.
    """

    def _proposal(self, statement: str, **kw: object) -> HypothesisProposal:
        base: dict[str, object] = {
            "hypothesis_id": "h1",
            "hypothesis_statement": statement,
            "proposition_type": "local_minimum_entrapment",
            "proposed_subject": "local_controller",
        }
        base.update(kw)
        return HypothesisProposal(**base)  # type: ignore[arg-type]

    def _labels(self, view: object) -> tuple[str, str]:
        verdict = view.packet.verdict  # type: ignore[attr-defined]
        return (
            view.aliases.label_for(str(verdict.candidate_a)),  # type: ignore[attr-defined]
            view.aliases.label_for(str(verdict.candidate_b)),  # type: ignore[attr-defined]
        )

    def test_a_comparison_is_refused_when_no_contrast_reached_support(self) -> None:
        view = build_episode_view(_context_only_packet())
        a, b = self._labels(view)
        reason = _compares_without_support(
            self._proposal(f"{a} entered local minima more times than {b} did"), view
        )
        assert reason is not None and "support strength" in reason

    def test_naming_one_side_is_not_weighing_two(self) -> None:
        """An observation about a single run stays sayable. What the
        packet cannot carry is the comparison, not the report."""
        view = build_episode_view(_context_only_packet())
        a, _ = self._labels(view)
        assert (
            _compares_without_support(self._proposal(f"{a} was stopped for a while"), view) is None
        )

    def test_a_supported_packet_lets_the_comparison_through(self) -> None:
        """**The measurement that decided the shape of this rule.**

        The first draft refused any comparison whose contract was unmet,
        and on the deployment arm that removed five of the six episodes a
        scorer marked `explains`. Explaining why one side beat the other
        *is* comparing them. Restricted to packets where nothing reached
        `support`, the same measurement caught the two wrong statements
        and touched no `explains` on any of the three recorded arms.
        """
        view = build_episode_view(_packet())
        a, b = self._labels(view)
        assert (
            _compares_without_support(
                self._proposal(f"{a} was trapped in a local minimum longer than {b}"), view
            )
            is None
        )

    def test_it_drops_rather_than_demotes(self) -> None:
        """Rule 10 keeps an over-claimed proposal as a diagnosis, which
        is right when the register was the only thing wrong. Here the
        comparison is in the sentence, so demoting relabels a claim the
        reader still meets in full."""
        source = (
            REPO / "services" / "analyst_service" / "planbench_analyst" / "episode_guard.py"
        ).read_text(encoding="utf-8")
        after = source.split("_compares_without_support(proposal, view)", 1)[-1]
        head = after.split("contradicts_verdict", 1)[0]
        assert "continue" in head, "a blocked comparison must not fall through to the register"


class TestTheCostFigureIsABound:
    """It was read as the bill and reported onward as one.

    `holdout-deployment` printed $0.6805 and cost $0.30. Episodes share a
    long prefix and a cached input token bills at a fraction of a fresh
    one, which the token counts do not separate — so the arithmetic is
    deliberately pessimistic, and what has to be right is the wording.
    """

    def _source(self) -> str:
        return (REPO / "scripts" / "run_episode_experiments.py").read_text(encoding="utf-8")

    def test_the_printed_figure_says_it_is_an_upper_bound(self) -> None:
        assert "at most $" in self._source()

    def test_the_artifact_carries_the_same_warning(self) -> None:
        """A number read out of a JSON file months later has no print
        statement beside it."""
        assert '"usd_is_upper_bound": True' in self._source()

    def test_the_prices_are_not_tuned_down_to_match_a_bill(self) -> None:
        """They gate spending: `--budget-usd` stops the sweep when the
        estimate reaches the ceiling, so overestimating stops early and
        underestimating spends somebody's money. One observed cache hit
        rate is not a rate."""
        source = self._source()
        assert "PRICE_IN_PER_M = 1.10" in source
        assert "PRICE_OUT_PER_M = 4.40" in source


class TestANameWithDigitsInItIsStillAName:
    """Rule 2's own docstring has always said so; the check did not.

    ``identifiers`` holds the candidate labels a packet uses, and the
    membership test was against the token exactly — so ``C1`` was a name
    and ``C1's`` was a quantity. Every inflected form fell through to
    the digit-bearing branch: the possessive, ``C1/C5``, ``C1-side``.

    It is worth its own class because of where it sits. Rule 2 refused
    109 of 211 proposals on the three-reading hold-out and appears in
    thirteen of the fifteen rounds where a packet could have been
    explained and the analyst said nothing — and a possessive is how
    anybody writes a comparison between two named sides.
    """

    IDS = frozenset({"C1", "C5"})

    def test_a_possessive_is_a_name(self) -> None:
        assert quantities_in("C5's stuck cluster was worse than C1's", self.IDS) == ()

    def test_two_names_joined_are_names(self) -> None:
        assert quantities_in("the C1/C5 pair diverged early", self.IDS) == ()

    def test_a_name_used_as_a_modifier_is_a_name(self) -> None:
        assert quantities_in("on the C1-side of the route", self.IDS) == ()

    def test_a_figure_welded_to_a_name_is_still_a_figure(self) -> None:
        """Split rather than stripped, so the loosening cannot be used
        to smuggle a number past by attaching it to a label."""
        assert quantities_in("C1-2.05 was recorded", self.IDS) == ("C1-2.05",)

    def test_a_number_joined_to_a_word_is_still_a_number(self) -> None:
        assert quantities_in("a 30-episode run", self.IDS) == ("30-episode",)

    def test_the_ordinary_refusals_are_untouched(self) -> None:
        for statement, expected in (
            ("C5 stopped for 2.05 s", "2.05"),
            ("clearance was 0.74m", "0.74m"),
            ("stopped 2x longer", "2x"),
            ("twice as long", "twice"),
        ):
            assert expected in quantities_in(statement, self.IDS), statement


class TestARefusalHasToSayWhatItObjectedTo:
    """Only the rule name was recorded, and it made the cheapest work
    available impossible.

    Thirty-six rounds were offered a rewrite and twenty-one still ended
    in silence. Reading those twenty-one costs nothing and points
    straight at the rule doing most of the blocking — except that what
    the model wrote was gone and only the word `quantity_in_statement`
    was left beside it.
    """

    def _sweep_source(self) -> str:
        return (REPO / "scripts" / "run_episode_experiments.py").read_text(encoding="utf-8")

    def test_the_artifact_records_what_the_rule_read(self) -> None:
        source = self._sweep_source()
        assert '"blocked_detail"' in source
        assert '"detail": item.detail' in source

    def test_the_rule_name_list_is_kept_beside_it(self) -> None:
        """Every artifact already written has `blocked`, and the hard
        constraints are counted off it. A replacement would have made
        the new sweeps incomparable with the old ones."""
        assert '"blocked": blocked,' in self._sweep_source()

    def test_a_rewrite_records_which_turn_each_refusal_came_from(self) -> None:
        """`blocked` on a reworded round is both turns concatenated —
        right for a spend count, useless for asking whether the second
        turn repeated the first mistake or made a new one."""
        source = (
            REPO / "services" / "analyst_service" / "planbench_analyst" / "episode_runner.py"
        ).read_text(encoding="utf-8")
        assert '"blocked_first_turn"' in source
        assert '"blocked_second_turn"' in source


class TestAnAdverbUsedToWalkPastTheVerdictRule:
    """Rule 9 is the one hard constraint whose ceiling is zero.

    Its job is to stop a sentence handing the episode to the side the
    platform did not name, and it was written as
    ``f"{label} {word}" in sentence`` — the label and the claim
    adjacent, nothing between. "C5 wins" was caught; "C5 clearly wins",
    "C5 ultimately won" and "C5 is clearly faster" walked through.

    The gap allowed is three words, and three was measured rather than
    picked: across every statement that survived on all four recorded
    arms, a gap of nought, one, two and three each flags exactly
    nothing, so the widening costs no true statement on the data in
    hand.
    """

    def _view(self):  # type: ignore[no-untyped-def]
        return build_episode_view(_packet())

    def _labels(self, view) -> tuple[str, str]:  # type: ignore[no-untyped-def]
        verdict = view.packet.verdict
        return (
            view.aliases.label_for(str(verdict.winner)),
            view.aliases.label_for(str(verdict.loser)),
        )

    def _said(self, sentence: str):  # type: ignore[no-untyped-def]
        view = self._view()
        return contradicts_verdict(
            HypothesisProposal(
                hypothesis_id="h",
                hypothesis_statement=sentence,
                proposition_type="local_minimum_entrapment",
                proposed_subject="local_controller",
            ),
            view,
        )

    def test_the_bare_claim_is_still_caught(self) -> None:
        _, loser = self._labels(self._view())
        assert self._said(f"{loser} wins this episode") is not None

    def test_an_adverb_no_longer_hides_it(self) -> None:
        _, loser = self._labels(self._view())
        for sentence in (
            "{} clearly wins this episode",
            "{} ultimately won",
            "{} is clearly faster",
            "{}, in the end, wins",
        ):
            assert self._said(sentence.format(loser)) is not None, sentence

    def test_the_winner_may_still_be_said_to_have_won(self) -> None:
        """The rule is about direction, not about the word. A sentence
        naming the side that did win is not a contradiction."""
        winner, _ = self._labels(self._view())
        assert self._said(f"{winner} clearly wins this episode") is None

    def test_an_ordinary_finding_about_the_loser_is_untouched(self) -> None:
        _, loser = self._labels(self._view())
        assert self._said(f"the local_controller on {loser} stalled in a local minimum") is None

    def test_a_far_apart_mention_is_not_read_as_a_claim(self) -> None:
        """The gap is bounded, so a sentence that names the loser early
        and says something about the winner much later is not swept in."""
        winner, loser = self._labels(self._view())
        assert (
            self._said(
                f"{loser} entered a local minimum near the corridor mouth, "
                f"which is the reason {winner} is faster"
            )
            is None
        )


class TestADetectionWithNoMechanismBehindItCarriesNothing:
    """The two detection kinds are graded `support` because a detector
    firing on one side and not the other is evidence about a mechanism.

    That holds only where the registry says *which* mechanism and which
    component owns it. `near_miss_cluster` has no entry in
    `DETECTION_HYPOTHESES`, so its contrasts arrive with
    `proposition_type` and `subject` both None — and `support` then
    licensed a claim about a component nothing in the packet names. It
    is the second most common detector in the hold-out cluster, six
    episodes of thirty, and two of the three statements a scorer marked
    `wrong` on the last sweep rest on it, blaming two different
    components with nothing to contradict either.
    """

    def _contrast(self, **kw: object) -> EpisodeContrast:
        base: dict[str, object] = {
            "kind": "detection_only_on_loser",
            "against_candidate_id": "B",
            "detail": "a detector fired on one side and not the other",
        }
        base.update(kw)
        return EpisodeContrast(**base)  # type: ignore[arg-type]

    def test_a_mapped_detection_still_supports(self) -> None:
        mapped = self._contrast(
            proposition_type="local_minimum_entrapment", subject="local_controller"
        )
        assert mapped.strength == "support"

    def test_an_unmapped_detection_is_demoted_to_context(self) -> None:
        assert self._contrast().strength == "context"

    def test_it_is_demoted_rather_than_withheld(self) -> None:
        """The detection is real. What it stops doing is standing behind
        an attribution — it stays in the packet as a difference and as
        an observation."""
        assert self._contrast().kind == "detection_only_on_loser"

    def test_the_other_kinds_are_untouched(self) -> None:
        """`component_differs` and the rest were already `context`, and
        they carry no proposition either — the rule must not be read as
        being about a missing field in general."""
        differs = EpisodeContrast(
            kind="component_differs", against_candidate_id="B", detail="the stacks differ"
        )
        assert differs.strength == "context"


class TestTheSupportingContrastHasToBeAboutWhatIsBlamed:
    """`subject_match` used to be granted on an empty set.

    Rule 6 refuses a citation naming a *different* component, so silence
    was read as silence rather than as a match. That held while every
    supporting contrast carried a subject and stopped holding when one
    arrived without.

    **After the demotion above, this fires on nothing in the recorded
    data** — the subject-less contrast is no longer `support`, so the
    case it was written for cannot arise the same way twice. It is kept
    as the rule the reasoning asks for, not as a measured improvement,
    and these tests pin it against a packet built to have the shape.
    """

    def _proposal(self, subject: str, refs: tuple[str, ...]) -> HypothesisProposal:
        return HypothesisProposal(
            hypothesis_id="h",
            hypothesis_statement="a mechanism happened on the losing side",
            proposition_type="local_minimum_entrapment",
            proposed_subject=subject,
            supports=tuple(EvidenceRef(ref=ref, kind="observation") for ref in refs),
        )

    def _supported_ref(self, view: object) -> str:
        return next(
            fact.ref
            for fact in view.facts  # type: ignore[attr-defined]
            if fact.ref.startswith("contrast:") and str(fact.value) == "support"
        )

    def test_the_right_component_still_matches(self) -> None:
        view = build_episode_view(_packet())
        ref = self._supported_ref(view)
        subject = view.fact(ref).subject
        missing, _ = contract_terms_met(self._proposal(subject, (ref,)), view)
        assert "subject_match" not in missing

    def test_a_different_component_no_longer_matches(self) -> None:
        """The term is read off the *supporting* contrasts. Citing one
        that belongs to the global planner and blaming the costmap is
        not a match, however many other refs are attached."""
        view = build_episode_view(_packet())
        ref = self._supported_ref(view)
        missing, _ = contract_terms_met(self._proposal("costmap_inflation", (ref,)), view)
        assert "subject_match" in missing

    def test_polarity_goes_with_it(self) -> None:
        """A supporting contrast about another mechanism is not evidence
        that this one harms the side it is stated against."""
        view = build_episode_view(_packet())
        ref = self._supported_ref(view)
        missing, _ = contract_terms_met(self._proposal("costmap_inflation", (ref,)), view)
        assert "polarity_match" in missing

    def test_a_proposal_citing_no_supporting_contrast_is_read_as_before(self) -> None:
        """Rule 10 already refuses it for want of `contrast_support`.
        Tightening the subject term there as well would say the same
        thing twice and change which reason gets recorded."""
        view = build_episode_view(_packet())
        missing, _ = contract_terms_met(self._proposal("local_controller", ()), view)
        assert "contrast_support" in missing
        assert "subject_match" not in missing
