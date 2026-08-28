"""A4 — the two contract objects a graded round is measured against.

The budget decides what a round may spend and the artifact decides
whether a packet on disk is evidence. Both exist because the party being
graded must not be able to answer either question itself: a bundle that
chose its own ceiling was calibrated as a system that does not exist,
and a fixture that carried its own checksum could be edited after the
fact to make an analyst look right.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from test_analyst_packet_view import observation, packet

from planbench_explanation.budget import (
    FRAME_TYPES,
    PLATFORM_BUDGET_CAP,
    AnalysisBudget,
    BudgetRefusal,
)
from planbench_explanation.catalog import TOOL_CATALOG
from planbench_explanation.packet_artifact import (
    PacketArtifactRefusal,
    PacketProvenance,
    load_packet_artifact,
    packet_checksum,
)
from planbench_explanation.protocol import AnalysisRequest


def budget(**overrides):  # type: ignore[no-untyped-def]
    fields = {
        "max_tool_requests": 8,
        "max_model_calls": 3,
        "max_input_tokens": 50_000,
        "max_output_tokens": 20_000,
        "max_wall_time_ms": 60_000,
        "max_frame_bytes": dict.fromkeys(FRAME_TYPES, 4_096),
    }
    fields.update(overrides)
    return AnalysisBudget(**fields)  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# The budget
# --------------------------------------------------------------------------


def test_a_frame_nobody_capped_is_refused() -> None:
    """An uncapped frame is the shape a hidden packet leaves through."""
    caps = dict.fromkeys(FRAME_TYPES, 4_096)
    del caps["model_response"]
    with pytest.raises((BudgetRefusal, ValidationError), match="model_response"):
        budget(max_frame_bytes=caps)


def test_a_cap_on_a_frame_that_does_not_exist_is_refused() -> None:
    with pytest.raises((BudgetRefusal, ValidationError), match="not on the protocol"):
        budget(max_frame_bytes={**dict.fromkeys(FRAME_TYPES, 4_096), "sneak": 1})


def test_the_effective_budget_is_the_field_wise_minimum() -> None:
    asked = budget(max_tool_requests=1024, max_model_calls=1)
    effective = asked.capped_by(PLATFORM_BUDGET_CAP)
    assert effective.max_tool_requests == PLATFORM_BUDGET_CAP.max_tool_requests
    # Asking for less than the cap is honoured: a bundle calibrated with
    # one model call must not quietly get twelve at the gate.
    assert effective.max_model_calls == 1


def test_a_bundle_cannot_raise_the_ceiling_on_any_axis() -> None:
    greedy = budget(
        max_tool_requests=1024,
        max_model_calls=64,
        max_input_tokens=10_000_000,
        max_output_tokens=10_000_000,
        max_wall_time_ms=10 * 60 * 60 * 1000,
        max_frame_bytes=dict.fromkeys(FRAME_TYPES, 100_000_000),
    )
    effective = greedy.capped_by(PLATFORM_BUDGET_CAP)
    assert effective == PLATFORM_BUDGET_CAP


def test_the_checksum_moves_when_any_axis_moves() -> None:
    assert budget().checksum != budget(max_model_calls=4).checksum
    assert budget().checksum == budget().checksum


def test_the_model_response_frame_is_the_generous_one() -> None:
    """It carries the vendor's own assistant turn, which the container
    must hand back untouched; everything the container writes itself is
    capped an order of magnitude tighter."""
    caps = PLATFORM_BUDGET_CAP.max_frame_bytes
    assert caps["model_response"] > caps["tool_request"] * 8


# --------------------------------------------------------------------------
# The packet artifact
# --------------------------------------------------------------------------


def write_case(root: Path, case_id: str, *, edit_packet: bool = False, **provenance_overrides):  # type: ignore[no-untyped-def]
    built = packet(observations=[observation()])
    folder = root / case_id
    folder.mkdir(parents=True, exist_ok=True)
    fields = {
        "packet_ref": f"fixtures/golden/visible/{case_id}/packet.json",
        "packet_checksum": packet_checksum(built),
        "run_id": built.run_id,
        "recorded_at": "2026-08-26T09:00:00Z",
        "sidecar_present": True,
        "source": "planted_run",
    }
    fields.update(provenance_overrides)
    provenance = PacketProvenance(**fields)  # type: ignore[arg-type]
    payload = built.model_dump(mode="json")
    if edit_packet:
        payload["run_id"] = "run_edited_after_the_fact"
    (folder / "packet.json").write_text(json.dumps(payload), encoding="utf-8")
    (folder / "provenance.json").write_text(
        json.dumps(
            {**provenance.model_dump(mode="json"), "provenance_checksum": provenance.checksum}
        ),
        encoding="utf-8",
    )
    return folder


def test_a_case_loads_and_carries_its_kind(tmp_path: Path) -> None:
    write_case(tmp_path, "inflation-001")
    artifact = load_packet_artifact(tmp_path, "inflation-001")
    assert artifact.fixture_kind == "recorded"
    assert artifact.packet_checksum == packet_checksum(artifact.packet)


def test_the_checksum_is_recomputed_rather_than_read(tmp_path: Path) -> None:
    """A fixture edited after its provenance was written is the one case
    a stored checksum exists to catch."""
    write_case(tmp_path, "inflation-001", edit_packet=True)
    with pytest.raises((PacketArtifactRefusal, ValidationError), match="hashes to"):
        load_packet_artifact(tmp_path, "inflation-001")


def test_a_provenance_whose_own_checksum_does_not_match_is_refused(tmp_path: Path) -> None:
    folder = write_case(tmp_path, "inflation-001")
    payload = json.loads((folder / "provenance.json").read_text(encoding="utf-8"))
    payload["run_id"] = "run_someone_else"
    (folder / "provenance.json").write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(PacketArtifactRefusal, match="fields hash to"):
        load_packet_artifact(tmp_path, "inflation-001")


def test_a_provenance_pointing_at_another_case_is_refused(tmp_path: Path) -> None:
    write_case(
        tmp_path,
        "inflation-001",
        packet_ref="fixtures/golden/visible/rrt-001/packet.json",
    )
    with pytest.raises(PacketArtifactRefusal, match="another case"):
        load_packet_artifact(tmp_path, "inflation-001")


def test_a_missing_file_names_itself(tmp_path: Path) -> None:
    (tmp_path / "inflation-001").mkdir(parents=True)
    with pytest.raises(PacketArtifactRefusal, match="provenance.json|packet.json"):
        load_packet_artifact(tmp_path, "inflation-001")


def test_a_run_without_the_sidecar_is_synthetic_however_it_is_labelled(tmp_path: Path) -> None:
    """A packet built from a run that predates the writer carries
    reconstructed planning inputs, and a threshold agreed against those
    bakes the reconstruction's errors into the bar."""
    write_case(tmp_path, "inflation-001", sidecar_present=False)
    assert load_packet_artifact(tmp_path, "inflation-001").fixture_kind == "synthetic"


def test_a_hand_written_fixture_says_so(tmp_path: Path) -> None:
    write_case(tmp_path, "inflation-001", source="hand_written")
    assert load_packet_artifact(tmp_path, "inflation-001").fixture_kind == "synthetic"


def test_the_loader_and_the_protocol_agree_on_what_a_packet_hashes_to(tmp_path: Path) -> None:
    """Two recipes for one checksum disagree the first time one of them
    sorts keys differently, and the disagreement surfaces as a tool
    request rejected for naming the wrong packet."""
    write_case(tmp_path, "inflation-001")
    artifact = load_packet_artifact(tmp_path, "inflation-001")
    request = AnalysisRequest(
        analysis_run_id="analysis-a4",
        analyst_bundle_id="bundle-a4",
        packet=artifact.packet,
        catalog=TOOL_CATALOG,
    )
    assert request.case_packet_checksum == artifact.packet_checksum
