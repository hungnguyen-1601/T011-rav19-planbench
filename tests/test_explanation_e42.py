"""E4.2 — a run that ranked nobody still gets a packet.

What these guard: a packet may carry no comparison; what it loses when
there is none is exactly the pair-shaped parts and nothing else; the
absence is an omission with a reason rather than an empty field; and
exemplars cannot survive without the ranking that defines their roles.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from test_explanation_e41 import built, stalled_trace

from planbench_explanation.case_packet import CasePacketRefusal
from planbench_explanation.exemplars import EXEMPLAR_ROLES
from planbench_explanation.packet_builder import packet_block, packet_from_block
from planbench_explanation.panel import plan_for


def no_card(**overrides):  # type: ignore[no-untyped-def]
    fields = {"waterfall": None, "decision_status": "NO_DECISION_CARD"}
    fields.update(overrides)
    return built(**fields)


def test_a_run_that_ranked_nobody_still_has_a_packet() -> None:
    """The runs somebody most asks "why did it fail" about.

    Building only in the ranked branch meant the detectors never ran
    here and the endpoint answered 409 to exactly that question.
    """
    outcome = no_card(traces=[stalled_trace("cand_a", "ep-001"), stalled_trace("cand_b", "ep-001")])
    assert outcome.packet.decision.waterfall is None
    assert outcome.packet.decision.status == "NO_DECISION_CARD"
    assert outcome.packet.observations
    assert outcome.packet.lattice


def test_what_it_loses_is_the_pair_shaped_parts_and_nothing_else() -> None:
    packet = no_card().packet
    assert packet.decision.waterfall is None
    assert packet.representative_episodes is None
    # Still there: the candidates, the gaps, the lattice, the gate table.
    assert len(packet.candidates) == 2
    assert packet.known_unknowns
    assert packet.lattice


def test_the_absence_of_a_comparison_is_an_omission_with_a_reason() -> None:
    """An empty field reads as "the recipe found nothing"."""
    outcome = no_card()
    assert any("ranked nobody" in note for note in outcome.omissions)


def test_exemplars_cannot_outlive_the_ranking_that_names_them() -> None:
    """Three of the four roles are defined against the pair ΔU used.

    A packet holding exemplars and no waterfall is four episodes wearing
    labels nothing earned, so the schema refuses it rather than letting
    a page render "best for the winner" on a run with no winner.
    """
    from planbench_explanation.case_packet import CasePacket

    with_pair = built().packet
    assert with_pair.decision.waterfall is not None

    payload = with_pair.model_dump(mode="json")
    payload["decision"]["waterfall"] = None
    payload["representative_episodes"] = {
        "candidate_a": "cand_a",
        "candidate_b": "cand_b",
        "n_episodes": 4,
        "exemplars": [
            {
                "role": role,
                "episode_context_id": f"ep-{index:03d}",
                "delta_utility": 0.1 * (index + 1),
                "criterion": 0.1 * (index + 1),
            }
            for index, role in enumerate(EXEMPLAR_ROLES)
        ],
    }
    with pytest.raises((CasePacketRefusal, ValidationError), match="labels nothing earned"):
        CasePacket.model_validate(payload)


def test_the_panel_already_knew_not_to_draw_a_comparison() -> None:
    """The matrix was right before the builder was; this closes the gap."""
    for outcome in ("no_survivors", "gate_only"):
        plan = plan_for(outcome, has_comparison=False)  # type: ignore[arg-type]
        assert not plan.show_waterfall
        assert not plan.show_exemplars
        # And the half that was always meant to be there.
        assert plan.show_trace_evidence
        assert plan.show_gate_table


def test_a_no_card_packet_round_trips_through_the_report_block() -> None:
    outcome = no_card()
    assert packet_from_block(packet_block(outcome)) == outcome.packet
