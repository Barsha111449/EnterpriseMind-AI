import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AuditLogResponse(BaseModel):
    """One organization audit-log record."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    actor_user_id: uuid.UUID | None

    action: str
    resource_type: str
    resource_id: uuid.UUID | None

    description: str | None
    details: dict[str, Any]

    created_at: datetime


class AuditLogListResponse(BaseModel):
    """Paginated collection of audit-log records."""

    items: list[AuditLogResponse]

    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)