"""W1.2 — the exemplar episode as it went, on one clock, for one candidate.

M2 derived the timeline points server-side and put them in the packet;
the card then asked for ``trace`` and ``reference_line``, which are what
that derivation was computed *from*. On a run whose sidecar is absent
the seam withholds those, so a packet carrying a timeline block was
answered "unavailable" — the same shape W1.1 found on the measurements.

Two more things are held here. That the clock is never resolved for the
reader, because at equal time and at equal progress are answers about
different moments. And that an episode both candidates drove is refused
rather than answered for whichever timeline came first: an
``episode_context_id`` is a hash of the conditions, so a comparison
shares one.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from test_analyst_real_host import ask, declare, round_for, sidecars
from test_analyst_runner import bundle

from planbench_analyst.round_host import evidence_for, in_process_round
from planbench_explanation.catalog import TOOL_CATALOG, TOOL_CATALOG_VERSION
from planbench_explanation.integration import TYPICAL_AVAILABLE_EVIDENCE
from planbench_explanation.packet_artifact import load_packet_artifact
from planbench_explanation.packet_facts import FactRefusal, serve_from_packet
from planbench_explanation.protocol import ProtocolRejection

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "golden" / "visible"
CARD = TOOL_CATALOG.card("get_episode_timeline", "1.0.0")


def packet(case_id: str = "dwa-001"):  # type: ignore[no-untyped-def]
    return load_packet_artifact(FIXTURES, case_id).packet


def episode_of(case_id: str = "dwa-001") -> str:
    return packet(case_id).timelines[0].episode_context_id


def without_timelines(source):  # type: ignore[no-untyped-def]
    return source.model_copy(update={"timelines": ()})


# --------------------------------------------------------------------------
# The contract
# --------------------------------------------------------------------------


def test_the_card_requires_the_block_and_not_what_it_was_derived_from() -> None:
    assert CARD.required_evidence == ("episode_timeline",)
    assert "episode_timeline" in TYPICAL_AVAILABLE_EVIDENCE


def test_the_candidate_argument_exists_and_is_optional() -> None:
    """Optional because a packet may hold one candidate's timeline for an
    episode; present because it may hold both."""
    argument = next(item for item in CARD.io.arguments if item.name == "candidate_id")
    assert argument.required is False


def test_the_wire_contract_moved_with_the_admission_rule() -> None:
    assert TOOL_CATALOG_VERSION == "3.4.0"


def test_every_refusal_this_serves_is_declared_on_the_card() -> None:
    assert set(CARD.failure_modes) >= {
        "episode_not_an_exemplar",
        "timeline_not_recorded",
        "clock_not_recognised",
        "candidate_required_for_episode",
    }


# --------------------------------------------------------------------------
# The reading, on one clock at a time
# --------------------------------------------------------------------------


@pytest.mark.parametrize("clock", ["at_time", "at_progress"])
def test_the_packet_answers_for_the_clock_that_was_asked_for(clock: str) -> None:
    served = serve_from_packet(
        CARD,
        packet(),
        {"episode_context_id": episode_of(), "clock": clock, "candidate_id": "astar+dwa"},
    )
    assert not isinstance(served, FactRefusal)
    assert served is not None
    measurements, _ = served
    assert measurements["n_points"] == 3.0
    assert measurements["progress_fraction"] >= 0.0
    assert 0.0 <= measurements["path_efficiency"] <= 1.0


def test_the_two_clocks_are_read_from_different_marks() -> None:
    """If they came back identical the argument would be decorative, and
    a clearance compared at equal time would be passing for one compared
    at equal progress."""
    arguments = {"episode_context_id": episode_of(), "candidate_id": "astar+dwa"}
    at_time = serve_from_packet(CARD, packet(), {**arguments, "clock": "at_time"})
    at_progress = serve_from_packet(CARD, packet(), {**arguments, "clock": "at_progress"})
    assert not isinstance(at_time, FactRefusal) and at_time is not None
    assert not isinstance(at_progress, FactRefusal) and at_progress is not None
    marks = [
        point.mark
        for point in packet().timelines[0].points
        if point.clock in ("at_time", "at_progress")
    ]
    assert len(set(marks)) > 1


def test_every_required_measurement_the_card_names_is_present() -> None:
    served = serve_from_packet(
        CARD,
        packet(),
        {"episode_context_id": episode_of(), "clock": "at_time", "candidate_id": "astar+dwa"},
    )
    assert not isinstance(served, FactRefusal)
    assert served is not None
    measurements, _ = served
    assert {spec.name for spec in CARD.io.measurements if spec.required} <= set(measurements)


# --------------------------------------------------------------------------
# What it will not answer
# --------------------------------------------------------------------------


def test_an_unrecognised_clock_is_refused_rather_than_resolved() -> None:
    served = serve_from_packet(
        CARD, packet(), {"episode_context_id": episode_of(), "clock": "wall"}
    )
    assert served == FactRefusal("clock_not_recognised")


def test_an_episode_both_candidates_drove_needs_a_candidate() -> None:
    """Both stacks of one comparison share the episode id, and an answer
    that does not say whose run it is describes neither."""
    served = serve_from_packet(
        CARD, packet(), {"episode_context_id": episode_of(), "clock": "at_time"}
    )
    assert served == FactRefusal("candidate_required_for_episode")


def test_an_episode_the_packet_carries_no_timeline_for_is_named_as_such() -> None:
    served = serve_from_packet(
        CARD, packet(), {"episode_context_id": "not-an-episode", "clock": "at_time"}
    )
    assert served == FactRefusal("episode_not_an_exemplar")


def test_a_candidate_that_did_not_drive_that_episode_is_a_different_refusal() -> None:
    served = serve_from_packet(
        CARD,
        packet(),
        {"episode_context_id": episode_of(), "clock": "at_time", "candidate_id": "teb+dwa"},
    )
    assert served == FactRefusal("timeline_not_recorded")


# --------------------------------------------------------------------------
# The lane
# --------------------------------------------------------------------------


def test_the_real_host_serves_the_timeline() -> None:
    prepared = round_for("dwa-001")
    declare(
        prepared,
        "local_minimum_entrapment",
        "local_controller",
        supports=("obs:stuck_cluster:astar+dwa",),
    )
    result = prepared.host.call(
        ask(
            prepared,
            "get_episode_timeline",
            {
                "episode_context_id": episode_of(),
                "clock": "at_progress",
                "candidate_id": "astar+dwa",
            },
        )
    )
    assert result.execution_status == "completed"
    assert result.measurements["n_points"] == 3.0


def test_the_seam_withholds_the_block_when_the_packet_has_none() -> None:
    assert (
        "episode_timeline"
        not in evidence_for(without_timelines(packet()), sidecar_present=True).available_evidence
    )
    assert "episode_timeline" in evidence_for(packet(), sidecar_present=True).available_evidence


def test_a_packet_with_no_timelines_is_refused_at_admission() -> None:
    prepared = in_process_round(
        without_timelines(packet()),
        bundle(),
        catalog=TOOL_CATALOG,
        analysis_run_id="analysis-no-timeline",
        sidecar_directories=sidecars("dwa-001"),
    )
    declare(
        prepared,
        "local_minimum_entrapment",
        "local_controller",
        supports=("obs:stuck_cluster:astar+dwa",),
    )
    with pytest.raises(ProtocolRejection) as caught:
        prepared.host.call(
            ask(
                prepared,
                "get_episode_timeline",
                {"episode_context_id": episode_of(), "clock": "at_time"},
            )
        )
    assert caught.value.code == "missing_required_evidence"


def test_a_run_without_the_sidecar_can_still_read_its_own_timelines() -> None:
    """The old rule asked for ``trace``, which the pre-sidecar set does
    not hold — so a packet carrying the block was answered "unavailable"
    on exactly the runs that most needed reading."""
    source = evidence_for(packet(), sidecar_present=False)
    assert "episode_timeline" in source.available_evidence
