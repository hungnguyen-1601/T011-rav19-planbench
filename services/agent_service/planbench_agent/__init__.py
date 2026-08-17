"""Agentic layer: LLM provider abstraction, tool calling, retrieval, critique.

The layer does two jobs and refuses the third.

**It answers questions about stored runs** (:mod:`workflow`), through a
read-only tool surface (:mod:`tools`) over a narrow port
(:mod:`gateway`), with documentation retrieval that returns citable chunk
ids (:mod:`rag`).

**It argues with a conclusion** (:mod:`critique`), on top of the
deterministic rules in :mod:`planbench_decision.self_check` — which it
may reorder and extend but never overrule.

**It does not run experiments.** Launching a comparison, editing a
deployment and approving a result are human acts on the decisions page.
The agent has no method for any of them, which is a stronger guarantee
than a policy flag: there is no code path to disable.

Provider choice is configuration (:mod:`factory`). With no API key the
layer falls back to a deterministic keyword responder and says so, so an
offline run is honest about being offline rather than silently thinner.
"""

from planbench_agent.critique import (
    CRITIQUE_MAX_TOKENS,
    CRITIQUE_SYSTEM,
    CritiqueResult,
    ScoredFinding,
    critique_schema,
    critique_with_model,
)
from planbench_agent.deterministic import DeterministicResponder
from planbench_agent.factory import (
    AUTO_ORDER,
    PROVIDERS,
    ProviderStatus,
    ProviderUnavailable,
    build_provider,
    provider_status,
)
from planbench_agent.gateway import (
    AgentGateway,
    CandidateSummary,
    DecisionRunSummary,
    DeploymentSummary,
    GatewayError,
    ScenarioSummary,
)
from planbench_agent.provider import (
    LLMMessage,
    LLMProvider,
    LLMRequest,
    LLMResponse,
    MessageRole,
    MockProvider,
    StopReason,
    ToolCall,
    ToolResult,
    ToolSpec,
)
from planbench_agent.rag import (
    Chunk,
    KnowledgeBase,
    RetrievedChunk,
    load_markdown_directory,
    split_markdown,
)
from planbench_agent.tools import (
    FORBIDDEN_CAPABILITIES,
    Effect,
    Tool,
    ToolPolicy,
    ToolRegistry,
    build_registry,
)
from planbench_agent.workflow import (
    CHAT_SYSTEM,
    MAX_TOOL_ITERATIONS,
    AgentService,
    ChatTurn,
)

__all__ = [
    "AUTO_ORDER",
    "CHAT_SYSTEM",
    "CRITIQUE_MAX_TOKENS",
    "CRITIQUE_SYSTEM",
    "FORBIDDEN_CAPABILITIES",
    "MAX_TOOL_ITERATIONS",
    "PROVIDERS",
    "AgentGateway",
    "AgentService",
    "CandidateSummary",
    "ChatTurn",
    "Chunk",
    "CritiqueResult",
    "DecisionRunSummary",
    "DeploymentSummary",
    "DeterministicResponder",
    "Effect",
    "GatewayError",
    "KnowledgeBase",
    "LLMMessage",
    "LLMProvider",
    "LLMRequest",
    "LLMResponse",
    "MessageRole",
    "MockProvider",
    "ProviderStatus",
    "ProviderUnavailable",
    "RetrievedChunk",
    "ScenarioSummary",
    "ScoredFinding",
    "StopReason",
    "Tool",
    "ToolCall",
    "ToolPolicy",
    "ToolRegistry",
    "ToolResult",
    "ToolSpec",
    "build_provider",
    "build_registry",
    "critique_schema",
    "critique_with_model",
    "load_markdown_directory",
    "provider_status",
    "split_markdown",
]
