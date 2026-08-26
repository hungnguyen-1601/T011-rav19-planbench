"""Diffing a candidate against the paper it came from.

The rule that earns this module is the one about silence. A paper states
two or three parameters; the registry fills eighteen; the resulting
candidate looks complete because every field has a value, and a reader
comparing their success rate against the paper's is comparing against a
configuration nobody published. Reporting the difference is easy —
noticing the sixteen defaults is the part that needs code.

The real registry is used throughout, not a stub. The point of the module
is that it knows what this platform's defaults actually are, and a stub
would test the arithmetic while leaving that claim unmeasured.
"""

from __future__ import annotations

from typing import Any

import pytest

from planbench_benchmark.candidates import candidate_from_stack
from planbench_benchmark.reproduction import (
    REPRODUCTION_CODES,
    build_comparison,
    reproduction_advice,
)
from planbench_decision.self_check import exists

PAPER: dict[str, Any] = {
    "stack": "astar+dwa",
    "parameters": [
        {"name": "horizon_seconds", "value": 2.0, "quote": "a 2.0 second horizon"},
        {"name": "velocity_samples", "value": 15, "quote": "15 linear velocities"},
    ],
    "assumptions": ["horizon_dt is not stated"],
    "not_representable": [],
    "claimed_conditions": "warehouse, differential drive",
    "unquoted": 0,
}

DEPLOYMENT: dict[str, Any] = {"id": "demo_hall", "environment": {"map": "hall"}}


def candidate(**params: Any) -> dict[str, Any]:
    built = candidate_from_stack("astar+dwa", params=params)
    return {"candidate_id": built.candidate_id, "stack": "astar+dwa", "params": built.params}


def comparison(paper: dict[str, Any] | None = None, /, **params: Any) -> dict[str, Any]:
    return build_comparison(paper or PAPER, candidate(**params), DEPLOYMENT)


def codes(source: dict[str, Any]) -> set[str]:
    return {a.code for a in reproduction_advice(source)}


class TestItReadsTheCandidatesRealParameters:
    """A built candidate nests its tunables under the controller name.
    Reading only the flat shape reported every stated parameter as
    "None here", which is a diff against nothing dressed up as a diff."""

    def test_a_matching_value_is_recognised_as_matching(self) -> None:
        rows = comparison(horizon_seconds=2.0, velocity_samples=15)["parameters"]
        stated = {row["name"]: row["verdict"] for row in rows if row["paper_stated"]}
        assert stated == {"horizon_seconds": "agrees", "velocity_samples": "agrees"}

    def test_a_differing_value_is_recognised_as_differing(self) -> None:
        rows = comparison(horizon_seconds=1.5, velocity_samples=15)["parameters"]
        row = next(r for r in rows if r["name"] == "horizon_seconds")
        assert row["verdict"] == "differs"
        assert row["paper"] == 2.0
        assert row["candidate"] == 1.5

    def test_an_int_and_a_float_of_one_value_agree(self) -> None:
        """JSON round-trips 15 through 15.0; reporting that as a change
        would bury the real differences under noise."""
        rows = comparison(horizon_seconds=2.0, velocity_samples=15.0)["parameters"]
        row = next(r for r in rows if r["name"] == "velocity_samples")
        assert row["verdict"] == "agrees"

    def test_a_flat_params_dict_is_read_too(self) -> None:
        """The API's CandidateSpec hands over a flat mapping; only a
        built Candidate nests."""
        flat = {"candidate_id": "x", "stack": "astar+dwa", "params": {"horizon_seconds": 2.0}}
        rows = build_comparison(PAPER, flat, DEPLOYMENT)["parameters"]
        assert next(r for r in rows if r["name"] == "horizon_seconds")["verdict"] == "agrees"


class TestSilenceIsTheLoudestFinding:
    def test_the_defaults_the_paper_never_chose_are_counted(self) -> None:
        found = [
            a
            for a in reproduction_advice(comparison(horizon_seconds=2.0, velocity_samples=15))
            if a.code == "RP_DEFAULT_TAKEN_FOR_SILENCE"
        ]
        assert found
        assert "16" in found[0].claim

    def test_it_names_one_of_them_rather_than_only_counting(self) -> None:
        """A count tells a reader there is a problem; a name tells them
        where to look."""
        found = next(
            a
            for a in reproduction_advice(comparison(horizon_seconds=2.0))
            if a.code == "RP_DEFAULT_TAKEN_FOR_SILENCE"
        )
        assert "=" in found.ground

    def test_it_fires_even_when_every_stated_value_agrees(self) -> None:
        """This is the case it exists for: the diff looks perfect and the
        configuration is still mostly this platform's."""
        found = codes(comparison(horizon_seconds=2.0, velocity_samples=15))
        assert "RP_PARAM_DIFFERS" not in found
        assert "RP_DEFAULT_TAKEN_FOR_SILENCE" in found


class TestItRefusesToCallThingsReproductions:
    def test_a_different_stack_is_blocking(self) -> None:
        other = {**PAPER, "stack": "rrtstar+dwa"}
        assert "RP_STACK_DIFFERS" in codes(build_comparison(other, candidate(), DEPLOYMENT))

    def test_something_the_platform_cannot_express_is_blocking(self) -> None:
        limited = {**PAPER, "not_representable": ["the paper's 8-connected A* grid"]}
        found = next(
            a
            for a in reproduction_advice(build_comparison(limited, candidate(), DEPLOYMENT))
            if a.code == "RP_NOT_REPRESENTABLE"
        )
        assert found.severity == "blocking"
        assert "8-connected" in found.ground

    def test_dropped_quotes_are_reported_as_an_incomplete_reading(self) -> None:
        sloppy = {**PAPER, "unquoted": 3}
        found = next(
            a
            for a in reproduction_advice(build_comparison(sloppy, candidate(), DEPLOYMENT))
            if a.code == "RP_UNQUOTED_VALUES_DROPPED"
        )
        assert "3" in found.claim

    def test_the_paper_conditions_are_set_against_the_deployment(self) -> None:
        found = next(
            a for a in reproduction_advice(comparison()) if a.code == "RP_CONDITIONS_DIFFER"
        )
        assert "warehouse" in found.claim
        assert "demo_hall" in found.claim

    def test_no_deployment_means_no_conditions_advice(self) -> None:
        """Nothing to compare against is not the same as a mismatch."""
        source = build_comparison(PAPER, candidate(), None)
        assert "RP_CONDITIONS_DIFFER" not in codes(source)


class TestEveryCitationResolves:
    @pytest.mark.parametrize(
        "paper",
        [
            PAPER,
            {**PAPER, "stack": "rrtstar+dwa"},
            {**PAPER, "not_representable": ["something"]},
            {**PAPER, "unquoted": 2},
            {**PAPER, "parameters": []},
        ],
    )
    def test_for_every_shape_of_paper(self, paper: dict[str, Any]) -> None:
        source = build_comparison(paper, candidate(horizon_seconds=1.5), DEPLOYMENT)
        for item in reproduction_advice(source):
            assert exists(source, item.field_path), f"{item.code} cites {item.field_path}"


class TestItNeverBreaks:
    def test_an_empty_comparison_returns_nothing(self) -> None:
        assert reproduction_advice({}) == ()

    def test_a_malformed_comparison_returns_nothing(self) -> None:
        assert reproduction_advice({"parameters": "not a list"}) == ()

    def test_an_unknown_stack_does_not_raise(self) -> None:
        source = build_comparison(
            {**PAPER, "stack": "no_such_stack"},
            {"candidate_id": "x", "stack": "no_such_stack", "params": {}},
            DEPLOYMENT,
        )
        assert isinstance(reproduction_advice(source), tuple)

    def test_the_order_is_stable(self) -> None:
        source = comparison(horizon_seconds=1.5)
        assert [a.code for a in reproduction_advice(source)] == [
            a.code for a in reproduction_advice(source)
        ]


class TestWhatIsPublished:
    def test_every_emitted_code_is_declared(self) -> None:
        emitted: set[str] = set()
        for paper in (
            PAPER,
            {**PAPER, "stack": "rrtstar+dwa"},
            {**PAPER, "not_representable": ["x"], "unquoted": 1},
        ):
            emitted |= codes(build_comparison(paper, candidate(horizon_seconds=1.5), DEPLOYMENT))
        assert emitted <= set(REPRODUCTION_CODES), emitted - set(REPRODUCTION_CODES)

    def test_the_codes_are_unique(self) -> None:
        assert len(REPRODUCTION_CODES) == len(set(REPRODUCTION_CODES))

    def test_everything_is_tagged_as_reproduction(self) -> None:
        assert all(a.kind == "reproduction" for a in reproduction_advice(comparison()))

    def test_every_blocking_advice_names_a_forbidden_move(self) -> None:
        source = build_comparison(
            {**PAPER, "stack": "rrtstar+dwa", "not_representable": ["x"]},
            candidate(),
            DEPLOYMENT,
        )
        for item in reproduction_advice(source):
            if item.severity == "blocking":
                assert item.do_not, item.code
