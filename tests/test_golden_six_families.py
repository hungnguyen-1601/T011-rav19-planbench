"""G6 — six families staged, and what each one is for.

Three families were blocked on the same thing: they are about a pattern
*across* episodes rather than inside one. An association between search
size and tick latency has no slope with a single point; a difference
that straddles zero needs a pair scored over shared episodes; and a run
whose traces nobody kept is a run, not a fixture with its files deleted.

What is held here is that each family's packet says what that family is
about, and that the ones which must be answered with "there is nothing
here" carry nothing to answer with.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_analyst_real_host import ask, declare, sidecars
from test_analyst_runner import bundle

from planbench_analyst.eval_spec import load_eval_spec
from planbench_analyst.round_host import in_process_round
from planbench_explanation.catalog import TOOL_CATALOG
from planbench_explanation.golden_fixtures import VISIBLE_SUITE
from planbench_explanation.packet_artifact import load_packet_artifact

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "golden" / "visible"
LABELS = ROOT / "fixtures" / "golden" / "labels" / "visible.json"

BUILT = ("inflation-001", "rrt-001", "dwa-001", "latency-001", "control-001", "gap-002")


def packet(case_id: str):  # type: ignore[no-untyped-def]
    return load_packet_artifact(FIXTURES, case_id).packet


def report(case_id: str):  # type: ignore[no-untyped-def]
    path = FIXTURES / case_id / "report.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


# --------------------------------------------------------------------------
# Six families, one case each
# --------------------------------------------------------------------------


def test_every_family_the_suite_names_now_has_a_packet() -> None:
    families = {case.family for case in VISIBLE_SUITE.cases}
    built = {packet(case_id).task.task_profile_id for case_id in BUILT}
    assert built == families


def test_six_families_is_not_twelve_cases() -> None:
    """The second variant of each family — the near-boundary and negative
    twins that separate a mechanism from its shape — is not built, and
    the preregistration reports counts rather than a rate below twelve."""
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    from plant_golden_runs import SECOND_VARIANTS_MISSING

    assert len(BUILT) == 6
    assert len(VISIBLE_SUITE.cases) == 12
    assert len(SECOND_VARIANTS_MISSING) == 6


def test_every_built_case_has_a_label(pytestconfig: pytest.Config) -> None:
    spec = load_eval_spec(LABELS)
    assert {item.case_id for item in spec.labels} == set(BUILT)


# --------------------------------------------------------------------------
# The three that needed episodes
# --------------------------------------------------------------------------


def test_the_latency_family_carries_a_search_that_varies() -> None:
    """One episode is one point, and a point has no slope."""
    rows = report("latency-001")["candidates"]
    grid = next(item for item in rows if item["candidate_id"] == "astar+dwa")["episodes"]
    nodes = [row["peak_search_nodes"] for row in grid]
    assert len(nodes) >= 8
    assert max(nodes) > 100 * max(1, min(nodes))


def test_the_latency_check_runs_and_supports_the_association() -> None:
    """The fixture has to plant a mechanism big enough for the platform's
    own instrument to see. The first draft of this world did not: the
    searches were tiny, latency stayed flat and the checker refuted it."""
    prepared = in_process_round(
        load_packet_artifact(FIXTURES, "latency-001"),
        bundle(),
        catalog=TOOL_CATALOG,
        analysis_run_id="g6-latency",
        sidecar_directories=sidecars("latency-001"),
        report=report("latency-001"),
    )
    declare(
        prepared,
        "expansion_latency_association",
        "global_planner",
        supports=("fact:metric:astar+dwa.latency_p99_ms",),
    )
    result = prepared.host.call(
        ask(prepared, "latency_vs_expanded_nodes", {"candidate_id": "astar+dwa"})
    )
    assert result.execution_status == "completed"
    assert result.proposition_verdict == "supported"
    assert result.measurements["n_episodes"] >= 8


def test_a_packet_without_its_report_says_the_check_is_not_checkable() -> None:
    """The honest answer for a run whose expansion counts nobody kept —
    and the reason the report travels beside the packet rather than
    being invented by the host."""
    prepared = in_process_round(
        load_packet_artifact(FIXTURES, "latency-001"),
        bundle(),
        catalog=TOOL_CATALOG,
        analysis_run_id="g6-latency-bare",
        sidecar_directories=sidecars("latency-001"),
    )
    declare(
        prepared,
        "expansion_latency_association",
        "global_planner",
        supports=("fact:metric:astar+dwa.latency_p99_ms",),
    )
    result = prepared.host.call(
        ask(prepared, "latency_vs_expanded_nodes", {"candidate_id": "astar+dwa"})
    )
    assert result.execution_status == "not_checkable"


def test_the_negative_control_has_nothing_to_explain() -> None:
    """No detector fired on either side, and the two candidates are one
    stack under two tunings."""
    built = packet("control-001")
    assert built.observations == ()
    assert {item.local_controller_config for item in built.candidates} == {
        "dwa_default",
        "dwa_patient",
    }
    assert {item.global_planner for item in built.candidates} == {"astar"}


def test_the_negative_controls_difference_is_a_rounding_error() -> None:
    waterfall = packet("control-001").decision.waterfall
    assert waterfall is not None
    assert abs(waterfall.delta_utility_mean) < 0.05
    assert waterfall.n_episodes >= 3


def test_the_insufficient_evidence_case_recorded_nothing() -> None:
    """Not a fixture with its files deleted: the episodes ran with no
    recorder attached, the way every run before the trace address change
    did."""
    artifact = load_packet_artifact(FIXTURES, "gap-002")
    assert artifact.packet.observations == ()
    assert artifact.packet.timelines == ()
    assert artifact.provenance.sidecar_present is False
    assert not (FIXTURES / "gap-002" / "sidecar").exists()


def test_the_two_abstention_cases_are_in_the_no_check_stratum() -> None:
    """The class is fixed by the labels before anything runs, and these
    two are the cases where the answer is that there is no answer."""
    strata = load_eval_spec(LABELS).strata
    assert "control-001" in strata["no_check_required"]
    assert "gap-002" in strata["no_check_required"]


# --------------------------------------------------------------------------
# What every fixture still owes
# --------------------------------------------------------------------------


@pytest.mark.parametrize("case_id", BUILT)
def test_every_packet_reads_back_under_its_own_checksum(case_id: str) -> None:
    artifact = load_packet_artifact(FIXTURES, case_id)
    assert artifact.case_id == case_id
    assert artifact.provenance.run_id == case_id


@pytest.mark.parametrize("case_id", BUILT)
def test_a_recorded_case_carries_a_sidecar_and_an_unrecorded_one_does_not(
    case_id: str,
) -> None:
    artifact = load_packet_artifact(FIXTURES, case_id)
    present = (FIXTURES / case_id / "sidecar").exists()
    assert artifact.provenance.sidecar_present == present
