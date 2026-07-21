import uuid
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Query,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_current_user
from backend.app.core.permissions import (
    ADMIN_ROLES,
    require_roles,
)
from backend.app.database.session import get_db
from backend.app.models.audit_log import AuditLog
from backend.app.schemas.audit_log import (
    AuditLogListResponse,
    AuditLogResponse,
)
from backend.app.schemas.authentication import (
    CurrentUserResponse,
)


router = APIRouter(
    prefix="/api/v1/admin/audit-logs",
    tags=["audit logs"],
)


@router.get(
    "",
    response_model=AuditLogListResponse,
)
def list_audit_logs(
    current_user: Annotated[
        CurrentUserResponse,
        Depends(get_current_user),
    ],
    database_session: Annotated[
        Session,
        Depends(get_db),
    ],
    action: Annotated[
        str | None,
        Query(
            min_length=1,
            max_length=100,
        ),
    ] = None,
    resource_type: Annotated[
        str | None,
        Query(
            min_length=1,
            max_length=50,
        ),
    ] = None,
    actor_user_id: Annotated[
        uuid.UUID | None,
        Query(),
    ] = None,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=100,
        ),
    ] = 50,
    offset: Annotated[
        int,
        Query(ge=0),
    ] = 0,
) -> AuditLogListResponse:
    """List audit records belonging to the current organization."""

    require_roles(
        current_user,
        ADMIN_ROLES,
        detail="Administrator access required.",
    )

    filters = [
        AuditLog.organization_id
        == current_user.organization_id
    ]

    if action is not None:
        filters.append(
            AuditLog.action == action
        )

    if resource_type is not None:
        filters.append(
            AuditLog.resource_type == resource_type
        )

    if actor_user_id is not None:
        filters.append(
            AuditLog.actor_user_id == actor_user_id
        )

    total = int(
        database_session.scalar(
            select(
                func.count(AuditLog.id)
            ).where(*filters)
        )
        or 0
    )

    statement = (
        select(AuditLog)
        .where(*filters)
        .order_by(
            AuditLog.created_at.desc(),
            AuditLog.id.desc(),
        )
        .offset(offset)
        .limit(limit)
    )

    audit_logs = database_session.scalars(
        statement
    ).all()

    return AuditLogListResponse(
        items=[
            AuditLogResponse.model_validate(audit_log)
            for audit_log in audit_logs
        ],
        total=total,
        limit=limit,
        offset=offset,
    )