import uuid
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

from backend.app.api.dependencies import (
    get_current_user,
)
from backend.app.database.session import get_db
from backend.app.models.conversation import Conversation
from backend.app.models.message import Message
from backend.app.schemas.authentication import (
    CurrentUserResponse,
)
from backend.app.schemas.conversation import (
    ConversationCreateRequest,
    ConversationResponse,
    MessageResponse,
)
from backend.app.services.audit_service import (
    record_audit_event,
)


router = APIRouter(
    prefix="/api/v1/conversations",
    tags=["conversations"],
)


def get_owned_conversation(
    conversation_id: uuid.UUID,
    current_user: CurrentUserResponse,
    database_session: Session,
) -> Conversation:
    """Return a conversation owned by the current user."""

    statement = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.organization_id
        == current_user.organization_id,
        Conversation.user_id
        == current_user.user_id,
    )

    conversation = database_session.scalar(
        statement
    )

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    return conversation


@router.post(
    "",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation(
    request: ConversationCreateRequest,
    current_user: Annotated[
        CurrentUserResponse,
        Depends(get_current_user),
    ],
    database_session: Annotated[
        Session,
        Depends(get_db),
    ],
) -> ConversationResponse:
    """Create a private conversation for the current user."""

    title = request.title.strip()

    if not title:
        title = "New conversation"

    conversation = Conversation(
        organization_id=current_user.organization_id,
        user_id=current_user.user_id,
        title=title,
    )

    database_session.add(conversation)
    database_session.flush()

    record_audit_event(
        database_session,
        organization_id=current_user.organization_id,
        actor_user_id=current_user.user_id,
        action="conversation.created",
        resource_type="conversation",
        resource_id=conversation.id,
        description=(
            f"Conversation '{conversation.title}' was created."
        ),
        details={
            "conversation_title": conversation.title,
            "conversation_user_id": str(
                conversation.user_id
            ),
        },
    )

    database_session.commit()
    database_session.refresh(conversation)

    return ConversationResponse.model_validate(
        conversation
    )


@router.get(
    "",
    response_model=list[ConversationResponse],
)
def list_conversations(
    current_user: Annotated[
        CurrentUserResponse,
        Depends(get_current_user),
    ],
    database_session: Annotated[
        Session,
        Depends(get_db),
    ],
) -> list[ConversationResponse]:
    """List conversations belonging to the current user."""

    statement = (
        select(Conversation)
        .where(
            Conversation.organization_id
            == current_user.organization_id,
            Conversation.user_id
            == current_user.user_id,
        )
        .order_by(
            Conversation.updated_at.desc()
        )
    )

    conversations = database_session.scalars(
        statement
    ).all()

    return [
        ConversationResponse.model_validate(
            conversation
        )
        for conversation in conversations
    ]


@router.get(
    "/{conversation_id}",
    response_model=ConversationResponse,
)
def get_conversation(
    conversation_id: uuid.UUID,
    current_user: Annotated[
        CurrentUserResponse,
        Depends(get_current_user),
    ],
    database_session: Annotated[
        Session,
        Depends(get_db),
    ],
) -> ConversationResponse:
    """Return one conversation owned by the current user."""

    conversation = get_owned_conversation(
        conversation_id=conversation_id,
        current_user=current_user,
        database_session=database_session,
    )

    return ConversationResponse.model_validate(
        conversation
    )


@router.get(
    "/{conversation_id}/messages",
    response_model=list[MessageResponse],
)
def list_conversation_messages(
    conversation_id: uuid.UUID,
    current_user: Annotated[
        CurrentUserResponse,
        Depends(get_current_user),
    ],
    database_session: Annotated[
        Session,
        Depends(get_db),
    ],
) -> list[MessageResponse]:
    """List messages stored inside one conversation."""

    conversation = get_owned_conversation(
        conversation_id=conversation_id,
        current_user=current_user,
        database_session=database_session,
    )

    statement = (
        select(Message)
        .where(
            Message.conversation_id
            == conversation.id,
            Message.organization_id
            == current_user.organization_id,
        )
        .order_by(
            Message.created_at,
            Message.id,
        )
    )

    messages = database_session.scalars(
        statement
    ).all()

    return [
        MessageResponse.model_validate(message)
        for message in messages
    ]


@router.delete(
    "/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_conversation(
    conversation_id: uuid.UUID,
    current_user: Annotated[
        CurrentUserResponse,
        Depends(get_current_user),
    ],
    database_session: Annotated[
        Session,
        Depends(get_db),
    ],
) -> Response:
    """Delete one conversation and its messages."""

    conversation = get_owned_conversation(
        conversation_id=conversation_id,
        current_user=current_user,
        database_session=database_session,
    )

    conversation_title = conversation.title
    conversation_user_id = conversation.user_id

    record_audit_event(
        database_session,
        organization_id=current_user.organization_id,
        actor_user_id=current_user.user_id,
        action="conversation.deleted",
        resource_type="conversation",
        resource_id=conversation.id,
        description=(
            f"Conversation '{conversation_title}' was deleted."
        ),
        details={
            "conversation_title": conversation_title,
            "conversation_user_id": str(
                conversation_user_id
            ),
        },
    )

    database_session.delete(conversation)
    database_session.commit()

    return Response(
        status_code=status.HTTP_204_NO_CONTENT
    )