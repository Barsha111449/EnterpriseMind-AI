import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.message import Message
from backend.app.models.message_feedback import MessageFeedback


def register_and_login(
    client: TestClient,
    *,
    organization_name: str,
    organization_slug: str,
    full_name: str,
    email: str,
    password: str,
) -> dict[str, str]:
    """Register a test account and return its authorization header."""

    register_response = client.post(
        "/api/v1/register",
        json={
            "organization_name": organization_name,
            "organization_slug": organization_slug,
            "full_name": full_name,
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

    access_token = login_response.json()["access_token"]

    return {
        "Authorization": f"Bearer {access_token}",
    }


def create_assistant_message(
    client: TestClient,
    database_session: Session,
    headers: dict[str, str],
    *,
    role: str = "assistant",
) -> Message:
    """Create a conversation and add one message to it."""

    conversation_response = client.post(
        "/api/v1/conversations",
        headers=headers,
        json={
            "title": "Feedback Test Conversation",
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
        role=role,
        content="This is a test AI answer.",
        grounded=True if role == "assistant" else None,
        citations=[],
    )

    database_session.add(message)
    database_session.commit()
    database_session.refresh(message)

    return message


def test_feedback_requires_authentication(
    client: TestClient,
) -> None:
    """A user must log in before submitting feedback."""

    response = client.post(
        f"/api/v1/messages/{uuid.uuid4()}/feedback",
        json={
            "rating": "helpful",
            "comment": "Good answer.",
        },
    )

    assert response.status_code == 401


def test_user_can_create_and_read_feedback(
    client: TestClient,
    database_session: Session,
) -> None:
    """A user can submit and retrieve feedback."""

    headers = register_and_login(
        client,
        organization_name="Feedback Test Company",
        organization_slug="feedback-test-company",
        full_name="Feedback Administrator",
        email="admin@feedback-test.example",
        password="FeedbackTest!2026",
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
            "comment": "The answer was clear.",
        },
    )

    assert create_response.status_code == 200

    feedback = create_response.json()

    assert feedback["message_id"] == str(message.id)
    assert feedback["rating"] == "helpful"
    assert feedback["comment"] == "The answer was clear."

    get_response = client.get(
        f"/api/v1/messages/{message.id}/feedback",
        headers=headers,
    )

    assert get_response.status_code == 200
    assert get_response.json()["id"] == feedback["id"]


def test_feedback_rejects_user_message(
    client: TestClient,
    database_session: Session,
) -> None:
    """Feedback can only be submitted for assistant messages."""

    headers = register_and_login(
        client,
        organization_name="User Message Company",
        organization_slug="user-message-company",
        full_name="User Message Administrator",
        email="admin@user-message.example",
        password="UserMessage!2026",
    )

    message = create_assistant_message(
        client,
        database_session,
        headers,
        role="user",
    )

    response = client.post(
        f"/api/v1/messages/{message.id}/feedback",
        headers=headers,
        json={
            "rating": "helpful",
        },
    )

    assert response.status_code == 400

    assert response.json() == {
        "detail": (
            "Feedback can only be submitted "
            "for assistant messages."
        )
    }


def test_user_cannot_rate_another_users_message(
    client: TestClient,
    database_session: Session,
) -> None:
    """A user cannot access another user's message."""

    first_headers = register_and_login(
        client,
        organization_name="First Feedback Company",
        organization_slug="first-feedback-company",
        full_name="First Administrator",
        email="admin@first-feedback.example",
        password="FirstFeedback!2026",
    )

    message = create_assistant_message(
        client,
        database_session,
        first_headers,
    )

    second_headers = register_and_login(
        client,
        organization_name="Second Feedback Company",
        organization_slug="second-feedback-company",
        full_name="Second Administrator",
        email="admin@second-feedback.example",
        password="SecondFeedback!2026",
    )

    response = client.post(
        f"/api/v1/messages/{message.id}/feedback",
        headers=second_headers,
        json={
            "rating": "unhelpful",
        },
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Message not found.",
    }


def test_submitting_feedback_again_updates_it(
    client: TestClient,
    database_session: Session,
) -> None:
    """Posting feedback again updates the existing record."""

    headers = register_and_login(
        client,
        organization_name="Update Feedback Company",
        organization_slug="update-feedback-company",
        full_name="Update Administrator",
        email="admin@update-feedback.example",
        password="UpdateFeedback!2026",
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
            "comment": "Initially helpful.",
        },
    )

    assert first_response.status_code == 200

    feedback_id = first_response.json()["id"]

    second_response = client.post(
        f"/api/v1/messages/{message.id}/feedback",
        headers=headers,
        json={
            "rating": "unhelpful",
            "comment": "The answer needs better evidence.",
        },
    )

    assert second_response.status_code == 200

    updated_feedback = second_response.json()

    assert updated_feedback["id"] == feedback_id
    assert updated_feedback["rating"] == "unhelpful"
    assert (
        updated_feedback["comment"]
        == "The answer needs better evidence."
    )

    database_session.expire_all()

    stored_feedback = database_session.scalars(
        select(MessageFeedback).where(
            MessageFeedback.message_id == message.id
        )
    ).all()

    assert len(stored_feedback) == 1


def test_user_can_delete_feedback(
    client: TestClient,
    database_session: Session,
) -> None:
    """A user can remove their feedback."""

    headers = register_and_login(
        client,
        organization_name="Delete Feedback Company",
        organization_slug="delete-feedback-company",
        full_name="Delete Administrator",
        email="admin@delete-feedback.example",
        password="DeleteFeedback!2026",
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
        },
    )

    assert create_response.status_code == 200

    delete_response = client.delete(
        f"/api/v1/messages/{message.id}/feedback",
        headers=headers,
    )

    assert delete_response.status_code == 204

    get_response = client.get(
        f"/api/v1/messages/{message.id}/feedback",
        headers=headers,
    )

    assert get_response.status_code == 404
    assert get_response.json() == {
        "detail": "Feedback not found.",
    }

    database_session.expire_all()

    stored_feedback = database_session.scalar(
        select(MessageFeedback).where(
            MessageFeedback.message_id == message.id
        )
    )

    assert stored_feedback is None