"""E4.1 — the packet built during scoring, and the route that serves it.

What these guard: observations come from every episode looked at rather
than from the ones that parsed; a trace the detectors refuse is reported
instead of dropped; a part that cannot be built is an omission with a
reason rather than an empty list; a run scored before E4.1 is refused
rather than handed an empty packet; and the detector version is owned by
the module whose rules it describes.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from planbench_decision.objectives import PREFERENCE_PROFILES
from planbench_explanation.case_packet import CasePacketRefusal
from planbench_explanation.catalog import TOOL_CATALOG_VERSION
from planbench_explanation.detectors import DETECTOR_VERSION
from planbench_explanation.knowledge import KNOWLEDGE_BASE_VERSION
from planbench_explanation.map_features import RouteFeatures
from planbench_explanation.packet_builder import (
    LATTICE_TYPES,
    EpisodeTrace,
    build_scoring_packet,
    lattice_from,
    observations_from_traces,
    packet_block,
    packet_from_block,
)
from planbench_explanation.waterfall import (
    ObjectiveLevels,
    UtilityDrillDown,
    Waterfall,
    WaterfallBar,
    WaterfallProfile,
)


def waterfall() -> Waterfall:
    weights = PREFERENCE_PROFILES["kho_ban_dem"]
    levels = tuple(
        ObjectiveLevels(objective=name, set_level=0.5, episode_mean=0.5)
        for name in ("U_R", "U_S", "U_E", "U_C")
    )
    bars = tuple(
        WaterfallBar(
            objective=name,
            weight=float(getattr(weights, field)),
            delta_objective_mean=0.0,
            contribution=0.0,
            ci95=(-0.01, 0.01),
        )
        for name, field in (("U_R", "w_r"), ("U_S", "w_s"), ("U_E", "w_e"), ("U_C", "w_c"))
    )
    return Waterfall(
        candidate_a="cand_a",
        candidate_b="cand_b",
        profile=WaterfallProfile(kind="canonical", base_profile="kho_ban_dem", weights=weights),
        n_episodes=4,
        delta_utility_mean=0.0,
        delta_utility_median=0.0,
        total_ci95=(-0.02, 0.02),
        bars=bars,
        drill_down=UtilityDrillDown(
            candidate_a="cand_a",
            candidate_b="cand_b",
            set_utility_a=0.5,
            set_utility_b=0.5,
            episode_mean_utility_a=0.5,
            episode_mean_utility_b=0.5,
            levels_a=levels,
            levels_b=levels,
        ),
        seed=0,
        n_resamples=1000,
    )


def straight_trace(candidate_id: str, episode: str, *, samples: int = 40) -> EpisodeTrace:
    """A clean run down a line. Nothing for a detector to find."""
    return EpisodeTrace(
        candidate_id=candidate_id,
        episode_context_id=episode,
        columns={
            "t": [index * 0.1 for index in range(samples)],
            "x": [index * 0.1 for index in range(samples)],
            "y": [0.0] * samples,
            "clearance_m": [1.5] * samples,
            "planner_latency_ms": [5.0] * samples,
            "events": [],
        },
    )


def stalled_trace(candidate_id: str, episode: str) -> EpisodeTrace:
    """Drives, then sits still long enough to be a stuck cluster."""
    moving = [(index * 0.1, index * 0.1) for index in range(20)]
    still = [(2.0 + index * 0.1, 1.9) for index in range(60)]
    times = [index * 0.1 for index in range(len(moving) + len(still))]
    return EpisodeTrace(
        candidate_id=candidate_id,
        episode_context_id=episode,
        columns={
            "t": times,
            "x": [x for _t, x in moving] + [1.9] * len(still),
            "y": [0.0] * len(moving) + [0.0] * len(still),
            "clearance_m": [1.2] * len(times),
            "planner_latency_ms": [5.0] * len(times),
            "events": [],
        },
    )


def report_with_components() -> dict[str, object]:
    return {
        "candidates": [
            {
                "candidate_id": "cand_a",
                "components": {
                    "global_planner": "astar",
                    "local_controller": "dwa",
                    "local_controller_config": "dwa_coarse",
                },
            },
            {
                "candidate_id": "cand_b",
                "components": {
                    "global_planner": "rrtstar",
                    "local_controller": "dwa",
                    "local_controller_config": "dwa_coarse",
                },
            },
        ]
    }


def built(**overrides):  # type: ignore[no-untyped-def]
    fields = {
        "run_id": "warehouse_a_v1_selection_abc",
        "source_manifest_ref": "manifest.json",
        "source_manifest_checksum": "a" * 64,
        "detector_version": DETECTOR_VERSION,
        "knowledge_base_version": KNOWLEDGE_BASE_VERSION,
        "tool_catalog_version": TOOL_CATALOG_VERSION,
        "task_profile_id": "warehouse_a_v1",
        "robot_radius_m": 0.26,
        "inflation_margin_m": 0.11,
        "decision_status": "CLEAR_RECOMMENDATION",
        "waterfall": waterfall(),
        "report": report_with_components(),
        "traces": [
            straight_trace("cand_a", "ep-001"),
            straight_trace("cand_b", "ep-001"),
        ],
        "episodes_total": 1,
        "evidence_class": "production",
    }
    fields.update(overrides)
    return build_scoring_packet(**fields)  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# The detectors, over the episodes that were looked at
# --------------------------------------------------------------------------


def test_the_denominator_is_episodes_looked_at_not_episodes_parsed() -> None:
    """Counting the ones that arrived makes a pattern look universal."""
    observations, skipped = observations_from_traces(
        [stalled_trace("cand_a", "ep-001")], episodes_total=30
    )
    assert not skipped
    for observation in observations:
        assert observation.episodes_total == 30


def test_a_trace_the_detectors_refuse_is_reported_not_dropped() -> None:
    """One fewer episode behind every rate in the packet."""
    ragged = EpisodeTrace(
        candidate_id="cand_a",
        episode_context_id="ep-009",
        columns={"t": [0.0, 0.1], "x": [0.0], "y": [0.0, 0.0]},
    )
    observations, skipped = observations_from_traces([ragged], episodes_total=1)
    assert observations == ()
    assert skipped and "ep-009" in skipped[0]


def test_a_clean_run_produces_no_sightings_and_that_is_an_answer() -> None:
    """Empty, and empty is the finding.

    Asserted as an equality rather than with ``all(...)`` over the
    result: ``all()`` of an empty sequence is true, so the first version
    of this passed without checking anything — the same vacuous shape
    the sidecar's no-path test had.
    """
    observations, skipped = observations_from_traces(
        [straight_trace("cand_a", "ep-001")], episodes_total=1
    )
    assert not skipped
    assert observations == ()


def test_a_run_with_a_stall_does_produce_a_sighting() -> None:
    """The other half of the pair, so the one above cannot pass by vacancy."""
    observations, skipped = observations_from_traces(
        [stalled_trace("cand_a", "ep-001")], episodes_total=1
    )
    assert not skipped
    assert any(observation.episodes_seen > 0 for observation in observations)


# --------------------------------------------------------------------------
# The lattice
# --------------------------------------------------------------------------


def test_the_lattice_is_read_for_every_detection_type() -> None:
    """A pattern on neither candidate is a finding, not an absence."""
    packet = built().packet
    assert {finding.detection_type for finding in packet.lattice} == set(LATTICE_TYPES)


def test_one_candidate_is_not_a_lattice_and_says_so() -> None:
    findings, refusals = lattice_from([], [])
    assert findings == ()
    assert refusals and "fewer than two candidates" in refusals[0]


def test_a_run_that_never_recorded_components_has_no_packet_at_all() -> None:
    """Not a thinner packet — none.

    A packet explains a *comparison*, and the comparison is the pair of
    component stacks. Without them there is nothing to be a case about,
    and the builder says so rather than emitting a packet whose lattice
    is empty for a reason nobody records. The caller catches this and
    keeps the run.
    """
    with pytest.raises((CasePacketRefusal, ValidationError), match="needs two candidates"):
        built(report={"candidates": [{"candidate_id": "cand_a"}]})


# --------------------------------------------------------------------------
# What the packet says about what it could not build
# --------------------------------------------------------------------------


def test_a_run_without_a_recorded_inflation_carries_no_width_at_all() -> None:
    """A clearance argument on a guessed margin is another costmap."""
    outcome = built(inflation_margin_m=None)
    assert outcome.packet.task.robot.required_passage_width_m is None
    assert any("required_passage_width_m" in note for note in outcome.omissions)


def test_the_width_is_derived_the_way_the_checker_validates_it() -> None:
    """``2 * (radius + margin)`` — a width compared against a width."""
    packet = built().packet
    assert packet.task.robot.required_passage_width_m == pytest.approx(0.74)
    assert packet.task.robot.derived_passage_width_m == pytest.approx(0.74)


def test_a_run_with_no_traces_says_so_rather_than_looking_clean() -> None:
    outcome = built(traces=[])
    assert outcome.packet.observations == ()
    assert any("no episode traces" in note for note in outcome.omissions)


def test_a_report_with_no_per_episode_utility_omits_the_exemplars() -> None:
    outcome = built()
    assert outcome.packet.representative_episodes is None
    assert any("representative_episodes" in note for note in outcome.omissions)


def test_the_packet_always_carries_the_platforms_standing_gaps() -> None:
    packet = built().packet
    assert packet.known_unknowns
    blocked = {kind for gap in packet.known_unknowns for kind in gap.blocks_claim_types}
    assert "perception_attribution" in blocked


def test_the_narrow_gap_detector_needs_a_measured_width_to_run() -> None:
    """With route features and a width, the detector is at least reachable."""
    observations, _skipped = observations_from_traces(
        [stalled_trace("cand_a", "ep-001")],
        episodes_total=1,
        route_features={
            "cand_a": RouteFeatures(
                narrowest_passage_m=0.50,
                narrowest_at_progress_m=1.0,
                narrowest_lower_bound_m=0.50,
                obstacle_density=0.2,
                density_band_m=1.0,
                route_length_m=6.0,
                unmeasured_samples=0,
                samples_limited_by_coverage=0,
            )
        },
        required_passage_width_m=0.74,
    )
    assert {observation.type for observation in observations}


# --------------------------------------------------------------------------
# The block, and reading it back
# --------------------------------------------------------------------------


def test_the_block_carries_the_omissions_beside_the_packet() -> None:
    """Whoever asks why an explanation is thin is reading the report."""
    block = packet_block(built(traces=[]))
    assert block["packet"]
    assert any("no episode traces" in note for note in block["omissions"])


def test_a_packet_round_trips_through_the_report_block() -> None:
    outcome = built()
    restored = packet_from_block(packet_block(outcome))
    assert restored == outcome.packet


def test_a_run_scored_before_e41_is_refused_rather_than_emptied() -> None:
    """ "No packet" and "nobody could explain this run" are different facts."""
    with pytest.raises(CasePacketRefusal, match="scored before E4.1"):
        packet_from_block({})


def test_the_detector_version_is_owned_by_the_module_whose_rules_it_names() -> None:
    """Every caller used to type the string, which is a version that drifts."""
    assert built().packet.header.detector_version == DETECTOR_VERSION


def test_a_build_that_failed_is_not_reported_as_an_old_run() -> None:
    """One line from losing the distinction.

    The block being present means the builder ran. Saying "scored before
    E4.1" would send somebody to re-run a sweep when the reason they
    need is already in the omissions.
    """
    with pytest.raises(CasePacketRefusal, match="the build failed"):
        packet_from_block({"packet": None, "omissions": ["detector exploded"]})


def test_a_build_that_failed_without_a_reason_still_says_which_fact_it_is() -> None:
    with pytest.raises(CasePacketRefusal, match="no reason recorded"):
        packet_from_block({"packet": None, "omissions": []})
