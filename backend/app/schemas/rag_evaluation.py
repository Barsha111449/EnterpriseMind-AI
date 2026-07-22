import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RagEvaluationResponse(BaseModel):
    """One stored RAG evaluation result."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: uuid.UUID
    organization_id: uuid.UUID
    user_id: uuid.UUID | None

    question: str
    answer: str
    grounded: bool
    citation_count: int

    retrieval_relevance: float
    citation_coverage: float
    groundedness_consistency: float
    response_latency_ms: float

    retrieved_candidate_count: int
    relevant_candidate_count: int

    created_at: datetime


class RagEvaluationListResponse(BaseModel):
    """Paginated collection of RAG evaluation records."""

    items: list[RagEvaluationResponse]
    total: int
    limit: int
    offset: int


class RagEvaluationSummaryResponse(BaseModel):
    """Aggregated RAG quality measurements."""

    total_evaluations: int
    grounded_count: int
    ungrounded_count: int
    grounded_rate: float

    average_retrieval_relevance: float
    average_citation_coverage: float
    average_groundedness_consistency: float
    average_response_latency_ms: float

    average_retrieved_candidate_count: float
    average_relevant_candidate_count: float