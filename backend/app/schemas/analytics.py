import uuid

from pydantic import BaseModel, Field


class FeedbackAnalyticsResponse(BaseModel):
    """Feedback and answer-quality statistics for one organization."""

    organization_id: uuid.UUID

    total_assistant_messages: int = Field(ge=0)
    grounded_answers: int = Field(ge=0)
    ungrounded_answers: int = Field(ge=0)

    total_feedback: int = Field(ge=0)
    helpful_feedback: int = Field(ge=0)
    unhelpful_feedback: int = Field(ge=0)
    rated_messages: int = Field(ge=0)

    helpful_percentage: float = Field(ge=0, le=100)
    feedback_coverage_percentage: float = Field(
        ge=0,
        le=100,
    )