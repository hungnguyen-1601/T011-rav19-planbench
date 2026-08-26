"""Reading a configuration out of a paper, and refusing to invent one.

The tests that matter are the ones about restraint. An extractor that
produces a plausible candidate for every input is worse than none: the
numbers it invents are indistinguishable from the ones it read, and a
reproduction built on them fails in a way nobody can trace.

So: a quote that is not in the source is dropped, a method this platform
does not implement yields no stack, and a value the registry rejects
comes back as an error rather than as a candidate somebody could
register.
"""

from __future__ import annotations

from typing import Any

import pytest

from planbench_agent.paper import (
    MAX_QUOTE_CHARS,
    SUPPORTED_UPLOADS,
    PdfUnavailable,
    extract_from_paper,
    paper_schema,
    read_upload,
    selectable_stacks,
)
from planbench_agent.provider import LLMRequest, LLMResponse, MockProvider

PAPER = """We evaluate in a warehouse with a differential-drive robot.
Global paths come from A* on an 8-connected grid.
For local control we use the Dynamic Window Approach.
The controller runs at 20 Hz over a 2.0 second horizon.
We sample 15 linear velocities and 30 angular velocities.
"""


def scripted(payload: Any) -> MockProvider:
    class _Scripted(MockProvider):
        def complete(self, request: LLMRequest) -> LLMResponse:  # noqa: ARG002
            return LLMResponse(structured=payload, model="scripted")

    return _Scripted()


def exploding() -> MockProvider:
    class _Boom(MockProvider):
        def complete(self, request: LLMRequest) -> LLMResponse:  # noqa: ARG002
            raise RuntimeError("connection reset")

    return _Boom()


def payload(**overrides: Any) -> dict[str, Any]:
    base = {
        "stack": "astar+dwa",
        "parameters": [
            {
                "name": "horizon_seconds",
                "value": 2.0,
                "quote": "The controller runs at 20 Hz over a 2.0 second horizon.",
                "note": "",
            },
            {
                "name": "velocity_samples",
                "value": 15,
                "quote": "We sample 15 linear velocities and 30 angular velocities.",
                "note": "",
            },
        ],
        "assumptions": ["horizon_dt is not stated"],
        "not_representable": [],
        "claimed_conditions": "warehouse, differential drive",
    }
    base.update(overrides)
    return base


class TestItReadsWhatIsThere:
    def test_it_maps_onto_a_real_stack(self) -> None:
        result = extract_from_paper(PAPER, scripted(payload()))
        assert result.stack == "astar+dwa"
        assert result.params == {"horizon_seconds": 2.0, "velocity_samples": 15}

    def test_a_valid_draft_gets_a_candidate_id(self) -> None:
        """The id a later run would key on, so the draft is registerable
        rather than merely well-formed."""
        result = extract_from_paper(PAPER, scripted(payload()))
        assert result.candidate_id
        assert result.errors == ()

    def test_what_the_paper_omitted_comes_back_as_output(self) -> None:
        """Unstated parameters are the reason reproductions fail, so they
        are reported rather than quietly defaulted."""
        result = extract_from_paper(PAPER, scripted(payload()))
        assert result.assumptions == ("horizon_dt is not stated",)

    def test_the_claimed_conditions_are_carried(self) -> None:
        result = extract_from_paper(PAPER, scripted(payload()))
        assert "warehouse" in result.claimed_conditions


class TestQuotesAreCheckedAgainstTheSource:
    def test_a_quote_absent_from_the_text_is_dropped_and_counted(self) -> None:
        bad = payload(
            parameters=[
                {
                    "name": "horizon_seconds",
                    "value": 9.0,
                    "quote": "The horizon was set to nine seconds.",
                    "note": "",
                }
            ]
        )
        result = extract_from_paper(PAPER, scripted(bad))
        assert result.unquoted == 1
        assert "horizon_seconds" not in result.params

    def test_a_real_quote_survives_line_wrapping(self) -> None:
        """A quote from a two-column PDF arrives with newlines the paper
        did not have; failing it would measure the extractor, not the
        model."""
        wrapped = payload(
            parameters=[
                {
                    "name": "horizon_seconds",
                    "value": 2.0,
                    "quote": "The controller runs at 20 Hz\n  over a 2.0 second horizon.",
                    "note": "",
                }
            ]
        )
        result = extract_from_paper(PAPER, scripted(wrapped))
        assert result.unquoted == 0
        assert result.params["horizon_seconds"] == 2.0

    def test_the_count_is_published_rather_than_swallowed(self) -> None:
        bad = payload(
            parameters=[
                {"name": "horizon_seconds", "value": 1, "quote": "invented one", "note": ""},
                {"name": "velocity_samples", "value": 2, "quote": "invented two", "note": ""},
            ]
        )
        assert extract_from_paper(PAPER, scripted(bad)).unquoted == 2


class TestItRefusesRatherThanSubstitutes:
    def test_an_unrepresentable_method_yields_no_stack(self) -> None:
        """A paper about TEB is not a paper about DWA. Mapping it onto
        "the nearest thing we have" would answer a different question."""
        result = extract_from_paper(
            PAPER,
            scripted(
                payload(
                    stack="",
                    parameters=[],
                    not_representable=["the paper proposes TEB, which this platform lacks"],
                )
            ),
        )
        assert result.stack == ""
        assert result.candidate_id == ""
        assert result.not_representable

    def test_an_empty_stack_still_explains_itself(self) -> None:
        """Even when the model gives no reason, the caller gets one."""
        result = extract_from_paper(PAPER, scripted(payload(stack="", not_representable=[])))
        assert result.not_representable

    def test_empty_input_is_refused_without_calling_the_provider(self) -> None:
        assert extract_from_paper("   ", exploding()).refused == "no text to read"

    def test_a_provider_failure_is_a_refusal_not_a_crash(self) -> None:
        result = extract_from_paper(PAPER, exploding())
        assert "provider failed" in result.refused
        assert result.stack == ""

    def test_unstructured_output_is_refused(self) -> None:
        assert extract_from_paper(PAPER, scripted(None)).refused

    def test_malformed_output_is_refused(self) -> None:
        assert extract_from_paper(PAPER, scripted({"stack": 42})).refused


class TestTheRegistryHasTheFinalWord:
    def test_an_out_of_range_value_is_an_error_not_a_candidate(self) -> None:
        """Caught here rather than three hundred episodes later."""
        result = extract_from_paper(
            PAPER,
            scripted(
                payload(
                    parameters=[
                        {
                            "name": "velocity_samples",
                            "value": 1,  # config model requires >= 2
                            "quote": "We sample 15 linear velocities and 30 angular velocities.",
                            "note": "",
                        }
                    ]
                )
            ),
        )
        assert result.errors
        assert result.candidate_id == ""

    def test_the_same_configuration_always_gets_the_same_id(self) -> None:
        first = extract_from_paper(PAPER, scripted(payload()))
        second = extract_from_paper(PAPER, scripted(payload()))
        assert first.candidate_id == second.candidate_id


class TestTheSchemaIsClosedOverWhatExists:
    def test_the_stack_enum_comes_from_the_registry(self) -> None:
        enum = paper_schema()["properties"]["stack"]["enum"]
        assert set(enum) == {"", *selectable_stacks()}

    def test_a_stack_needing_a_checkpoint_is_not_offered(self) -> None:
        """astar+ppo is benchmarkable and still unofferable: a paper does
        not carry a trained policy, and its config model says so."""
        assert "astar+ppo" not in selectable_stacks()

    def test_every_offered_stack_can_actually_be_built(self) -> None:
        from planbench_benchmark.candidates import candidate_from_stack

        for stack_id in selectable_stacks():
            assert candidate_from_stack(stack_id, params={}).candidate_id

    def test_parameter_names_are_enumerated(self) -> None:
        names = paper_schema()["properties"]["parameters"]["items"]["properties"]["name"]["enum"]
        assert "velocity_samples" in names
        assert "no_such_parameter" not in names

    def test_quotes_are_length_capped(self) -> None:
        """So "quoting" cannot become pasting the whole section."""
        item = paper_schema()["properties"]["parameters"]["items"]["properties"]
        assert item["quote"]["maxLength"] == MAX_QUOTE_CHARS

    def test_extra_properties_are_forbidden(self) -> None:
        schema = paper_schema()
        assert schema["additionalProperties"] is False
        assert schema["properties"]["parameters"]["items"]["additionalProperties"] is False


@pytest.mark.parametrize("field", ["stack", "parameters", "assumptions", "not_representable"])
def test_the_schema_requires_the_fields_the_reader_needs(field: str) -> None:
    assert field in paper_schema()["required"]


class TestReadingAnUploadedFile:
    """The upload is a shortcut past the copy step, and it has to fail in
    ways a person can act on: a file this cannot read says which ones it
    can, and a missing PDF reader says so rather than blaming the file."""

    def test_a_text_file_is_read_as_it_is(self) -> None:
        assert read_upload("paper.txt", PAPER.encode()) == PAPER

    def test_markdown_and_latex_are_read_too(self) -> None:
        """A preprint source is often the cleanest thing a reader has."""
        for name in ("paper.md", "paper.tex"):
            assert "Dynamic Window" in read_upload(name, PAPER.encode())

    def test_undecodable_bytes_do_not_crash_the_read(self) -> None:
        """A mislabelled encoding should cost a few mangled characters,
        not the whole extraction."""
        assert read_upload("paper.txt", b"horizon \xff 2.0 s")

    def test_an_unreadable_extension_names_the_readable_ones(self) -> None:
        with pytest.raises(ValueError, match=r"\.pdf"):
            read_upload("paper.docx", b"anything")

    def test_a_file_with_no_extension_is_refused_legibly(self) -> None:
        with pytest.raises(ValueError, match="no extension"):
            read_upload("paper", b"anything")

    def test_a_corrupt_pdf_is_a_bad_file_not_a_broken_server(self) -> None:
        """pypdf raises its own error types, and a truncated xref table
        surfaces as a bare `KeyError` from inside the parser. Letting
        either escape turns the caller's damaged file into a 500 that
        blames the platform."""
        try:
            read_upload("paper.pdf", b"%PDF-1.4 truncated here")
        except PdfUnavailable as exc:
            # A deployment without pypdf; a different answer, still not
            # a crash.
            assert "pypdf" in str(exc)
        except ValueError as exc:
            assert "paste" in str(exc)

    def test_a_pdf_is_never_quietly_decoded_as_text(self) -> None:
        """The fallback for an unreadable PDF must not be "treat the
        bytes as UTF-8" — that yields mojibake the model would read as
        if it were the paper."""
        try:
            got = read_upload("paper.pdf", b"%PDF-1.4 truncated here")
        except (ValueError, PdfUnavailable):
            return
        assert "%PDF" not in got

    def test_the_offered_extensions_are_published(self) -> None:
        """The browser's `accept` filter is written against this list."""
        assert ".pdf" in SUPPORTED_UPLOADS
