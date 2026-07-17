import uuid
from datetime import datetime
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class ConversationCreateRequest(BaseModel):
    """Information required to create a conversation."""

    title: str = Field(
        default="New conversation",
        min_length=1,
        max_length=255,
    )


class ConversationResponse(BaseModel):
    """One conversation returned by the API."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: uuid.UUID
    organization_id: uuid.UUID
    user_id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime


class MessageResponse(BaseModel):
    """One stored message inside a conversation."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: uuid.UUID
    organization_id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    grounded: bool | None
    citations: list[dict[str, Any]]
    created_at: datetime