"""The wire between the platform and an analyst it does not trust.

One JSON object per line on stdout, one per line on stdin. That is the
whole transport, and it is deliberately the dullest part of the design:
the interesting decisions are about what the platform refuses.

**stdout carries protocol and nothing else.** A container that prints a
warning to stdout has corrupted the stream, and the honest reading of a
corrupted stream is "this round is over" — not "skip the line and hope".
Logs go to stderr, which is a restricted artifact (see
:mod:`planbench_analyst.restricted`), never a channel.

**Every frame is capped, per type.** The cap comes from the round's
effective budget rather than from a constant here, because the frame
that legitimately carries a megabyte — a vendor's assistant turn coming
back through the gateway — is exactly the frame an exfiltration would
choose. One cap for all frames is either too small for that one or too
generous for the rest, and "too generous for the rest" is the shape a
hidden packet leaves through.

**Sequence is strictly increasing and phase is a machine.** A duplicate
sequence number is a replay; a frame in the wrong phase is a request for
evidence about a hypothesis nobody declared. Both are refused with a
closed code, because an error message that quotes the offending payload
is an error message that exfiltrates it.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from planbench_explanation.budget import FRAME_TYPES, AnalysisBudget
from planbench_explanation.protocol import ANALYST_RUNNER_PROTOCOL_VERSION

__all__ = [
    "Frame",
    "FrameSession",
    "ProtocolViolation",
    "ViolationCode",
    "decode",
    "encode",
    "safe_detail",
]

#: Every way a frame can be refused. Closed, and closed for the reason
#: the rejection codes in the tool protocol are: a harness counts
#: refusals by kind, and prose cannot be counted.
ViolationCode = Literal[
    "not_json",
    "unknown_frame",
    "protocol_version_mismatch",
    "frame_too_large",
    "sequence_out_of_order",
    "duplicate_sequence",
    "wrong_phase",
    "identity_mismatch",
    "stream_closed_early",
]


class ProtocolViolation(RuntimeError):
    """A frame the platform will not process, with a code and no payload.

    The payload is **not** in the message on purpose. An error that
    quotes what it refused is a channel: refuse a frame carrying a
    hidden packet, log the refusal with the frame in it, and the packet
    is now in a log somebody less careful will read.
    """

    def __init__(self, code: ViolationCode, detail: str = "") -> None:
        self.code: ViolationCode = code
        super().__init__(f"{code}: {detail}" if detail else code)


@dataclass(frozen=True)
class Frame:
    """One line on the wire."""

    message_type: str
    analysis_run_id: str
    bundle_id: str
    sequence: int
    payload: Mapping[str, Any] = field(default_factory=dict)
    #: Ties a response to the request it answers. Required on the four
    #: paired frames; a pairing carried by position instead would break
    #: the moment anything is ever answered out of order.
    correlation_id: str = ""
    protocol_version: str = ANALYST_RUNNER_PROTOCOL_VERSION


def encode(frame: Frame) -> str:
    """One frame, one line. Sorted keys so a transcript diffs cleanly."""
    return json.dumps(
        {
            "protocol_version": frame.protocol_version,
            "message_type": frame.message_type,
            "analysis_run_id": frame.analysis_run_id,
            "bundle_id": frame.bundle_id,
            "sequence": frame.sequence,
            "correlation_id": frame.correlation_id,
            "payload": dict(frame.payload),
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


#: Characters a detail string may carry, and how much of one. Every
#: other byte the container sent is dropped rather than quoted.
_SAFE_DETAIL = re.compile(r"[^A-Za-z0-9._:-]")


def safe_detail(value: str, *, limit: int = 32) -> str:
    """A version string or frame name, reduced to something quotable.

    Found by a tooth that would not bite: ``decode`` used to put the
    container's own ``message_type`` into the refusal verbatim, so a
    container could name a frame after a hidden packet and read it back
    out of the platform's log. The raw line belongs in the restricted
    transcript, which nobody outside the platform receives; what travels
    with an error is this.
    """
    reduced = _SAFE_DETAIL.sub("", value)[:limit]
    return reduced or "<unprintable>"


def decode(line: str) -> Frame:
    """Parse one line, or refuse it by code."""
    try:
        parsed = json.loads(line)
    except json.JSONDecodeError as broken:
        raise ProtocolViolation("not_json", "stdout carries protocol only") from broken
    if not isinstance(parsed, Mapping):
        raise ProtocolViolation("not_json", "a frame is an object")
    message_type = parsed.get("message_type")
    if not isinstance(message_type, str) or message_type not in FRAME_TYPES:
        raise ProtocolViolation("unknown_frame", safe_detail(str(message_type)))
    try:
        return Frame(
            message_type=message_type,
            analysis_run_id=str(parsed["analysis_run_id"]),
            bundle_id=str(parsed["bundle_id"]),
            sequence=int(parsed["sequence"]),
            payload=parsed.get("payload") or {},
            correlation_id=str(parsed.get("correlation_id", "")),
            protocol_version=str(parsed.get("protocol_version", "")),
        )
    except (KeyError, TypeError, ValueError) as missing:
        raise ProtocolViolation("unknown_frame", "envelope incomplete") from missing


#: What may follow what. ``error`` and ``done`` are reachable from
#: everywhere: a round that has gone wrong must always be able to say so
#: and stop, and a state machine that can trap a failing round in a
#: phase is a state machine that hangs.
_ALLOWED_AFTER: dict[str, frozenset[str]] = {
    "": frozenset({"hello"}),
    "hello": frozenset({"analysis_request"}),
    "analysis_request": frozenset({"declare_proposals", "model_request"}),
    "declare_proposals": frozenset({"declaration_ack"}),
    "declaration_ack": frozenset(
        {"tool_request", "model_request", "declare_proposals", "final_response"}
    ),
    "model_request": frozenset({"model_response"}),
    "model_response": frozenset(
        {"declare_proposals", "model_request", "tool_request", "final_response"}
    ),
    "tool_request": frozenset({"tool_result"}),
    "tool_result": frozenset(
        {"tool_request", "model_request", "declare_proposals", "final_response"}
    ),
    "final_response": frozenset({"done"}),
    "done": frozenset(),
    "error": frozenset({"done"}),
}


@dataclass
class FrameSession:
    """One round's stream, and everything it refuses.

    Stateful for the same reason :class:`~planbench_explanation.protocol.ToolSession`
    is: "may this frame arrive now" is a question about what has already
    arrived, and a stateless check cannot see it.
    """

    analysis_run_id: str
    bundle_id: str
    budget: AnalysisBudget
    last_sequence: int = 0
    phase: str = ""
    closed: bool = False
    seen_sequences: set[int] = field(default_factory=set)

    def admit(self, line: str) -> Frame:
        """Accept one line, or raise with a code and no payload."""
        raw = line.encode("utf-8")
        frame = decode(line)
        cap = self.budget.max_frame_bytes[frame.message_type]
        if len(raw) > cap:
            raise ProtocolViolation(
                "frame_too_large", f"{frame.message_type} is capped at {cap} bytes"
            )
        if frame.protocol_version != ANALYST_RUNNER_PROTOCOL_VERSION:
            raise ProtocolViolation(
                "protocol_version_mismatch", safe_detail(frame.protocol_version)
            )
        if (frame.analysis_run_id, frame.bundle_id) != (self.analysis_run_id, self.bundle_id):
            raise ProtocolViolation("identity_mismatch", frame.message_type)
        if frame.sequence in self.seen_sequences:
            raise ProtocolViolation("duplicate_sequence", str(frame.sequence))
        if frame.sequence != self.last_sequence + 1:
            raise ProtocolViolation("sequence_out_of_order", str(frame.sequence))
        # ``error`` is reachable from every phase, and ``done`` from an
        # error: a round that has gone wrong must always be able to say
        # so and stop. A state machine that can trap a failing round in
        # a phase is a state machine that hangs, which is the failure
        # this whole layer exists to make impossible.
        always = frame.message_type == "error" and not self.closed
        if not always and frame.message_type not in _ALLOWED_AFTER.get(self.phase, frozenset()):
            raise ProtocolViolation(
                "wrong_phase", f"{frame.message_type} after {self.phase or 'nothing'}"
            )

        self.seen_sequences.add(frame.sequence)
        self.last_sequence = frame.sequence
        self.phase = frame.message_type
        if frame.message_type == "done":
            self.closed = True
        return frame

    def next_frame(self, message_type: str, payload: Mapping[str, Any], **extra: str) -> Frame:
        """A frame from the platform's side, numbered in the same stream."""
        self.last_sequence += 1
        self.seen_sequences.add(self.last_sequence)
        self.phase = message_type
        return Frame(
            message_type=message_type,
            analysis_run_id=self.analysis_run_id,
            bundle_id=self.bundle_id,
            sequence=self.last_sequence,
            payload=payload,
            correlation_id=extra.get("correlation_id", ""),
        )

    def closed_early(self) -> ProtocolViolation:
        """What an EOF before ``done`` is: a round that ended, not a round
        that finished. Scored as the analyst raising."""
        return ProtocolViolation(
            "stream_closed_early", f"stream ended in phase {self.phase or 'nothing'}"
        )
