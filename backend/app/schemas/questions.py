import uuid

from pydantic import BaseModel, Field


class AskQuestionRequest(BaseModel):
    """Question sent by the authenticated user."""

    question: str = Field(
        min_length=2,
        max_length=2000,
    )

    top_k: int = Field(
        default=5,
        ge=1,
        le=10,
    )


class AnswerCitation(BaseModel):
    """One document chunk supporting the answer."""

    citation_number: int
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    original_filename: str
    page_number: int | None
    chunk_index: int
    excerpt: str
    rerank_score: float


class AskQuestionResponse(BaseModel):
    """Grounded answer and its supporting citations."""

    question: str
    answer: str
    grounded: bool
    citation_count: int
    citations: list[AnswerCitation]