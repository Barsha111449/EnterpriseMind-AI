import jwt
from fastapi.testclient import TestClient

from backend.app.core.config import settings


def create_test_account(client: TestClient) -> None:
    response = client.post(
        "/api/v1/register",
        json={
            "organization_name": "Login Test Company",
            "organization_slug": "login-test-company",
            "full_name": "Login Test Administrator",
            "email": "admin@login-test.example",
            "password": "LoginTest!2026",
        },
    )

    assert response.status_code == 201


def test_login_returns_valid_access_token(
    client: TestClient,
) -> None:
    create_test_account(client)

    response = client.post(
        "/api/v1/auth/login",
        json={
            "organization_slug": "login-test-company",
            "email": "admin@login-test.example",
            "password": "LoginTest!2026",
        },
    )

    assert response.status_code == 200

    response_data = response.json()

    assert response_data["token_type"] == "bearer"
    assert response_data["expires_in"] == 1800
    assert response_data["role"] == "admin"
    assert response_data["access_token"]

    token_payload = jwt.decode(
        response_data["access_token"],
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )

    assert token_payload["sub"] == response_data["user_id"]
    assert (
        token_payload["organization_id"]
        == response_data["organization_id"]
    )
    assert token_payload["role"] == "admin"
    assert "iat" in token_payload
    assert "exp" in token_payload


def test_login_rejects_incorrect_password(
    client: TestClient,
) -> None:
    create_test_account(client)

    response = client.post(
        "/api/v1/auth/login",
        json={
            "organization_slug": "login-test-company",
            "email": "admin@login-test.example",
            "password": "WrongPassword2026",
        },
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Invalid login credentials."
    }