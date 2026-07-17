from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_current_user
from backend.app.api.search import hybrid_search
from backend.app.database.session import get_db
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
from backend.app.services.rag_service import (
    prepare_evidence,
)


router = APIRouter(
    prefix="/api/v1/questions",
    tags=["questions"],
)


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
    """Answer using validated evidence from organisation documents."""

    question_text = request.question.strip()

    if not question_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The question cannot be empty.",
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
        return AskQuestionResponse(
            question=question_text,
            answer=NO_EVIDENCE_ANSWER,
            grounded=False,
            citation_count=0,
            citations=[],
        )

    answer = generate_grounded_answer(
        question=question_text,
        context=evidence.context,
    )

    grounded = (
        answer != NO_EVIDENCE_ANSWER
        and bool(evidence.citations)
    )

    return AskQuestionResponse(
        question=question_text,
        answer=answer,
        grounded=grounded,
        citation_count=len(evidence.citations),
        citations=evidence.citations,
    )