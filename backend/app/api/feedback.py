import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Response,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_current_user
from backend.app.database.session import get_db
from backend.app.models.conversation import Conversation
from backend.app.models.message import Message
from backend.app.models.message_feedback import MessageFeedback
from backend.app.schemas.authentication import CurrentUserResponse
from backend.app.schemas.feedback import (
    FeedbackCreateRequest,
    FeedbackResponse,
)
from backend.app.services.audit_service import record_audit_event


router = APIRouter(
    prefix="/api/v1/messages",
    tags=["feedback"],
)


def get_owned_message(
    message_id: uuid.UUID,
    current_user: CurrentUserResponse,
    database_session: Session,
) -> Message:
    """Return a message from a conversation owned by the current user."""

    statement = (
        select(Message)
        .join(
            Conversation,
            Conversation.id == Message.conversation_id,
        )
        .where(
            Message.id == message_id,
            Message.organization_id
            == current_user.organization_id,
            Conversation.organization_id
            == current_user.organization_id,
            Conversation.user_id
            == current_user.user_id,
        )
    )

    message = database_session.scalar(statement)

    if message is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found.",
        )

    return message


def get_owned_assistant_message(
    message_id: uuid.UUID,
    current_user: CurrentUserResponse,
    database_session: Session,
) -> Message:
    """Return an assistant message owned by the current user."""

    message = get_owned_message(
        message_id=message_id,
        current_user=current_user,
        database_session=database_session,
    )

    if message.role != "assistant":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Feedback can only be submitted "
                "for assistant messages."
            ),
        )

    return message


@router.post(
    "/{message_id}/feedback",
    response_model=FeedbackResponse,
    status_code=status.HTTP_200_OK,
)
def create_or_update_feedback(
    message_id: uuid.UUID,
    request: FeedbackCreateRequest,
    current_user: Annotated[
        CurrentUserResponse,
        Depends(get_current_user),
    ],
    database_session: Annotated[
        Session,
        Depends(get_db),
    ],
) -> FeedbackResponse:
    """Create new feedback or update existing feedback."""

    message = get_owned_assistant_message(
        message_id=message_id,
        current_user=current_user,
        database_session=database_session,
    )

    statement = select(MessageFeedback).where(
        MessageFeedback.message_id == message.id,
        MessageFeedback.user_id == current_user.user_id,
        MessageFeedback.organization_id
        == current_user.organization_id,
    )

    feedback = database_session.scalar(statement)

    comment = request.comment

    if comment is not None:
        comment = comment.strip()

        if not comment:
            comment = None

    if feedback is None:
        feedback = MessageFeedback(
            organization_id=current_user.organization_id,
            user_id=current_user.user_id,
            message_id=message.id,
            rating=request.rating,
            comment=comment,
        )

        database_session.add(feedback)
        database_session.flush()

        record_audit_event(
            database_session,
            organization_id=current_user.organization_id,
            actor_user_id=current_user.user_id,
            action="feedback.created",
            resource_type="feedback",
            resource_id=feedback.id,
            description=(
                "Feedback was submitted for an assistant message."
            ),
            details={
                "message_id": str(message.id),
                "conversation_id": str(message.conversation_id),
                "rating": feedback.rating,
                "comment": feedback.comment,
            },
        )

    else:
        previous_rating = feedback.rating
        previous_comment = feedback.comment

        if (
            previous_rating == request.rating
            and previous_comment == comment
        ):
            return FeedbackResponse.model_validate(feedback)

        feedback.rating = request.rating
        feedback.comment = comment
        feedback.updated_at = datetime.now(timezone.utc)

        record_audit_event(
            database_session,
            organization_id=current_user.organization_id,
            actor_user_id=current_user.user_id,
            action="feedback.updated",
            resource_type="feedback",
            resource_id=feedback.id,
            description=(
                "Feedback for an assistant message was updated."
            ),
            details={
                "message_id": str(message.id),
                "conversation_id": str(message.conversation_id),
                "previous_rating": previous_rating,
                "new_rating": feedback.rating,
                "previous_comment": previous_comment,
                "new_comment": feedback.comment,
            },
        )

    database_session.commit()
    database_session.refresh(feedback)

    return FeedbackResponse.model_validate(feedback)


@router.get(
    "/{message_id}/feedback",
    response_model=FeedbackResponse,
)
def get_feedback(
    message_id: uuid.UUID,
    current_user: Annotated[
        CurrentUserResponse,
        Depends(get_current_user),
    ],
    database_session: Annotated[
        Session,
        Depends(get_db),
    ],
) -> FeedbackResponse:
    """Return the current user's feedback for an assistant message."""

    message = get_owned_assistant_message(
        message_id=message_id,
        current_user=current_user,
        database_session=database_session,
    )

    statement = select(MessageFeedback).where(
        MessageFeedback.message_id == message.id,
        MessageFeedback.user_id == current_user.user_id,
        MessageFeedback.organization_id
        == current_user.organization_id,
    )

    feedback = database_session.scalar(statement)

    if feedback is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feedback not found.",
        )

    return FeedbackResponse.model_validate(feedback)


@router.delete(
    "/{message_id}/feedback",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_feedback(
    message_id: uuid.UUID,
    current_user: Annotated[
        CurrentUserResponse,
        Depends(get_current_user),
    ],
    database_session: Annotated[
        Session,
        Depends(get_db),
    ],
) -> Response:
    """Delete the current user's feedback."""

    message = get_owned_assistant_message(
        message_id=message_id,
        current_user=current_user,
        database_session=database_session,
    )

    statement = select(MessageFeedback).where(
        MessageFeedback.message_id == message.id,
        MessageFeedback.user_id == current_user.user_id,
        MessageFeedback.organization_id
        == current_user.organization_id,
    )

    feedback = database_session.scalar(statement)

    if feedback is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feedback not found.",
        )

    record_audit_event(
        database_session,
        organization_id=current_user.organization_id,
        actor_user_id=current_user.user_id,
        action="feedback.deleted",
        resource_type="feedback",
        resource_id=feedback.id,
        description=(
            "Feedback for an assistant message was deleted."
        ),
        details={
            "message_id": str(message.id),
            "conversation_id": str(message.conversation_id),
            "deleted_rating": feedback.rating,
            "deleted_comment": feedback.comment,
        },
    )

    database_session.delete(feedback)
    database_session.commit()

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )