"""The only way a graded analyst reaches a model, and it holds no key.

The container is frozen code with no credentials and no network. When it
wants a completion it sends a ``model_request`` frame; this gateway
checks it against the bundle, calls the provider with the *platform's*
credential, and sends back a ``model_response``. Three consequences,
each of them the reason a step exists:

**The configuration is the bundle's, not the request's.** A container
that could raise its own temperature between calibration and the gate
would be graded as a system nobody ran. So the generation config is read
off the frozen bundle and the frame's own copy is compared against it;
a mismatch ends the round rather than being merged.

**The vendor's assistant turn goes back untouched.** Gemini signs a
function call with a ``thought_signature`` and refuses the next turn
without it; Anthropic wants thinking blocks echoed verbatim. The
gateway therefore round-trips :class:`~planbench_agent.provider.ProviderTurn`
as an opaque JSON mapping — deep structural equality, array order kept,
unknown formats forwarded unchanged. It does not inspect it, and the
container may not modify it.

**Spend is charged from what the provider reported, not from an
estimate.** The estimate decides whether to dispatch; the invoice
decides what was spent. A round whose estimate read low is stopped
*after* the call, with the response held in a restricted artifact — the
one place it is honest to keep an answer the round may not use.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from planbench_agent.provider import (
    LLMMessage,
    LLMProvider,
    LLMRequest,
    LLMResponse,
    ProviderTurn,
)
from planbench_analyst.restricted import RestrictedArtifact
from planbench_explanation.budget import AnalysisBudget
from planbench_explanation.bundle import AnalystBundle

__all__ = ["GatewayRefusal", "ModelGateway", "provider_turn_payload", "turn_from_payload"]


class GatewayRefusal(RuntimeError):
    """A model request the platform will not dispatch."""


def provider_turn_payload(turn: ProviderTurn | None) -> dict[str, Any] | None:
    """A provider turn as JSON the container may carry and not read."""
    if turn is None:
        return None
    return {"format": turn.format, "payload": dict(turn.payload)}


def turn_from_payload(payload: Mapping[str, Any] | None) -> ProviderTurn | None:
    """The inverse. Unknown formats survive: that is what makes a
    transcript portable across a provider switch."""
    if not payload:
        return None
    return ProviderTurn(format=str(payload.get("format", "")), payload=payload.get("payload") or {})


@dataclass
class ModelGateway:
    """Holds the credential, the bundle, and the running total."""

    bundle: AnalystBundle
    provider: LLMProvider
    budget: AnalysisBudget
    transcript: RestrictedArtifact = field(
        default_factory=lambda: RestrictedArtifact(name="model_transcript")
    )
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    def _check_identity(self, frame_payload: Mapping[str, Any]) -> None:
        model = frame_payload.get("model_id")
        if model is not None and model != self.bundle.model_id:
            raise GatewayRefusal(
                f"the round is bundled against {self.bundle.model_id!r} and the request "
                f"names {model!r}; a model swapped mid-round is a system nobody graded"
            )
        config = frame_payload.get("generation_parameters")
        if config is not None and dict(config) != dict(self.bundle.generation_parameters):
            raise GatewayRefusal(
                "the request carries generation parameters other than the frozen "
                "bundle's; the same prompt at another temperature is another system"
            )

    def _check_budget(self, estimated_input: int) -> None:
        if self.calls >= self.budget.max_model_calls:
            raise GatewayRefusal("model call budget exhausted")
        if self.input_tokens + estimated_input > self.budget.max_input_tokens:
            raise GatewayRefusal("estimated input would exceed the round's token budget")
        if self.output_tokens >= self.budget.max_output_tokens:
            raise GatewayRefusal(
                "no output budget remains; dispatching a call whose answer cannot be "
                "paid for spends money for a response the round must discard"
            )

    def complete(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Serve one ``model_request`` payload, or refuse it.

        Returns the ``model_response`` payload: text, structured output,
        usage, and the vendor's turn as an opaque mapping.
        """
        self._check_identity(payload)
        messages = tuple(
            LLMMessage(
                role=item.get("role", "user"),
                text=str(item.get("text", "")),
                provider_turn=turn_from_payload(item.get("provider_turn")),
            )
            for item in payload.get("messages", ())
        )
        estimated_input = sum(len(message.text) for message in messages) // 4
        self._check_budget(estimated_input)

        request = LLMRequest(
            system=str(payload.get("system", "")),
            messages=messages,
            output_schema=payload.get("output_schema"),
            max_tokens=min(
                int(payload.get("max_tokens", self.budget.max_output_tokens)),
                self.budget.max_output_tokens - self.output_tokens,
            ),
        )
        response: LLMResponse = self.provider.complete(request)

        # Charge what the provider reported. An estimate that read low
        # is how a round ends up outside a budget it believed it was
        # inside, so the overshoot is detected here — after the call,
        # which is the only place the true number exists.
        self.calls += 1
        self.input_tokens += response.input_tokens
        self.output_tokens += response.output_tokens
        self.transcript.append(
            f"call {self.calls}: in={response.input_tokens} out={response.output_tokens}\n"
        )
        if (
            self.input_tokens > self.budget.max_input_tokens
            or self.output_tokens > self.budget.max_output_tokens
        ):
            self.transcript.append("budget exceeded on reported usage; response withheld\n")
            raise GatewayRefusal(
                "the reported usage put this round over its token budget; the response "
                "is held in the restricted transcript and the round stops here"
            )

        return {
            "text": response.text,
            "structured": response.structured,
            "stop_reason": str(response.stop_reason),
            "model": response.model,
            "usage": {
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
            },
            "provider_turn": provider_turn_payload(response.provider_turn),
        }

    @property
    def credential_visible_to_container(self) -> bool:
        """Always false, and asserted in a test rather than promised here.

        The container receives frames. There is no field on any frame
        that carries a key, and the provider object lives on this side
        of the wire.
        """
        return False
