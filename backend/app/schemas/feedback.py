import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FeedbackCreateRequest(BaseModel):
    """Feedback submitted for an assistant answer."""

    rating: Literal[
        "helpful",
        "unhelpful",
    ]

    comment: str | None = Field(
        default=None,
        max_length=2000,
    )


class FeedbackResponse(BaseModel):
    """Stored feedback returned by the API."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: uuid.UUID
    organization_id: uuid.UUID
    user_id: uuid.UUID
    message_id: uuid.UUID
    rating: str
    comment: str | None
    created_at: datetime
    updated_at: datetime