"""A number the analyst may legally state, and what stops it lying.

Rule 2 removes a figure written into a sentence, correctly: a number a
reader cannot open is one they must take on trust. It never offered
anywhere else to put one, so the model wrote them anyway and lost whole
sentences — sixty per cent of hold-out rounds ended blank, every one of
them that way, over figures the packet was already carrying.

A placeholder is that somewhere else, and it is worth having only if
two things hold: the digits on screen come from the packet rather than
from anybody's memory of it, and a slot the packet cannot fill never
reaches a reader.
"""

from __future__ import annotations

import pytest

from planbench_explanation.magnitudes import (
    MagnitudeRefusal,
    placeholders_in,
    render,
    unresolvable,
)

REF = "obs:stuck_cluster:C1@ep-1/stopped_seconds"
FACTS: dict[str, object] = {
    REF: 1.3000000000000185,
    "obs:stuck_cluster:C1@ep-1/stops": 6,
    "obs:stuck_cluster:C1@ep-1": "stuck_cluster",
    "verdict:winner": "C1",
}


class TestWhatCountsAsAPlaceholder:
    def test_it_finds_the_ref_a_sentence_asks_for(self) -> None:
        assert placeholders_in(f"stopped for {{{REF}}} seconds") == (REF,)

    def test_a_sentence_with_no_slot_asks_for_nothing(self) -> None:
        assert placeholders_in("the local controller stopped repeatedly") == ()

    def test_several_slots_come_back_in_the_order_written(self) -> None:
        text = f"stopped {{{'obs:stuck_cluster:C1@ep-1/stops'}}} times over {{{REF}}} seconds"
        assert placeholders_in(text) == ("obs:stuck_cluster:C1@ep-1/stops", REF)


class TestASlotThePacketCannotFill:
    def test_a_ref_the_packet_never_carried(self) -> None:
        assert unresolvable("stopped for {obs:invented@ep-1/seconds}", FACTS) == (
            "obs:invented@ep-1/seconds",
        )

    def test_a_ref_that_resolves_to_something_that_is_not_a_number(self) -> None:
        """The quieter failure of the two: this one renders, and reads
        as a quantity, while naming a detector."""
        assert unresolvable("stopped for {obs:stuck_cluster:C1@ep-1} seconds", FACTS) == (
            "obs:stuck_cluster:C1@ep-1",
        )

    def test_a_ref_holding_a_label_is_not_a_magnitude_either(self) -> None:
        assert unresolvable("{verdict:winner} was ahead", FACTS) == ("verdict:winner",)

    def test_a_fillable_one_is_not_reported(self) -> None:
        assert unresolvable(f"stopped for {{{REF}}} seconds", FACTS) == ()


class TestWhatAReaderSees:
    def test_the_figure_comes_from_the_packet(self) -> None:
        assert render(f"stopped for {{{REF}}} seconds", FACTS) == "stopped for 1.3 seconds"

    def test_a_whole_number_keeps_no_decimal_tail(self) -> None:
        assert render("{obs:stuck_cluster:C1@ep-1/stops} stops", FACTS) == "6 stops"

    def test_it_refuses_rather_than_leaving_a_slot_on_screen(self) -> None:
        # A sentence reading "stopped for {obs:…}" in front of somebody
        # is worse than either version it was meant to be.
        with pytest.raises(MagnitudeRefusal):
            render("stopped for {obs:invented@ep-1/seconds}", FACTS)

    def test_nothing_is_copied_so_nothing_can_go_stale(self) -> None:
        """The property that makes this better than rewriting the
        sentence: re-score the run and the same statement renders the
        new number, because the statement never held the old one."""
        statement = f"stopped for {{{REF}}} seconds"
        rescored = {**FACTS, REF: 2.5}
        assert render(statement, FACTS) == "stopped for 1.3 seconds"
        assert render(statement, rescored) == "stopped for 2.5 seconds"
