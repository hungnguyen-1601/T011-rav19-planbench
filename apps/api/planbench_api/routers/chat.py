"""Assistant conversation endpoints.

Nothing here exposes a provider name, a model name, an API key variable
or an internal tool. Those are diagnostics — they live on /system, for
whoever has to fix something — and a person preparing a benchmark should
never have to know them.

Creating a benchmark takes two calls, not one: `messages` returns a
proposal, `confirm-draft` acts on it. The split is the guarantee that
the assistant cannot create anything on its own.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from planbench_api.auth import ActiveUser
from planbench_api.chat import ChatMessage, Conversation, ConversationDetail, conversation_from_row
from planbench_api.chat_service import ChatService
from planbench_api.dependencies import get_chat_service

router = APIRouter(prefix="/ai", tags=["assistant"])

Chat = Annotated[ChatService, Depends(get_chat_service)]


class StartRequest(BaseModel):
    locale: str = "en"


class MessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class ConfirmRequest(BaseModel):
    proposal_id: str


@router.post("/conversations", response_model=Conversation, status_code=status.HTTP_201_CREATED)
def start_conversation(payload: StartRequest, chat: Chat, user: ActiveUser) -> Conversation:
    return conversation_from_row(chat.start(user, payload.locale))


@router.get("/conversations", response_model=list[Conversation])
def list_conversations(chat: Chat, user: ActiveUser) -> list[Conversation]:
    return [conversation_from_row(row) for row in chat.list(user)]


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: str, chat: Chat, user: ActiveUser) -> ConversationDetail:
    return ConversationDetail(
        conversation=chat.conversation(conversation_id, user),
        messages=chat.history(conversation_id, user),
    )


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conversation_id: str, chat: Chat, user: ActiveUser) -> None:
    chat.delete(conversation_id, user)


@router.post("/conversations/{conversation_id}/messages", response_model=ChatMessage)
def send_message(
    conversation_id: str, payload: MessageRequest, chat: Chat, user: ActiveUser
) -> ChatMessage:
    """Say something. The reply may carry a proposal — never a benchmark."""
    return chat.reply(conversation_id, user, payload.message)


@router.post("/conversations/{conversation_id}/confirm-draft", response_model=ChatMessage)
def confirm_draft(
    conversation_id: str, payload: ConfirmRequest, chat: Chat, user: ActiveUser
) -> ChatMessage:
    """Create the benchmark a proposal describes.

    A person clicked. The result is a **draft** — running it is still a
    separate, deliberate act on the benchmark page.
    """
    return chat.confirm(conversation_id, user, payload.proposal_id)


@router.get("/results/{benchmark_id}", response_model=dict | None)
def result_card(benchmark_id: str, chat: Chat, _: ActiveUser) -> dict | None:
    """The figures for one benchmark, read from its stored report.

    Read, never recalled: the assistant cannot misquote a number it does
    not compose.
    """
    return chat.result_card(benchmark_id)


@router.get("/latest-result", response_model=dict | None)
def latest_result(chat: Chat, _: ActiveUser) -> dict | None:
    benchmark_id = chat.latest_finished_id()
    return chat.result_card(benchmark_id) if benchmark_id else None
