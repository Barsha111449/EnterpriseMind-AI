from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_current_user
from backend.app.core.permissions import (
    ANALYTICS_VIEW_ROLES,
    require_roles,
)
from backend.app.database.session import get_db
from backend.app.models.message import Message
from backend.app.models.message_feedback import MessageFeedback
from backend.app.schemas.analytics import (
    FeedbackAnalyticsResponse,
)
from backend.app.schemas.authentication import (
    CurrentUserResponse,
)


router = APIRouter(
    prefix="/api/v1/admin/analytics",
    tags=["admin analytics"],
)


def percentage(
    numerator: int,
    denominator: int,
) -> float:
    """Return a percentage safely when the denominator may be zero."""

    if denominator == 0:
        return 0.0

    return round(
        numerator / denominator * 100,
        2,
    )


@router.get(
    "/feedback",
    response_model=FeedbackAnalyticsResponse,
)
def get_feedback_analytics(
    current_user: Annotated[
        CurrentUserResponse,
        Depends(get_current_user),
    ],
    database_session: Annotated[
        Session,
        Depends(get_db),
    ],
) -> FeedbackAnalyticsResponse:
    """Return organization-scoped feedback and answer statistics."""

    require_roles(
        current_user,
        ANALYTICS_VIEW_ROLES,
        detail="Analytics access required.",
    )

    organization_id = current_user.organization_id

    total_assistant_messages = int(
        database_session.scalar(
            select(func.count(Message.id)).where(
                Message.organization_id == organization_id,
                Message.role == "assistant",
            )
        )
        or 0
    )

    grounded_answers = int(
        database_session.scalar(
            select(func.count(Message.id)).where(
                Message.organization_id == organization_id,
                Message.role == "assistant",
                Message.grounded.is_(True),
            )
        )
        or 0
    )

    ungrounded_answers = int(
        database_session.scalar(
            select(func.count(Message.id)).where(
                Message.organization_id == organization_id,
                Message.role == "assistant",
                Message.grounded.is_(False),
            )
        )
        or 0
    )

    total_feedback = int(
        database_session.scalar(
            select(func.count(MessageFeedback.id)).where(
                MessageFeedback.organization_id
                == organization_id
            )
        )
        or 0
    )

    helpful_feedback = int(
        database_session.scalar(
            select(func.count(MessageFeedback.id)).where(
                MessageFeedback.organization_id
                == organization_id,
                MessageFeedback.rating == "helpful",
            )
        )
        or 0
    )

    unhelpful_feedback = int(
        database_session.scalar(
            select(func.count(MessageFeedback.id)).where(
                MessageFeedback.organization_id
                == organization_id,
                MessageFeedback.rating == "unhelpful",
            )
        )
        or 0
    )

    rated_messages = int(
        database_session.scalar(
            select(
                func.count(
                    func.distinct(
                        MessageFeedback.message_id
                    )
                )
            ).where(
                MessageFeedback.organization_id
                == organization_id
            )
        )
        or 0
    )

    return FeedbackAnalyticsResponse(
        organization_id=organization_id,
        total_assistant_messages=total_assistant_messages,
        grounded_answers=grounded_answers,
        ungrounded_answers=ungrounded_answers,
        total_feedback=total_feedback,
        helpful_feedback=helpful_feedback,
        unhelpful_feedback=unhelpful_feedback,
        rated_messages=rated_messages,
        helpful_percentage=percentage(
            helpful_feedback,
            total_feedback,
        ),
        feedback_coverage_percentage=percentage(
            rated_messages,
            total_assistant_messages,
        ),
    )