"""A5 — retrieval that offers keys, and natures an analyst may cite.

The contract was built before any retrieval existed, and these tests are
mostly about what this side is structurally unable to do: it hands back
keys, not mechanisms; it does not read a review status, because that is
the platform's answer and hiding it inside retrieval would put the
promotion rule where nobody can see it.
"""

from __future__ import annotations

import pytest
from test_analyst_packet_view import observation, packet, stack

from planbench_analyst.knowledge_provider import (
    MAX_OFFERS,
    RETRIEVAL_VERSION,
    query_for,
    retrieve,
    trait_offers,
)
from planbench_analyst.packet_view import build_packet_view
from planbench_benchmark.outcome import SHIPPED_TRAITS
from planbench_benchmark.traits_store import TraitEntry, TraitSource
from planbench_explanation.catalog import TOOL_CATALOG_VERSION
from planbench_explanation.knowledge import KNOWLEDGE_BASE, KNOWLEDGE_BASE_VERSION
from planbench_explanation.knowledge_contract import (
    KnowledgeResult,
    MechanismReferenceCandidate,
    resolve_candidates,
)


def case(**overrides):  # type: ignore[no-untyped-def]
    fields = {"observations": [observation("stuck_cluster")]}
    fields.update(overrides)
    return packet(**fields)


def approved(algorithm_id: str = "dwa") -> TraitEntry:
    return TraitEntry(
        algorithm_id=algorithm_id,
        kind="local",
        strengths=("reacts within one control period",),
        weaknesses=("a local minimum is a local minimum: it cannot see round a corner",),
        anchor="defining mechanics: one-step velocity sampling",
        review_status="approved",
        reviewed_by="An",
    )


# --------------------------------------------------------------------------
# The query is features, never prose
# --------------------------------------------------------------------------


def test_the_query_carries_features_and_no_narrative() -> None:
    """A provider handed the case narrative is a provider given room to
    answer the narrative rather than the evidence."""
    query = query_for(case())
    assert query.observations == ("stuck_cluster",)
    assert "astar" in query.candidate_components
    assert query.task_features == ("warehouse_a_v1",)


def test_a_mechanism_already_ruled_out_is_not_offered_again() -> None:
    ruled_out = query_for(case(), excluded=["local_minimum_entrapment"])
    offered = retrieve(ruled_out).entries
    assert all(item.entry_id != "kb-dwa-local-minimum" for item in offered)


# --------------------------------------------------------------------------
# Retrieval offers keys and nothing else
# --------------------------------------------------------------------------


def test_an_offer_carries_no_mechanism_text() -> None:
    """There is no field for it, and ``extra='forbid'`` turns an attempt
    to add one into an error at the boundary."""
    with pytest.raises(ValueError, match="extra"):
        MechanismReferenceCandidate(
            knowledge_base_id="navigation-mechanisms",
            entry_id="kb-1",
            entry_version=1,
            retrieval_score=0.9,
            mechanism="the aisle is too narrow",  # type: ignore[call-arg]
        )


def test_a_detection_nobody_indexed_gets_no_offers() -> None:
    """An entry whose conditions name none of this packet's detections is
    an entry about a different run, whatever else it matches."""
    assert retrieve(query_for(packet())).entries == ()


def test_offers_are_capped() -> None:
    offered = retrieve(query_for(case(observations=[observation("stuck_cluster")])))
    assert len(offered.entries) <= MAX_OFFERS


def test_the_result_names_the_base_and_the_retrieval_it_came_from() -> None:
    """Two analysts offered different entries for one packet are two
    systems, however identical their prompts."""
    offered = retrieve(query_for(case()))
    assert offered.kb_version == KNOWLEDGE_BASE_VERSION
    assert offered.retrieval_version == RETRIEVAL_VERSION


def test_retrieval_does_not_filter_on_review_status() -> None:
    """Filtering here would move the promotion rule into retrieval,
    where nobody would be able to see it."""
    assert all(entry.review_status == "draft" for entry in KNOWLEDGE_BASE)
    assert retrieve(query_for(case())).entries


def test_the_platform_is_the_one_that_says_a_draft_may_not_promote() -> None:
    offered = retrieve(query_for(case()))
    outcome = resolve_candidates(offered)
    assert outcome.resolved
    assert not any(item.may_support_a_claim for item in outcome.resolved)


def test_an_answer_about_another_base_version_is_refused_whole() -> None:
    stale = KnowledgeResult(
        entries=(),
        kb_version="v0.0.1",
        retrieval_version=RETRIEVAL_VERSION,
    )
    with pytest.raises(Exception, match="knowledge base"):
        resolve_candidates(stale)


# --------------------------------------------------------------------------
# Natures an analyst may cite
# --------------------------------------------------------------------------


def test_only_the_algorithms_this_packet_ran_are_offered() -> None:
    """A table of every algorithm the platform knows would put six
    paragraphs about controllers nobody ran into a paid prompt."""
    offers = trait_offers(case(), SHIPPED_TRAITS)
    assert {item.algorithm_id for item in offers} <= {"astar", "rrtstar", "dwa"}


def test_an_algorithm_nobody_described_contributes_no_offer() -> None:
    """ "Nobody described this" belongs in the packet's account of its
    gaps, not in a citation an analyst could lean on."""
    imported = case(candidates=[stack("cand_a", "mppi"), stack("cand_b", "rrtstar")])
    offered = trait_offers(imported, SHIPPED_TRAITS)
    assert not [item for item in offered if item.algorithm_id == "mppi"]


def test_a_draft_nature_may_be_cited_and_may_not_promote() -> None:
    offers = trait_offers(case(), SHIPPED_TRAITS)
    assert offers
    assert not any(item.may_support_a_claim for item in offers)


def test_an_approved_nature_may_promote() -> None:
    described = TraitSource([approved()])
    (offer,) = [item for item in trait_offers(case(), described) if "weakness" in item.ref]
    assert offer.may_support_a_claim
    assert offer.anchor


def test_a_nature_is_citable_by_ref_in_the_packet_view() -> None:
    """Otherwise the guard's first rule drops every proposal that leans
    on one, and the table would be a table nobody can use."""
    indexed = build_packet_view(
        case(), tool_catalog_version=TOOL_CATALOG_VERSION, traits=SHIPPED_TRAITS
    )
    refs = [fact.ref for fact in indexed.facts if fact.ref.startswith("trait:")]
    assert refs
    assert indexed.fact(refs[0]) is not None


def test_a_nature_carries_the_component_it_is_about() -> None:
    """So rule 6 catches a nature about the planner being used to support
    a claim about the controller."""
    indexed = build_packet_view(
        case(), tool_catalog_version=TOOL_CATALOG_VERSION, traits=SHIPPED_TRAITS
    )
    subjects = {fact.subject for fact in indexed.facts if fact.ref.startswith("trait:")}
    assert subjects <= {"global_planner", "local_controller"}


def test_a_view_built_without_traits_holds_none() -> None:
    """The natures are opt-in: a caller with no trait source gets a
    packet view that says nothing about algorithm natures rather than
    one that quietly asserts there are none."""
    indexed = build_packet_view(case(), tool_catalog_version=TOOL_CATALOG_VERSION)
    assert not [fact for fact in indexed.facts if fact.ref.startswith("trait:")]


def test_the_review_status_is_visible_to_a_reader() -> None:
    indexed = build_packet_view(
        case(), tool_catalog_version=TOOL_CATALOG_VERSION, traits=SHIPPED_TRAITS
    )
    trait_fact = next(fact for fact in indexed.facts if fact.ref.startswith("trait:"))
    assert "draft" in trait_fact.label
