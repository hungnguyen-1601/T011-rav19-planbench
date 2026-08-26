"""W1.7 — the arm vector is part of what a run was.

An input flag outside the identity is a flag two runs can disagree about
while producing one checksum: a bundle graded with the timeline block in
the prompt and replayed without it answers differently, and the second
reading reads as model variance rather than as a different system.

Also held here: the flags are independent (E3 needs a full two-by-two,
and a pair that only moves together is one arm wearing two names), and
the two flags W3 will implement refuse rather than accepting ``True``
and changing nothing — an arm reported as run that was never run is the
one failure this layer cannot detect afterwards.
"""

from __future__ import annotations

import pytest
from test_analyst_packet_view import observation, packet
from test_analyst_runner import MEASURED_TASK, answer, hypothesis, prepared, scripted

from planbench_analyst.features import FeatureRefusal, RoundFeatures
from planbench_analyst.identity import runtime_config_checksum
from planbench_analyst.packet_view import build_packet_view
from planbench_analyst.runner import run_round
from planbench_explanation.case_packet import (
    CandidateMeasurements,
    EpisodeTimeline,
    MeasuredValue,
    TimelinePoint,
)
from planbench_explanation.catalog import TOOL_CATALOG_VERSION


def checksum(features: RoundFeatures | None = None) -> str:
    return runtime_config_checksum(
        prompt_checksum="a" * 64,
        generation_config={"temperature": 0.0},
        catalog_version=TOOL_CATALOG_VERSION,
        source_manifest_hash="b" * 64,
        features=features,
    )


def rich_packet():  # type: ignore[no-untyped-def]
    """A packet carrying both of the blocks the flags can withhold."""
    return packet(
        observations=[observation()],
        task=MEASURED_TASK,
        measurements=[
            CandidateMeasurements(
                candidate_id="cand_a",
                success_rate=MeasuredValue(value=0.9, unit="ratio", denominator=30),
            )
        ],
        timelines=[
            EpisodeTimeline(
                episode_context_id="ep-001",
                candidate_id="cand_a",
                role="typical",
                points=(
                    TimelinePoint(
                        clock="at_time",
                        mark=1.0,
                        progress_fraction=0.5,
                        safety_margin=1.2,
                        compute_budget=0.4,
                        path_efficiency=0.9,
                        elapsed_s=1.0,
                        replans=0,
                    ),
                ),
            )
        ],
    )


# --------------------------------------------------------------------------
# The checksum moves with the arm
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "features",
    [
        RoundFeatures(measurements=False),
        RoundFeatures(timelines=False),
        RoundFeatures(knowledge=True),
        RoundFeatures(traits=True),
    ],
)
def test_every_flag_changes_the_runtime_checksum(features: RoundFeatures) -> None:
    assert checksum(features) != checksum()


def test_the_default_vector_is_what_the_platform_did_before_the_flags() -> None:
    """A default that changed behaviour would re-run every existing
    measurement under a new arm without anybody asking."""
    assert checksum(RoundFeatures()) == checksum(None)
    assert RoundFeatures().measurements and RoundFeatures().timelines
    assert not RoundFeatures().knowledge and not RoundFeatures().traits


def test_two_different_arms_never_share_a_checksum() -> None:
    seen = {
        checksum(RoundFeatures(measurements=m, timelines=t, knowledge=k, traits=r))
        for m in (True, False)
        for t in (True, False)
        for k in (True, False)
        for r in (True, False)
    }
    assert len(seen) == 16


# --------------------------------------------------------------------------
# A flag that is off withholds the block
# --------------------------------------------------------------------------


def test_the_measurement_block_is_hidden_when_its_flag_is_off() -> None:
    built = rich_packet()
    shown = build_packet_view(built, tool_catalog_version=TOOL_CATALOG_VERSION)
    hidden = build_packet_view(
        built,
        tool_catalog_version=TOOL_CATALOG_VERSION,
        features=RoundFeatures(measurements=False),
    )
    assert "fact:metric:cand_a.success_rate" in shown
    assert "fact:metric:cand_a.success_rate" not in hidden


def test_the_timeline_block_is_hidden_when_its_flag_is_off() -> None:
    built = rich_packet()
    shown = build_packet_view(built, tool_catalog_version=TOOL_CATALOG_VERSION)
    hidden = build_packet_view(
        built,
        tool_catalog_version=TOOL_CATALOG_VERSION,
        features=RoundFeatures(timelines=False),
    )
    assert len(hidden.serialize()) < len(shown.serialize())
    assert "episode:ep-001/cand_a/at_time/1.progress_fraction" in shown


def test_hiding_one_block_leaves_the_other_alone() -> None:
    """E1 and E2 are separate arms; one flag that moved both would make
    either result unreadable."""
    built = rich_packet()
    without_timelines = build_packet_view(
        built,
        tool_catalog_version=TOOL_CATALOG_VERSION,
        features=RoundFeatures(timelines=False),
    )
    assert "fact:metric:cand_a.success_rate" in without_timelines


# --------------------------------------------------------------------------
# What is declared and not built refuses
# --------------------------------------------------------------------------


@pytest.mark.parametrize("flag", ["filter_tool_menu", "auto_route_checker"])
def test_a_w3_flag_refuses_rather_than_reporting_an_arm_that_never_ran(flag: str) -> None:
    with pytest.raises(FeatureRefusal, match=flag):
        RoundFeatures(**{flag: True})  # type: ignore[arg-type]


def test_the_w3_flags_are_still_in_the_checksum_while_off() -> None:
    """Named now because W3 changes what ``checker_selection`` means, and
    a preregistration written against a checksum that could not express
    the change would have to be rewritten after the fact."""
    assert "filter_tool_menu" in RoundFeatures().as_config
    assert "auto_route_checker" in RoundFeatures().as_config


# --------------------------------------------------------------------------
# The runner will not run one thing and record another
# --------------------------------------------------------------------------


def test_handing_traits_to_a_round_that_does_not_declare_them_is_refused() -> None:
    """Otherwise the checksum says the arm was off while the prompt
    carried the natures."""
    from test_analyst_retrieval_round import traits_for

    with pytest.raises(FeatureRefusal, match="traits"):
        run_round(
            prepared(),
            scripted(answer(hypothesis())),
            features=RoundFeatures(traits=False),
            traits=traits_for("dwa"),
        )
