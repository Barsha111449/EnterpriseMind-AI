import uuid
from typing import Any

from sqlalchemy.orm import Session

from backend.app.models.audit_log import AuditLog


def record_audit_event(
    database_session: Session,
    *,
    organization_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
    action: str,
    resource_type: str,
    resource_id: uuid.UUID | None = None,
    description: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    """Add an audit event to the current database transaction."""

    audit_log = AuditLog(
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        description=description,
        details=details or {},
    )

    database_session.add(audit_log)
    database_session.flush()

    return audit_log