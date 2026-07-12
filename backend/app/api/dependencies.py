import uuid
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.security import decode_access_token
from backend.app.database.session import get_db
from backend.app.models import (
    Organization,
    OrganizationMembership,
    User,
)
from backend.app.schemas.authentication import CurrentUserResponse


bearer_scheme = HTTPBearer(auto_error=False)


def unauthorized_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired access token.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    database_session: Annotated[Session, Depends(get_db)],
) -> CurrentUserResponse:
    """Validate the token and load the current user and organisation."""

    if credentials is None:
        raise unauthorized_exception()

    if credentials.scheme.lower() != "bearer":
        raise unauthorized_exception()

    try:
        token_payload = decode_access_token(credentials.credentials)

        user_id = uuid.UUID(str(token_payload["sub"]))
        organization_id = uuid.UUID(
            str(token_payload["organization_id"])
        )

    except (
        jwt.InvalidTokenError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        raise unauthorized_exception() from exc

    statement = (
        select(
            User,
            Organization,
            OrganizationMembership,
        )
        .join(
            OrganizationMembership,
            OrganizationMembership.user_id == User.id,
        )
        .join(
            Organization,
            Organization.id
            == OrganizationMembership.organization_id,
        )
        .where(
            User.id == user_id,
            Organization.id == organization_id,
        )
    )

    record = database_session.execute(statement).one_or_none()

    if record is None:
        raise unauthorized_exception()

    user, organization, membership = record

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive.",
        )

    return CurrentUserResponse(
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        organization_id=organization.id,
        organization_name=organization.name,
        organization_slug=organization.slug,
        role=membership.role,
    )