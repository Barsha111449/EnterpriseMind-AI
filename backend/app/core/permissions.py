from collections.abc import Collection

from fastapi import HTTPException, status

from backend.app.schemas.authentication import CurrentUserResponse


ADMIN_ROLES = frozenset(
    {
        "admin",
    }
)

DOCUMENT_UPLOAD_ROLES = frozenset(
    {
        "admin",
        "manager",
    }
)

DOCUMENT_DELETE_ROLES = frozenset(
    {
        "admin",
    }
)

ANALYTICS_VIEW_ROLES = frozenset(
    {
        "admin",
        "manager",
        "reviewer",
    }
)

KNOWLEDGE_ACCESS_ROLES = frozenset(
    {
        "admin",
        "manager",
        "employee",
        "reviewer",
    }
)


def require_roles(
    current_user: CurrentUserResponse,
    allowed_roles: Collection[str],
    *,
    detail: str = "You do not have permission to perform this action.",
) -> None:
    """Reject users whose organization role is not permitted."""

    if current_user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )