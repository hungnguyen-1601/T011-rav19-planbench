"""Turn a paper's description of a configuration into a candidate draft.

The honest version of "read a paper and add an algorithm". This module
does not write a planner: a paper proposing TEB or MPPI describes code
that is not in this repository, and generating it from prose would
produce something that compiles and cannot be trusted. What it does is
narrower and actually checkable — recover the **configuration** a paper
reports, expressed in the parameters this platform already runs.

Four things make the output worth acting on rather than plausible.

**The schema is closed over what exists.** Stack ids come from the
registry and parameter names from that stack's own config schema, both
enumerated in the JSON Schema handed to the model. A compliant provider
cannot name a planner this repository does not have, and a
non-compliant one is caught by validation immediately after.

**Every extracted value cites the sentence it came from.** The measured
rate of fabricated citations in published work is high enough that an
uncited number is not evidence of anything. A quote that does not appear
in the source text is dropped and counted, the same rule the critique
layer lives under.

**What the paper did not say is an output, not a gap.** Papers
under-report; the parameters they omit are exactly the ones that make a
reproduction fail. Those come back as ``assumptions`` naming the default
that will be used instead, and they flow into the Decision Card's
``declared_assumptions`` rather than disappearing.

**What cannot be represented is stated.** A paper about a planner this
platform does not implement produces ``not_representable`` and no
candidate. Refusing is the correct answer there, and a mapping onto "the
nearest thing we have" would quietly answer a different question.

Nothing here registers anything. The output is a draft a person reads,
corrects and submits — which is also what the published gap between
autonomous and human-supervised extraction says to do.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from planbench_agent.provider import LLMMessage, LLMProvider, LLMRequest
from planbench_benchmark.candidates import candidate_from_stack
from planbench_benchmark.registry import ALGORITHMS, algorithm_info

__all__ = [
    "PAPER_MAX_TOKENS",
    "PdfUnavailable",
    "read_upload",
    "PAPER_SYSTEM",
    "ExtractedParameter",
    "PaperExtraction",
    "extract_from_paper",
    "paper_schema",
    "selectable_stacks",
]

#: Room for a long quote list. Reasoning models spend part of the budget
#: thinking, and a truncated JSON object is discarded whole — the same
#: failure the critique layer hit at the default.
PAPER_MAX_TOKENS = 32768

#: How much of the source a quote may be. Long enough to carry a full
#: sentence, short enough that "quoting" cannot mean pasting the section.
MAX_QUOTE_CHARS = 300

#: Extensions this module knows how to turn into text. A ``.pdf`` needs
#: pypdf; the rest are read directly.
SUPPORTED_UPLOADS = (".pdf", ".txt", ".md", ".tex")


class PdfUnavailable(RuntimeError):
    """A PDF arrived and no PDF reader is installed.

    Its own type rather than a generic error so the caller can answer
    with the one-line fix instead of a stack trace: the feature works
    without pypdf for text uploads, and degrades loudly rather than
    silently for PDFs (the same bargain the optional providers make).
    """


def read_upload(filename: str, data: bytes) -> str:
    """Text out of an uploaded paper. Raises on anything it cannot read.

    PDF extraction is deliberately naive — page text, joined. A
    two-column layout will interleave, and that is visible to whoever
    pastes the result into the box rather than hidden behind a
    confident-looking extraction. The alternative, a layout-aware
    parser, is a second thing to be wrong and not the part of this that
    is hard.
    """
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_UPLOADS:
        raise ValueError(
            f"cannot read {suffix or 'a file with no extension'}; "
            f"upload one of {', '.join(SUPPORTED_UPLOADS)}"
        )
    if suffix != ".pdf":
        return data.decode("utf-8", errors="replace")

    try:
        from pypdf import PdfReader
    except ImportError as exc:  # optional, like every provider SDK
        raise PdfUnavailable(
            "reading PDFs needs pypdf, which is not installed. Install it with "
            "`.venv/bin/pip install pypdf`, or paste the text instead"
        ) from exc

    # A truncated or malformed PDF is the caller's file, not this
    # deployment's fault, so it must not surface as a 500. pypdf raises
    # its own error types (and, on damaged xref tables, plain
    # `KeyError`/`struct.error` from deep inside the parser), so the net
    # is cast by behaviour rather than by exception class: anything that
    # goes wrong reading these bytes means these bytes could not be read.
    try:
        reader = PdfReader(BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:
        raise ValueError(f"that PDF could not be read ({exc}); paste the text instead") from exc

    text = "\n\n".join(pages).strip()
    if not text:
        raise ValueError(
            "no text found in that PDF. Scanned papers are images, and this reads "
            "text — paste the section instead"
        )
    return text


PAPER_SYSTEM = """You are reading a robotics paper to recover the navigation \
configuration it reports, so it can be re-run on a different deployment.

You are not summarising the paper and you are not judging it.

What to extract:
- Which planner stack it used, chosen from the list in the schema. If the \
paper's method is not in that list, do not substitute a similar one: say so \
in `not_representable` and return no stack.
- The parameter values it reports, using only the parameter names in the \
schema for that stack.
- For every value, the exact sentence you took it from, copied verbatim from \
the text you were given.
- Every parameter the paper does NOT state. Those are the reason a \
reproduction fails, so list them in `assumptions` rather than leaving them \
out.
- The conditions the paper claims its result under: environment, robot, \
speeds, obstacle density.

Rules:
1. Copy quotes exactly. Do not paraphrase, do not reconstruct from memory, \
do not quote a sentence that is not in the text.
2. Convert units to SI (metres, seconds, radians) and say in `note` when you \
converted.
3. If a value is a range or a swept set, take the one the paper reports its \
headline result with, and say so in `note`.
4. Never invent a parameter the paper did not give. An unstated parameter \
belongs in `assumptions`."""


class ExtractedParameter(BaseModel):
    """One value, and the sentence it came from."""

    model_config = ConfigDict(frozen=True)

    name: str
    value: float | int | bool | str
    #: Verbatim from the source. Checked against it, not trusted.
    quote: str
    note: str = ""


class PaperExtraction(BaseModel):
    """A draft candidate, everything it assumed, and what it could not do.

    ``candidate_id`` is present only when the draft validated against the
    registry — an extraction that produced an unrunnable configuration is
    still worth showing a reader, but it must not look registerable.
    """

    model_config = ConfigDict(frozen=True)

    stack: str = ""
    params: dict[str, Any] = {}
    parameters: tuple[ExtractedParameter, ...] = ()
    #: Parameters the paper never stated, with the default that will
    #: stand in. These become the card's declared assumptions.
    assumptions: tuple[str, ...] = ()
    #: What the paper describes that this platform cannot express.
    not_representable: tuple[str, ...] = ()
    claimed_conditions: str = ""
    #: Quotes that do not appear in the source, dropped and counted.
    unquoted: int = 0
    #: Set when nothing usable came back, with the reason.
    refused: str = ""
    candidate_id: str = ""
    #: Why the draft would not validate, per field, when it did not.
    errors: tuple[str, ...] = ()
    provider: str = ""
    model: str = ""
    deterministic: bool = True


def selectable_stacks() -> tuple[str, ...]:
    """Stacks a candidate can actually be built from, with no extra input.

    Established by *building* one rather than by reading flags. A stack
    can be benchmarkable, follow a global path, and still be
    unofferable: ``astar+ppo`` needs a trained checkpoint a paper does
    not carry, and its config model rejects a candidate without one.
    Offering it would put a name in the enum that fails at registration,
    one step after the model has committed to it.
    """
    offerable: list[str] = []
    for stack_id, entry in ALGORITHMS.items():
        if not (entry.info.benchmarkable and entry.info.requires_global_path):
            continue
        try:
            candidate_from_stack(stack_id, params={})
        except (ValidationError, ValueError):
            continue
        offerable.append(stack_id)
    return tuple(sorted(offerable))


def _parameter_names() -> tuple[str, ...]:
    """Every configurable parameter across the selectable stacks.

    Flat rather than per-stack because JSON Schema cannot express "these
    keys depend on that enum" in a form providers reliably honour. The
    per-stack check happens in validation, where the error can name the
    stack and the offending key.
    """
    names: set[str] = set()
    for stack_id in selectable_stacks():
        info = algorithm_info(stack_id)
        if info is not None:
            names.update(info.config_schema.get("properties", {}))
    return tuple(sorted(names))


def paper_schema() -> dict[str, Any]:
    """The shape the provider is forced into.

    Both enums are computed from the registry rather than written here,
    so a stack added tomorrow is offerable without editing this file —
    and, more to the point, a stack removed tomorrow stops being
    offerable without anyone remembering to.
    """
    return {
        "type": "object",
        "properties": {
            "stack": {
                "type": "string",
                "enum": ["", *selectable_stacks()],
                "description": (
                    "The stack this paper's method maps onto. Empty string if none "
                    "of them is the paper's method — do not substitute."
                ),
            },
            "parameters": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "enum": list(_parameter_names())},
                        "value": {
                            "type": ["number", "boolean", "string"],
                            "description": "In SI units.",
                        },
                        "quote": {
                            "type": "string",
                            "maxLength": MAX_QUOTE_CHARS,
                            "description": "Verbatim sentence from the text stating this value.",
                        },
                        "note": {
                            "type": "string",
                            "description": "Unit conversion or choice among reported values.",
                        },
                    },
                    "required": ["name", "value", "quote", "note"],
                    "additionalProperties": False,
                },
            },
            "assumptions": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Parameters the paper does not state. One sentence each, naming "
                    "the parameter and why its absence matters."
                ),
            },
            "not_representable": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "What the paper describes that this platform cannot express — a "
                    "planner it does not implement, a sensor it does not model."
                ),
            },
            "claimed_conditions": {
                "type": "string",
                "description": "Environment, robot and traffic the paper claims its result under.",
            },
        },
        "required": [
            "stack",
            "parameters",
            "assumptions",
            "not_representable",
            "claimed_conditions",
        ],
        "additionalProperties": False,
    }


def _normalise(text: str) -> str:
    """Collapse whitespace so a quote survives PDF line wrapping.

    Without this, every quote from a two-column PDF fails the source
    check for having a newline where the paper had one — and the reader
    would see a fabrication count that measured the extractor, not the
    model.
    """
    return " ".join(text.split()).lower()


def extract_from_paper(text: str, provider: LLMProvider) -> PaperExtraction:
    """Read a paper's text into a candidate draft. Never raises.

    The draft is validated against the registry before it comes back, so
    a reader is never shown a configuration that would fail three
    hundred episodes later.
    """
    meta = {
        "provider": provider.name,
        "model": provider.model,
        "deterministic": provider.deterministic,
    }
    if not text.strip():
        return PaperExtraction(refused="no text to read", **meta)

    request = LLMRequest(
        system=PAPER_SYSTEM,
        messages=(LLMMessage.user(text),),
        output_schema=paper_schema(),
        max_tokens=PAPER_MAX_TOKENS,
    )
    try:
        response = provider.complete(request)
    except Exception as exc:  # a provider failure is a refusal, not a crash
        return PaperExtraction(refused=f"provider failed: {exc}", **meta)

    if not isinstance(response.structured, dict):
        return PaperExtraction(refused="provider returned no structured output", **meta)
    try:
        parsed = _Payload.model_validate(response.structured)
    except ValidationError as exc:
        return PaperExtraction(
            refused=f"structured output did not validate: {exc.error_count()} error(s)", **meta
        )

    source = _normalise(text)
    kept: list[ExtractedParameter] = []
    unquoted = 0
    for item in parsed.parameters:
        if _normalise(item.quote) not in source:
            unquoted += 1
            continue
        kept.append(
            ExtractedParameter(
                name=item.name, value=item.value, quote=item.quote.strip(), note=item.note
            )
        )

    if not parsed.stack:
        return PaperExtraction(
            parameters=tuple(kept),
            assumptions=parsed.assumptions,
            not_representable=parsed.not_representable
            or ("the paper's method is not one of the stacks this platform implements",),
            claimed_conditions=parsed.claimed_conditions,
            unquoted=unquoted,
            **meta,
        )

    params = {item.name: item.value for item in kept}
    candidate_id, errors = _validate(parsed.stack, params)
    return PaperExtraction(
        stack=parsed.stack,
        params=params,
        parameters=tuple(kept),
        assumptions=parsed.assumptions,
        not_representable=parsed.not_representable,
        claimed_conditions=parsed.claimed_conditions,
        unquoted=unquoted,
        candidate_id=candidate_id,
        errors=errors,
        **meta,
    )


def _validate(stack: str, params: dict[str, Any]) -> tuple[str, tuple[str, ...]]:
    """Build the candidate to find out whether it is buildable.

    Cheaper and more honest than re-deriving the rules: the registry
    already rejects an unknown parameter and an out-of-range value, and
    the id it returns is the one a later run would key on.
    """
    try:
        return candidate_from_stack(stack, params=params).candidate_id, ()
    except (ValidationError, ValueError) as exc:
        # ValueError covers the registry's own refusals — unknown stack,
        # unknown parameter, reference-only entry — which all subclass it.
        return "", (str(exc),)


class _Parameter(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    value: float | int | bool | str
    quote: str
    note: str = ""


class _Payload(BaseModel):
    """What the provider must return, validated before anything is used."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    stack: str = ""
    parameters: tuple[_Parameter, ...] = ()
    assumptions: tuple[str, ...] = ()
    not_representable: tuple[str, ...] = ()
    claimed_conditions: str = ""
