"""What one analysis round is allowed to spend, and who decides it.

A round costs money and wall-clock, and both are spent by code the
platform did not write. So the limits are a **contract object**, not a
handful of keyword arguments: they travel inside the frozen bundle, they
have a checksum, and the gate decision names the one it was judged
against.

**Requested is the submitter's; effective is the platform's.**
:meth:`AnalysisBudget.capped_by` takes the field-wise minimum, so a
submitter can ask for less than the cap and never for more. The
effective budget is what actually runs — and calibration, gate and
production must all run under the *same* effective budget, because an
analyst graded with twice the tool calls it gets in production was
graded as a system that does not exist. :func:`verify_gate_decision`
enforces that; here we only make the comparison possible.

**The cap is a constant in this module, not a parameter.** Same reason
:data:`~planbench_explanation.golden.OFFICIAL_GOLDEN_READY` is one: it
decides what the platform will pay for, and the party being graded must
not be able to pass it as an argument.

**Frame sizes are per frame type, not one number.** The container lane
sends a model response back through the platform, carrying whatever the
vendor attached to the assistant turn; that frame is legitimately larger
than a tool request. One cap for both is either too small for the
response or too generous for everything else, and "too generous for
everything else" is the shape a packet leaves through.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from planbench_explanation.versioning import artifact_checksum

__all__ = [
    "FRAME_TYPES",
    "PLATFORM_BUDGET_CAP",
    "AnalysisBudget",
    "BudgetRefusal",
]


class BudgetRefusal(ValueError):
    """A budget this platform will not run under."""


#: Every frame the stdio lane may carry. Listed here rather than in the
#: protocol module because the cap is a budget decision: a frame type
#: nobody wrote a limit for is a frame type with no limit.
FRAME_TYPES: tuple[str, ...] = (
    "hello",
    "analysis_request",
    "declare_proposals",
    "declaration_ack",
    "model_request",
    "model_response",
    "tool_request",
    "tool_result",
    "final_response",
    "error",
    "done",
)


class AnalysisBudget(BaseModel):
    """The ceiling for one round, on every axis that can run away."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_tool_requests: int = Field(ge=1, le=1024)
    #: Cumulative over the whole round, not per proposal. A per-proposal
    #: limit multiplies by however many proposals the analyst makes,
    #: which is a number the analyst chooses.
    max_model_calls: int = Field(ge=1, le=64)
    #: Cumulative, counted from the usage the provider reports rather
    #: than from an estimate. An estimate that reads low is how a budget
    #: is exceeded by a round that believed it was inside.
    max_input_tokens: int = Field(ge=1)
    max_output_tokens: int = Field(ge=1)
    #: Monotonic deadline for the whole round — provider time and tool
    #: time together, because a round that spends an hour in checkers is
    #: as stuck as one that spends it waiting on a model.
    max_wall_time_ms: int = Field(ge=1)
    max_frame_bytes: dict[str, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check(self) -> AnalysisBudget:
        unknown = sorted(set(self.max_frame_bytes) - set(FRAME_TYPES))
        if unknown:
            raise BudgetRefusal(
                f"frame type(s) {unknown} are not on the protocol; a cap on a frame "
                f"nobody sends is a cap that protects nothing. Known frames: "
                f"{list(FRAME_TYPES)}"
            )
        missing = sorted(set(FRAME_TYPES) - set(self.max_frame_bytes))
        if missing:
            raise BudgetRefusal(
                f"no size cap for frame(s) {missing}; an uncapped frame is the shape "
                "a hidden packet leaves through"
            )
        bad = sorted(name for name, size in self.max_frame_bytes.items() if size < 1)
        if bad:
            raise BudgetRefusal(f"frame cap(s) {bad} are not positive")
        return self

    @property
    def checksum(self) -> str:
        """Identifies these limits. A decision names the ones it ran under."""
        return artifact_checksum(self.model_dump(mode="json"))

    def capped_by(self, cap: AnalysisBudget) -> AnalysisBudget:
        """The effective budget: field-wise minimum, never the maximum.

        A submitter asking for less than the cap gets what it asked for,
        which is worth honouring — a bundle that declared a small budget
        and then ran under a large one was calibrated as a different
        system.
        """
        return AnalysisBudget(
            max_tool_requests=min(self.max_tool_requests, cap.max_tool_requests),
            max_model_calls=min(self.max_model_calls, cap.max_model_calls),
            max_input_tokens=min(self.max_input_tokens, cap.max_input_tokens),
            max_output_tokens=min(self.max_output_tokens, cap.max_output_tokens),
            max_wall_time_ms=min(self.max_wall_time_ms, cap.max_wall_time_ms),
            max_frame_bytes={
                name: min(self.max_frame_bytes[name], cap.max_frame_bytes[name])
                for name in FRAME_TYPES
            },
        )


#: What this platform will pay for in one round, whatever a bundle asks.
#:
#: The model-response frame is two megabytes because it carries the
#: vendor's own assistant turn — Gemini thought signatures, Anthropic
#: thinking blocks — which the container must hand back untouched. Every
#: other frame is capped an order of magnitude tighter: they are written
#: by the container, and the tight cap is what stops a packet being
#: narrated out one tool request at a time.
PLATFORM_BUDGET_CAP = AnalysisBudget(
    max_tool_requests=64,
    max_model_calls=12,
    max_input_tokens=400_000,
    max_output_tokens=120_000,
    max_wall_time_ms=15 * 60 * 1000,
    max_frame_bytes={
        "hello": 8_192,
        "analysis_request": 1_048_576,
        "declare_proposals": 262_144,
        "declaration_ack": 8_192,
        "model_request": 1_048_576,
        "model_response": 2_097_152,
        "tool_request": 65_536,
        "tool_result": 262_144,
        "final_response": 262_144,
        "error": 8_192,
        "done": 8_192,
    },
)
