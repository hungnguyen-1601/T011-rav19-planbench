"""Agentic layer: LLM provider abstraction, tool calling, evidence, RAG.

Boundaries that hold everywhere in this package:

- no vendor name outside :mod:`planbench_agent.anthropic_provider`;
- the agent reaches PlanBench only through
  :class:`planbench_agent.gateway.AgentGateway`, so it has no path to the
  simulator, ``/cmd_vel``, map editing, or the approval decision itself;
- every generated claim carries a citation that is checked against
  recorded data before the text is returned.
"""

from planbench_agent.evidence import (
    Citation,
    EvidenceBundle,
    EvidenceItem,
    InsufficientEvidence,
    SourceKind,
    collect_benchmark_evidence,
    extract_citations,
)
from planbench_agent.factory import (
    AUTO_ORDER,
    PROVIDERS,
    ProviderStatus,
    build_provider,
    describe_unavailable,
    provider_status,
)
from planbench_agent.gateway import (
    AgentGateway,
    AlgorithmSummary,
    ApprovalRequired,
    BenchmarkSummary,
    EpisodeSummary,
    GatewayError,
    LeaderboardRow,
    ScenarioSummary,
)
from planbench_agent.openai_provider import PRESETS, OpenAICompatibleProvider
from planbench_agent.provider import (
    LLMMessage,
    LLMProvider,
    LLMRequest,
    LLMResponse,
    MockProvider,
    ProviderError,
    ProviderUnavailable,
    StopReason,
    ToolCall,
    ToolResult,
    ToolSpec,
)
from planbench_agent.rag import Chunk, KnowledgeBase, load_markdown_directory, split_markdown
from planbench_agent.report import (
    SAFETY_DISCLAIMER,
    FabricatedCitation,
    GeneratedReport,
    generate_report,
)
from planbench_agent.specs import (
    MissionDraft,
    MissionRefusal,
    mission_schema,
    parse_mission_text,
    parse_structured,
    validate_draft,
)
from planbench_agent.tools import (
    FORBIDDEN_CAPABILITIES,
    Effect,
    ToolPolicy,
    ToolRegistry,
    build_registry,
)
from planbench_agent.workflow import (
    AgentEvent,
    AgentService,
    AgentSession,
    AgentState,
    ChatTurn,
)

__all__ = [
    "AUTO_ORDER",
    "FORBIDDEN_CAPABILITIES",
    "PRESETS",
    "PROVIDERS",
    "SAFETY_DISCLAIMER",
    "AgentEvent",
    "AgentGateway",
    "AgentService",
    "AgentSession",
    "AgentState",
    "AlgorithmSummary",
    "ApprovalRequired",
    "BenchmarkSummary",
    "ChatTurn",
    "Chunk",
    "Citation",
    "Effect",
    "EpisodeSummary",
    "EvidenceBundle",
    "EvidenceItem",
    "FabricatedCitation",
    "GatewayError",
    "GeneratedReport",
    "InsufficientEvidence",
    "KnowledgeBase",
    "LLMMessage",
    "LLMProvider",
    "LLMRequest",
    "LLMResponse",
    "LeaderboardRow",
    "MissionDraft",
    "MissionRefusal",
    "MockProvider",
    "OpenAICompatibleProvider",
    "ProviderError",
    "ProviderStatus",
    "ProviderUnavailable",
    "ScenarioSummary",
    "SourceKind",
    "StopReason",
    "ToolCall",
    "ToolPolicy",
    "ToolRegistry",
    "ToolResult",
    "ToolSpec",
    "build_provider",
    "build_registry",
    "collect_benchmark_evidence",
    "describe_unavailable",
    "extract_citations",
    "generate_report",
    "load_markdown_directory",
    "mission_schema",
    "parse_mission_text",
    "parse_structured",
    "provider_status",
    "split_markdown",
    "validate_draft",
]
