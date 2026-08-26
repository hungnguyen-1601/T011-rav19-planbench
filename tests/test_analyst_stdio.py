"""A4-iv — the wire, the gateway that holds the key, and what stays back.

Everything here is about a boundary the platform does not trust. The
frames are checked because a container can send anything; the gateway
exists because the container must never hold a credential; the
restricted artifacts exist because stderr is a place a whole hidden
packet fits.
"""

from __future__ import annotations

import json

import pytest

from planbench_agent.provider import LLMResponse, MockProvider, ProviderTurn
from planbench_analyst.model_gateway import (
    GatewayRefusal,
    ModelGateway,
    provider_turn_payload,
    turn_from_payload,
)
from planbench_analyst.restricted import (
    MAX_RESTRICTED_BYTES,
    PUBLIC_ERROR_CODES,
    RestrictedArtifact,
    case_token,
    public_error,
)
from planbench_analyst.stdio_protocol import (
    Frame,
    FrameSession,
    ProtocolViolation,
    decode,
    encode,
)
from planbench_explanation.budget import FRAME_TYPES, PLATFORM_BUDGET_CAP
from planbench_explanation.bundle import AnalystBundle
from planbench_explanation.catalog import TOOL_CATALOG_VERSION
from planbench_explanation.protocol import ANALYST_RUNNER_PROTOCOL_VERSION

RUN = "analysis-a4"
BUNDLE = "bundle-a4"


def bundle(**overrides):  # type: ignore[no-untyped-def]
    fields = {
        "bundle_id": BUNDLE,
        "agent_code_digest": "git:" + "a" * 40,
        "container_digest": "sha256:" + "b" * 64,
        "model_id": "claude-opus-5",
        "model_revision": "2026-05-01",
        "prompt_checksum": "c" * 64,
        "rag_index_version": "kb-index-3",
        "retrieval_config_checksum": "d" * 64,
        "tool_catalog_version": TOOL_CATALOG_VERSION,
        "generation_parameters": {"temperature": 0.0},
        "runner_protocol_version": ANALYST_RUNNER_PROTOCOL_VERSION,
        "requested_budget": PLATFORM_BUDGET_CAP,
        "created_at": "2026-08-26T09:30:00Z",
    }
    fields.update(overrides)
    return AnalystBundle(**fields)  # type: ignore[arg-type]


def session(**overrides):  # type: ignore[no-untyped-def]
    fields = {
        "analysis_run_id": RUN,
        "bundle_id": BUNDLE,
        "budget": PLATFORM_BUDGET_CAP,
    }
    fields.update(overrides)
    return FrameSession(**fields)  # type: ignore[arg-type]


def line(message_type: str, sequence: int, **overrides):  # type: ignore[no-untyped-def]
    fields = {
        "message_type": message_type,
        "analysis_run_id": RUN,
        "bundle_id": BUNDLE,
        "sequence": sequence,
    }
    fields.update(overrides)
    return encode(Frame(**fields))  # type: ignore[arg-type]


def walk(stream, *frames):  # type: ignore[no-untyped-def]
    for index, message_type in enumerate(frames, start=1):
        stream.admit(line(message_type, index))
    return stream


# --------------------------------------------------------------------------
# The line format
# --------------------------------------------------------------------------


def test_a_frame_survives_the_round_trip() -> None:
    frame = Frame(
        message_type="tool_request",
        analysis_run_id=RUN,
        bundle_id=BUNDLE,
        sequence=4,
        payload={"tool_id": "gap_vs_footprint"},
        correlation_id="req-004",
    )
    assert decode(encode(frame)) == frame


def test_stdout_carries_protocol_and_nothing_else() -> None:
    """A container that prints a warning to stdout has corrupted the
    stream, and the honest reading of a corrupted stream is that the
    round is over."""
    with pytest.raises(ProtocolViolation) as raised:
        decode("Warning: falling back to CPU")
    assert raised.value.code == "not_json"


def test_a_frame_nobody_wrote_a_name_for_is_refused() -> None:
    with pytest.raises(ProtocolViolation) as raised:
        decode(json.dumps({"message_type": "exfiltrate", "sequence": 1}))
    assert raised.value.code == "unknown_frame"


def test_the_refusal_does_not_quote_what_it_refused() -> None:
    """An error that quotes its input is a channel: refuse a frame
    carrying a hidden packet, log the refusal with the frame in it, and
    the packet is in a log somebody less careful will read."""
    secret = "narrow-gap-007 packet contents"
    with pytest.raises(ProtocolViolation) as raised:
        decode(json.dumps({"message_type": secret, "sequence": 1}))
    assert secret not in str(raised.value)
    assert raised.value.code == "unknown_frame"


def test_a_version_string_cannot_carry_a_packet_out_either() -> None:
    """Same channel, second field. A tooth found the first one.

    The rule is not "no character survives" — a version somebody has to
    debug is worth printing. It is that the detail is **bounded**, so a
    payload cannot ride out inside it however long the container makes
    it."""
    stream = session()
    smuggled = "0.0.0-" + "A" * 500 + "-tail-of-the-packet"
    with pytest.raises(ProtocolViolation) as raised:
        stream.admit(line("hello", 1, protocol_version=smuggled))
    assert "tail-of-the-packet" not in str(raised.value)
    assert len(str(raised.value)) < 80


# --------------------------------------------------------------------------
# The session: size, sequence, phase
# --------------------------------------------------------------------------


def test_a_hello_opens_the_round() -> None:
    stream = session()
    frame = stream.admit(line("hello", 1))
    assert frame.message_type == "hello"
    assert stream.phase == "hello"


def test_every_frame_type_has_a_cap_and_the_cap_is_enforced() -> None:
    tight = PLATFORM_BUDGET_CAP.model_copy(
        update={"max_frame_bytes": dict.fromkeys(FRAME_TYPES, 64)}
    )
    stream = session(budget=tight)
    with pytest.raises(ProtocolViolation) as raised:
        stream.admit(line("hello", 1, payload={"note": "x" * 200}))
    assert raised.value.code == "frame_too_large"


def test_the_generous_cap_belongs_to_the_frame_that_needs_it() -> None:
    """One cap for every frame is either too small for the vendor turn
    coming back or too generous for everything else, and too generous
    for everything else is the shape a packet leaves through."""
    caps = PLATFORM_BUDGET_CAP.max_frame_bytes
    assert caps["model_response"] > caps["tool_request"]


def test_a_replayed_sequence_number_is_refused() -> None:
    stream = walk(session(), "hello")
    with pytest.raises(ProtocolViolation) as raised:
        stream.admit(line("analysis_request", 1))
    assert raised.value.code == "duplicate_sequence"


def test_a_gap_in_the_sequence_is_refused() -> None:
    stream = walk(session(), "hello")
    with pytest.raises(ProtocolViolation) as raised:
        stream.admit(line("analysis_request", 7))
    assert raised.value.code == "sequence_out_of_order"


def test_a_frame_from_another_round_is_refused() -> None:
    stream = session()
    with pytest.raises(ProtocolViolation) as raised:
        stream.admit(line("hello", 1, analysis_run_id="analysis-somebody-else"))
    assert raised.value.code == "identity_mismatch"


def test_a_container_built_against_another_protocol_is_refused() -> None:
    stream = session()
    with pytest.raises(ProtocolViolation) as raised:
        stream.admit(line("hello", 1, protocol_version="0.9.0"))
    assert raised.value.code == "protocol_version_mismatch"


def test_a_tool_request_before_anything_was_declared_is_refused() -> None:
    """It is a request for evidence about a hypothesis nobody declared."""
    stream = walk(session(), "hello", "analysis_request")
    with pytest.raises(ProtocolViolation) as raised:
        stream.admit(line("tool_request", 3))
    assert raised.value.code == "wrong_phase"


def test_the_ordinary_round_walks_the_whole_machine() -> None:
    stream = walk(
        session(),
        "hello",
        "analysis_request",
        "declare_proposals",
        "declaration_ack",
        "tool_request",
        "tool_result",
        "model_request",
        "model_response",
        "final_response",
        "done",
    )
    assert stream.closed


def test_a_round_may_always_say_it_went_wrong() -> None:
    """A state machine that can trap a failing round in a phase is a
    state machine that hangs."""
    stream = walk(session(), "hello", "analysis_request", "declare_proposals")
    stream.admit(line("error", 4))
    stream.admit(line("done", 5))
    assert stream.closed


def test_an_eof_before_done_is_a_round_that_ended_not_one_that_finished() -> None:
    stream = walk(session(), "hello", "analysis_request")
    assert stream.closed_early().code == "stream_closed_early"
    assert not stream.closed


# --------------------------------------------------------------------------
# The gateway
# --------------------------------------------------------------------------


def gateway(provider=None, budget=PLATFORM_BUDGET_CAP, **overrides):  # type: ignore[no-untyped-def]
    return ModelGateway(
        bundle=overrides.get("bundle", bundle()),
        provider=provider
        or MockProvider(script=[LLMResponse(text="ok", input_tokens=10, output_tokens=5)]),
        budget=budget,
    )


def request_payload(**overrides):  # type: ignore[no-untyped-def]
    fields = {
        "system": "you are proposing mechanisms",
        "messages": [{"role": "user", "text": "the packet"}],
        "model_id": "claude-opus-5",
        "generation_parameters": {"temperature": 0.0},
    }
    fields.update(overrides)
    return fields


def test_a_completion_comes_back_with_its_usage() -> None:
    served = gateway().complete(request_payload())
    assert served["text"] == "ok"
    assert served["usage"] == {"input_tokens": 10, "output_tokens": 5}


def test_the_container_never_holds_a_credential() -> None:
    """It receives frames, and no frame has a field for a key."""
    served = gateway().complete(request_payload())
    assert "api_key" not in served
    assert gateway().credential_visible_to_container is False


def test_a_model_swapped_mid_round_is_refused() -> None:
    with pytest.raises(GatewayRefusal, match="graded"):
        gateway().complete(request_payload(model_id="some-cheaper-model"))


def test_a_temperature_the_bundle_did_not_freeze_is_refused() -> None:
    """The same prompt at another temperature is another system."""
    with pytest.raises(GatewayRefusal, match="another system"):
        gateway().complete(request_payload(generation_parameters={"temperature": 1.0}))


def test_the_call_budget_stops_the_round_before_the_call() -> None:
    tight = PLATFORM_BUDGET_CAP.model_copy(update={"max_model_calls": 1})
    served = gateway(
        provider=MockProvider(
            script=[LLMResponse(text="one", input_tokens=1, output_tokens=1) for _ in range(2)]
        ),
        budget=tight,
    )
    served.complete(request_payload())
    with pytest.raises(GatewayRefusal, match="model call budget"):
        served.complete(request_payload())


def test_usage_that_overshoots_is_caught_after_the_call_and_held_back() -> None:
    """The estimate decides whether to dispatch; the invoice decides what
    was spent, and a round whose estimate read low is stopped with the
    response in the restricted transcript."""
    tight = PLATFORM_BUDGET_CAP.model_copy(update={"max_output_tokens": 10})
    live = gateway(
        provider=MockProvider(script=[LLMResponse(text="long", input_tokens=5, output_tokens=99)]),
        budget=tight,
    )
    with pytest.raises(GatewayRefusal, match="over its token budget"):
        live.complete(request_payload())
    assert "budget exceeded" in live.transcript.text


def test_input_usage_that_overshoots_is_caught_the_same_way() -> None:
    """The output half had a test and the input half did not, which a
    tooth found by not biting: an injection that disabled the input
    check left every test green."""
    tight = PLATFORM_BUDGET_CAP.model_copy(update={"max_input_tokens": 10})
    live = gateway(
        provider=MockProvider(script=[LLMResponse(text="x", input_tokens=99, output_tokens=1)]),
        budget=tight,
    )
    with pytest.raises(GatewayRefusal, match="over its token budget"):
        live.complete(request_payload())
    assert "budget exceeded" in live.transcript.text


def test_a_round_with_no_output_budget_left_is_refused_before_the_call() -> None:
    """An estimate decides whether to dispatch, and zero remaining
    output tokens is not an estimate anybody needs to make."""
    tight = PLATFORM_BUDGET_CAP.model_copy(update={"max_output_tokens": 5})
    live = gateway(
        provider=MockProvider(
            script=[LLMResponse(text="x", input_tokens=1, output_tokens=5) for _ in range(2)]
        ),
        budget=tight,
    )
    live.complete(request_payload())
    with pytest.raises(GatewayRefusal, match="no output budget"):
        live.complete(request_payload())


def test_a_vendor_turn_round_trips_with_its_shape_intact() -> None:
    """Gemini refuses the next turn without its thought signature and
    Anthropic wants thinking blocks verbatim, so the gateway carries the
    turn opaquely rather than rebuilding it."""
    turn = ProviderTurn(
        format="google.genai.v1",
        payload={"parts": [{"thought_signature": "sig-1"}, {"text": "hello"}]},
    )
    assert turn_from_payload(provider_turn_payload(turn)) == turn


def test_an_unknown_vendor_format_is_forwarded_unchanged() -> None:
    """That is what makes a transcript portable across a provider switch."""
    turn = ProviderTurn(format="some.vendor.v9", payload={"opaque": [1, 2, 3]})
    assert turn_from_payload(provider_turn_payload(turn)) == turn


def test_array_order_survives_the_round_trip() -> None:
    turn = ProviderTurn(format="x", payload={"parts": [{"a": 1}, {"b": 2}]})
    restored = turn_from_payload(provider_turn_payload(turn))
    assert [tuple(part) for part in restored.payload["parts"]] == [("a",), ("b",)]  # type: ignore[index]


# --------------------------------------------------------------------------
# What stays with the platform
# --------------------------------------------------------------------------


def test_a_restricted_stream_is_capped_and_says_how_much_went() -> None:
    """A cap that silently drops the end of a log is a log that lies."""
    artifact = RestrictedArtifact(name="stderr")
    artifact.append("x" * (MAX_RESTRICTED_BYTES + 500))
    assert artifact.size == MAX_RESTRICTED_BYTES
    assert artifact.truncated_bytes == 500
    assert "truncated" in artifact.text


def test_a_container_narrating_a_packet_fills_the_cap_and_gets_cut() -> None:
    artifact = RestrictedArtifact(name="stderr")
    for _ in range(500):
        artifact.append("packet line " + "y" * 1000)
    assert artifact.truncated_bytes > 0


def test_the_submitter_gets_a_code_and_a_token_not_a_case_id() -> None:
    """"Your analyst crashed on narrow-gap-007" tells a submitter which
    hidden case exists and what it is about."""
    told = public_error("analyst_raised", case_id="narrow-gap-007", run_salt="run-1")
    assert told["error"] == "analyst_raised"
    assert "narrow" not in told["case"]


def test_a_code_nobody_enumerated_becomes_the_generic_one() -> None:
    told = public_error("stack trace follows", case_id="c", run_salt="s")
    assert told["error"] == "platform_error"
    assert told["error"] in PUBLIC_ERROR_CODES


def test_a_token_is_stable_in_one_run_and_useless_across_two() -> None:
    first = case_token("narrow-gap-007", run_salt="run-1")
    assert first == case_token("narrow-gap-007", run_salt="run-1")
    assert first != case_token("narrow-gap-007", run_salt="run-2")
