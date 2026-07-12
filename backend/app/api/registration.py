from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.core.security import hash_password
from backend.app.database.session import get_db
from backend.app.models import (
    Organization,
    OrganizationMembership,
    User,
)
from backend.app.schemas.registration import (
    RegistrationRequest,
    RegistrationResponse,
)


router = APIRouter(
    prefix="/api/v1",
    tags=["registration"],
)


@router.post(
    "/register",
    response_model=RegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_organization(
    payload: RegistrationRequest,
    database_session: Annotated[Session, Depends(get_db)],
) -> RegistrationResponse:
    normalized_email = str(payload.email).lower()
    normalized_slug = payload.organization_slug.lower()

    existing_organization = database_session.scalar(
        select(Organization.id).where(
            Organization.slug == normalized_slug
        )
    )

    if existing_organization is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An organisation with this slug already exists.",
        )

    existing_user = database_session.scalar(
        select(User.id).where(
            User.email == normalized_email
        )
    )

    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )

    try:
        organization = Organization(
            name=payload.organization_name.strip(),
            slug=normalized_slug,
        )

        user = User(
            email=normalized_email,
            password_hash=hash_password(payload.password),
            full_name=payload.full_name.strip(),
        )

        database_session.add_all([organization, user])
        database_session.flush()

        membership = OrganizationMembership(
            user_id=user.id,
            organization_id=organization.id,
            role="admin",
        )

        database_session.add(membership)
        database_session.commit()

        return RegistrationResponse(
            organization_id=organization.id,
            user_id=user.id,
            membership_id=membership.id,
            role=membership.role,
            message="Organisation and administrator created successfully.",
        )

    except IntegrityError as exc:
        database_session.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The organisation or user already exists.",
        ) from exc

    except SQLAlchemyError as exc:
        database_session.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration could not be completed.",
        ) from exc