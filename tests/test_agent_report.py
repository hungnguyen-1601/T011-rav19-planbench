"""Evidence collection and the guards on generated reports."""

from __future__ import annotations

import pytest
from agent_fakes import FakeGateway, sample_report

from planbench_agent.evidence import (
    Citation,
    EvidenceBundle,
    EvidenceItem,
    InsufficientEvidence,
    SourceKind,
    collect_benchmark_evidence,
    extract_citations,
)
from planbench_agent.provider import LLMResponse, MockProvider, StopReason
from planbench_agent.report import (
    PROVISIONAL_NOTICE,
    SAFETY_DISCLAIMER,
    FabricatedCitation,
    contains_safety_claim,
    generate_report,
)


@pytest.fixture
def gateway() -> FakeGateway:
    return FakeGateway()


@pytest.fixture
def bundle(gateway) -> EvidenceBundle:
    summary = gateway.add_benchmark("a1b2c3d4e5f6", state="accepted", with_report=True)
    return collect_benchmark_evidence(
        summary,
        gateway.get_report("a1b2c3d4e5f6"),
        question="Which stack succeeded more often?",
    )


class TestCitations:
    def test_extracts_every_token_in_order(self):
        text = "A [benchmark:abc] then B [aggregate:abc#astar+dwa] then A again [benchmark:abc]."
        assert extract_citations(text) == (
            "benchmark:abc",
            "aggregate:abc#astar+dwa",
            "benchmark:abc",
        )

    def test_ignores_ordinary_brackets(self):
        assert extract_citations("see [1] and [Figure 2]") == ()

    def test_citation_id_is_kind_colon_locator(self):
        citation = Citation(kind=SourceKind.EPISODE, locator="ep0001")
        assert citation.id == "episode:ep0001"


class TestEvidenceCollection:
    def test_an_unrun_benchmark_yields_only_its_identity(self, gateway):
        summary = gateway.add_benchmark("a1b2c3d4e5f6", state="draft")
        collected = collect_benchmark_evidence(summary, None)
        assert len(collected.items) == 1
        assert collected.of_kind(SourceKind.AGGREGATE) == ()

    def test_aggregates_become_citable_items(self, bundle):
        aggregate_ids = {item.citation.id for item in bundle.of_kind(SourceKind.AGGREGATE)}
        assert "aggregate:a1b2c3d4e5f6#astar+dwa" in aggregate_ids
        assert "aggregate:a1b2c3d4e5f6#astar+ppo" in aggregate_ids

    def test_the_fairness_checksum_is_recorded(self, bundle):
        checksum = sample_report().fairness.conditions_checksum
        assert any(checksum in item.statement for item in bundle.items)

    def test_episodes_and_artifacts_are_cited_separately(self, gateway):
        summary = gateway.add_benchmark("b22222222222", with_report=True, with_episodes=True)
        collected = collect_benchmark_evidence(
            summary,
            gateway.get_report("b22222222222"),
            tuple(gateway.list_episodes("b22222222222")),
        )
        assert collected.of_kind(SourceKind.EPISODE)
        artifacts = collected.of_kind(SourceKind.ARTIFACT)
        assert artifacts and artifacts[0].citation.uri.startswith("file://")

    def test_failure_analysis_evidence_is_carried_through(self, gateway):
        summary = gateway.add_benchmark("b33333333333", with_report=True, with_episodes=True)
        episodes = tuple(gateway.list_episodes("b33333333333"))
        failed = [episode for episode in episodes if episode.status != "success"]
        analyses = tuple((episode.id, gateway.analyse_episode(episode.id)) for episode in failed)
        collected = collect_benchmark_evidence(
            summary, gateway.get_report("b33333333333"), episodes, analyses
        )
        assert any("static_obstacle_collision" in item.statement for item in collected.items)
        assert any("collision at t=4.2" in item.statement for item in collected.items)

    def test_require_raises_below_the_minimum(self):
        with pytest.raises(InsufficientEvidence):
            EvidenceBundle().require(1)

    def test_rendered_block_is_one_line_per_item(self, bundle):
        assert len(bundle.render().splitlines()) == len(bundle.items)


class TestGenerateReport:
    def test_empty_evidence_refuses_without_calling_the_provider(self):
        provider = MockProvider(script=[])  # any call would raise
        report = generate_report(provider, EvidenceBundle(), "anything?")
        assert report.refused and "INSUFFICIENT EVIDENCE" in report.text

    def test_deterministic_provider_writes_a_cited_report(self, bundle):
        report = generate_report(
            MockProvider(), bundle, bundle.question, benchmark_state="accepted"
        )
        assert not report.refused
        assert set(report.citations) <= bundle.ids
        assert report.citations

    def test_accepted_results_are_not_marked_provisional(self, bundle):
        report = generate_report(MockProvider(), bundle, "q", benchmark_state="accepted")
        assert report.provisional is False
        assert PROVISIONAL_NOTICE not in report.text

    def test_unreviewed_results_carry_the_provisional_notice(self, bundle):
        report = generate_report(MockProvider(), bundle, "q", benchmark_state="pending_review")
        assert report.provisional is True
        assert PROVISIONAL_NOTICE in report.text

    def test_every_report_carries_the_safety_disclaimer(self, bundle):
        report = generate_report(MockProvider(), bundle, "q", benchmark_state="accepted")
        assert SAFETY_DISCLAIMER in report.text

    def test_a_fabricated_citation_is_rejected(self, bundle):
        provider = MockProvider(
            script=[LLMResponse(text="A* + DWA won [aggregate:does-not-exist#astar+dwa].")]
        )
        with pytest.raises(FabricatedCitation) as exc:
            generate_report(provider, bundle, "q")
        assert exc.value.unknown == ("aggregate:does-not-exist#astar+dwa",)

    def test_a_partly_fabricated_report_is_rejected_whole(self, bundle):
        real = next(iter(sorted(bundle.ids)))
        provider = MockProvider(
            script=[LLMResponse(text=f"True [{real}] but also false [episode:invented].")]
        )
        with pytest.raises(FabricatedCitation):
            generate_report(provider, bundle, "q")

    def test_uncited_prose_is_discarded(self, bundle):
        provider = MockProvider(script=[LLMResponse(text="A*+DWA is clearly the better stack.")])
        report = generate_report(provider, bundle, "q")
        assert report.refused and report.refusal_reason == "no citations"

    def test_a_model_refusal_is_reported_as_a_refusal(self, bundle):
        provider = MockProvider(script=[LLMResponse(text="", stop_reason=StopReason.REFUSAL)])
        report = generate_report(provider, bundle, "q")
        assert report.refused and report.refusal_reason == "provider refusal"

    def test_an_empty_response_is_a_refusal_not_an_empty_report(self, bundle):
        report = generate_report(MockProvider(script=[LLMResponse(text="   ")]), bundle, "q")
        assert report.refused and report.refusal_reason == "empty response"

    def test_model_declaring_insufficient_evidence_is_passed_through(self, bundle):
        provider = MockProvider(
            script=[LLMResponse(text="INSUFFICIENT EVIDENCE — no clearance data was supplied.")]
        )
        report = generate_report(provider, bundle, "q")
        assert report.refused
        assert "clearance" in report.text

    def test_provenance_is_recorded_on_every_report(self, bundle):
        report = generate_report(MockProvider(), bundle, "q")
        assert report.provider == "mock"
        assert report.deterministic is True
        assert report.evidence_count == len(bundle.items)


class TestSafetyClaimDetector:
    @pytest.mark.parametrize(
        "text",
        [
            "This planner is safe for deployment.",
            "The stack is production-ready.",
            "Results are certified.",
        ],
    )
    def test_flags_a_safety_verdict(self, text):
        assert contains_safety_claim(text) is True

    def test_the_disclaimer_itself_is_not_a_claim(self):
        body = "A*+DWA reached the goal in 2/2 episodes [x:y].\n\n" + SAFETY_DISCLAIMER
        assert contains_safety_claim(body) is False

    def test_the_deterministic_report_makes_no_safety_claim(self, bundle):
        report = generate_report(MockProvider(), bundle, "Is this planner safe?")
        assert contains_safety_claim(report.text) is False


def _item(citation_id: str) -> EvidenceItem:
    kind, locator = citation_id.split(":", 1)
    return EvidenceItem(citation=Citation(kind=SourceKind(kind), locator=locator), statement="fact")


def test_bundle_ids_are_exactly_the_item_ids():
    bundle = EvidenceBundle(items=(_item("benchmark:a"), _item("episode:b")))
    assert bundle.ids == {"benchmark:a", "episode:b"}
