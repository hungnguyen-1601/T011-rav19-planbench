"""W0 — the evaluation foundation, and what it refuses to let happen.

Four things are held here. That the labels for a case can be read by
the scorer and by nothing the model sees. That the bar was written down
before any run and cannot move without a diff. That a reliability number
below the case threshold does not travel as a number. And that a
measured run with a cache hit in it is refused rather than reported.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from test_analyst_packet_view import observation, packet

from planbench_analyst.eval_spec import (
    EvalSpec,
    EvalSpecRefusal,
    RefPredicate,
    assert_no_label_in,
    load_eval_spec,
    refs_satisfy,
)
from planbench_analyst.harness import quality_pass_hat_k, wilson_interval
from planbench_analyst.packet_view import build_packet_view
from planbench_analyst.preregistration import PREREGISTRATION, preregistration_checksum
from planbench_explanation.catalog import TOOL_CATALOG_VERSION
from planbench_explanation.ledger import EvidenceRef
from planbench_explanation.packet_artifact import load_packet_artifact

REPO_ROOT = Path(__file__).resolve().parents[1]
LABELS = REPO_ROOT / "fixtures" / "golden" / "labels" / "visible.json"
FIXTURES = REPO_ROOT / "fixtures" / "golden" / "visible"

#: Locked 2026-08-26, before B1. Changing the preregistration changes
#: this; the diff is the decision, and this test is what makes it one.
PREREGISTRATION_CHECKSUM = "17354118e80a864b8d52fd2603342058389366e8a0c81fc7f2d0fc02353f510a"


# --------------------------------------------------------------------------
# Labels: scorer-side, any-of, stratified before any run
# --------------------------------------------------------------------------


def test_the_shipped_labels_load_and_cover_the_built_fixtures() -> None:
    spec = load_eval_spec(LABELS)
    assert {item.case_id for item in spec.labels} == {"inflation-001", "rrt-001", "dwa-001"}
    for label in spec.labels:
        assert (FIXTURES / label.case_id / "packet.json").exists()


def test_the_stratum_is_decided_by_the_fixture_not_the_model() -> None:
    """A stratum chosen after seeing the model's branch is a
    post-treatment comparison."""
    spec = load_eval_spec(LABELS)
    assert spec.strata["check_required"] == ("inflation-001", "rrt-001")
    assert spec.strata["no_check_required"] == ("dwa-001",)


def test_a_citation_that_is_different_and_correct_still_counts() -> None:
    """A ref written as one exact string fails every other valid one."""
    artifact = load_packet_artifact(FIXTURES, "inflation-001")
    view = build_packet_view(artifact.packet, tool_catalog_version=TOOL_CATALOG_VERSION)
    label = load_eval_spec(LABELS).label_for("inflation-001")
    assert label is not None
    # Neither of these is the "canonical" ref; both are about the mechanism.
    by_subject = EvidenceRef(ref="fact:robot.required_passage_width_m", kind="fact")
    by_prefix = EvidenceRef(ref="obs:narrow_gap_refusal:astar+dwa", kind="observation")
    assert refs_satisfy([by_subject], label, view)
    assert refs_satisfy([by_prefix], label, view)
    unrelated = EvidenceRef(ref="fact:decision.status", kind="fact")
    assert not refs_satisfy([unrelated], label, view)


def test_a_label_with_no_predicates_makes_no_claim() -> None:
    spec = EvalSpec(suite_version="x", labels=[{"case_id": "c"}])  # type: ignore[list-item]
    label = spec.label_for("c")
    assert label is not None
    view = build_packet_view(
        packet(observations=[observation()]), tool_catalog_version=TOOL_CATALOG_VERSION
    )
    assert refs_satisfy([], label, view)


def test_a_predicate_on_a_ref_the_packet_does_not_hold_fails() -> None:
    view = build_packet_view(
        packet(observations=[observation()]), tool_catalog_version=TOOL_CATALOG_VERSION
    )
    predicate = RefPredicate(subject="costmap_inflation")
    assert not predicate.matches(EvidenceRef(ref="obs:invented:x", kind="fact"), view)


# --------------------------------------------------------------------------
# The eval has an identity, and it is content
# --------------------------------------------------------------------------


def test_the_checksum_moves_with_content_and_not_only_with_the_version() -> None:
    """A version string somebody forgot to bump would let two label sets
    share one identity."""
    spec = load_eval_spec(LABELS)
    edited = spec.model_copy(
        update={
            "labels": tuple(
                item.model_copy(
                    update={"expected_check_required": not item.expected_check_required}
                )
                if item.case_id == "dwa-001"
                else item
                for item in spec.labels
            )
        }
    )
    assert edited.checksum != spec.checksum
    assert edited.scoring_semantics_version == spec.scoring_semantics_version


def test_the_distractor_knobs_are_inside_the_checksum() -> None:
    spec = load_eval_spec(LABELS)
    assert spec.distractor_rate == 0.0
    assert spec.model_copy(update={"distractor_seed": 7}).checksum != spec.checksum


def test_a_confirmatory_label_file_is_refused(tmp_path: Path) -> None:
    """The confirmatory set is the hidden suite behind ``run_gate``; a
    label file claiming to be it is an answer key for a set nobody is
    meant to see."""
    payload = json.loads(LABELS.read_text(encoding="utf-8"))
    payload["partition"] = "confirmatory"
    path = tmp_path / "hidden.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(EvalSpecRefusal, match="confirmatory"):
        load_eval_spec(path)


# --------------------------------------------------------------------------
# Nothing the model sees carries a label
# --------------------------------------------------------------------------


def test_the_packet_view_of_every_fixture_carries_no_label() -> None:
    spec = load_eval_spec(LABELS)
    for label in spec.labels:
        artifact = load_packet_artifact(FIXTURES, label.case_id)
        view = build_packet_view(artifact.packet, tool_catalog_version=TOOL_CATALOG_VERSION)
        assert_no_label_in(view, spec)


def test_the_analyst_image_does_not_copy_the_label_directory() -> None:
    dockerfile = (REPO_ROOT / "docker" / "Dockerfile.analyst").read_text(encoding="utf-8")
    copied = re.findall(r"^COPY (\S+)", dockerfile, flags=re.MULTILINE)
    assert not any(source.startswith("fixtures") for source in copied)


def test_the_analyst_image_removes_the_visible_suite() -> None:
    """The visible suite is code and carries every calibration answer.
    The image copies the package, so it has to take the file back out —
    and this test is what keeps that line from being tidied away."""
    dockerfile = (REPO_ROOT / "docker" / "Dockerfile.analyst").read_text(encoding="utf-8")
    assert re.search(r"^RUN rm .*golden_fixtures\.py", dockerfile, flags=re.MULTILINE)


def test_the_visible_suite_resolves_lazily_so_the_image_can_drop_it() -> None:
    import planbench_explanation

    assert "VISIBLE_SUITE" not in planbench_explanation.__dict__
    assert len(planbench_explanation.VISIBLE_SUITE.cases) == 12


# --------------------------------------------------------------------------
# The bar was written down first
# --------------------------------------------------------------------------


def test_the_preregistration_is_pinned() -> None:
    """Changing any value is a diff somebody has to explain."""
    assert preregistration_checksum() == PREREGISTRATION_CHECKSUM


def test_the_primary_endpoint_is_one_number_tested_one_way() -> None:
    assert PREREGISTRATION.primary_endpoint == "case_level_mechanism_correctness"
    assert PREREGISTRATION.primary_test == "mcnemar_exact_paired"
    assert 0 < PREREGISTRATION.delta < 0.5


def test_hard_constraints_include_zero_structural_violations() -> None:
    assert dict(PREREGISTRATION.hard_constraints)["structural_violations"] == 0.0


def test_the_staged_family_count_is_stated_not_implied() -> None:
    assert len(PREREGISTRATION.families_staged) == 3
    assert PREREGISTRATION.families_total == 6


# --------------------------------------------------------------------------
# pass^k below the threshold is counts, not a rate
# --------------------------------------------------------------------------


def test_pass_hat_k_does_not_travel_as_a_number_on_too_few_cases() -> None:
    """On three cases one flip is thirty-three points."""
    rate, counts, interval = quality_pass_hat_k(
        [[True, True, True], [True, False, True], [True, True, True]],
        min_cases=PREREGISTRATION.min_cases_for_pass_k,
    )
    assert rate is None
    assert counts == (2, 3)
    assert interval[0] < 2 / 3 < interval[1]


def test_pass_hat_k_is_a_number_once_there_are_enough_cases() -> None:
    runs = [[True] * 3] * 11 + [[True, False, True]]
    rate, counts, interval = quality_pass_hat_k(runs, min_cases=12)
    assert rate == pytest.approx(11 / 12)
    assert counts == (11, 12)
    assert interval[1] <= 1.0


def test_the_interval_does_not_collapse_at_the_edges() -> None:
    """Wald gives zero width at 0/n and n/n, which is where small
    evaluations land."""
    low, high = wilson_interval(3, 3)
    assert high == 1.0 and low < 1.0
    low, high = wilson_interval(0, 3)
    assert low == 0.0 and high > 0.0
