import uuid
from collections.abc import Sequence

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.evaluation.metrics import (
    calculate_citation_coverage,
    calculate_groundedness_consistency,
    calculate_retrieval_relevance,
)
from backend.app.models.rag_evaluation import RagEvaluation
from backend.app.services.answer_generation_service import (
    NO_EVIDENCE_ANSWER,
)


def record_rag_evaluation(
    database_session: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    question: str,
    answer: str,
    grounded: bool,
    citation_count: int,
    evidence_texts: Sequence[str],
    response_latency_ms: float,
    retrieved_candidate_count: int,
    relevant_candidate_count: int,
) -> RagEvaluation | None:
    """
    Calculate and save quality metrics for one RAG response.

    Evaluation failures do not break the user's question request.
    """

    retrieval_relevance = calculate_retrieval_relevance(
        question=question,
        evidence_texts=evidence_texts,
    )

    citation_coverage = calculate_citation_coverage(
        grounded=grounded,
        citation_count=citation_count,
    )

    groundedness_consistency = (
        calculate_groundedness_consistency(
            answer=answer,
            grounded=grounded,
            citation_count=citation_count,
            no_evidence_answer=NO_EVIDENCE_ANSWER,
        )
    )

    evaluation = RagEvaluation(
        organization_id=organization_id,
        user_id=user_id,
        question=question,
        answer=answer,
        grounded=grounded,
        citation_count=max(0, citation_count),
        retrieval_relevance=retrieval_relevance,
        citation_coverage=citation_coverage,
        groundedness_consistency=groundedness_consistency,
        response_latency_ms=max(
            0.0,
            round(response_latency_ms, 3),
        ),
        retrieved_candidate_count=max(
            0,
            retrieved_candidate_count,
        ),
        relevant_candidate_count=max(
            0,
            relevant_candidate_count,
        ),
    )

    try:
        database_session.add(evaluation)
        database_session.commit()
        database_session.refresh(evaluation)

        return evaluation

    except SQLAlchemyError:
        database_session.rollback()

        return None