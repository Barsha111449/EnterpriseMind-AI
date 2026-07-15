import uuid
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
    HybridSearchRequest,
    HybridSearchResponse,
    HybridSearchResult,
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
from backend.app.services.reranking_service import (
    rerank_candidates,
)


router = APIRouter(
    prefix="/api/v1/search",
    tags=["search"],
)


def clean_query(query: str) -> str:
    """Remove unnecessary spaces and reject empty queries."""

    query_text = query.strip()

    if not query_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The search query cannot be empty.",
        )

    return query_text


def get_semantic_rows(
    query_text: str,
    result_limit: int,
    organization_id: uuid.UUID,
    database_session: Session,
):
    """Retrieve document chunks using vector similarity."""

    query_embeddings = generate_embeddings(
        [query_text]
    )

    if not query_embeddings:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
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
            == organization_id,
            Document.organization_id
            == organization_id,
            DocumentChunk.embedding.is_not(None),
            Document.status == "ready",
        )
        .order_by(cosine_distance)
        .limit(result_limit)
    )

    return database_session.execute(
        statement
    ).all()


def get_keyword_rows(
    query_text: str,
    result_limit: int,
    organization_id: uuid.UUID,
    database_session: Session,
):
    """Retrieve document chunks using PostgreSQL keyword search."""

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
            == organization_id,
            Document.organization_id
            == organization_id,
            Document.status == "ready",
            search_vector.bool_op("@@")(
                search_query
            ),
        )
        .order_by(keyword_score.desc())
        .limit(result_limit)
    )

    return database_session.execute(
        statement
    ).all()


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
    """Search document chunks using semantic similarity."""

    query_text = clean_query(
        search_request.query
    )

    rows = get_semantic_rows(
        query_text=query_text,
        result_limit=search_request.top_k,
        organization_id=current_user.organization_id,
        database_session=database_session,
    )

    results: list[SemanticSearchResult] = []

    for chunk, original_filename, distance in rows:
        similarity_score = (
            1.0 - float(distance)
        )

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
    """Search document chunks using exact words and phrases."""

    query_text = clean_query(
        search_request.query
    )

    rows = get_keyword_rows(
        query_text=query_text,
        result_limit=search_request.top_k,
        organization_id=current_user.organization_id,
        database_session=database_session,
    )

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


@router.post(
    "/hybrid",
    response_model=HybridSearchResponse,
)
def hybrid_search(
    search_request: HybridSearchRequest,
    current_user: Annotated[
        CurrentUserResponse,
        Depends(get_current_user),
    ],
    database_session: Annotated[
        Session,
        Depends(get_db),
    ],
) -> HybridSearchResponse:
    """Combine semantic search, keyword search, and reranking."""

    query_text = clean_query(
        search_request.query
    )

    candidate_limit = min(
        search_request.top_k * 4,
        80,
    )

    semantic_rows = get_semantic_rows(
        query_text=query_text,
        result_limit=candidate_limit,
        organization_id=current_user.organization_id,
        database_session=database_session,
    )

    keyword_rows = get_keyword_rows(
        query_text=query_text,
        result_limit=candidate_limit,
        organization_id=current_user.organization_id,
        database_session=database_session,
    )

    combined_results: dict[
        str,
        dict,
    ] = {}

    reciprocal_rank_constant = 60.0

    for rank, row in enumerate(
        semantic_rows,
        start=1,
    ):
        chunk, original_filename, distance = row

        similarity_score = (
            1.0 - float(distance)
        )

        similarity_score = max(
            -1.0,
            min(1.0, similarity_score),
        )

        chunk_key = str(chunk.id)

        combined_results[chunk_key] = {
            "chunk_id": chunk.id,
            "document_id": chunk.document_id,
            "original_filename": original_filename,
            "page_number": chunk.page_number,
            "chunk_index": chunk.chunk_index,
            "content": chunk.content,
            "semantic_score": round(
                similarity_score,
                6,
            ),
            "keyword_score": None,
            "hybrid_score": (
                1.0
                / (
                    reciprocal_rank_constant
                    + rank
                )
            ),
        }

    for rank, row in enumerate(
        keyword_rows,
        start=1,
    ):
        chunk, original_filename, score = row

        chunk_key = str(chunk.id)

        keyword_score = round(
            float(score or 0.0),
            6,
        )

        rank_score = (
            1.0
            / (
                reciprocal_rank_constant
                + rank
            )
        )

        if chunk_key in combined_results:
            combined_results[chunk_key][
                "keyword_score"
            ] = keyword_score

            combined_results[chunk_key][
                "hybrid_score"
            ] += rank_score

        else:
            combined_results[chunk_key] = {
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "original_filename": original_filename,
                "page_number": chunk.page_number,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "semantic_score": None,
                "keyword_score": keyword_score,
                "hybrid_score": rank_score,
            }

    ranked_results = sorted(
        combined_results.values(),
        key=lambda result: result[
            "hybrid_score"
        ],
        reverse=True,
    )

    reranked_results = rerank_candidates(
        query=query_text,
        candidates=ranked_results,
        top_k=search_request.top_k,
    )

    results = [
        HybridSearchResult(
            chunk_id=result["chunk_id"],
            document_id=result["document_id"],
            original_filename=(
                result["original_filename"]
            ),
            page_number=result["page_number"],
            chunk_index=result["chunk_index"],
            content=result["content"],
            semantic_score=(
                result["semantic_score"]
            ),
            keyword_score=(
                result["keyword_score"]
            ),
            hybrid_score=round(
                float(result["hybrid_score"]),
                8,
            ),
            rerank_score=round(
                float(result["rerank_score"]),
                6,
            ),
        )
        for result in reranked_results
    ]

    return HybridSearchResponse(
        query=query_text,
        result_count=len(results),
        results=results,
    )