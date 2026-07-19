import uuid
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_current_user
from backend.app.core.security import hash_password
from backend.app.database.session import get_db
from backend.app.models import (
    OrganizationMembership,
    User,
)
from backend.app.schemas.authentication import CurrentUserResponse
from backend.app.schemas.employees import (
    EmployeeCreateRequest,
    EmployeeResponse,
    EmployeeRoleUpdateRequest,
    EmployeeStatusUpdateRequest,
)


router = APIRouter(
    prefix="/api/v1/admin/employees",
    tags=["employee management"],
)


def require_admin(
    current_user: CurrentUserResponse,
) -> None:
    """Allow only organization administrators."""

    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required.",
        )


def build_employee_response(
    user: User,
    membership: OrganizationMembership,
) -> EmployeeResponse:
    """Convert database records into an API response."""

    return EmployeeResponse(
        user_id=user.id,
        membership_id=membership.id,
        organization_id=membership.organization_id,
        email=user.email,
        full_name=user.full_name,
        role=membership.role,
        is_active=user.is_active,
        user_created_at=user.created_at,
        joined_at=membership.created_at,
    )


def get_organization_employee(
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
    database_session: Session,
) -> tuple[User, OrganizationMembership]:
    """Find an employee belonging to the current organization."""

    statement = (
        select(
            User,
            OrganizationMembership,
        )
        .join(
            OrganizationMembership,
            OrganizationMembership.user_id == User.id,
        )
        .where(
            User.id == user_id,
            OrganizationMembership.organization_id
            == organization_id,
        )
    )

    record = database_session.execute(
        statement
    ).one_or_none()

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found.",
        )

    user, membership = record

    return user, membership


@router.get(
    "",
    response_model=list[EmployeeResponse],
)
def list_employees(
    current_user: Annotated[
        CurrentUserResponse,
        Depends(get_current_user),
    ],
    database_session: Annotated[
        Session,
        Depends(get_db),
    ],
) -> list[EmployeeResponse]:
    """List employees belonging to the current organization."""

    require_admin(current_user)

    statement = (
        select(
            User,
            OrganizationMembership,
        )
        .join(
            OrganizationMembership,
            OrganizationMembership.user_id == User.id,
        )
        .where(
            OrganizationMembership.organization_id
            == current_user.organization_id
        )
        .order_by(
            User.full_name,
            User.email,
        )
    )

    records = database_session.execute(
        statement
    ).all()

    return [
        build_employee_response(user, membership)
        for user, membership in records
    ]


@router.post(
    "",
    response_model=EmployeeResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_employee(
    request: EmployeeCreateRequest,
    current_user: Annotated[
        CurrentUserResponse,
        Depends(get_current_user),
    ],
    database_session: Annotated[
        Session,
        Depends(get_db),
    ],
) -> EmployeeResponse:
    """Create an employee in the administrator's organization."""

    require_admin(current_user)

    normalized_email = str(request.email).lower()
    full_name = request.full_name.strip()

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
        user = User(
            email=normalized_email,
            password_hash=hash_password(request.password),
            full_name=full_name,
        )

        database_session.add(user)
        database_session.flush()

        membership = OrganizationMembership(
            user_id=user.id,
            organization_id=current_user.organization_id,
            role=request.role,
        )

        database_session.add(membership)
        database_session.commit()

        database_session.refresh(user)
        database_session.refresh(membership)

        return build_employee_response(
            user,
            membership,
        )

    except IntegrityError as exc:
        database_session.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The employee account already exists.",
        ) from exc

    except SQLAlchemyError as exc:
        database_session.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The employee account could not be created.",
        ) from exc


@router.patch(
    "/{user_id}/role",
    response_model=EmployeeResponse,
)
def update_employee_role(
    user_id: uuid.UUID,
    request: EmployeeRoleUpdateRequest,
    current_user: Annotated[
        CurrentUserResponse,
        Depends(get_current_user),
    ],
    database_session: Annotated[
        Session,
        Depends(get_db),
    ],
) -> EmployeeResponse:
    """Change an employee's organization role."""

    require_admin(current_user)

    user, membership = get_organization_employee(
        user_id=user_id,
        organization_id=current_user.organization_id,
        database_session=database_session,
    )

    if (
        user.id == current_user.user_id
        and request.role != "admin"
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot remove your own administrator role.",
        )

    membership.role = request.role

    database_session.commit()
    database_session.refresh(membership)

    return build_employee_response(
        user,
        membership,
    )


@router.patch(
    "/{user_id}/status",
    response_model=EmployeeResponse,
)
def update_employee_status(
    user_id: uuid.UUID,
    request: EmployeeStatusUpdateRequest,
    current_user: Annotated[
        CurrentUserResponse,
        Depends(get_current_user),
    ],
    database_session: Annotated[
        Session,
        Depends(get_db),
    ],
) -> EmployeeResponse:
    """Activate or deactivate an employee account."""

    require_admin(current_user)

    user, membership = get_organization_employee(
        user_id=user_id,
        organization_id=current_user.organization_id,
        database_session=database_session,
    )

    if (
        user.id == current_user.user_id
        and not request.is_active
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account.",
        )

    user.is_active = request.is_active

    database_session.commit()
    database_session.refresh(user)

    return build_employee_response(
        user,
        membership,
    )