"""The assistant as a conversation, not a set of forms.

The old page asked a user to know which provider was configured, what an
internal tool was called, and which benchmark id they meant. This module
replaces that with an ordinary chat: the assistant asks what it needs,
and the answer arrives as structured data the backend validates.

Three rules shape it, and each is enforced here rather than requested in
a prompt:

**The assistant proposes; the person disposes.** A proposal is a message
in the transcript. Nothing is created until a separate, explicit
``confirm-draft`` call — a different endpoint, with the proposal id — so
"the model decided to make a benchmark" cannot happen.

**It never runs anything.** There is no run tool in the conversation
surface. Running is a button on the benchmark page, pressed by a person.

**It cannot invent an id.** Every id in a proposal is checked against
real records before a draft is created; an id the assistant made up
fails validation with a message saying so, rather than producing a
benchmark pointing at nothing.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from planbench_api.accounts import now_iso


class Role(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class ProposalStatus(StrEnum):
    """What has happened to a proposal the assistant made."""

    DRAFT = "draft"
    #: Turned into a real benchmark, by a person clicking.
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class BenchmarkProposal(BaseModel):
    """What the assistant thinks the user wants, as structured data.

    Every id here must exist. ``missing_fields`` is how the assistant
    says "I still need this" without guessing — a proposal with anything
    in it is shown as a question, not as a confirm button.
    """

    model_config = ConfigDict(frozen=True)

    id: str = ""
    name: str = ""
    map_id: str = ""
    scenario_id: str = ""
    scenario_name: str = ""
    stacks: tuple[str, ...] = ()
    seeds: tuple[int, ...] = ()
    robot_profile_id: str = ""
    model_id: str = ""
    model_label: str = ""
    user_priority: str = ""
    #: What the assistant assumed because the user did not say.
    assumptions: tuple[str, ...] = ()
    #: What it still needs before this can be created.
    missing_fields: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    status: ProposalStatus = ProposalStatus.DRAFT
    benchmark_id: str = ""

    @property
    def ready(self) -> bool:
        """Complete enough to offer a "create draft" button."""
        return (
            not self.missing_fields
            and bool(self.map_id)
            and bool(self.scenario_id)
            and bool(self.stacks)
            and bool(self.seeds)
        )


class ChatMessage(BaseModel):
    """One turn, as the client renders it."""

    model_config = ConfigDict(frozen=True)

    sequence: int = 0
    role: Role
    content: str
    #: A proposal or a result card, when the turn produced one.
    proposal: BenchmarkProposal | None = None
    result: dict | None = None
    created_at: str = Field(default_factory=now_iso)


class Conversation(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    title: str = ""
    locale: str = "en"
    created_at: str = ""
    updated_at: str = ""


class ConversationDetail(BaseModel):
    conversation: Conversation
    messages: list[ChatMessage] = []


def message_from_row(row: dict) -> ChatMessage:
    """Rehydrate a stored turn, tolerating a payload from an older build."""
    payload = row.get("payload") or {}
    proposal = payload.get("proposal")
    return ChatMessage(
        sequence=row.get("sequence", 0),
        role=Role(row.get("role", "assistant")),
        content=row.get("content", ""),
        proposal=BenchmarkProposal.model_validate(proposal) if proposal else None,
        result=payload.get("result"),
        created_at=row.get("created_at", ""),
    )


def conversation_from_row(row: dict) -> Conversation:
    return Conversation(
        id=row["id"],
        title=row.get("title", ""),
        locale=row.get("locale", "en"),
        created_at=row.get("created_at", ""),
        updated_at=row.get("updated_at", ""),
    )


#: A short title for the sidebar, taken from the first thing asked.
TITLE_LENGTH = 60


def title_from(text: str) -> str:
    cleaned = " ".join(text.split())
    return cleaned[:TITLE_LENGTH] + ("…" if len(cleaned) > TITLE_LENGTH else "")


__all__ = [
    "BenchmarkProposal",
    "ChatMessage",
    "Conversation",
    "ConversationDetail",
    "ProposalStatus",
    "Role",
    "conversation_from_row",
    "message_from_row",
    "title_from",
]
