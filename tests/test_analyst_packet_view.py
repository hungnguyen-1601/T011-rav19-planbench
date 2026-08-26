"""A1 — the packet, read once, as facts that can be pointed at.

Three things are being held here. That the same packet reads the same
way every time, because a cache key and a prompt checksum are both
statements about bytes. That a packet written by another build is
refused rather than half-understood. And that every ref the model-free
floor already emits resolves in this index — the guard's first rule
drops a proposal whose citation does not resolve, so an index that
disagreed with the floor would score the floor as fabricating.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from planbench_analyst.packet_view import Fact, PacketViewRefusal, build_packet_view
from planbench_decision.objectives import PREFERENCE_PROFILES
from planbench_explanation.case_packet import (
    CandidateMeasurements,
    CasePacketRefusal,
    DecisionFacts,
    GateOutcome,
    MeasuredValue,
    RobotFacts,
    TaskFacts,
    build_case_packet,
)
from planbench_explanation.catalog import TOOL_CATALOG, TOOL_CATALOG_VERSION
from planbench_explanation.contrast import CandidateComponents, ContrastFinding
from planbench_explanation.detectors import Observation
from planbench_explanation.exemplars import Exemplar, ExemplarSet
from planbench_explanation.integration import TYPICAL_AVAILABLE_EVIDENCE, reference_analyst
from planbench_explanation.knowledge import KNOWLEDGE_BASE_VERSION
from planbench_explanation.map_features import RouteFeatures
from planbench_explanation.protocol import AnalysisRequest
from planbench_explanation.versioning import ExplanationArtifactHeader
from planbench_explanation.waterfall import (
    ObjectiveLevels,
    UtilityDrillDown,
    Waterfall,
    WaterfallBar,
    WaterfallProfile,
)

RUN_ID = "run_a1"


def header(**overrides: str) -> ExplanationArtifactHeader:
    fields: dict[str, str] = {
        "source_manifest_ref": "runs/2026-08-26/abc/manifest.json",
        "source_manifest_checksum": "a" * 64,
        "detector_version": "0.1.0",
        "knowledge_base_version": KNOWLEDGE_BASE_VERSION,
        "tool_catalog_version": TOOL_CATALOG_VERSION,
    }
    fields.update(overrides)
    return ExplanationArtifactHeader.for_current_code(**fields)  # type: ignore[arg-type]


def stack(candidate_id: str, global_planner: str = "astar") -> CandidateComponents:
    return CandidateComponents(
        candidate_id=candidate_id,
        global_planner=global_planner,
        local_controller="dwa",
        local_controller_config="dwa_coarse",
    )


def waterfall() -> Waterfall:
    weights = PREFERENCE_PROFILES["kho_ban_dem"]
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
    levels = tuple(
        ObjectiveLevels(objective=name, set_level=0.5, episode_mean=0.5)
        for name in ("U_R", "U_S", "U_E", "U_C")
    )
    return Waterfall(
        candidate_a="cand_a",
        candidate_b="cand_b",
        profile=WaterfallProfile(kind="canonical", base_profile="kho_ban_dem", weights=weights),
        n_episodes=30,
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
        seed=7,
        n_resamples=1000,
    )


def observation(kind: str = "narrow_gap_refusal") -> Observation:
    return Observation(
        type=kind,  # type: ignore[arg-type]
        candidate_id="cand_a",
        episodes_seen=9,
        episodes_total=30,
        typical={"margin_m": -0.06},
        worst_episode_context_id="ep-004",
    )


def exemplars(*episode_ids: str) -> ExemplarSet:
    roles = ("typical", "strongest_for_winner", "strongest_for_runnerup", "safety_critical")
    chosen = list(episode_ids) + [f"ep-{index:03d}" for index in range(len(episode_ids), 4)]
    return ExemplarSet(
        candidate_a="cand_a",
        candidate_b="cand_b",
        n_episodes=30,
        exemplars=tuple(
            Exemplar(
                role=role,  # type: ignore[arg-type]
                episode_context_id=episode_id,
                delta_utility=-0.01 * index,
                criterion=-0.01 * index,
            )
            for index, (role, episode_id) in enumerate(zip(roles, chosen, strict=True))
        ),
    )


def packet(**overrides):  # type: ignore[no-untyped-def]
    fields = {
        "run_id": RUN_ID,
        "header": header(),
        "task": TaskFacts(
            task_profile_id="warehouse_a_v1",
            robot=RobotFacts(radius_m=0.26, required_passage_width_m=0.74),
        ),
        "candidates": [stack("cand_a"), stack("cand_b", "rrtstar")],
        "decision": DecisionFacts(status="CLEAR_RECOMMENDATION", waterfall=waterfall()),
    }
    fields.update(overrides)
    return build_case_packet(**fields)  # type: ignore[arg-type]


def view(**overrides):  # type: ignore[no-untyped-def]
    return build_packet_view(packet(**overrides), tool_catalog_version=TOOL_CATALOG_VERSION)


# --------------------------------------------------------------------------
# Determinism
# --------------------------------------------------------------------------


def test_the_same_packet_reads_as_the_same_string() -> None:
    first = view(observations=[observation()])
    second = view(observations=[observation()])
    assert first.serialize() == second.serialize()
    assert first.checksum == second.checksum


def test_a_packet_that_differs_by_one_measurement_reads_differently() -> None:
    """Otherwise the checksum is decoration: it would key a cache that
    served the answer for one run to another."""
    louder = observation()
    quieter = Observation(**{**louder.model_dump(), "typical": {"margin_m": -0.09}})
    assert view(observations=[louder]).checksum != view(observations=[quieter]).checksum


# --------------------------------------------------------------------------
# What it refuses to read
# --------------------------------------------------------------------------


def test_a_packet_from_another_detector_build_is_refused() -> None:
    with pytest.raises(PacketViewRefusal, match="detector_version"):
        view(header=header(detector_version="0.0.9"))


def test_the_catalog_version_is_the_one_the_caller_names() -> None:
    """The bundle names the catalog a graded round runs against.

    Reading it from the catalog module instead would make this check
    agree with itself while disagreeing with the bundle being graded —
    which is the one disagreement it exists to catch.
    """
    with pytest.raises(PacketViewRefusal, match="tool_catalog_version"):
        build_packet_view(packet(), tool_catalog_version="99.0.0")


def test_every_mismatch_is_named_at_once() -> None:
    """A refusal that stops at the first field sends somebody round the
    loop twice for a packet that is two versions behind."""
    stale = header(detector_version="0.0.9", tool_catalog_version="1.0.0")
    with pytest.raises(PacketViewRefusal) as raised:
        view(header=stale)
    assert "detector_version" in str(raised.value)
    assert "tool_catalog_version" in str(raised.value)


# --------------------------------------------------------------------------
# What the index holds
# --------------------------------------------------------------------------


def test_an_observation_and_its_measurements_are_separate_refs() -> None:
    indexed = view(observations=[observation()])
    assert "obs:narrow_gap_refusal:cand_a" in indexed
    margin = indexed.fact("obs:narrow_gap_refusal:cand_a/margin_m")
    assert margin is not None
    assert margin.value == pytest.approx(-0.06)
    assert margin.unit == "m"
    assert margin.candidate_id == "cand_a"


def test_a_null_the_packet_declares_is_indexed_rather_than_dropped() -> None:
    """``inflation_margin_m`` holding null is the run saying it did not
    record one. An analyst that cannot cite that has to guess or go
    quiet about the one thing it knows is missing."""
    fact = view().fact("fact:robot.inflation_margin_m")
    assert fact is not None
    assert fact.value is None


def test_a_declared_gap_is_a_fact_with_no_value() -> None:
    fact = view().fact("unknown:latency_accounting_unavailable")
    assert fact is not None
    assert fact.value is None


def test_the_index_carries_no_structured_values() -> None:
    """A dict rendered into a ref is a number nobody can locate in the
    packet, which is what this index exists to prevent."""
    for fact in view(observations=[observation()]).facts:
        assert isinstance(fact.value, float | int | str | type(None))


# --------------------------------------------------------------------------
# What a fact is *about*
# --------------------------------------------------------------------------


def test_the_lattice_reading_is_reachable_by_the_component_it_names() -> None:
    finding = ContrastFinding(
        detection_type="stuck_cluster",
        verdict="supports_component_specific_attribution",
        subject="local_controller",
        pairs=(("cand_a", "cand_b"),),
        reason="only the stacks carrying this controller show the pattern",
    )
    indexed = view(lattice=[finding], observations=[observation("stuck_cluster")])
    reachable = indexed.refs_for_subject("local_controller")
    assert "contrast:stuck_cluster" in reachable
    # The stack fields are attributed to their component too (A3),
    # which is what lets rule 6 catch a claim about one component
    # leaning on a fact about another.
    assert "fact:candidate:cand_a.local_controller" in reachable


def test_a_measurement_the_packet_does_not_attribute_names_no_component() -> None:
    """The guard's sixth rule reads ``subject`` as a contradiction test,
    so a measurement that guessed a component would hand it a confident
    wrong answer. Saying who is responsible is the lattice's job."""
    indexed = view(observations=[observation()])
    assert indexed.fact("obs:narrow_gap_refusal:cand_a").subject is None  # type: ignore[union-attr]


def test_route_geometry_is_attributed_to_the_task() -> None:
    route = RouteFeatures(
        narrowest_passage_m=0.71,
        narrowest_at_progress_m=4.0,
        narrowest_lower_bound_m=0.71,
        obstacle_density=0.2,
        density_band_m=1.0,
        route_length_m=12.0,
        unmeasured_samples=0,
        samples_limited_by_coverage=0,
    )
    indexed = view(
        task=TaskFacts(
            task_profile_id="warehouse_a_v1",
            robot=RobotFacts(radius_m=0.26, required_passage_width_m=0.74),
            route=route,
        )
    )
    assert "fact:route.narrowest_passage_m" in indexed.refs_for_subject("task_geometry")


# --------------------------------------------------------------------------
# Identifiers, and the episode two roles can share
# --------------------------------------------------------------------------


def test_identifiers_hold_names_and_not_quantities() -> None:
    indexed = view(observations=[observation()])
    names = indexed.identifiers
    assert {"cand_a", "narrow_gap_refusal", "ep-004", "warehouse_a_v1"} <= names
    assert not any(name.replace("-", "").replace(".", "").isdigit() for name in names)


def test_two_roles_on_one_episode_do_not_fight_over_the_ref() -> None:
    """The ref names the episode, not the role, because that is the ref
    the floor and the replay window already use. A duplicate would be
    refused, so the roles are collected onto one fact instead."""
    indexed = view(representative_episodes=exemplars("ep-004", "ep-004"))
    fact = indexed.fact("episode:ep-004")
    assert fact is not None
    assert "typical" in fact.label and "strongest_for_winner" in fact.label


# --------------------------------------------------------------------------
# The floor has to survive its own citations
# --------------------------------------------------------------------------


def test_every_ref_the_floor_cites_resolves_in_the_index() -> None:
    """The guard drops a proposal whose citation does not resolve, and
    the floor is what the model is scored against. An index that did not
    hold the floor's refs would score the floor as fabricating."""
    built = packet(observations=[observation(), observation("stuck_cluster")])
    indexed = build_packet_view(built, tool_catalog_version=TOOL_CATALOG_VERSION)
    response = reference_analyst(
        AnalysisRequest(
            analysis_run_id="analysis-a1",
            analyst_bundle_id="bundle-a1",
            packet=built,
            catalog=TOOL_CATALOG,
            available_evidence=TYPICAL_AVAILABLE_EVIDENCE,
        )
    )
    assert response.proposals
    cited = [ref.ref for item in response.proposals for ref in item.supports + item.contradicts]
    assert cited
    unresolved = [ref for ref in cited if ref not in indexed]
    assert not unresolved, f"the floor cites {unresolved}, which this index does not hold"


def test_a_fact_is_frozen() -> None:
    fact = Fact(ref="fact:x", kind="fact", label="x", value=1.0, scope="run")
    with pytest.raises(ValueError, match="frozen"):
        fact.ref = "fact:y"  # type: ignore[misc]


# --------------------------------------------------------------------------
# M1 — what each candidate scored, and what each gate decided against
# --------------------------------------------------------------------------


def measured(candidate_id: str = "cand_a", **overrides):  # type: ignore[no-untyped-def]
    fields = {
        "candidate_id": candidate_id,
        "success_rate": MeasuredValue(value=0.7, unit="ratio", denominator=30),
        "latency_p99_ms": MeasuredValue(value=19.3, unit="ms", denominator=30),
        "min_clearance_m": MeasuredValue(value=0.2617, unit="m", denominator=30),
    }
    fields.update(overrides)
    return CandidateMeasurements(**fields)  # type: ignore[arg-type]


def test_a_rate_without_its_denominator_is_refused() -> None:
    """100% over five episodes and over three hundred are different
    claims wearing one number."""
    with pytest.raises((CasePacketRefusal, ValidationError), match="denominator"):
        MeasuredValue(value=1.0, unit="ratio")


def test_what_a_candidate_scored_is_reachable_by_ref() -> None:
    indexed = view(measurements=[measured()])
    rate = indexed.fact("fact:metric:cand_a.success_rate")
    assert rate is not None
    assert rate.value == pytest.approx(0.7)
    assert rate.unit == "ratio"
    assert rate.candidate_id == "cand_a"


def test_the_denominator_is_a_fact_of_its_own() -> None:
    """"Over thirty episodes" is the half of a rate that keeps it from
    being read as a promise, so a statement has to be able to cite it."""
    fact = view(measurements=[measured()]).fact("fact:metric:cand_a.success_rate.denominator")
    assert fact is not None
    assert fact.value == 30


def test_a_measurement_the_run_did_not_record_is_simply_absent() -> None:
    """Absent must not read as zero: an unmeasured collision count and a
    clean run are different sentences."""
    indexed = view(measurements=[measured(collisions=None)])
    assert indexed.fact("fact:metric:cand_a.collisions") is None
    assert "fact:metric:cand_a.success_rate" in indexed


def test_a_packet_recorded_before_m1_carries_no_measurement_facts() -> None:
    indexed = view()
    assert not [fact for fact in indexed.facts if fact.ref.startswith("fact:metric:")]


def test_a_gate_carries_the_number_it_was_decided_on() -> None:
    gated = DecisionFacts(
        status="GATE_ONLY",
        gate_rows=(
            GateOutcome(
                gate_id="G1_success",
                passed=False,
                threshold=0.95,
                value=0.7,
                unit="ratio",
                direction="at_least",
            ),
        ),
    )
    indexed = view(decision=gated)
    assert indexed.fact("fact:gate:G1_success.threshold").value == pytest.approx(0.95)  # type: ignore[union-attr]
    assert indexed.fact("fact:gate:G1_success.value").value == pytest.approx(0.7)  # type: ignore[union-attr]
    assert indexed.fact("fact:gate:G1_success.direction").value == "at_least"  # type: ignore[union-attr]


def test_an_old_gate_row_reads_as_pass_or_fail_and_says_nothing_more() -> None:
    """The old shape recorded whether a candidate was eliminated and
    nothing about how close it was; the null is that, said plainly."""
    legacy = DecisionFacts(status="GATE_ONLY", gates={"e1251e42a20b": {"passed": False}})
    indexed = view(decision=legacy)
    assert indexed.fact("fact:gate:e1251e42a20b.passed").value == "false"  # type: ignore[union-attr]
    assert indexed.fact("fact:gate:e1251e42a20b.threshold").value is None  # type: ignore[union-attr]
