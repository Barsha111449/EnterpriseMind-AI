from datetime import datetime, timezone
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_current_user
from backend.app.api.search import hybrid_search
from backend.app.database.session import get_db
from backend.app.models.conversation import Conversation
from backend.app.models.message import Message
from backend.app.schemas.authentication import CurrentUserResponse
from backend.app.schemas.questions import (
    AskQuestionRequest,
    AskQuestionResponse,
)
from backend.app.schemas.search import HybridSearchRequest
from backend.app.services.answer_generation_service import (
    NO_EVIDENCE_ANSWER,
    generate_grounded_answer,
)
from backend.app.services.evidence_validation_service import (
    filter_relevant_candidates,
)
from backend.app.services.rag_service import prepare_evidence


router = APIRouter(
    prefix="/api/v1/questions",
    tags=["questions"],
)


def get_question_conversation(
    request: AskQuestionRequest,
    current_user: CurrentUserResponse,
    database_session: Session,
) -> Conversation | None:
    """
    Return the conversation selected by the current user.

    When no conversation ID is provided, the question is answered
    normally without saving it to conversation history.
    """

    conversation_id = getattr(
        request,
        "conversation_id",
        None,
    )

    if conversation_id is None:
        return None

    statement = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.organization_id
        == current_user.organization_id,
        Conversation.user_id == current_user.user_id,
    )

    conversation = database_session.scalar(statement)

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    return conversation


def save_question_exchange(
    conversation: Conversation,
    response: AskQuestionResponse,
    current_user: CurrentUserResponse,
    database_session: Session,
) -> None:
    """
    Save the user's question and the assistant's answer.

    Two separate message records are created:
    one user message and one assistant message.
    """

    user_message = Message(
        organization_id=current_user.organization_id,
        conversation_id=conversation.id,
        role="user",
        content=response.question,
        grounded=None,
        citations=[],
    )

    assistant_message = Message(
        organization_id=current_user.organization_id,
        conversation_id=conversation.id,
        role="assistant",
        content=response.answer,
        grounded=response.grounded,
        citations=[
            citation.model_dump(mode="json")
            for citation in response.citations
        ],
    )

    conversation.updated_at = datetime.now(timezone.utc)

    database_session.add_all(
        [
            user_message,
            assistant_message,
        ]
    )

    database_session.commit()


@router.post(
    "/ask",
    response_model=AskQuestionResponse,
)
def ask_question(
    request: AskQuestionRequest,
    current_user: Annotated[
        CurrentUserResponse,
        Depends(get_current_user),
    ],
    database_session: Annotated[
        Session,
        Depends(get_db),
    ],
) -> AskQuestionResponse:
    """
    Answer a question using validated organisation evidence.

    When a conversation ID is supplied, the user question and
    assistant answer are also saved in the messages table.
    """

    question_text = request.question.strip()

    if not question_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The question cannot be empty.",
        )

    conversation = get_question_conversation(
        request=request,
        current_user=current_user,
        database_session=database_session,
    )

    hybrid_response = hybrid_search(
        search_request=HybridSearchRequest(
            query=question_text,
            top_k=request.top_k,
        ),
        current_user=current_user,
        database_session=database_session,
    )

    retrieved_candidates = [
        result.model_dump()
        for result in hybrid_response.results
    ]

    relevant_candidates = filter_relevant_candidates(
        candidates=retrieved_candidates,
        top_k=request.top_k,
    )

    evidence = prepare_evidence(
        candidates=relevant_candidates,
        top_k=request.top_k,
    )

    if not evidence.citations:
        response = AskQuestionResponse(
            question=question_text,
            answer=NO_EVIDENCE_ANSWER,
            grounded=False,
            citation_count=0,
            citations=[],
        )

    else:
        answer = generate_grounded_answer(
            question=question_text,
            context=evidence.context,
        )

        grounded = (
            answer != NO_EVIDENCE_ANSWER
            and bool(evidence.citations)
        )

        response = AskQuestionResponse(
            question=question_text,
            answer=answer,
            grounded=grounded,
            citation_count=len(evidence.citations),
            citations=evidence.citations,
        )

    if conversation is not None:
        save_question_exchange(
            conversation=conversation,
            response=response,
            current_user=current_user,
            database_session=database_session,
        )

    return response