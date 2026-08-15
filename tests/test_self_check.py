"""The critic is measured the way it will be measured in the report.

Two kinds of test live here and the split is deliberate.

The first kind is ordinary: each rule fires on a report that has its
defect and stays quiet on one that does not. The second kind is the
evaluation harness in miniature — :data:`FAULTS` injects one known defect
into a clean report and asserts the critic recovers exactly it. That is
the same construction the written evaluation uses at scale, so a rule
added later without a fault entry is caught here rather than discovered
missing when the numbers are being collected.

The clean-report tests carry the most weight. A critic that objects to a
sound run is worse than no critic: the reviewer stops reading it, and
every real finding after that is lost. False-alarm rate is the metric
this file protects.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from planbench_decision.self_check import Finding, critique, resolve

REPO_ROOT = Path(__file__).resolve().parents[1]


def clean_report() -> dict[str, Any]:
    """A run with nothing to object to.

    Written out rather than loaded from ``artifacts/`` because every
    stored run has real findings — a fixture that starts dirty cannot
    measure a false alarm.
    """
    return {
        "artifact": "comparison_report",
        "identity": {
            "task_profile_id": "open_hall_v2",
            "experiment_scope": "local_controller_selection",
            "sensor_noise": {"lidar_range_sigma_m": 0.02, "wheel_slip_fraction": 0.02},
            "git_sha": "64d86d5fa07d6fa880da9c59d99b5e2b781f6437",
            "anchor_config_version": "v1.2",
            "created_at": "2026-08-12T15:33:47.368447+00:00",
        },
        "sample": {
            "n_episodes": 30,
            "n_episodes_requested": 30,
            "interrupted": False,
            "n_min_required": 30,
            "episode_context_ids": [f"ctx{i:02d}" for i in range(30)],
        },
        "early_stop": {"enabled": False, "stopped": [], "episodes_saved": 0},
        "candidates": [
            _candidate("60c8e26fe591", "astar+dwa"),
            _candidate("be4a8c4b7fb3", "rrtstar+dwa"),
        ],
        "measurement_environment": {"benchmark_host": {"cores_allocated": 2}, "warning": None},
        "decision_card": {
            "status": "CLEAR_RECOMMENDATION",
            "tie_break_reason": None,
            "evidence": {
                "delta_u_vs_second": 0.0321,
                "ci95": [0.0318, 0.0370],
                "n_episodes": 30,
                "effect_size": 4.74,
            },
        },
        "why_no_card": None,
        "run_checksum": "791dee7cb650",
    }


def _candidate(candidate_id: str, label: str) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "stack_label": label,
        "n_episodes": 30,
        "cleared_gates": True,
        "blocking_gates": [],
        "n_distinct_episodes": 30,
        "success_rate": 0.9,
        "gates": {
            "candidate_id": candidate_id,
            "G1": "pass",
            "G2": {
                "result": "pass",
                "observed": 0,
                "n_runs": 30,
                "n_distinct_episodes": 30,
                "upper_bound_95": 0.1,
                "n_min": 30,
            },
            "G3": "pass",
            "G4": {
                "result": "pass",
                "status": "confirmed_on_target",
                "p99_ms": 6.1,
                "threshold_ms": 50.0,
            },
            "G5": {"result": "pass", "status": "estimated_from_structure"},
            "G6": "pass",
        },
    }


# --------------------------------------------------------------------
# Fault injection: the evaluation harness, in miniature.
# --------------------------------------------------------------------


def _replay_seeds(report: dict[str, Any]) -> None:
    report["candidates"][0]["gates"]["G2"]["n_distinct_episodes"] = 6


def _cut_sample(report: dict[str, Any]) -> None:
    report["sample"]["n_episodes"] = 12


def _interrupt(report: dict[str, Any]) -> None:
    report["sample"]["interrupted"] = True


def _retire_one(report: dict[str, Any]) -> None:
    report["early_stop"]["stopped"] = ["be4a8c4b7fb3"]


def _widen_interval(report: dict[str, Any]) -> None:
    report["decision_card"]["evidence"]["ci95"] = [-0.004, 0.008]


def _shrink_effect(report: dict[str, Any]) -> None:
    report["decision_card"]["evidence"]["effect_size"] = 0.02


def _force_tie_break(report: dict[str, Any]) -> None:
    report["decision_card"]["tie_break_reason"] = "lower worst-case latency"


def _screen_g4_on_host(report: dict[str, Any]) -> None:
    report["candidates"][0]["gates"]["G4"]["status"] = "screened_on_host"


def _declare_g5(report: dict[str, Any]) -> None:
    report["candidates"][0]["gates"]["G5"]["status"] = "declared_by_author"


def _unpin_host(report: dict[str, Any]) -> None:
    report["measurement_environment"]["warning"] = "measured on all 20 cores, unpinned"


def _zero_noise(report: dict[str, Any]) -> None:
    report["identity"]["sensor_noise"] = {"lidar_range_sigma_m": 0.0, "wheel_slip_fraction": 0.0}


def _drop_git_sha(report: dict[str, Any]) -> None:
    report["identity"]["git_sha"] = ""


def _withdraw_card(report: dict[str, Any]) -> None:
    report["decision_card"] = None
    report["why_no_card"] = "only 1 of 2 candidates cleared all six gates"


def _block_a_candidate(report: dict[str, Any]) -> None:
    report["candidates"][0]["cleared_gates"] = False
    report["candidates"][0]["blocking_gates"] = ["G3"]


def _drop_second_candidate(report: dict[str, Any]) -> None:
    del report["candidates"][1]


#: One entry per rule: the injection, and the code it must recover.
#: A rule without an entry here is a rule the evaluation cannot score.
FAULTS: tuple[tuple[str, Any], ...] = (
    ("G2_REPLAYED_EPISODES", _replay_seeds),
    ("SAMPLE_BELOW_N_MIN", _cut_sample),
    ("SAMPLE_INTERRUPTED", _interrupt),
    ("EARLY_STOP_APPLIED", _retire_one),
    ("DELTA_U_CI_STRADDLES_ZERO", _widen_interval),
    ("EFFECT_SIZE_SMALL", _shrink_effect),
    ("WON_ON_TIE_BREAK", _force_tie_break),
    ("G4_HOST_ONLY", _screen_g4_on_host),
    ("G5_DECLARED_NOT_MEASURED", _declare_g5),
    ("HOST_NOT_PINNED", _unpin_host),
    ("SENSOR_NOISE_ZERO", _zero_noise),
    ("PROVENANCE_MISSING_GIT_SHA", _drop_git_sha),
    ("NO_RECOMMENDATION", _withdraw_card),
    ("BLOCKED_CANDIDATE_HAS_SCORES", _block_a_candidate),
    ("SINGLE_CANDIDATE", _drop_second_candidate),
)


class TestACleanRunDrawsNoObjection:
    def test_it_finds_nothing(self) -> None:
        assert critique(clean_report()) == ()

    def test_near_equivalent_is_not_an_objection(self) -> None:
        """The card admitting a tie is the card being honest.

        An interval containing zero is what NEAR_EQUIVALENT means. A
        critic that objects here is objecting to correct behaviour, and
        a reviewer who sees that once stops trusting the rest.
        """
        report = clean_report()
        report["decision_card"]["status"] = "NEAR_EQUIVALENT"
        report["decision_card"]["evidence"]["ci95"] = [-0.004, 0.008]
        report["decision_card"]["evidence"]["effect_size"] = 0.02
        assert critique(report) == ()

    def test_an_empty_report_does_not_crash(self) -> None:
        """Older schemas produce fewer findings, never an exception."""
        assert critique({}) == ()


class TestEachInjectedFaultIsRecovered:
    @pytest.mark.parametrize("code,inject", FAULTS, ids=[c for c, _ in FAULTS])
    def test_the_rule_fires(self, code: str, inject: Any) -> None:
        report = clean_report()
        inject(report)
        assert code in {f.code for f in critique(report)}

    @pytest.mark.parametrize("code,inject", FAULTS, ids=[c for c, _ in FAULTS])
    def test_it_does_not_drag_in_unrelated_findings(self, code: str, inject: Any) -> None:
        """Precision, not just recall.

        One injected defect should surface that defect. Extra findings
        would mean a rule reads state it has no business reading, and at
        evaluation time they would count as false alarms.
        """
        report = clean_report()
        inject(report)
        codes = {f.code for f in critique(report)}
        # Two injections legitimately imply a second finding: withdrawing
        # the card leaves the run unranked *and* unexplained, and blocking
        # a candidate is why a card would be withdrawn. Both are stated
        # rather than tolerated silently.
        allowed = {code} | {"NO_RECOMMENDATION" if code == "BLOCKED_CANDIDATE_HAS_SCORES" else code}
        assert codes <= allowed, f"unexpected extra findings: {codes - allowed}"


class TestEveryFindingCitesSomethingReal:
    @pytest.mark.parametrize("code,inject", FAULTS, ids=[c for c, _ in FAULTS])
    def test_field_path_resolves(self, code: str, inject: Any) -> None:
        """The invariant the LLM layer inherits, enforced on the rules.

        A finding whose ``field_path`` does not resolve is dropped by
        `critique` rather than shown, so this test is what keeps that
        guard from silently swallowing a working rule.
        """
        report = clean_report()
        inject(report)
        for finding in critique(report):
            assert resolve(report, finding.field_path) is not None, finding.field_path

    def test_a_fabricated_path_resolves_to_none(self) -> None:
        report = clean_report()
        assert resolve(report, "decision_card.evidence.no_such_field") is None
        assert resolve(report, "candidates[9].stack_label") is None
        assert resolve(report, "identity.git_sha") is not None


class TestSeverityOrdersTheReading:
    def test_blocking_comes_first(self) -> None:
        report = clean_report()
        _cut_sample(report)  # blocking
        _screen_g4_on_host(report)  # disclosure
        _unpin_host(report)  # material
        severities = [f.severity for f in critique(report)]
        assert severities == sorted(severities, key=["blocking", "material", "disclosure"].index)

    def test_omissions_are_labelled_as_such(self) -> None:
        """The evaluation reports present and omitted defects apart."""
        report = clean_report()
        _zero_noise(report)
        assert [f.kind for f in critique(report)] == ["omission"]


class TestAgainstStoredRuns:
    """The rules have to survive contact with reports nobody wrote for them."""

    @staticmethod
    def _stored() -> list[Path]:
        return sorted((REPO_ROOT / "artifacts" / "runs").glob("*/*/comparison_report.json"))

    def test_every_stored_report_is_critiqued_without_error(self) -> None:
        paths = self._stored()
        if not paths:
            pytest.skip("no stored runs in artifacts/runs")
        for path in paths:
            report = json.loads(path.read_text(encoding="utf-8"))
            for finding in critique(report):
                assert isinstance(finding, Finding)
                assert resolve(report, finding.field_path) is not None, (
                    f"{path.parent.name}: {finding.code} cites {finding.field_path}"
                )

    def test_critique_does_not_mutate_the_report(self) -> None:
        report = clean_report()
        _cut_sample(report)
        before = copy.deepcopy(report)
        critique(report)
        assert report == before
