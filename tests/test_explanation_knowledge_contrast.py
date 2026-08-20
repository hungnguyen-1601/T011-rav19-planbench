"""E3 — the lattice reading and the knowledge base.

Both are places where a plausible sentence is cheap and a defensible one
is not. The lattice reading is mostly a machine for *refusing* to
attribute; the knowledge base is a machine for citing something a reader
can go and check, and for admitting when it has nothing to say.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from planbench_explanation.contrast import (
    CandidateComponents,
    ContrastFinding,
    ContrastRefusal,
    components_from_report,
    read_lattice,
)
from planbench_explanation.knowledge import (
    KNOWLEDGE_BASE,
    ActivationConditions,
    KnowledgeEntry,
    KnowledgeRefusal,
    match,
    resolve,
)


def stack(candidate_id: str, global_planner: str, local: str, config: str = "dwa_coarse"):
    return CandidateComponents(
        candidate_id=candidate_id,
        global_planner=global_planner,
        local_controller=local,
        local_controller_config=config,
    )


# --------------------------------------------------------------------------
# The lattice, which mostly refuses
# --------------------------------------------------------------------------


def test_a_pattern_on_both_sides_of_a_swap_rules_that_component_out() -> None:
    """And says, in the same breath, what it does not show.

    Two stacks sharing DWA and differing in the global planner both
    stall: the global planner is not what produces it. The controller
    they share is *not* thereby proven — geometry, costmap, providers
    and the interaction between layers all produce shared patterns.
    """
    lattice = [stack("c1", "astar", "dwa"), stack("c2", "rrtstar", "dwa")]

    finding = read_lattice(lattice, {"c1": True, "c2": True}, detection_type="stuck_cluster")

    assert finding.verdict == "rules_out_component_specific_attribution"
    assert finding.subject == "global_planner"
    assert "does not show" in finding.reason
    assert finding.pairs == (("c1", "c2"),)


def test_a_pattern_that_follows_one_swapped_component_supports_attribution() -> None:
    lattice = [stack("c1", "astar", "dwa"), stack("c2", "rrtstar", "dwa")]

    finding = read_lattice(lattice, {"c1": True, "c2": False}, detection_type="detour")

    assert finding.verdict == "supports_component_specific_attribution"
    assert finding.subject == "global_planner"


def test_a_lattice_with_no_single_component_swap_attributes_nothing() -> None:
    """Two stacks differing in both layers say nothing about either."""
    lattice = [stack("c1", "astar", "dwa"), stack("c2", "rrtstar", "teb")]

    finding = read_lattice(lattice, {"c1": True, "c2": False}, detection_type="detour")

    assert finding.verdict == "insufficient_contrast"
    assert finding.subject is None


def test_one_candidate_is_not_a_contrast() -> None:
    finding = read_lattice([stack("c1", "astar", "dwa")], {"c1": True}, detection_type="detour")
    assert finding.verdict == "insufficient_contrast"


def test_contradicting_swaps_reach_an_interaction_and_stop_there() -> None:
    """The pattern follows the global planner in one pair and not another.

    Reported as an interaction rather than resolved by majority: two
    pairs disagreeing is exactly the evidence that the layers are not
    separable here.
    """
    lattice = [
        stack("c1", "astar", "dwa", "coarse"),
        stack("c2", "rrtstar", "dwa", "coarse"),
        stack("c3", "astar", "dwa", "fine"),
        stack("c4", "rrtstar", "dwa", "fine"),
    ]

    finding = read_lattice(
        lattice,
        {"c1": True, "c2": True, "c3": True, "c4": False},
        detection_type="oscillation",
    )

    assert finding.verdict == "interaction_not_isolated"
    assert finding.subject is None


def test_a_candidate_nobody_looked_at_takes_no_part() -> None:
    """Absence of a lookup is not absence of a pattern."""
    lattice = [stack("c1", "astar", "dwa"), stack("c2", "rrtstar", "dwa")]

    finding = read_lattice(lattice, {"c1": True}, detection_type="detour")

    assert finding.verdict == "insufficient_contrast"


def test_a_verdict_about_a_component_must_name_one() -> None:
    with pytest.raises((ContrastRefusal, ValidationError)):
        ContrastFinding(
            detection_type="detour",
            verdict="rules_out_component_specific_attribution",
            reason="no subject given",
        )
    with pytest.raises((ContrastRefusal, ValidationError)):
        ContrastFinding(
            detection_type="detour",
            verdict="insufficient_contrast",
            subject="global_planner",
            reason="a statement about the lattice does not name a component",
        )


def test_the_lattice_is_read_from_typed_fields_not_from_a_label() -> None:
    """A run predating the typed block has no lattice, not a guessed one."""
    report = {
        "candidates": [
            {
                "candidate_id": "c1",
                "stack_label": "astar+dwa",
                "components": {
                    "global_planner": "astar",
                    "local_controller": "dwa",
                    "local_controller_config": "dwa_coarse",
                },
            },
            {"candidate_id": "c2", "stack_label": "rrtstar+dwa"},
            {"candidate_id": "c3", "stack_label": "ppo", "components": None},
        ]
    }

    found = components_from_report(report)

    assert [item.candidate_id for item in found] == ["c1"]


# --------------------------------------------------------------------------
# The knowledge base
# --------------------------------------------------------------------------


def test_v1_ships_unapproved_so_nothing_here_can_back_a_claim_yet() -> None:
    """Written by one person, reviewed by nobody.

    E0 says an unapproved entry may not back a promoted claim. Shipping
    these as approved because they look right to their author is the
    move the review status exists to prevent.
    """
    assert KNOWLEDGE_BASE
    assert all(entry.review_status == "draft" for entry in KNOWLEDGE_BASE)
    matches = match("narrow_gap_refusal", {"margin_m": -0.06})
    assert matches
    assert all(not item.may_support_a_claim for item in matches)


def test_the_matcher_is_literal_and_ordered() -> None:
    first = match("stuck_cluster", {})
    second = match("stuck_cluster", {})
    assert [item.entry.entry_id for item in first] == [item.entry.entry_id for item in second]
    assert [item.entry.entry_id for item in first] == sorted(item.entry.entry_id for item in first)


def test_a_numeric_condition_keeps_a_narrow_entry_narrow() -> None:
    """The inflation entry is about a gap that is *too narrow*."""
    assert any(
        item.entry.entry_id == "inflation_gap_closure"
        for item in match("narrow_gap_refusal", {"margin_m": -0.06})
    )
    assert not any(
        item.entry.entry_id == "inflation_gap_closure"
        for item in match("narrow_gap_refusal", {"margin_m": 0.30})
    )
    # And a detection that never measured the quantity does not match by
    # omission.
    assert not any(
        item.entry.entry_id == "inflation_gap_closure" for item in match("narrow_gap_refusal", {})
    )


def test_nothing_matched_is_an_answer() -> None:
    """The bare symptom is what a reader gets. Inventing a mechanism for
    it is the failure this layer is built against."""
    assert match("latency_spike", {}, subject="task_geometry") == ()


def test_a_citation_resolves_only_at_the_version_it_names() -> None:
    entry = KNOWLEDGE_BASE[0]
    assert resolve(entry.citation).entry_id == entry.entry_id

    with pytest.raises(KnowledgeRefusal, match="version"):
        resolve(f"kb:{entry.entry_id}@99")
    with pytest.raises(KnowledgeRefusal, match="no knowledge entry"):
        resolve("kb:not_a_mechanism@1")
    with pytest.raises(KnowledgeRefusal, match="not a knowledge citation"):
        resolve("inflation_gap_closure")


def test_an_entry_matching_everything_is_refused() -> None:
    with pytest.raises((KnowledgeRefusal, ValidationError)):
        ActivationConditions(detection_types=(), subject="global_planner")


def test_approval_without_sources_is_refused() -> None:
    """Approval says somebody checked something; there must be something."""
    with pytest.raises((KnowledgeRefusal, ValidationError)):
        KnowledgeEntry(
            entry_id="unsourced",
            entry_version=1,
            title="A mechanism nobody can look up",
            mechanism="It just happens.",
            proposition_type="local_minimum_entrapment",
            conditions=ActivationConditions(
                detection_types=("stuck_cluster",), subject="local_controller"
            ),
            source_strength="practitioner_lore",
            review_status="approved",
        )


def test_every_shipped_entry_says_what_it_does_not_explain() -> None:
    """The near-miss reading is the one a reader makes unaided."""
    assert all(entry.does_not_explain for entry in KNOWLEDGE_BASE)
    assert all(entry.source_refs for entry in KNOWLEDGE_BASE)


def test_a_pattern_moving_with_two_components_attributes_it_to_neither() -> None:
    """The alphabetical coin flip.

    Swapping the global planner moves the pattern; so does swapping the
    controller config. An earlier version took the field that sorted
    first and reported ``global_planner`` — a choice dressed as a
    finding. Two axes that each look sufficient have not been separated.
    """
    lattice = [
        stack("c1", "astar", "dwa", "coarse"),
        stack("c2", "rrtstar", "dwa", "coarse"),
        stack("c3", "astar", "dwa", "fine"),
    ]

    finding = read_lattice(
        lattice, {"c1": True, "c2": False, "c3": False}, detection_type="oscillation"
    )

    assert finding.verdict == "interaction_not_isolated"
    assert finding.subject is None
    assert "more than one component" in finding.reason
    # Both pairs are kept, so a reader can see what disagreed.
    assert set(finding.pairs) == {("c1", "c2"), ("c1", "c3")}


def test_one_axis_and_only_one_still_supports_attribution() -> None:
    lattice = [
        stack("c1", "astar", "dwa", "coarse"),
        stack("c2", "rrtstar", "dwa", "coarse"),
        stack("c3", "astar", "dwa", "fine"),
    ]

    finding = read_lattice(
        lattice, {"c1": True, "c2": False, "c3": True}, detection_type="oscillation"
    )

    assert finding.verdict == "supports_component_specific_attribution"
    assert finding.subject == "global_planner"
