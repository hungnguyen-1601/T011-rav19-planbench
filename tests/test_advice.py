"""The shape advice has to hold, and the two ways it fails.

Advice is text a reader acts on, so the tests that matter are about what
it is not allowed to be: unverifiable (a citation that resolves nowhere),
or unstable (two runs of one input disagreeing about the order). Both
failures look like working software until somebody trusts the output.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from planbench_decision.advice import Advice, keep_resolvable, order


def advice(**overrides: Any) -> Advice:
    base: dict[str, Any] = {
        "code": "P1",
        "kind": "preflight",
        "severity": "material",
        "claim": "the two candidates see different worlds",
        "ground": "one reads a static map, the other only LiDAR",
        "field_path": "candidates[0].observation_class",
        "do": "run them on the same observation class",
        "do_not": "read the ranking as a planner comparison",
    }
    base.update(overrides)
    return Advice(**base)


REPORT: dict[str, Any] = {
    "candidates": [{"observation_class": "map_static"}, {"observation_class": "lidar_only"}],
    "decision_card": {"status": "NEAR_EQUIVALENT"},
}


class TestEveryPieceOfAdviceCitesSomethingReal:
    def test_a_resolvable_citation_survives(self) -> None:
        assert keep_resolvable((advice(),), REPORT) == (advice(),)

    def test_a_citation_that_resolves_nowhere_is_dropped(self) -> None:
        """The reader cannot tell an unverifiable rule from a
        hallucinating model, so neither is published."""
        assert keep_resolvable((advice(field_path="candidates[0].no_such_field"),), REPORT) == ()

    def test_an_index_past_the_end_is_dropped(self) -> None:
        assert (
            keep_resolvable((advice(field_path="candidates[7].observation_class"),), REPORT) == ()
        )

    def test_the_rule_applies_to_rules_too_not_only_to_the_model(self) -> None:
        """A rule pointing at a field this particular report does not
        carry makes exactly the claim a fabrication would."""
        kept = keep_resolvable(
            (advice(code="R1"), advice(code="R2", field_path="absent.path")), REPORT
        )
        assert [a.code for a in kept] == ["R1"]


class TestOrderIsStable:
    def test_blocking_comes_before_material_before_disclosure(self) -> None:
        items = (
            advice(code="A", severity="disclosure"),
            advice(code="B", severity="blocking"),
            advice(code="C", severity="material"),
        )
        assert [a.code for a in order(items)] == ["B", "C", "A"]

    def test_two_orderings_of_one_input_agree(self) -> None:
        """Rules fire in whatever order their module evaluates them; a
        list that reshuffles between identical runs cannot be diffed."""
        items = tuple(advice(code=c) for c in ("Z", "A", "M"))
        assert order(items) == order(tuple(reversed(items)))

    def test_ties_break_on_code_rather_than_on_arrival(self) -> None:
        items = (advice(code="P9"), advice(code="P2"))
        assert [a.code for a in order(items)] == ["P2", "P9"]

    def test_an_unknown_severity_sorts_last_rather_than_crashing(self) -> None:
        """Advice arriving from a model layer is validated, but a future
        severity added upstream must not take the ordering down."""
        loose = advice()
        widened = Advice.model_construct(**{**loose.model_dump(), "severity": "someday"})
        assert order((widened, advice(code="A", severity="blocking")))[0].code == "A"


class TestTheShapeRefusesWhatWouldMislead:
    def test_advice_is_frozen(self) -> None:
        """A caller that could edit `do_not` could erase the forbidden
        move from a copy the reader sees."""
        with pytest.raises(ValidationError):
            advice().code = "changed"

    def test_a_forbidden_move_may_be_empty_but_must_be_deliberate(self) -> None:
        """Empty is allowed — some situations have no tempting wrong
        move — and it defaults to empty rather than to a placeholder,
        so a rule that never set it reads as "none" rather than as
        advice nobody wrote."""
        assert advice(do_not="").do_not == ""

    @pytest.mark.parametrize("field", ["code", "kind", "severity", "claim", "ground", "do"])
    def test_the_fields_a_reader_needs_are_required(self, field: str) -> None:
        payload = advice().model_dump()
        payload.pop(field)
        with pytest.raises(ValidationError):
            Advice(**payload)

    def test_a_kind_outside_the_lifecycle_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            advice(kind="whenever")

    def test_a_severity_outside_the_three_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            advice(severity="catastrophic")


class TestTheCitationWalkerAcceptsWhatCallersActuallyPass:
    """Every module in this family type-hints its source as a `Mapping`.

    The walker tested `isinstance(node, dict)`, so a caller who honoured
    that hint with a `MappingProxyType` — the obvious way to hand out a
    read-only report — had every citation fail and every piece of advice
    deleted in silence. A dropped citation and a rule that declined to
    fire look identical from outside, so nothing would have reported it.
    """

    def test_a_read_only_mapping_resolves(self) -> None:
        from types import MappingProxyType

        source = MappingProxyType({"candidates": [MappingProxyType({"observation_class": "x"})]})
        assert keep_resolvable((advice(),), source) == (advice(),)

    def test_a_tuple_indexes_like_a_list(self) -> None:
        """`model_dump()` on a frozen model yields tuples for sequence
        fields, and a rule citing `xs[0]` must not care which it got."""
        from planbench_decision.self_check import exists

        assert exists({"xs": (1, 2, 3)}, "xs[1]")

    def test_a_string_is_not_indexed_as_a_sequence(self) -> None:
        """`summary.note[0]` would otherwise resolve to a character, and
        a nonsense citation would pass the check that exists to catch
        nonsense citations."""
        from planbench_decision.self_check import exists

        assert not exists({"note": "abc"}, "note[0]")
