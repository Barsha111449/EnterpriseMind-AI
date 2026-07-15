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
    """One chunk returned by semantic search."""

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


class KeywordSearchRequest(BaseModel):
    """Request body for keyword search."""

    query: str = Field(
        min_length=2,
        max_length=1000,
    )

    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
    )


class KeywordSearchResult(BaseModel):
    """One chunk returned by keyword search."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    original_filename: str
    page_number: int | None
    chunk_index: int
    content: str
    keyword_score: float


class KeywordSearchResponse(BaseModel):
    """Complete keyword-search response."""

    query: str
    result_count: int
    results: list[KeywordSearchResult]


class HybridSearchRequest(BaseModel):
    """Request body for hybrid search."""

    query: str = Field(
        min_length=2,
        max_length=1000,
    )

    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
    )


class HybridSearchResult(BaseModel):
    """One chunk returned by hybrid search."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    original_filename: str
    page_number: int | None
    chunk_index: int
    content: str

    semantic_score: float | None
    keyword_score: float | None
    hybrid_score: float


class HybridSearchResponse(BaseModel):
    """Complete hybrid-search response."""

    query: str
    result_count: int
    results: list[HybridSearchResult]