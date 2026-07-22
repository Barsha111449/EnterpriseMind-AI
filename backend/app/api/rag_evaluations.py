import uuid
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Query,
)
from sqlalchemy import (
    case,
    func,
    select,
)
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_current_user
from backend.app.core.permissions import (
    ANALYTICS_VIEW_ROLES,
    require_roles,
)
from backend.app.database.session import get_db
from backend.app.models.rag_evaluation import RagEvaluation
from backend.app.schemas.authentication import CurrentUserResponse
from backend.app.schemas.rag_evaluation import (
    RagEvaluationListResponse,
    RagEvaluationResponse,
    RagEvaluationSummaryResponse,
)


router = APIRouter(
    prefix="/api/v1/admin/rag-evaluations",
    tags=["RAG evaluation"],
)


@router.get(
    "",
    response_model=RagEvaluationListResponse,
)
def list_rag_evaluations(
    current_user: Annotated[
        CurrentUserResponse,
        Depends(get_current_user),
    ],
    database_session: Annotated[
        Session,
        Depends(get_db),
    ],
    grounded: Annotated[
        bool | None,
        Query(
            description=(
                "Filter evaluations by grounded status."
            ),
        ),
    ] = None,
    user_id: Annotated[
        uuid.UUID | None,
        Query(
            description=(
                "Filter evaluations by the user "
                "who asked the question."
            ),
        ),
    ] = None,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=200,
        ),
    ] = 50,
    offset: Annotated[
        int,
        Query(
            ge=0,
        ),
    ] = 0,
) -> RagEvaluationListResponse:
    """List RAG evaluations belonging to the organization."""

    require_roles(
        current_user,
        ANALYTICS_VIEW_ROLES,
        detail="Analytics access required.",
    )

    filters = [
        RagEvaluation.organization_id
        == current_user.organization_id
    ]

    if grounded is not None:
        filters.append(
            RagEvaluation.grounded.is_(grounded)
        )

    if user_id is not None:
        filters.append(
            RagEvaluation.user_id == user_id
        )

    total_statement = (
        select(
            func.count(RagEvaluation.id)
        )
        .where(*filters)
    )

    total = (
        database_session.scalar(
            total_statement
        )
        or 0
    )

    evaluations_statement = (
        select(RagEvaluation)
        .where(*filters)
        .order_by(
            RagEvaluation.created_at.desc(),
            RagEvaluation.id.desc(),
        )
        .limit(limit)
        .offset(offset)
    )

    evaluations = database_session.scalars(
        evaluations_statement
    ).all()

    return RagEvaluationListResponse(
        items=[
            RagEvaluationResponse.model_validate(
                evaluation
            )
            for evaluation in evaluations
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/summary",
    response_model=RagEvaluationSummaryResponse,
)
def get_rag_evaluation_summary(
    current_user: Annotated[
        CurrentUserResponse,
        Depends(get_current_user),
    ],
    database_session: Annotated[
        Session,
        Depends(get_db),
    ],
) -> RagEvaluationSummaryResponse:
    """Return organization-level RAG quality statistics."""

    require_roles(
        current_user,
        ANALYTICS_VIEW_ROLES,
        detail="Analytics access required.",
    )

    statement = (
        select(
            func.count(
                RagEvaluation.id
            ).label("total_evaluations"),
            func.sum(
                case(
                    (
                        RagEvaluation.grounded.is_(True),
                        1,
                    ),
                    else_=0,
                )
            ).label("grounded_count"),
            func.avg(
                RagEvaluation.retrieval_relevance
            ).label(
                "average_retrieval_relevance"
            ),
            func.avg(
                RagEvaluation.citation_coverage
            ).label(
                "average_citation_coverage"
            ),
            func.avg(
                RagEvaluation.groundedness_consistency
            ).label(
                "average_groundedness_consistency"
            ),
            func.avg(
                RagEvaluation.response_latency_ms
            ).label(
                "average_response_latency_ms"
            ),
            func.avg(
                RagEvaluation.retrieved_candidate_count
            ).label(
                "average_retrieved_candidate_count"
            ),
            func.avg(
                RagEvaluation.relevant_candidate_count
            ).label(
                "average_relevant_candidate_count"
            ),
        )
        .where(
            RagEvaluation.organization_id
            == current_user.organization_id
        )
    )

    result = database_session.execute(
        statement
    ).mappings().one()

    total_evaluations = int(
        result["total_evaluations"] or 0
    )

    grounded_count = int(
        result["grounded_count"] or 0
    )

    ungrounded_count = (
        total_evaluations - grounded_count
    )

    grounded_rate = (
        grounded_count / total_evaluations
        if total_evaluations > 0
        else 0.0
    )

    return RagEvaluationSummaryResponse(
        total_evaluations=total_evaluations,
        grounded_count=grounded_count,
        ungrounded_count=ungrounded_count,
        grounded_rate=round(
            grounded_rate,
            4,
        ),
        average_retrieval_relevance=round(
            float(
                result[
                    "average_retrieval_relevance"
                ]
                or 0.0
            ),
            4,
        ),
        average_citation_coverage=round(
            float(
                result[
                    "average_citation_coverage"
                ]
                or 0.0
            ),
            4,
        ),
        average_groundedness_consistency=round(
            float(
                result[
                    "average_groundedness_consistency"
                ]
                or 0.0
            ),
            4,
        ),
        average_response_latency_ms=round(
            float(
                result[
                    "average_response_latency_ms"
                ]
                or 0.0
            ),
            3,
        ),
        average_retrieved_candidate_count=round(
            float(
                result[
                    "average_retrieved_candidate_count"
                ]
                or 0.0
            ),
            2,
        ),
        average_relevant_candidate_count=round(
            float(
                result[
                    "average_relevant_candidate_count"
                ]
                or 0.0
            ),
            2,
        ),
    )