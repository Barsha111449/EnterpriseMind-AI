from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_current_user
from backend.app.database.session import get_db
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.schemas.authentication import CurrentUserResponse
from backend.app.schemas.search import (
    KeywordSearchRequest,
    KeywordSearchResponse,
    KeywordSearchResult,
    SemanticSearchRequest,
    SemanticSearchResponse,
    SemanticSearchResult,
)
from backend.app.services.embedding_service import (
    generate_embeddings,
)


router = APIRouter(
    prefix="/api/v1/search",
    tags=["search"],
)


@router.post(
    "/semantic",
    response_model=SemanticSearchResponse,
)
def semantic_search(
    search_request: SemanticSearchRequest,
    current_user: Annotated[
        CurrentUserResponse,
        Depends(get_current_user),
    ],
    database_session: Annotated[
        Session,
        Depends(get_db),
    ],
) -> SemanticSearchResponse:
    """Search document chunks using vector similarity."""

    query_text = search_request.query.strip()

    if not query_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The search query cannot be empty.",
        )

    query_embeddings = generate_embeddings(
        [query_text]
    )

    if not query_embeddings:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail="Could not generate the query embedding.",
        )

    query_embedding = query_embeddings[0]

    cosine_distance = (
        DocumentChunk.embedding.cosine_distance(
            query_embedding
        ).label("cosine_distance")
    )

    statement = (
        select(
            DocumentChunk,
            Document.original_filename,
            cosine_distance,
        )
        .join(
            Document,
            Document.id == DocumentChunk.document_id,
        )
        .where(
            DocumentChunk.organization_id
            == current_user.organization_id,
            Document.organization_id
            == current_user.organization_id,
            DocumentChunk.embedding.is_not(None),
            Document.status == "ready",
        )
        .order_by(cosine_distance)
        .limit(search_request.top_k)
    )

    rows = database_session.execute(statement).all()

    results: list[SemanticSearchResult] = []

    for chunk, original_filename, distance in rows:
        similarity_score = 1.0 - float(distance)

        similarity_score = max(
            -1.0,
            min(1.0, similarity_score),
        )

        results.append(
            SemanticSearchResult(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                original_filename=original_filename,
                page_number=chunk.page_number,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                similarity_score=round(
                    similarity_score,
                    6,
                ),
            )
        )

    return SemanticSearchResponse(
        query=query_text,
        result_count=len(results),
        results=results,
    )


@router.post(
    "/keyword",
    response_model=KeywordSearchResponse,
)
def keyword_search(
    search_request: KeywordSearchRequest,
    current_user: Annotated[
        CurrentUserResponse,
        Depends(get_current_user),
    ],
    database_session: Annotated[
        Session,
        Depends(get_db),
    ],
) -> KeywordSearchResponse:
    """Search document chunks using PostgreSQL full-text search."""

    query_text = search_request.query.strip()

    if not query_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The search query cannot be empty.",
        )

    search_vector = func.to_tsvector(
        "english",
        DocumentChunk.content,
    )

    search_query = func.plainto_tsquery(
        "english",
        query_text,
    )

    keyword_score = func.ts_rank_cd(
        search_vector,
        search_query,
    ).label("keyword_score")

    statement = (
        select(
            DocumentChunk,
            Document.original_filename,
            keyword_score,
        )
        .join(
            Document,
            Document.id == DocumentChunk.document_id,
        )
        .where(
            DocumentChunk.organization_id
            == current_user.organization_id,
            Document.organization_id
            == current_user.organization_id,
            Document.status == "ready",
            search_vector.bool_op("@@")(
                search_query
            ),
        )
        .order_by(keyword_score.desc())
        .limit(search_request.top_k)
    )

    rows = database_session.execute(statement).all()

    results: list[KeywordSearchResult] = []

    for chunk, original_filename, score in rows:
        results.append(
            KeywordSearchResult(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                original_filename=original_filename,
                page_number=chunk.page_number,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                keyword_score=round(
                    float(score or 0.0),
                    6,
                ),
            )
        )

    return KeywordSearchResponse(
        query=query_text,
        result_count=len(results),
        results=results,
    )