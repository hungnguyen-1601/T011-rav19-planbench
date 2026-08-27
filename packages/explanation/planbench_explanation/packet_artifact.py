"""A packet on disk, and the question "where did this come from".

``VISIBLE_SUITE`` points every case at
``fixtures/golden/visible/<case_id>/packet.json``. A file at that path
is not yet evidence: it is a file. What makes it evidence is that the
platform can say, without trusting whoever wrote it, that the bytes are
the packet they claim to be and that the run behind them was recorded
rather than assembled.

So the loader **recomputes** both checksums instead of reading them.
A checksum a caller supplies is a checksum a caller can supply for
anything, and the one case that matters — a fixture edited after the
fact to make an analyst look right — is exactly the case a stored value
cannot catch.

**``fixture_kind`` is derived, never declared.** It says whether the
packet came out of a run with the planning-input sidecar attached
(``recorded``) or was written by hand to exercise a shape
(``synthetic``). The hidden gate accepts only ``recorded``, and a field
the submitter fills in would make that rule a request rather than a
check.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from planbench_explanation.case_packet import CasePacket
from planbench_explanation.versioning import CHECKSUM_PATTERN, artifact_checksum

__all__ = [
    "PACKET_FILENAME",
    "PROVENANCE_FILENAME",
    "FixtureKind",
    "PacketArtifact",
    "PacketArtifactRefusal",
    "PacketProvenance",
    "load_packet_artifact",
    "packet_checksum",
]


class PacketArtifactRefusal(ValueError):
    """The files on disk are not the packet they claim to be."""


PACKET_FILENAME = "packet.json"
PROVENANCE_FILENAME = "provenance.json"

#: ``recorded`` — built from a run whose planning inputs were written as
#: they happened. ``synthetic`` — written to exercise a shape, and
#: useful for that and for nothing a threshold is agreed against.
FixtureKind = Literal["recorded", "synthetic"]


def packet_checksum(packet: CasePacket) -> str:
    """The one recipe, shared with :attr:`AnalysisRequest.case_packet_checksum`.

    Two recipes for "the checksum of this packet" would disagree the
    first time one of them started sorting keys differently, and the
    disagreement would surface as a tool request rejected for naming the
    wrong packet.
    """
    return artifact_checksum(packet.model_dump(mode="json"))


class PacketProvenance(BaseModel):
    """Where a packet fixture came from, in fields that can be checked."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    #: The path this provenance is about, as the suite names it.
    packet_ref: str = Field(min_length=1)
    #: What the writer says the packet hashes to. Recomputed on load;
    #: kept in the file so a mismatch names both values.
    packet_checksum: str = Field(pattern=CHECKSUM_PATTERN)
    run_id: str = Field(min_length=1)
    recorded_at: str = Field(min_length=1)
    #: Whether the run carried a
    #: :class:`~planbench_explanation.sidecar_writer.PlanningInputRecorder`.
    #: A packet built from a run that predates the writer carries
    #: *reconstructed* planning inputs, and a threshold agreed against
    #: those bakes the reconstruction's errors into the bar.
    sidecar_present: bool
    source: Literal["planted_run", "production_run", "hand_written"]

    @property
    def checksum(self) -> str:
        return artifact_checksum(self.model_dump(mode="json"))

    @property
    def fixture_kind(self) -> FixtureKind:
        """Derived from what the provenance says, not from a field."""
        if self.source == "hand_written" or not self.sidecar_present:
            return "synthetic"
        return "recorded"


class PacketArtifact(BaseModel):
    """One case's packet, its provenance, and the checks that passed."""

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    case_id: str = Field(min_length=1)
    packet: CasePacket
    provenance: PacketProvenance

    @model_validator(mode="after")
    def _check(self) -> PacketArtifact:
        recomputed = packet_checksum(self.packet)
        if recomputed != self.provenance.packet_checksum:
            raise PacketArtifactRefusal(
                f"{self.case_id}: the provenance names packet checksum "
                f"{self.provenance.packet_checksum} and the packet hashes to "
                f"{recomputed}. A fixture edited after its provenance was written "
                "is the one case a stored checksum exists to catch."
            )
        return self

    @property
    def fixture_kind(self) -> FixtureKind:
        return self.provenance.fixture_kind

    @property
    def packet_checksum(self) -> str:
        return self.provenance.packet_checksum


def load_packet_artifact(root: Path, case_id: str) -> PacketArtifact:
    """Read one case from ``<root>/<case_id>/``, or refuse to.

    ``root`` is the suite's fixture root — ``fixtures/golden/visible``
    for the calibration set. Everything the caller could have got wrong
    is checked here rather than trusted: missing files, unreadable JSON,
    a provenance whose stored checksum does not match its own bytes, a
    provenance pointing at another packet's path.
    """
    folder = root / case_id
    packet_path = folder / PACKET_FILENAME
    provenance_path = folder / PROVENANCE_FILENAME
    for path in (packet_path, provenance_path):
        if not path.is_file():
            raise PacketArtifactRefusal(
                f"{case_id}: {path.as_posix()} is missing; a suite that names a case "
                "it cannot load has cases nobody is graded on"
            )

    try:
        packet_payload = json.loads(packet_path.read_text(encoding="utf-8"))
        provenance_payload = json.loads(provenance_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as broken:
        raise PacketArtifactRefusal(f"{case_id}: {broken}") from broken

    stored_checksum = provenance_payload.pop("provenance_checksum", None)
    provenance = PacketProvenance.model_validate(provenance_payload)
    if stored_checksum is not None and stored_checksum != provenance.checksum:
        raise PacketArtifactRefusal(
            f"{case_id}: the provenance file carries checksum {stored_checksum} and "
            f"its own fields hash to {provenance.checksum}"
        )
    if not provenance.packet_ref.endswith(f"{case_id}/{PACKET_FILENAME}"):
        raise PacketArtifactRefusal(
            f"{case_id}: provenance points at {provenance.packet_ref!r}, which is "
            "another case's packet"
        )
    return PacketArtifact(
        case_id=case_id,
        packet=CasePacket.model_validate(packet_payload),
        provenance=provenance,
    )
