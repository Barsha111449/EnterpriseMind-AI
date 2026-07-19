import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.message import Message
from backend.app.models.message_feedback import MessageFeedback


def register_admin(
    client: TestClient,
    *,
    organization_name: str,
    organization_slug: str,
    email: str,
) -> tuple[dict[str, str], uuid.UUID, uuid.UUID]:
    """Register and log in an organization administrator."""

    password = "AnalyticsTest!2026"

    register_response = client.post(
        "/api/v1/register",
        json={
            "organization_name": organization_name,
            "organization_slug": organization_slug,
            "full_name": "Analytics Administrator",
            "email": email,
            "password": password,
        },
    )

    assert register_response.status_code == 201

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "organization_slug": organization_slug,
            "email": email,
            "password": password,
        },
    )

    assert login_response.status_code == 200

    login_data = login_response.json()

    headers = {
        "Authorization": (
            f"Bearer {login_data['access_token']}"
        ),
    }

    return (
        headers,
        uuid.UUID(login_data["organization_id"]),
        uuid.UUID(login_data["user_id"]),
    )


def test_analytics_requires_authentication(
    client: TestClient,
) -> None:
    """The analytics endpoint requires authentication."""

    response = client.get(
        "/api/v1/admin/analytics/feedback"
    )

    assert response.status_code == 401


def test_empty_analytics_returns_zero_values(
    client: TestClient,
) -> None:
    """A new organization receives zero statistics."""

    headers, organization_id, _ = register_admin(
        client,
        organization_name="Empty Analytics Company",
        organization_slug="empty-analytics-company",
        email="admin@empty-analytics.example",
    )

    response = client.get(
        "/api/v1/admin/analytics/feedback",
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["organization_id"] == str(organization_id)
    assert data["total_assistant_messages"] == 0
    assert data["grounded_answers"] == 0
    assert data["ungrounded_answers"] == 0
    assert data["total_feedback"] == 0
    assert data["helpful_feedback"] == 0
    assert data["unhelpful_feedback"] == 0
    assert data["rated_messages"] == 0
    assert data["helpful_percentage"] == 0.0
    assert data["feedback_coverage_percentage"] == 0.0


def test_admin_receives_organization_feedback_analytics(
    client: TestClient,
    database_session: Session,
) -> None:
    """Analytics count only the current organization's records."""

    headers, organization_id, user_id = register_admin(
        client,
        organization_name="Analytics Test Company",
        organization_slug="analytics-test-company",
        email="admin@analytics-test.example",
    )

    conversation_response = client.post(
        "/api/v1/conversations",
        headers=headers,
        json={
            "title": "Analytics Conversation",
        },
    )

    assert conversation_response.status_code == 201

    conversation_id = uuid.UUID(
        conversation_response.json()["id"]
    )

    grounded_message = Message(
        organization_id=organization_id,
        conversation_id=conversation_id,
        role="assistant",
        content="Grounded test answer.",
        grounded=True,
        citations=[],
    )

    ungrounded_message = Message(
        organization_id=organization_id,
        conversation_id=conversation_id,
        role="assistant",
        content="Ungrounded test answer.",
        grounded=False,
        citations=[],
    )

    database_session.add_all(
        [
            grounded_message,
            ungrounded_message,
        ]
    )
    database_session.commit()
    database_session.refresh(grounded_message)
    database_session.refresh(ungrounded_message)

    database_session.add_all(
        [
            MessageFeedback(
                organization_id=organization_id,
                user_id=user_id,
                message_id=grounded_message.id,
                rating="helpful",
                comment="Good answer.",
            ),
            MessageFeedback(
                organization_id=organization_id,
                user_id=user_id,
                message_id=ungrounded_message.id,
                rating="unhelpful",
                comment="Needs better evidence.",
            ),
        ]
    )

    database_session.commit()

    response = client.get(
        "/api/v1/admin/analytics/feedback",
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total_assistant_messages"] == 2
    assert data["grounded_answers"] == 1
    assert data["ungrounded_answers"] == 1
    assert data["total_feedback"] == 2
    assert data["helpful_feedback"] == 1
    assert data["unhelpful_feedback"] == 1
    assert data["rated_messages"] == 2
    assert data["helpful_percentage"] == 50.0
    assert data["feedback_coverage_percentage"] == 100.0