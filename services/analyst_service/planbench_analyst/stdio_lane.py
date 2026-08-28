"""The container side of the wire: two adapters and a loop.

The runner does not change. It holds a
:class:`~planbench_analyst.round_host.RoundHostProtocol` (two verbs) and
an :class:`~planbench_agent.provider.LLMProvider` (one verb), and this
module supplies both over frames instead of over function calls. That is
the whole point of the seam: the in-process lane and the container lane
run the same loop, so a bug in the loop cannot be a bug in only one of
them.

**Everything the container needs arrives as a frame, and nothing else
does.** No credential, no database, no filesystem it may write to. When
it wants a completion it asks; when it wants a check it asks; the
platform decides both.

**stdout is protocol.** Every log line goes to stderr, which the
platform keeps as a restricted artifact. A ``print`` in this process is
a corrupted stream and ends the round — see
:mod:`planbench_analyst.stdio_protocol`.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import TextIO

from planbench_agent.provider import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
    ProviderError,
    StopReason,
)
from planbench_analyst.model_gateway import provider_turn_payload, turn_from_payload
from planbench_analyst.stdio_protocol import Frame, ProtocolViolation, decode, encode
from planbench_explanation.protocol import AnalysisResponse, ToolRequest, ToolResult

__all__ = ["FrameHost", "FrameProvider", "FrameStream", "run_from_frames"]


@dataclass
class FrameStream:
    """One numbered conversation over a pair of text streams."""

    analysis_run_id: str
    bundle_id: str
    outbound: TextIO
    inbound: TextIO
    sequence: int = 0
    log: TextIO | None = None

    def send(self, message_type: str, payload: dict, correlation_id: str = "") -> Frame:
        self.sequence += 1
        frame = Frame(
            message_type=message_type,
            analysis_run_id=self.analysis_run_id,
            bundle_id=self.bundle_id,
            sequence=self.sequence,
            payload=payload,
            correlation_id=correlation_id,
        )
        self.outbound.write(encode(frame) + "\n")
        self.outbound.flush()
        return frame

    def receive(self) -> Frame:
        """The next frame, or the end of the round.

        An EOF here is the platform having gone away, which is a round
        that ended rather than one that finished — reported as a
        violation so the caller cannot mistake it for a quiet answer.
        """
        line = self.inbound.readline()
        if not line:
            raise ProtocolViolation("stream_closed_early", "the platform closed the stream")
        frame = decode(line)
        self.sequence = max(self.sequence, frame.sequence)
        return frame

    def note(self, text: str) -> None:
        """A log line. **stderr only** — stdout is protocol."""
        if self.log is not None:
            self.log.write(text + "\n")
            self.log.flush()


@dataclass
class FrameProvider(LLMProvider):
    """A model the container can only reach by asking for it.

    The vendor's own assistant turn goes back out untouched on the next
    request: it is carried opaquely in both directions, because Gemini
    refuses a follow-up without its thought signature and Anthropic
    wants thinking blocks verbatim.
    """

    stream: FrameStream
    model_id: str = ""
    generation_parameters: dict = field(default_factory=dict)

    @property
    def name(self) -> str:
        return "gateway"

    @property
    def model(self) -> str:
        return self.model_id

    @property
    def deterministic(self) -> bool:
        """False, and stated rather than assumed: whatever the platform
        calls on the other side is a model, and a bundle does not make
        one deterministic."""
        return False

    def complete(self, request: LLMRequest) -> LLMResponse:
        sent = self.stream.send(
            "model_request",
            {
                "system": request.system,
                "messages": [
                    {
                        "role": str(message.role),
                        "text": message.text,
                        "provider_turn": provider_turn_payload(message.provider_turn),
                    }
                    for message in request.messages
                ],
                "output_schema": dict(request.output_schema) if request.output_schema else None,
                "max_tokens": request.max_tokens,
                "model_id": self.model_id,
                "generation_parameters": dict(self.generation_parameters),
            },
        )
        answered = self.stream.receive()
        if answered.message_type == "error":
            raise ProviderError(str(answered.payload.get("error", "the gateway refused")))
        if answered.message_type != "model_response":
            raise ProviderError(f"expected model_response, got {answered.message_type}")
        if answered.correlation_id and answered.correlation_id != str(sent.sequence):
            raise ProviderError("the gateway answered a different request")
        payload = answered.payload
        usage = payload.get("usage") or {}
        return LLMResponse(
            text=str(payload.get("text", "")),
            structured=payload.get("structured"),
            stop_reason=StopReason(payload.get("stop_reason", "end_turn")),
            model=str(payload.get("model", self.model_id)),
            input_tokens=int(usage.get("input_tokens", 0)),
            output_tokens=int(usage.get("output_tokens", 0)),
            provider_turn=turn_from_payload(payload.get("provider_turn")),
        )


@dataclass
class FrameHost:
    """A tool host the container can only reach by asking for it.

    Implements :class:`~planbench_analyst.round_host.RoundHostProtocol`
    exactly — ``declare`` and ``call`` — so the runner cannot tell this
    from the in-process host, which is what makes one loop serve both
    lanes.
    """

    stream: FrameStream

    def declare(self, response: AnalysisResponse) -> None:
        self.stream.send(
            "declare_proposals",
            {"response": response.model_dump(mode="json")},
        )
        acknowledged = self.stream.receive()
        if acknowledged.message_type != "declaration_ack":
            raise ProtocolViolation("wrong_phase", acknowledged.message_type)

    def call(self, request: ToolRequest) -> ToolResult:
        sent = self.stream.send("tool_request", {"request": request.model_dump(mode="json")})
        answered = self.stream.receive()
        if answered.message_type != "tool_result":
            raise ProtocolViolation("wrong_phase", answered.message_type)
        if answered.correlation_id and answered.correlation_id != str(sent.sequence):
            raise ProtocolViolation("wrong_phase", "a result for another request")
        return ToolResult.model_validate(answered.payload.get("result") or {})


def frames_from(stream: TextIO) -> Iterator[Frame]:
    """Every frame on a stream until it closes. For a platform-side reader."""
    for line in stream:
        if line.strip():
            yield decode(line)


def run_from_frames(stream: FrameStream) -> int:
    """One round, driven entirely by what the platform sends.

    The container derives nothing about its own permissions: the packet,
    the catalog version, the available evidence and the budget all
    arrive in the ``analysis_request`` frame, because each of them is a
    statement about what the platform will allow and a container that
    computed its own would be answering a question it was not asked.
    """
    from planbench_analyst.round_host import PreparedRound
    from planbench_analyst.runner import run_round
    from planbench_explanation.budget import AnalysisBudget
    from planbench_explanation.case_packet import CasePacket
    from planbench_explanation.catalog import TOOL_CATALOG
    from planbench_explanation.protocol import AnalysisRequest

    hello = stream.receive()
    if hello.message_type != "hello":
        raise ProtocolViolation("wrong_phase", hello.message_type)
    stream.analysis_run_id = hello.analysis_run_id
    stream.bundle_id = hello.bundle_id
    stream.note(f"round {hello.analysis_run_id} opened")

    opening = stream.receive()
    if opening.message_type != "analysis_request":
        raise ProtocolViolation("wrong_phase", opening.message_type)
    payload = opening.payload
    budget = AnalysisBudget.model_validate(payload["effective_budget"])
    analysis = AnalysisRequest(
        analysis_run_id=hello.analysis_run_id,
        analyst_bundle_id=hello.bundle_id,
        packet=CasePacket.model_validate(payload["packet"]),
        catalog=TOOL_CATALOG,
        available_evidence=frozenset(payload.get("available_evidence") or ()),
        max_tool_requests=budget.max_tool_requests,
    )
    prepared = PreparedRound(
        analysis=analysis,
        host=FrameHost(stream),
        effective_budget=budget,
        requested_budget_checksum=str(payload.get("requested_budget_checksum", "")),
        effective_budget_checksum=budget.checksum,
        evidence_identity_checksum=str(payload.get("evidence_identity_checksum", "")),
    )
    provider = FrameProvider(
        stream=stream,
        model_id=str(payload.get("model_id", "")),
        generation_parameters=dict(payload.get("generation_parameters") or {}),
    )

    outcome = run_round(prepared, provider)
    stream.note(f"round ended: {outcome.stopped_because}")
    stream.send(
        "final_response",
        {
            "response": outcome.response.model_dump(mode="json"),
            "stopped_because": outcome.stopped_because,
            "cost": {
                "model_calls": outcome.cost.model_calls,
                "input_tokens": outcome.cost.input_tokens,
                "output_tokens": outcome.cost.output_tokens,
                "tool_requests": outcome.cost.tool_requests,
            },
        },
    )
    stream.send("done", {})
    return 0


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - process entry
    """The container's entry point: wire the adapters to the real streams.

    Thin on purpose. Everything about *analysis* lives in the modules
    the in-process lane also goes through, so a container cannot behave
    differently by holding its own copy of the logic.
    """
    stream = FrameStream(
        analysis_run_id="",
        bundle_id="",
        outbound=sys.stdout,
        inbound=sys.stdin,
        log=sys.stderr,
    )
    try:
        return run_from_frames(stream)
    except ProtocolViolation as violation:
        stream.note(f"protocol violation: {violation.code}")
        stream.send("error", {"error": violation.code})
        return 2


if __name__ == "__main__":  # pragma: no cover - process entry
    raise SystemExit(main())
