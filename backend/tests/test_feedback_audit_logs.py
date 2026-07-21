import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.message import Message


TEST_PASSWORD = "FeedbackAudit!2026"


def register_and_login_admin(
    client: TestClient,
    *,
    organization_name: str,
    organization_slug: str,
    email: str,
) -> tuple[dict[str, str], dict]:
    """Register an organization and log in its administrator."""

    register_response = client.post(
        "/api/v1/register",
        json={
            "organization_name": organization_name,
            "organization_slug": organization_slug,
            "full_name": "Feedback Audit Administrator",
            "email": email,
            "password": TEST_PASSWORD,
        },
    )

    assert register_response.status_code == 201

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "organization_slug": organization_slug,
            "email": email,
            "password": TEST_PASSWORD,
        },
    )

    assert login_response.status_code == 200

    login_data = login_response.json()

    headers = {
        "Authorization": (
            f"Bearer {login_data['access_token']}"
        ),
    }

    return headers, login_data


def create_assistant_message(
    client: TestClient,
    database_session: Session,
    headers: dict[str, str],
    *,
    title: str = "Feedback Audit Conversation",
) -> Message:
    """Create a conversation and insert one assistant message."""

    conversation_response = client.post(
        "/api/v1/conversations",
        headers=headers,
        json={
            "title": title,
        },
    )

    assert conversation_response.status_code == 201

    conversation = conversation_response.json()

    message = Message(
        organization_id=uuid.UUID(
            conversation["organization_id"]
        ),
        conversation_id=uuid.UUID(
            conversation["id"]
        ),
        role="assistant",
        content="This is a test assistant answer.",
        grounded=True,
        citations=[],
    )

    database_session.add(message)
    database_session.commit()
    database_session.refresh(message)

    return message


def get_feedback_audit_logs(
    client: TestClient,
    headers: dict[str, str],
    *,
    action: str | None = None,
) -> dict:
    """Retrieve feedback audit logs for the current organization."""

    query = (
        "/api/v1/admin/audit-logs"
        "?resource_type=feedback"
    )

    if action is not None:
        query += f"&action={action}"

    response = client.get(
        query,
        headers=headers,
    )

    assert response.status_code == 200

    return response.json()


def test_creating_feedback_creates_audit_log(
    client: TestClient,
    database_session: Session,
) -> None:
    """Submitting feedback records feedback.created."""

    headers, login_data = register_and_login_admin(
        client,
        organization_name="Feedback Create Audit Company",
        organization_slug="feedback-create-audit-company",
        email="admin@feedback-create-audit.example",
    )

    message = create_assistant_message(
        client,
        database_session,
        headers,
    )

    create_response = client.post(
        f"/api/v1/messages/{message.id}/feedback",
        headers=headers,
        json={
            "rating": "helpful",
            "comment": "The answer was useful.",
        },
    )

    assert create_response.status_code == 200

    feedback = create_response.json()

    data = get_feedback_audit_logs(
        client,
        headers,
        action="feedback.created",
    )

    assert data["total"] == 1
    assert len(data["items"]) == 1

    audit_log = data["items"][0]

    assert audit_log["organization_id"] == (
        login_data["organization_id"]
    )

    assert audit_log["actor_user_id"] == (
        login_data["user_id"]
    )

    assert audit_log["action"] == "feedback.created"
    assert audit_log["resource_type"] == "feedback"
    assert audit_log["resource_id"] == feedback["id"]

    assert audit_log["details"]["message_id"] == str(
        message.id
    )

    assert audit_log["details"]["rating"] == "helpful"

    assert (
        audit_log["details"]["comment"]
        == "The answer was useful."
    )


def test_updating_feedback_creates_audit_log(
    client: TestClient,
    database_session: Session,
) -> None:
    """Changing existing feedback records feedback.updated."""

    headers, _ = register_and_login_admin(
        client,
        organization_name="Feedback Update Audit Company",
        organization_slug="feedback-update-audit-company",
        email="admin@feedback-update-audit.example",
    )

    message = create_assistant_message(
        client,
        database_session,
        headers,
    )

    first_response = client.post(
        f"/api/v1/messages/{message.id}/feedback",
        headers=headers,
        json={
            "rating": "helpful",
            "comment": "Initially useful.",
        },
    )

    assert first_response.status_code == 200

    feedback_id = first_response.json()["id"]

    update_response = client.post(
        f"/api/v1/messages/{message.id}/feedback",
        headers=headers,
        json={
            "rating": "unhelpful",
            "comment": "The answer needs stronger evidence.",
        },
    )

    assert update_response.status_code == 200
    assert update_response.json()["id"] == feedback_id

    data = get_feedback_audit_logs(
        client,
        headers,
        action="feedback.updated",
    )

    assert data["total"] == 1

    audit_log = data["items"][0]

    assert audit_log["resource_id"] == feedback_id

    assert (
        audit_log["details"]["previous_rating"]
        == "helpful"
    )

    assert (
        audit_log["details"]["new_rating"]
        == "unhelpful"
    )

    assert (
        audit_log["details"]["previous_comment"]
        == "Initially useful."
    )

    assert (
        audit_log["details"]["new_comment"]
        == "The answer needs stronger evidence."
    )


def test_deleting_feedback_creates_audit_log(
    client: TestClient,
    database_session: Session,
) -> None:
    """Deleting feedback records feedback.deleted."""

    headers, _ = register_and_login_admin(
        client,
        organization_name="Feedback Delete Audit Company",
        organization_slug="feedback-delete-audit-company",
        email="admin@feedback-delete-audit.example",
    )

    message = create_assistant_message(
        client,
        database_session,
        headers,
    )

    create_response = client.post(
        f"/api/v1/messages/{message.id}/feedback",
        headers=headers,
        json={
            "rating": "helpful",
            "comment": "Temporary feedback.",
        },
    )

    assert create_response.status_code == 200

    feedback_id = create_response.json()["id"]

    delete_response = client.delete(
        f"/api/v1/messages/{message.id}/feedback",
        headers=headers,
    )

    assert delete_response.status_code == 204

    data = get_feedback_audit_logs(
        client,
        headers,
        action="feedback.deleted",
    )

    assert data["total"] == 1

    audit_log = data["items"][0]

    assert audit_log["action"] == "feedback.deleted"
    assert audit_log["resource_id"] == feedback_id

    assert audit_log["details"]["message_id"] == str(
        message.id
    )

    assert (
        audit_log["details"]["deleted_rating"]
        == "helpful"
    )

    assert (
        audit_log["details"]["deleted_comment"]
        == "Temporary feedback."
    )


def test_unchanged_feedback_does_not_create_update_log(
    client: TestClient,
    database_session: Session,
) -> None:
    """Submitting identical feedback does not create duplicate logs."""

    headers, _ = register_and_login_admin(
        client,
        organization_name="Feedback No Change Company",
        organization_slug="feedback-no-change-company",
        email="admin@feedback-no-change.example",
    )

    message = create_assistant_message(
        client,
        database_session,
        headers,
    )

    request_body = {
        "rating": "helpful",
        "comment": "The answer was clear.",
    }

    first_response = client.post(
        f"/api/v1/messages/{message.id}/feedback",
        headers=headers,
        json=request_body,
    )

    assert first_response.status_code == 200

    second_response = client.post(
        f"/api/v1/messages/{message.id}/feedback",
        headers=headers,
        json=request_body,
    )

    assert second_response.status_code == 200

    data = get_feedback_audit_logs(
        client,
        headers,
    )

    assert data["total"] == 1
    assert len(data["items"]) == 1

    assert (
        data["items"][0]["action"]
        == "feedback.created"
    )


def test_feedback_audit_logs_are_organization_isolated(
    client: TestClient,
    database_session: Session,
) -> None:
    """Another organization cannot see feedback audit records."""

    first_headers, _ = register_and_login_admin(
        client,
        organization_name="First Feedback Audit Company",
        organization_slug="first-feedback-audit-company",
        email="admin@first-feedback-audit.example",
    )

    message = create_assistant_message(
        client,
        database_session,
        first_headers,
    )

    create_response = client.post(
        f"/api/v1/messages/{message.id}/feedback",
        headers=first_headers,
        json={
            "rating": "helpful",
            "comment": "Private organization feedback.",
        },
    )

    assert create_response.status_code == 200

    second_headers, _ = register_and_login_admin(
        client,
        organization_name="Second Feedback Audit Company",
        organization_slug="second-feedback-audit-company",
        email="admin@second-feedback-audit.example",
    )

    data = get_feedback_audit_logs(
        client,
        second_headers,
    )

    assert data["total"] == 0
    assert data["items"] == []