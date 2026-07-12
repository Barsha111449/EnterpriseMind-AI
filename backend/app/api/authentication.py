from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.security import (
    create_access_token,
    verify_password,
)
from backend.app.database.session import get_db
from backend.app.models import (
    Organization,
    OrganizationMembership,
    User,
)
from backend.app.schemas.authentication import (
    LoginRequest,
    LoginResponse,
)


router = APIRouter(
    prefix="/api/v1/auth",
    tags=["authentication"],
)


@router.post(
    "/login",
    response_model=LoginResponse,
)
def login(
    payload: LoginRequest,
    database_session: Annotated[Session, Depends(get_db)],
) -> LoginResponse:
    normalized_email = str(payload.email).lower()
    normalized_slug = payload.organization_slug.lower()

    user = database_session.scalar(
        select(User).where(User.email == normalized_email)
    )

    organization = database_session.scalar(
        select(Organization).where(
            Organization.slug == normalized_slug
        )
    )

    if user is None or organization is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid login credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(
        payload.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid login credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive.",
        )

    membership = database_session.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.organization_id
            == organization.id,
        )
    )

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid login credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        user_id=str(user.id),
        organization_id=str(organization.id),
        role=membership.role,
    )

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
        user_id=user.id,
        organization_id=organization.id,
        role=membership.role,
    )