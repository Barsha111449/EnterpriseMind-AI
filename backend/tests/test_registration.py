from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.security import verify_password
from backend.app.models import (
    Organization,
    OrganizationMembership,
    User,
)


def test_register_organization_and_administrator(
    client: TestClient,
    database_session: Session,
) -> None:
    payload = {
        "organization_name": "BrightPath Services",
        "organization_slug": "brightpath-services",
        "full_name": "BrightPath Administrator",
        "email": "admin@brightpath.example",
        "password": "BrightPath!2026",
    }

    response = client.post(
        "/api/v1/register",
        json=payload,
    )

    assert response.status_code == 201

    response_data = response.json()

    assert response_data["role"] == "admin"
    assert (
        response_data["message"]
        == "Organisation and administrator created successfully."
    )

    organization = database_session.scalar(
        select(Organization).where(
            Organization.slug == "brightpath-services"
        )
    )

    user = database_session.scalar(
        select(User).where(
            User.email == "admin@brightpath.example"
        )
    )

    assert organization is not None
    assert user is not None

    # Confirm that the plain password was not stored.
    assert user.password_hash != "BrightPath!2026"

    # Confirm that the stored hash matches the password.
    assert verify_password(
        "BrightPath!2026",
        user.password_hash,
    )

    membership = database_session.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.organization_id == organization.id,
        )
    )

    assert membership is not None
    assert membership.role == "admin"

    duplicate_response = client.post(
        "/api/v1/register",
        json=payload,
    )

    assert duplicate_response.status_code == 409
    assert duplicate_response.json() == {
        "detail": "An organisation with this slug already exists."
    }


def test_registration_rejects_invalid_data(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/register",
        json={
            "organization_name": "A",
            "organization_slug": "Invalid Slug",
            "full_name": "B",
            "email": "not-an-email",
            "password": "short",
        },
    )

    assert response.status_code == 422