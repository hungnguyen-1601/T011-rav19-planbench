"""W1.0 — the dev lane runs the platform's real host.

Until now ``InProcessHost`` wrapped ``MockToolHost``: real admission,
stub execution, ``checker_not_implemented`` to every mechanism check. A
lane measured against that measures whether the analyst *asks* for
verification and never whether asking gets it, and the two numbers were
being read as one.

What is held here is the whole path on a real fixture — proposal, real
checker, verdict, promotion — plus the three things the swap could
quietly have broken: fact queries, the one-source invariant between the
request and the host, and a refusal staying a refusal instead of taking
the round down with it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from test_analyst_runner import bundle

from planbench_analyst.round_host import (
    SIDECAR_EVIDENCE,
    in_process_round,
    platform_implementation_ref,
)
from planbench_explanation.catalog import TOOL_CATALOG
from planbench_explanation.host import ROUTE_REGION_ID, EvidenceMismatch, ReportEvidence
from planbench_explanation.integration import MockToolHost
from planbench_explanation.ledger import (
    EvidenceRef,
    HypothesisProposal,
    InvestigationRecord,
)
from planbench_explanation.packet_artifact import load_packet_artifact
from planbench_explanation.promotion import promote
from planbench_explanation.protocol import ToolRequest
from planbench_explanation.replay import check_replay_global_plan
from planbench_explanation.sidecar_writer import read_sidecar
from planbench_simulator.replay_planner import SimulatorReplayPlanner

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "golden" / "visible"

#: The episode every candidate of a planted world shares. It is a hash of
#: the conditions — task profile, mission, variant, seed — so two stacks
#: run against one world carry one id, which is why the sidecars are
#: filed per candidate.


def sidecars(case_id: str) -> dict[str, Path]:
    return {folder.name: folder for folder in (FIXTURES / case_id / "sidecar").iterdir()}


def _first_episode(case_id: str) -> str:
    """The episode this fixture's sidecars are filed under.

    Read from the fixture rather than pinned as a constant: the id is a
    hash of the conditions, so a world that gains a mission or moves a
    seed gets a new one — and a constant would then be testing a run
    nobody has.
    """
    directory = sidecars(case_id)["astar+dwa"]
    return next(directory.glob("*.planning_inputs.jsonl")).name.split(".")[0]


RRT_EPISODE = _first_episode("rrt-001")


def recorded_reference(case_id: str, candidate_id: str) -> str:
    """The build the sidecar names.

    A replay is a comparison against the run that was recorded, so the
    harness has to be the build that recorded it. Reading it here is not
    the harness echoing its own identity — the checker still asks the
    planner what it configured — it is a test saying which run these
    fixtures came from.
    """
    directory = sidecars(case_id)[candidate_id]
    header, _records = read_sidecar(next(directory.glob("*.planning_inputs.jsonl")))
    return header.execution_environment_ref


def round_for(case_id: str, **overrides):  # type: ignore[no-untyped-def]
    fields = {
        "catalog": TOOL_CATALOG,
        "analysis_run_id": f"analysis-{case_id}",
        "sidecar_directories": sidecars(case_id),
    }
    fields.update(overrides)
    return in_process_round(load_packet_artifact(FIXTURES, case_id), bundle(), **fields)  # type: ignore[arg-type]


def declare(  # type: ignore[no-untyped-def]
    prepared, proposition: str, subject: str, supports=("obs:narrow_gap_refusal:astar+dwa",)
):
    proposal = HypothesisProposal(
        hypothesis_id="hyp-1",
        hypothesis_statement="the aisle is closed to this footprint",
        proposition_type=proposition,  # type: ignore[arg-type]
        proposed_subject=subject,  # type: ignore[arg-type]
        supports=tuple(
            EvidenceRef(ref=ref, kind="observation" if ref.startswith("obs:") else "fact")
            for ref in supports
        ),
    )
    prepared.host.declare((proposal,))
    return proposal


def ask(prepared, tool_id: str, arguments: dict[str, object], sequence: int = 1) -> ToolRequest:  # type: ignore[no-untyped-def]
    analysis = prepared.analysis
    card = next(card for card in TOOL_CATALOG.cards if card.tool_id == tool_id)
    return ToolRequest(
        request_id=f"req-{sequence:03d}",
        analysis_run_id=analysis.analysis_run_id,
        case_packet_checksum=analysis.case_packet_checksum,
        tool_catalog_version=analysis.catalog.catalog_version,
        analyst_bundle_id=analysis.analyst_bundle_id,
        sequence=sequence,
        tool_id=tool_id,
        tool_version=card.tool_version,
        hypothesis_id="hyp-1",
        arguments=arguments,
    )


# --------------------------------------------------------------------------
# The path the phase exists for
# --------------------------------------------------------------------------


def test_a_proposal_reaches_a_real_checker_and_comes_back_verified() -> None:
    """Proposal, check, verdict, promotion — on a packet from a real run."""
    prepared = round_for("inflation-001")
    proposal = declare(
        prepared,
        "geometric_infeasibility",
        "costmap_inflation",
        supports=("obs:narrow_gap_refusal:astar+dwa",),
    )
    result = prepared.host.call(
        ask(
            prepared,
            "gap_vs_footprint",
            {"candidate_id": "astar+dwa", "region_id": ROUTE_REGION_ID},
        )
    )

    assert result.execution_status == "completed"
    assert result.proposition_verdict == "supported"
    # The measurement is the packet's own geometry, not a number the
    # checker invented: 0.25 m of passage against the 0.66 m this
    # configuration needs.
    assert result.measurements["passage_width_m"] == pytest.approx(0.25)
    assert result.measurements["margin_m"] < 0

    outcome = promote(
        claim_id="claim-1",
        proposal=proposal,
        record=InvestigationRecord(
            record_id="rec-1",
            proposal_ref=proposal.hypothesis_id,
            status="checked",
            checker_results=(result.as_checker_result(),),
        ),
        catalog=TOOL_CATALOG,
        statement="the refusals on astar+dwa are associated with the aisle being "
        "narrower than this configuration needs",
        scope="inflation_gap_closure, one planted episode per stack",
    )
    assert outcome.promoted, outcome.reasons
    assert outcome.claim is not None
    assert outcome.claim.level in ("verified", "associated")


def test_the_result_is_signed_by_a_build_and_not_by_the_stub() -> None:
    """``MockToolHost`` signed everything with sixty-four zeros."""
    prepared = round_for("inflation-001")
    declare(prepared, "geometric_infeasibility", "costmap_inflation")
    result = prepared.host.call(
        ask(
            prepared,
            "gap_vs_footprint",
            {"candidate_id": "astar+dwa", "region_id": ROUTE_REGION_ID},
        )
    )
    assert result.implementation_ref == platform_implementation_ref()
    assert result.implementation_ref != MockToolHost.IMPLEMENTATION_REF
    assert result.evidence_artifact_ref is not None
    assert not result.evidence_artifact_ref.startswith("mock://")


def test_a_region_the_packet_does_not_carry_is_refused_not_measured() -> None:
    prepared = round_for("inflation-001")
    declare(prepared, "geometric_infeasibility", "costmap_inflation")
    result = prepared.host.call(
        ask(prepared, "gap_vs_footprint", {"candidate_id": "astar+dwa", "region_id": "aisle_B7"})
    )
    assert result.execution_status == "not_checkable"
    assert result.failure_code == "region_not_resolved"
    assert result.measurements == {}


# --------------------------------------------------------------------------
# What the swap could have broken quietly
# --------------------------------------------------------------------------


def test_the_real_host_still_answers_a_fact_query_from_the_packet() -> None:
    """The stub host owned every fact query, and the real one owned none.

    Swapping the lane over without moving the reading would have made a
    round that verifies a mechanism report the packet's own known
    unknowns as unavailable.
    """
    prepared = round_for("inflation-001")
    declare(prepared, "geometric_infeasibility", "costmap_inflation")
    result = prepared.host.call(ask(prepared, "get_known_unknowns", {}))
    assert result.execution_status == "completed"
    assert result.measurements["n_known_unknowns"] > 0
    assert result.implementation_ref == platform_implementation_ref()


def test_the_request_and_the_host_are_built_from_one_packet() -> None:
    prepared = round_for("inflation-001")
    assert prepared.evidence_identity_checksum
    # Same packet on both sides: the host would refuse at construction
    # otherwise, which is the next test.
    assert prepared.analysis.packet.run_id == "inflation-001"


def test_a_host_about_another_run_is_refused_at_construction() -> None:
    other = load_packet_artifact(FIXTURES, "rrt-001").packet
    prepared = round_for("inflation-001")
    from planbench_analyst.round_host import InProcessHost

    with pytest.raises(EvidenceMismatch):
        InProcessHost(
            prepared.analysis,
            ReportEvidence.from_packet(other),
            implementation_ref=platform_implementation_ref(),
        )


# --------------------------------------------------------------------------
# The sidecar, and the checks it makes reachable
# --------------------------------------------------------------------------


def test_a_run_with_a_sidecar_is_allowed_to_be_asked_for_a_replay() -> None:
    """The two replay checks were unreachable on every run.

    ``TYPICAL_AVAILABLE_EVIDENCE`` never named what a sidecar holds, so
    admission refused ``rrt_convergence`` and ``replay_global_plan``
    whether or not the file existed — a menu offering a check nothing
    could reach, which an analyst reads as the platform having no answer
    rather than as itself not asking.
    """
    prepared = round_for(
        "rrt-001",
        replay_planner=SimulatorReplayPlanner(
            execution_environment_ref=recorded_reference("rrt-001", "rrtstar+dwa")
        ),
    )
    assert prepared.analysis.available_evidence >= SIDECAR_EVIDENCE
    declare(prepared, "sampling_budget_insufficiency", "global_planner")
    result = prepared.host.call(
        ask(
            prepared,
            "rrt_convergence",
            {
                "candidate_id": "rrtstar+dwa",
                "episode_context_id": RRT_EPISODE,
                "budget_multiplier": 4.0,
            },
        )
    )
    # It reaches the checker and the checker refuses on its own terms:
    # one planted episode is one seed, and a success rate over one draw
    # is an anecdote about that draw. The fixture owes this family a
    # multi-seed run; what W1.0 owed it was a way to be asked.
    assert result.execution_status == "not_checkable"
    assert result.failure_code == "seed_set_too_small"


def test_a_run_without_a_sidecar_is_not_offered_the_replay_checks() -> None:
    packet = load_packet_artifact(FIXTURES, "rrt-001").packet
    prepared = in_process_round(
        packet,  # a bare packet: no provenance, so no sidecar is assumed
        bundle(),
        catalog=TOOL_CATALOG,
        analysis_run_id="analysis-bare",
    )
    assert not (SIDECAR_EVIDENCE & prepared.analysis.available_evidence)


def test_each_candidate_reads_its_own_sidecar() -> None:
    """One flat directory would have the second stack overwrite the first.

    Both candidates of a planted world share an ``episode_context_id`` —
    that is what the id is, a hash of the conditions — so the file name
    is the same for both, and only the directory tells them apart.
    """
    evidence = ReportEvidence.from_packet(
        load_packet_artifact(FIXTURES, "rrt-001").packet,
        sidecar_directories=sidecars("rrt-001"),
    )
    for candidate in ("astar+dwa", "rrtstar+dwa"):
        replay = evidence.replay_evidence(
            candidate_id=candidate, episode_context_id=RRT_EPISODE, planning_attempt=1
        )
        assert replay is not None, candidate
        assert replay.snapshot.planner_name == candidate.split("+")[0]


def test_a_candidate_with_no_sidecar_directory_yields_no_evidence() -> None:
    evidence = ReportEvidence.from_packet(
        load_packet_artifact(FIXTURES, "rrt-001").packet,
        sidecar_directories={"astar+dwa": sidecars("rrt-001")["astar+dwa"]},
    )
    assert (
        evidence.replay_evidence(
            candidate_id="rrtstar+dwa", episode_context_id=RRT_EPISODE, planning_attempt=1
        )
        is None
    )


def test_the_recorded_query_replays_to_the_same_answer() -> None:
    """The sidecar is only worth writing if it reconstructs the run.

    The planner is handed **the build the sidecar names**, because that
    is the comparison the checker is making: this query, replayed by the
    build that ran it, reaches the same answer. Run from any later build
    the checker refuses, and it is right to — a fixture planted by one
    commit is not evidence about another.
    """
    reference = recorded_reference("rrt-001", "rrtstar+dwa")
    evidence = ReportEvidence.from_packet(
        load_packet_artifact(FIXTURES, "rrt-001").packet,
        sidecar_directories=sidecars("rrt-001"),
    )
    replay = evidence.replay_evidence(
        candidate_id="rrtstar+dwa", episode_context_id=RRT_EPISODE, planning_attempt=1
    )
    assert replay is not None
    outcome = check_replay_global_plan(
        replay,
        planner=SimulatorReplayPlanner(execution_environment_ref=reference),
    )
    assert outcome.verdict == "supported"
    assert outcome.measurements["attempts_replayed"] == outcome.measurements["attempts_recorded"]


# --------------------------------------------------------------------------
# A refusal must not take the round with it
# --------------------------------------------------------------------------


def test_a_code_the_card_never_declared_is_reported_not_raised() -> None:
    """``session.record`` refuses an unenumerated code, and it kills the round.

    The refusal is right — a code nobody declared cannot be told from a
    typo — but the analyst loses a whole analysis because a checker and
    its card disagree about a word. That disagreement is the platform's,
    so the host reports it as the platform's.
    """
    prepared = round_for("inflation-001")
    declare(prepared, "geometric_infeasibility", "costmap_inflation")
    card = next(card for card in TOOL_CATALOG.cards if card.tool_id == "gap_vs_footprint")
    assert "invented_code" not in card.failure_modes
    result = prepared.host._host._unavailable(
        card, ask(prepared, "gap_vs_footprint", {"candidate_id": "a", "region_id": "b"}),
        "invented_code",
    )
    assert result.failure_code == "host_internal_error"
