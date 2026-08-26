"""W1.1 — what a candidate scored reaches the analyst, or is refused by name.

M1 put the measurement block in the packet and nothing could read it:
the card asked for ``episode_decision_utility``, which it never touches,
so on a gate-only run — every planted world is one — the seam withheld
that evidence and the tool was refused at admission. The block was in
the packet, the card was on the menu, and the path between them did not
exist. This holds the corrected contract, the reading, and the two
refusals that are now told apart.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from test_analyst_real_host import ask, declare, round_for, sidecars
from test_analyst_runner import bundle

from planbench_analyst.round_host import (
    evidence_for,
    in_process_round,
    platform_implementation_ref,
)
from planbench_explanation.catalog import TOOL_CATALOG, TOOL_CATALOG_VERSION
from planbench_explanation.integration import TYPICAL_AVAILABLE_EVIDENCE, MockToolHost
from planbench_explanation.packet_artifact import load_packet_artifact
from planbench_explanation.packet_facts import FactRefusal, serve_from_packet
from planbench_explanation.protocol import ProtocolRejection

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "golden" / "visible"
CARD = TOOL_CATALOG.card("get_candidate_measurements", "1.0.0")


def packet(case_id: str = "inflation-001"):  # type: ignore[no-untyped-def]
    return load_packet_artifact(FIXTURES, case_id).packet


def packet_without_measurements(source):  # type: ignore[no-untyped-def]
    """The same packet as a run that recorded no measurements left it."""
    return source.model_copy(update={"measurements": ()})


# --------------------------------------------------------------------------
# The contract: a card that names evidence it does not read is uncallable
# --------------------------------------------------------------------------


def test_the_card_requires_the_block_it_actually_reads() -> None:
    assert CARD.required_evidence == ("candidate_measurements",)
    assert "candidate_measurements" in TYPICAL_AVAILABLE_EVIDENCE


def test_the_wire_contract_moved_because_admission_did() -> None:
    """Same arguments, same measurements, different admission rule. A
    bundle frozen against 3.2.0 was graded on a menu this tool could not
    be called from, and a version that did not move would let that
    grading keep looking valid."""
    assert TOOL_CATALOG_VERSION == "3.3.0"


def test_both_refusal_codes_are_ones_the_card_declares() -> None:
    """An undeclared code is rejected by the session, which ends the
    analysis over one word."""
    assert set(CARD.failure_modes) >= {"candidate_not_in_packet", "measurements_not_recorded"}


# --------------------------------------------------------------------------
# The reading
# --------------------------------------------------------------------------


def test_the_packet_answers_with_what_the_run_recorded() -> None:
    served = serve_from_packet(CARD, packet(), {"candidate_id": "astar+dwa"})
    assert not isinstance(served, FactRefusal)
    assert served is not None
    measurements, references = served
    assert measurements["success_rate"] in (0.0, 1.0)
    assert measurements["n_episodes"] == 1.0
    # The card declares no reference kinds, and a result carrying one it
    # does not name is rejected by the session — the candidate id is in
    # the request the transcript already recorded.
    assert references == ()


def test_every_required_measurement_the_card_names_is_present() -> None:
    served = serve_from_packet(CARD, packet(), {"candidate_id": "astar+dwa"})
    assert not isinstance(served, FactRefusal)
    assert served is not None
    measurements, _ = served
    required = {spec.name for spec in CARD.io.measurements if spec.required}
    assert required <= set(measurements)


def test_the_denominator_travels_with_the_rate() -> None:
    """A success rate over one episode and one over thirty are different
    claims wearing one number."""
    served = serve_from_packet(CARD, packet(), {"candidate_id": "rrtstar+dwa"})
    assert not isinstance(served, FactRefusal)
    assert served is not None
    measurements, _ = served
    row = next(item for item in packet().measurements if item.candidate_id == "rrtstar+dwa")
    assert row.success_rate is not None
    assert measurements["n_episodes"] == float(row.success_rate.denominator or 0)


def test_a_measurement_the_run_did_not_record_is_absent_rather_than_zero() -> None:
    """These worlds rank nobody, so there is no decision utility. A zero
    would read as "scored nothing" instead of "was never scored"."""
    served = serve_from_packet(CARD, packet(), {"candidate_id": "astar+dwa"})
    assert not isinstance(served, FactRefusal)
    assert served is not None
    measurements, _ = served
    assert "decision_utility" not in measurements


# --------------------------------------------------------------------------
# Two refusals, told apart
# --------------------------------------------------------------------------


def test_a_candidate_the_packet_does_not_compare_is_named_as_such() -> None:
    served = serve_from_packet(CARD, packet(), {"candidate_id": "teb+dwa"})
    assert served == FactRefusal("candidate_not_in_packet")


def test_a_candidate_with_nothing_recorded_is_a_different_refusal() -> None:
    """The analyst's mistake and the run's gap are different facts: one
    is worth asking again about with another id, the other is not."""
    served = serve_from_packet(
        CARD, packet_without_measurements(packet()), {"candidate_id": "astar+dwa"}
    )
    assert served == FactRefusal("measurements_not_recorded")


def test_a_missing_argument_is_refused_rather_than_guessed() -> None:
    assert serve_from_packet(CARD, packet(), {}) == FactRefusal("candidate_not_in_packet")


# --------------------------------------------------------------------------
# Both hosts, one answer
# --------------------------------------------------------------------------


def test_the_real_host_serves_it_signed_by_the_build() -> None:
    prepared = round_for("inflation-001")
    declare(prepared, "geometric_infeasibility", "costmap_inflation")
    result = prepared.host.call(
        ask(prepared, "get_candidate_measurements", {"candidate_id": "astar+dwa"})
    )
    assert result.execution_status == "completed"
    assert result.measurements["n_episodes"] == 1.0
    assert result.implementation_ref == platform_implementation_ref()
    assert not (result.evidence_artifact_ref or "").startswith("mock://")


def test_the_real_host_forwards_the_refusal_code_rather_than_tool_unavailable() -> None:
    prepared = round_for("inflation-001")
    declare(prepared, "geometric_infeasibility", "costmap_inflation")
    result = prepared.host.call(
        ask(prepared, "get_candidate_measurements", {"candidate_id": "teb+dwa"})
    )
    assert result.execution_status == "not_checkable"
    assert result.failure_code == "candidate_not_in_packet"


def test_the_stub_host_answers_the_same_thing_it_always_did() -> None:
    """Two hosts answering one question two ways is the shape this layer
    keeps refusing; the stub differs only in what it signs with."""
    prepared = round_for("inflation-001")
    stub = MockToolHost(prepared.analysis)
    stub.session.declare((declare(prepared, "geometric_infeasibility", "costmap_inflation"),))
    served = stub.call(ask(prepared, "get_candidate_measurements", {"candidate_id": "astar+dwa"}))
    assert served.execution_status == "completed"
    assert served.measurements["n_episodes"] == 1.0
    refused = stub.call(
        ask(prepared, "get_candidate_measurements", {"candidate_id": "teb+dwa"}, sequence=2)
    )
    assert refused.failure_code == "candidate_not_in_packet"


# --------------------------------------------------------------------------
# The seam still derives what is available rather than being told
# --------------------------------------------------------------------------


def test_a_packet_with_no_measurements_withholds_the_evidence() -> None:
    bare = packet_without_measurements(packet())
    source = evidence_for(bare, sidecar_present=True)
    assert "candidate_measurements" not in source.available_evidence


def test_the_fixtures_now_carry_the_block_so_the_tool_is_admissible() -> None:
    source = evidence_for(packet(), sidecar_present=True)
    assert "candidate_measurements" in source.available_evidence


def test_a_request_against_a_packet_without_the_block_is_refused_at_admission() -> None:
    """Refused before it runs, rather than answered with an empty
    result: "the run recorded nothing" is a fact about the run, and the
    session is where it belongs."""
    prepared = in_process_round(
        packet_without_measurements(packet()),
        bundle(),
        catalog=TOOL_CATALOG,
        analysis_run_id="analysis-bare",
        sidecar_directories=sidecars("inflation-001"),
    )
    declare(prepared, "geometric_infeasibility", "costmap_inflation")
    with pytest.raises(ProtocolRejection) as caught:
        prepared.host.call(
            ask(prepared, "get_candidate_measurements", {"candidate_id": "astar+dwa"})
        )
    assert caught.value.code == "missing_required_evidence"
