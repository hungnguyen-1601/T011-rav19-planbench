"""E6a — the two mechanism checks the platform can actually run.

What these guard: a check reports only what its evidence supports; a
lower bound never becomes a width; an association is refused where the
data cannot rank; the two checks that need the planning-input sidecar
say so rather than approximating; and a host result is bound to an
admitted request the same way the mock's was.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from planbench_decision.objectives import PREFERENCE_PROFILES
from planbench_explanation.case_packet import (
    DecisionFacts,
    RobotFacts,
    TaskFacts,
    build_case_packet,
)
from planbench_explanation.catalog import TOOL_CATALOG, TOOL_CATALOG_VERSION
from planbench_explanation.checkers import (
    ASSOCIATION_RHO,
    MINIMUM_EPISODES_FOR_ASSOCIATION,
    CheckerRefusal,
    EpisodeSearchCost,
    GapEvidence,
    LatencyEvidence,
    check_gap_vs_footprint,
    check_latency_vs_expanded_nodes,
)
from planbench_explanation.contrast import CandidateComponents
from planbench_explanation.host import (
    AWAITING_SIDECAR,
    EvidenceIdentity,
    EvidenceMismatch,
    InMemoryEvidenceSink,
    PacketEvidence,
    ReportEvidence,
    ToolHost,
    identity_of,
)
from planbench_explanation.knowledge import KNOWLEDGE_BASE_VERSION
from planbench_explanation.ledger import HypothesisProposal
from planbench_explanation.map_features import RouteFeatures
from planbench_explanation.protocol import AnalysisRequest, ToolRequest
from planbench_explanation.versioning import ExplanationArtifactHeader
from planbench_explanation.waterfall import (
    ObjectiveLevels,
    UtilityDrillDown,
    Waterfall,
    WaterfallBar,
    WaterfallProfile,
)

BUILD = "git:" + "b" * 40
BUNDLE_ID = "bundle-017"


# --------------------------------------------------------------------------
# gap_vs_footprint
# --------------------------------------------------------------------------


def features(
    narrowest: float | None = 0.68, lower_bound: float = 0.68, **overrides
) -> RouteFeatures:  # type: ignore[no-untyped-def]
    fields = {
        "narrowest_passage_m": narrowest,
        "narrowest_at_progress_m": 4.2 if narrowest is not None else None,
        "narrowest_lower_bound_m": lower_bound,
        "obstacle_density": 0.18,
        "density_band_m": 2.0,
        "route_length_m": 12.0,
        "unmeasured_samples": 0,
        "samples_limited_by_coverage": 0,
    }
    fields.update(overrides)
    return RouteFeatures(**fields)  # type: ignore[arg-type]


def gap(radius: float = 0.26, margin: float = 0.11, **overrides) -> GapEvidence:  # type: ignore[no-untyped-def]
    fields = {
        "region_id": "aisle_B7",
        "features": features(),
        "robot_radius_m": radius,
        "inflation_margin_m": margin,
        "required_passage_width_m": 2.0 * (radius + margin),
    }
    fields.update(overrides)
    return GapEvidence(**fields)  # type: ignore[arg-type]


def test_a_passage_narrower_than_the_configured_clearance_is_supported() -> None:
    outcome = check_gap_vs_footprint(gap())
    assert outcome.verdict == "supported"
    assert outcome.measurements["required_passage_width_m"] == pytest.approx(0.74)
    assert outcome.measurements["margin_m"] == pytest.approx(-0.06)


def test_a_width_is_never_compared_against_a_radius() -> None:
    """The unit bug, pinned.

    ``narrowest_passage_m`` is a corridor cross-section. A 0.26 m robot
    with an 0.11 m margin needs ``2 * 0.37 = 0.74`` m of corridor, not
    ``0.37``. The first version compared against the radius sum and a
    0.50 m doorway read as passable.
    """
    evidence = gap(features=features(0.50, 0.50))
    assert evidence.required_passage_width_m == pytest.approx(0.74)
    assert check_gap_vs_footprint(evidence).verdict == "supported"


def test_a_required_width_that_does_not_follow_from_the_parts_is_refused() -> None:
    """One definition in the platform, and the schema checks it is the one used."""
    with pytest.raises((CheckerRefusal, ValidationError), match="does not"):
        GapEvidence(
            region_id="aisle_B7",
            features=features(),
            robot_radius_m=0.26,
            inflation_margin_m=0.11,
            required_passage_width_m=0.37,
        )


def test_a_passage_that_clears_refutes_rather_than_going_quiet() -> None:
    """ "The geometry is fine" is a finding, and it kills a hypothesis."""
    outcome = check_gap_vs_footprint(gap(features=features(0.80, 0.80)))
    assert outcome.verdict == "refuted"
    assert outcome.measurements["margin_m"] == pytest.approx(0.06)
    assert "another cause" in outcome.note


def test_a_route_measured_only_on_one_side_yields_no_verdict() -> None:
    """A lower bound cannot show a passage is too narrow.

    ``0.30 m`` here is "at least 0.30 m" — the unmapped side may open
    into a hall — and the check refuses rather than comparing it against
    0.74 m and calling the passage impassable.
    """
    with pytest.raises(CheckerRefusal, match="lower bound"):
        check_gap_vs_footprint(gap(features=features(None, 0.30)))


def test_the_check_is_about_the_configuration_not_the_robot() -> None:
    """Same robot, same passage, different inflation: different answer."""
    assert check_gap_vs_footprint(gap(margin=0.11)).verdict == "supported"
    assert check_gap_vs_footprint(gap(margin=0.04)).verdict == "refuted"


# --------------------------------------------------------------------------
# latency_vs_expanded_nodes
# --------------------------------------------------------------------------


def costs(pairs: list[tuple[int, float]]) -> LatencyEvidence:
    return LatencyEvidence(
        candidate_id="cand_a",
        episodes=tuple(
            EpisodeSearchCost(
                episode_context_id=f"ep-{index:03d}",
                expanded_nodes=expanded,
                planner_latency_ms=latency,
            )
            for index, (expanded, latency) in enumerate(pairs)
        ),
    )


def rising(n: int = 10) -> list[tuple[int, float]]:
    return [(100 * (index + 1), 5.0 * (index + 1)) for index in range(n)]


def test_searches_and_their_cost_moving_together_is_supported() -> None:
    outcome = check_latency_vs_expanded_nodes(costs(rising()))
    assert outcome.verdict == "supported"
    assert outcome.measurements["spearman_rho"] == pytest.approx(1.0)
    assert outcome.measurements["n_episodes"] == 10.0


def test_an_association_that_is_not_there_is_refuted_not_left_open() -> None:
    """The question was "do these move together"; "no" is an answer."""
    zigzag = [(100, 50.0), (200, 10.0), (300, 45.0), (400, 12.0)] * 3
    outcome = check_latency_vs_expanded_nodes(costs(zigzag))
    assert outcome.verdict == "refuted"
    assert outcome.measurements["spearman_rho"] < ASSOCIATION_RHO


def test_moving_together_the_other_way_is_still_not_the_proposition() -> None:
    """Larger searches finishing *faster* refutes it as surely as noise does.

    The rule is one-sided on purpose: the proposition says expansions and
    latency rise together, and a strong negative rank correlation is
    evidence against that, not a strong association in its favour.
    """
    falling = [(100 * (index + 1), 50.0 - 4.0 * index) for index in range(10)]
    outcome = check_latency_vs_expanded_nodes(costs(falling))
    assert outcome.measurements["spearman_rho"] == pytest.approx(-1.0)
    assert outcome.verdict == "refuted"


def test_a_handful_of_episodes_is_a_shape_not_an_association() -> None:
    with pytest.raises(CheckerRefusal, match="at least"):
        check_latency_vs_expanded_nodes(costs(rising(MINIMUM_EPISODES_FOR_ASSOCIATION - 1)))


def test_a_constant_column_is_no_measurement_rather_than_a_weak_one() -> None:
    flat = [(400, 5.0 * (index + 1)) for index in range(10)]
    with pytest.raises(CheckerRefusal, match="same expanded-node"):
        check_latency_vs_expanded_nodes(costs(flat))


def test_one_runaway_episode_does_not_carry_the_correlation() -> None:
    """Spearman rather than Pearson, and this is what that buys."""
    with_outlier = [*rising(9), (100_000, 1.0)]
    outcome = check_latency_vs_expanded_nodes(costs(with_outlier))
    assert outcome.measurements["spearman_rho"] < 1.0
    assert outcome.verdict == "supported"


def test_an_episode_counted_twice_is_refused() -> None:
    with pytest.raises((CheckerRefusal, ValidationError), match="twice"):
        LatencyEvidence(
            candidate_id="cand_a",
            episodes=(
                EpisodeSearchCost(
                    episode_context_id="ep-001", expanded_nodes=100, planner_latency_ms=5.0
                ),
                EpisodeSearchCost(
                    episode_context_id="ep-001", expanded_nodes=200, planner_latency_ms=9.0
                ),
            ),
        )


# --------------------------------------------------------------------------
# The host
# --------------------------------------------------------------------------


def header() -> ExplanationArtifactHeader:
    return ExplanationArtifactHeader.for_current_code(
        source_manifest_ref="runs/2026-08-19/abc/manifest.json",
        source_manifest_checksum="a" * 64,
        detector_version="0.1.0",
        knowledge_base_version=KNOWLEDGE_BASE_VERSION,
        tool_catalog_version=TOOL_CATALOG_VERSION,
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
        seed=0,
        n_resamples=1000,
    )


def stack(candidate_id: str, global_planner: str = "astar") -> CandidateComponents:
    return CandidateComponents(
        candidate_id=candidate_id,
        global_planner=global_planner,
        local_controller="dwa",
        local_controller_config="dwa_coarse",
    )


AVAILABLE = frozenset(
    {
        "map_checksum",
        "region_geometry",
        "robot_footprint",
        "inflation_parameters",
        "inflation_implementation_version",
        "episode_expanded_nodes",
        "episode_latency",
    }
)


def analysis(**overrides) -> AnalysisRequest:  # type: ignore[no-untyped-def]
    packet = build_case_packet(
        run_id="run_017",
        header=header(),
        task=TaskFacts(
            task_profile_id="warehouse_a_v1",
            robot=RobotFacts(radius_m=0.26, inflation_margin_m=0.11, required_passage_width_m=0.74),
        ),
        candidates=[stack("cand_a"), stack("cand_b", "rrtstar")],
        decision=DecisionFacts(status="CLEAR_RECOMMENDATION", waterfall=waterfall()),
    )
    fields = {
        "analysis_run_id": "analysis-1",
        "analyst_bundle_id": BUNDLE_ID,
        "packet": packet,
        "catalog": TOOL_CATALOG,
        "available_evidence": AVAILABLE,
    }
    fields.update(overrides)
    return AnalysisRequest(**fields)  # type: ignore[arg-type]


def report(n: int = 10, *, expanded: bool = True, tree: bool = False) -> dict[str, object]:
    """Episode rows in the shape scoring writes them."""
    rows = [
        {
            "episode_context_id": f"ep-{index:03d}",
            "peak_search_nodes": 100 * (index + 1) if expanded else 0,
            "peak_tree_nodes": 40 * (index + 1) if tree else 0,
            "p99_latency_ms": 5.0 * (index + 1),
        }
        for index in range(n)
    ]
    return {
        "identity": {"task_profile_id": "warehouse_a_v1"},
        "candidates": [
            {"candidate_id": "cand_a", "episodes": rows},
            {"candidate_id": "cand_b", "episodes": rows},
        ],
    }


def host_for(evidence, **overrides) -> ToolHost:  # type: ignore[no-untyped-def]
    live = analysis(**overrides)
    running = ToolHost(live, evidence, implementation_ref=BUILD, sink=InMemoryEvidenceSink())
    running.session.declare(
        (
            HypothesisProposal(
                hypothesis_id="hyp-1",
                hypothesis_statement="the aisle is closed by inflation",
                proposition_type="geometric_infeasibility",
                proposed_subject="costmap_inflation",
            ),
        )
    )
    return running


def ask(running: ToolHost, tool_id: str, arguments: dict[str, object], **overrides) -> ToolRequest:  # type: ignore[no-untyped-def]
    live = running.analysis
    fields = {
        "request_id": "req-001",
        "analysis_run_id": live.analysis_run_id,
        "case_packet_checksum": live.case_packet_checksum,
        "tool_catalog_version": live.catalog.catalog_version,
        "analyst_bundle_id": live.analyst_bundle_id,
        "sequence": 1,
        "tool_id": tool_id,
        "tool_version": TOOL_CATALOG.card(tool_id, "2.0.0").tool_version
        if tool_id in ("gap_vs_footprint", "latency_vs_expanded_nodes")
        else "1.0.0",
        "hypothesis_id": "hyp-1",
        "arguments": arguments,
    }
    fields.update(overrides)
    return ToolRequest(**fields)  # type: ignore[arg-type]


def evidence_for(**overrides) -> ReportEvidence:  # type: ignore[no-untyped-def]
    fields = {
        "report": report(),
        "packet": analysis().packet,
        "regions": {("cand_a", "aisle_B7"): features()},
    }
    fields.update(overrides)
    return ReportEvidence(fields.pop("report"), **fields)  # type: ignore[arg-type]


def test_the_host_runs_the_gap_check_and_signs_the_result() -> None:
    running = host_for(evidence_for())
    result = running.call(
        ask(running, "gap_vs_footprint", {"candidate_id": "cand_a", "region_id": "aisle_B7"})
    )
    assert result.execution_status == "completed"
    assert result.proposition_verdict == "supported"
    assert result.measurements["margin_m"] == pytest.approx(-0.06)
    assert result.implementation_ref == BUILD
    assert result.references[0].kind == "map_region"
    assert running.session.checker_results[0].tool_id == "gap_vs_footprint"


def test_the_host_stamps_the_refusals_the_card_carries() -> None:
    running = host_for(evidence_for())
    result = running.call(
        ask(running, "gap_vs_footprint", {"candidate_id": "cand_a", "region_id": "aisle_B7"})
    )
    card = TOOL_CATALOG.card("gap_vs_footprint", "2.0.0")
    assert set(result.unsupported_inferences) == set(
        card.proposition_policy.forbidden_inference_types
    )


def test_a_region_the_run_never_measured_is_not_checkable() -> None:
    running = host_for(evidence_for())
    result = running.call(
        ask(running, "gap_vs_footprint", {"candidate_id": "cand_a", "region_id": "aisle_B9"})
    )
    assert result.execution_status == "not_checkable"
    assert result.failure_code == "region_not_resolved"
    assert result.measurements == {}


def test_a_one_sided_measurement_comes_back_as_ambiguous_geometry() -> None:
    """Not as a narrow passage, which is the conclusion it cannot support."""
    running = host_for(evidence_for(regions={("cand_a", "aisle_B7"): features(None, 0.30)}))
    result = running.call(
        ask(running, "gap_vs_footprint", {"candidate_id": "cand_a", "region_id": "aisle_B7"})
    )
    assert result.failure_code == "ambiguous_passage_geometry"


def test_the_host_runs_the_latency_check_off_the_report() -> None:
    running = host_for(evidence_for())
    result = running.call(ask(running, "latency_vs_expanded_nodes", {"candidate_id": "cand_a"}))
    assert result.execution_status == "completed"
    assert result.measurements["n_episodes"] == 10.0
    assert result.measurements["spearman_rho"] == pytest.approx(1.0)


def test_a_run_that_never_recorded_expansions_says_so() -> None:
    """No populated node column is not a search that expanded nothing."""
    running = host_for(evidence_for(report=report(expanded=False)))
    result = running.call(ask(running, "latency_vs_expanded_nodes", {"candidate_id": "cand_a"}))
    assert result.execution_status == "not_checkable"
    assert result.failure_code == "expansion_counts_missing"


def test_too_few_episodes_is_reported_as_such() -> None:
    running = host_for(evidence_for(report=report(4)))
    result = running.call(ask(running, "latency_vs_expanded_nodes", {"candidate_id": "cand_a"}))
    assert result.failure_code == "insufficient_episodes"


def test_nothing_is_awaiting_the_sidecar_any_more() -> None:
    """Both replay checks landed in E6b.

    ``replay_global_plan`` when E4.5 gave it inputs and a planner could
    be injected; ``rrt_convergence`` when its evidence grew the run's own
    seed set. The set stays as a named empty one: a tool with no branch
    still answers ``checker_not_implemented``, and the next card added
    lands in exactly that situation.
    """
    assert frozenset() == AWAITING_SIDECAR


def test_a_host_without_a_planner_cannot_replay_and_says_which_half_is_missing() -> None:
    """Not a failure of the run: this host was built without a planner."""
    running = host_for(
        evidence_for(),
        available_evidence=AVAILABLE
        | {"planning_inputs", "planner_parameters", "planner_implementation_version"},
    )
    assert running.replay_planner is None
    result = running.call(
        ask(
            running,
            "replay_global_plan",
            {"candidate_id": "cand_a", "episode_context_id": "ep-001", "attempt_index": 1},
        )
    )
    assert result.execution_status == "not_checkable"
    assert result.failure_code == "checker_not_implemented"


def test_a_host_with_no_evidence_source_answers_nothing_and_invents_nothing() -> None:
    running = host_for(PacketEvidence(analysis().packet))
    result = running.call(
        ask(running, "gap_vs_footprint", {"candidate_id": "cand_a", "region_id": "aisle_B7"})
    )
    assert result.execution_status == "not_checkable"
    assert result.measurements == {}


def test_a_result_still_cannot_exist_without_an_admitted_request() -> None:
    """The E5 gate is unchanged by there being a real checker behind it."""
    from planbench_explanation.protocol import ProtocolRejection, ToolSession

    running = host_for(evidence_for())
    result = running.call(
        ask(running, "gap_vs_footprint", {"candidate_id": "cand_a", "region_id": "aisle_B7"})
    )
    stranger = ToolSession(analysis())
    with pytest.raises(ProtocolRejection) as caught:
        stranger.record(result)
    assert caught.value.code == "unknown_request"


def test_the_latency_card_promises_only_what_the_trace_records() -> None:
    """HĐ-5 has planner latency per row and no expanded-node column.

    The first card said "ticks carrying larger expansions took longer",
    which cannot be computed from a frozen schema that does not record
    expansions per tick. The card now says across episodes, and the
    evidence it asks for is what scoring actually writes.
    """
    card = TOOL_CATALOG.card("latency_vs_expanded_nodes", "2.0.0")
    assert card.required_evidence == ("episode_expanded_nodes", "episode_latency")
    assert "n_episodes" in card.io.measurement_keys
    assert "n_replans" not in card.io.measurement_keys


def test_a_sampling_planner_is_ranked_on_its_tree_not_on_a_zero() -> None:
    running = host_for(evidence_for(report=report(expanded=False, tree=True)))
    result = running.call(ask(running, "latency_vs_expanded_nodes", {"candidate_id": "cand_a"}))
    assert result.execution_status == "completed"
    assert result.measurements["median_expanded_nodes"] > 0.0


def test_a_candidate_reporting_both_node_columns_is_not_guessed_at() -> None:
    """Grid frontier and sampling tree count different things.

    A candidate populating both is one this reader has no rule for, and
    picking a column would be a guess presented as a measurement.
    """
    running = host_for(evidence_for(report=report(expanded=True, tree=True)))
    result = running.call(ask(running, "latency_vs_expanded_nodes", {"candidate_id": "cand_a"}))
    assert result.execution_status == "not_checkable"
    assert result.failure_code == "expansion_counts_missing"


# --------------------------------------------------------------------------
# The source has to be about the packet
# --------------------------------------------------------------------------


def test_a_report_about_another_task_profile_is_refused() -> None:
    """Derived from the report, not declared beside it.

    The identity used to be a constructor argument, so a caller could
    hand over run B's report with run A's identity and pass the host's
    check. It stopped accidental miswiring and was not a trust boundary.
    """
    wrong = report()
    wrong["identity"] = {"task_profile_id": "some_other_profile"}
    with pytest.raises(EvidenceMismatch, match="task profile"):
        ReportEvidence(wrong, packet=analysis().packet)


def test_a_report_missing_a_candidate_the_packet_compares_is_refused() -> None:
    wrong = report()
    wrong["candidates"] = [{"candidate_id": "cand_z", "episodes": []}]
    with pytest.raises(EvidenceMismatch, match="no rows for"):
        ReportEvidence(wrong, packet=analysis().packet)


def test_a_host_refuses_a_source_bound_to_another_packet() -> None:
    other = analysis(
        packet=build_case_packet(
            run_id="run_099",
            header=header(),
            task=TaskFacts(
                task_profile_id="warehouse_a_v1",
                robot=RobotFacts(radius_m=0.26),
            ),
            candidates=[stack("cand_a"), stack("cand_b", "rrtstar")],
            decision=DecisionFacts(status="CLEAR_RECOMMENDATION", waterfall=waterfall()),
        )
    )
    with pytest.raises(EvidenceMismatch, match="different run"):
        ToolHost(
            analysis(),
            ReportEvidence(report(), packet=other.packet),
            implementation_ref=BUILD,
            sink=InMemoryEvidenceSink(),
        )


def test_what_the_report_claims_and_the_packet_cannot_confirm_is_labelled() -> None:
    """``run_uri`` and ``run_checksum`` have no counterpart to check against."""
    with_uri = report()
    with_uri["run_uri"] = "file://artifacts/runs/2026-08-19/whatever"
    with_uri["run_checksum"] = "b21b6d0d"
    source = ReportEvidence(with_uri, packet=analysis().packet)
    assert source.unverified_report_identity["run_uri"].endswith("whatever")


def test_the_identity_a_source_must_match_comes_off_the_packet() -> None:
    packet = analysis().packet
    identity = identity_of(packet)
    assert identity.run_id == packet.run_id
    assert identity.candidate_ids == {"cand_a", "cand_b"}
    assert isinstance(identity, EvidenceIdentity)


def test_the_robot_facts_a_check_uses_come_from_the_packet() -> None:
    """Two sources for one fact is one source too many."""
    packet = analysis().packet
    source = ReportEvidence(report(), packet=packet, regions={("cand_a", "aisle_B7"): features()})
    evidence = source.gap_evidence(candidate_id="cand_a", region_id="aisle_B7")
    assert evidence is not None
    assert evidence.robot_radius_m == packet.task.robot.radius_m
    assert evidence.required_passage_width_m == packet.task.robot.required_passage_width_m


def test_a_run_that_never_recorded_its_inflation_cannot_be_gap_checked() -> None:
    """Absent rather than assumed: a guessed margin is another costmap."""
    packet = build_case_packet(
        run_id="run_017",
        header=header(),
        task=TaskFacts(task_profile_id="warehouse_a_v1", robot=RobotFacts(radius_m=0.26)),
        candidates=[stack("cand_a"), stack("cand_b", "rrtstar")],
        decision=DecisionFacts(status="CLEAR_RECOMMENDATION", waterfall=waterfall()),
    )
    source = ReportEvidence(report(), packet=packet, regions={("cand_a", "aisle_B7"): features()})
    assert source.gap_evidence(candidate_id="cand_a", region_id="aisle_B7") is None


# --------------------------------------------------------------------------
# The artifact a result points at exists
# --------------------------------------------------------------------------


def test_a_completed_result_points_at_an_artifact_that_was_written() -> None:
    """A reference that resolves to nothing looks like diligence and is not."""
    sink = InMemoryEvidenceSink()
    live = analysis()
    running = ToolHost(live, evidence_for(), implementation_ref=BUILD, sink=sink)
    running.session.declare(
        (
            HypothesisProposal(
                hypothesis_id="hyp-1",
                hypothesis_statement="the aisle is closed by inflation",
                proposition_type="geometric_infeasibility",
                proposed_subject="costmap_inflation",
            ),
        )
    )
    result = running.call(
        ask(running, "gap_vs_footprint", {"candidate_id": "cand_a", "region_id": "aisle_B7"})
    )
    assert result.evidence_artifact_ref in sink.artifacts
    stored = sink.artifacts[result.evidence_artifact_ref]
    assert stored["measurements"] == result.measurements
    assert stored["run_id"] == live.packet.run_id


def test_the_checksum_on_a_result_is_of_what_was_stored(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from planbench_explanation.host import FileEvidenceSink
    from planbench_explanation.versioning import artifact_checksum

    sink = FileEvidenceSink(tmp_path / "artifacts" / "explain", relative_to=tmp_path)
    running = ToolHost(analysis(), evidence_for(), implementation_ref=BUILD, sink=sink)
    running.session.declare(
        (
            HypothesisProposal(
                hypothesis_id="hyp-1",
                hypothesis_statement="the aisle is closed by inflation",
                proposition_type="geometric_infeasibility",
                proposed_subject="costmap_inflation",
            ),
        )
    )
    result = running.call(
        ask(running, "gap_vs_footprint", {"candidate_id": "cand_a", "region_id": "aisle_B7"})
    )
    written = tmp_path / result.evidence_artifact_ref
    assert written.exists()
    assert artifact_checksum(json.loads(written.read_text(encoding="utf-8"))) == (
        result.evidence_checksum
    )


# --------------------------------------------------------------------------
# A changed contract is a changed version
# --------------------------------------------------------------------------


def test_the_catalog_version_moved_with_the_contract() -> None:
    """A bundle frozen against the old wire contract must stop matching."""
    assert TOOL_CATALOG_VERSION == "3.2.0"
    assert TOOL_CATALOG.card("latency_vs_expanded_nodes", "2.0.0").tool_version == "2.0.0"
    assert TOOL_CATALOG.card("gap_vs_footprint", "2.0.0").tool_version == "2.0.0"
    assert TOOL_CATALOG.card("rrt_convergence", "2.0.0").tool_version == "2.0.0"


def test_the_old_tool_version_is_gone_rather_than_quietly_reinterpreted() -> None:
    from planbench_explanation.tools import ToolNotInCatalog

    with pytest.raises(ToolNotInCatalog):
        TOOL_CATALOG.card("latency_vs_expanded_nodes", "1.0.0")


# --------------------------------------------------------------------------
# The sink writes inside the root, whatever the analyst calls its request
# --------------------------------------------------------------------------


def test_a_request_id_cannot_walk_out_of_the_artifact_root(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """It is analyst-supplied and it used to be pasted into a path."""
    from planbench_explanation.host import FileEvidenceSink

    sink = FileEvidenceSink(tmp_path / "root", relative_to=tmp_path)
    stored = sink.store(tool_id="gap_vs_footprint", request_id="../../outside", payload={"x": 1})
    written = tmp_path / stored.artifact_ref
    assert written.resolve().is_relative_to((tmp_path / "root").resolve())
    assert not (tmp_path.parent / "outside.json").exists()


def test_the_request_id_survives_inside_the_artifact_even_though_the_name_is_hashed(
    tmp_path,
) -> None:  # type: ignore[no-untyped-def]
    from planbench_explanation.host import FileEvidenceSink

    sink = FileEvidenceSink(tmp_path, relative_to=tmp_path)
    stored = sink.store(tool_id="gap_vs_footprint", request_id="req-001", payload={"x": 1})
    body = json.loads((tmp_path / stored.artifact_ref).read_text(encoding="utf-8"))
    assert body["request_id"] == "req-001"


def test_a_protocol_request_id_is_bounded_and_printable() -> None:
    """Defence in depth: a value that cannot be a path in the first place."""
    live = analysis()
    with pytest.raises(ValidationError):
        ask(
            ToolHost(live, evidence_for(), implementation_ref=BUILD, sink=InMemoryEvidenceSink()),
            "gap_vs_footprint",
            {"candidate_id": "cand_a", "region_id": "aisle_B7"},
            request_id="../../outside",
        )


def test_a_host_will_not_default_to_a_sink_that_dies_with_it() -> None:
    """``memory://`` outliving the dict it points into is a dangling pointer."""
    with pytest.raises(TypeError):
        ToolHost(analysis(), evidence_for(), implementation_ref=BUILD)  # type: ignore[call-arg]
