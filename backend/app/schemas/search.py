import uuid

from pydantic import BaseModel, Field


class SemanticSearchRequest(BaseModel):
    """Request body for semantic search."""

    query: str = Field(
        min_length=2,
        max_length=1000,
    )

    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
    )


class SemanticSearchResult(BaseModel):
    """One document chunk returned by semantic search."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    original_filename: str
    page_number: int | None
    chunk_index: int
    content: str
    similarity_score: float


class SemanticSearchResponse(BaseModel):
    """Complete semantic-search response."""

    query: str
    result_count: int
    results: list[SemanticSearchResult]