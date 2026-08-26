"""W1.5 — retrieval reaches the round, and only when it is asked for.

A5 built the retriever, the resolver and the trait offers, and the
runner called none of them: the two knowledge inputs existed and no
round had ever been run with either. This wires them in **off by
default**, which is the part that matters for the measurement — a
default that quietly turned them on would put what E1 is meant to add
inside the baseline it is measured against.

The second thing held here is the citation path. Guard rule 1 refuses a
ref the view cannot resolve, so an entry the model was shown and could
not cite would read as a base it is forbidden to use. Offers are indexed
as facts, and the review status rides in the label rather than filtering
what is shown: whether an entry may *promote* a claim is the promotion
matrix's answer, not retrieval's.
"""

from __future__ import annotations

import pytest
from test_analyst_packet_view import observation, packet
from test_analyst_runner import MEASURED_TASK, answer, hypothesis, prepared, scripted

from planbench_analyst.knowledge_provider import query_for, retrieve
from planbench_analyst.packet_view import build_packet_view
from planbench_analyst.runner import run_round
from planbench_benchmark.traits_store import TraitEntry, TraitSource
from planbench_explanation.catalog import TOOL_CATALOG_VERSION
from planbench_explanation.knowledge_contract import resolve_candidates


def traits_for(algorithm_id: str = "dwa", **overrides) -> TraitSource:
    fields = {
        "algorithm_id": algorithm_id,
        "kind": "local",
        "strengths": ("smooth near obstacles",),
        "weaknesses": ("concave pockets",),
        "anchor": "planbench_planning.dwa: the sampled-rollout scoring loop",
    }
    fields.update(overrides)
    return TraitSource((TraitEntry(**fields),))  # type: ignore[arg-type]


def offers_for(built=None):  # type: ignore[no-untyped-def]
    built = built or packet(observations=[observation()], task=MEASURED_TASK)
    return resolve_candidates(retrieve(query_for(built))).resolved


# --------------------------------------------------------------------------
# Off by default
# --------------------------------------------------------------------------


def test_a_round_offers_nothing_unless_it_was_asked_to() -> None:
    """B1 has to be a baseline. If retrieval were on by default it would
    already contain what E1 adds, and the difference would measure
    nothing."""
    outcome = run_round(prepared(), scripted(answer(hypothesis())))
    assert not any(event.startswith("knowledge:") for event in outcome.events)
    assert not any(event.startswith("traits:") for event in outcome.events)


def test_asking_for_knowledge_puts_the_count_in_the_transcript() -> None:
    outcome = run_round(prepared(), scripted(answer(hypothesis())), knowledge=True)
    (event,) = [item for item in outcome.events if item.startswith("knowledge:")]
    resolved, offered = event.removeprefix("knowledge:").split("/")
    assert int(offered) >= int(resolved) >= 1


def test_the_transcript_separates_nothing_offered_from_nothing_resolved() -> None:
    """ "No entry matched" and "five matched and none resolved" are
    different runs, and only one of them is a retrieval problem."""
    outcome = run_round(prepared(), scripted(answer(hypothesis())), knowledge=True)
    (event,) = [item for item in outcome.events if item.startswith("knowledge:")]
    assert "/" in event


def test_asking_for_traits_counts_the_natures_this_packet_could_use() -> None:
    outcome = run_round(
        prepared(), scripted(answer(hypothesis())), traits=traits_for("dwa")
    )
    assert any(event.startswith("traits:") for event in outcome.events)


# --------------------------------------------------------------------------
# What retrieval offers is citable
# --------------------------------------------------------------------------


def test_an_offered_entry_can_be_cited_because_the_view_resolves_it() -> None:
    """Guard rule 1 drops a ref the view does not hold. An entry shown
    and not citable would be a base the model is forbidden to use."""
    built = packet(observations=[observation()], task=MEASURED_TASK)
    offers = offers_for(built)
    assert offers
    view = build_packet_view(built, tool_catalog_version=TOOL_CATALOG_VERSION, knowledge=offers)
    for reference in offers:
        assert reference.entry.citation in view
        fact = view.fact(reference.entry.citation)
        assert fact is not None
        assert fact.kind == "knowledge_entry"


def test_the_review_status_is_shown_rather_than_used_as_a_filter() -> None:
    """Whether an entry may promote a claim is the promotion matrix's
    answer. Filtering here would move that rule into retrieval, where
    nobody would find it."""
    built = packet(observations=[observation()], task=MEASURED_TASK)
    offers = offers_for(built)
    view = build_packet_view(built, tool_catalog_version=TOOL_CATALOG_VERSION, knowledge=offers)
    labels = [view.fact(item.entry.citation).label for item in offers]  # type: ignore[union-attr]
    assert any(
        item.entry.review_status in label for item, label in zip(offers, labels, strict=True)
    )


def test_an_entry_the_platform_does_not_hold_never_reaches_the_view() -> None:
    """Retrieval offers keys and the platform resolves them; an entry
    the curated base does not hold is rejected before a prompt."""
    built = packet(observations=[observation()], task=MEASURED_TASK)
    result = retrieve(query_for(built))
    invented = result.model_copy(
        update={
            "entries": tuple(
                item.model_copy(update={"entry_id": "an_entry_nobody_curated"})
                for item in result.entries
            )
        }
    )
    outcome = resolve_candidates(invented)
    assert outcome.resolved == ()
    assert outcome.rejected


def test_a_packet_with_no_matching_detection_is_offered_nothing() -> None:
    """An entry whose conditions name none of this run's detections is
    an entry about a different run."""
    bare = packet(task=MEASURED_TASK)
    assert offers_for(bare) == ()


# --------------------------------------------------------------------------
# The two inputs are independent
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("knowledge", "traits"),
    [(False, False), (True, False), (False, True), (True, True)],
)
def test_each_input_can_be_switched_without_the_other(knowledge: bool, traits: bool) -> None:
    """E1 and E3 need the full two-by-two; a pair that only moves
    together is one arm wearing two names."""
    outcome = run_round(
        prepared(),
        scripted(answer(hypothesis())),
        knowledge=knowledge,
        traits=traits_for("dwa") if traits else None,
    )
    assert any(item.startswith("knowledge:") for item in outcome.events) is knowledge
    assert any(item.startswith("traits:") for item in outcome.events) is traits


def test_turning_an_input_on_changes_what_the_model_was_shown() -> None:
    """If the bytes did not move, the arm is decorative."""
    built = packet(observations=[observation()], task=MEASURED_TASK)
    bare = build_packet_view(built, tool_catalog_version=TOOL_CATALOG_VERSION).serialize()
    with_knowledge = build_packet_view(
        built, tool_catalog_version=TOOL_CATALOG_VERSION, knowledge=offers_for(built)
    ).serialize()
    with_traits = build_packet_view(
        built,
        tool_catalog_version=TOOL_CATALOG_VERSION,
        traits=traits_for("dwa"),
    ).serialize()
    assert len(with_knowledge) > len(bare)
    assert len(with_traits) > len(bare)
    assert with_knowledge != with_traits
