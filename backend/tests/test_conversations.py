import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.message import Message


def register_and_login(
    client: TestClient,
    *,
    organization_name: str,
    organization_slug: str,
    full_name: str,
    email: str,
    password: str,
) -> dict[str, str]:
    """Register an account and return its authorization header."""

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


def test_conversation_endpoint_requires_authentication(
    client: TestClient,
) -> None:
    """Unauthenticated users cannot list conversations."""

    response = client.get("/api/v1/conversations")

    assert response.status_code == 401


def test_user_can_create_list_and_open_conversation(
    client: TestClient,
) -> None:
    """An authenticated user can manage their conversation."""

    headers = register_and_login(
        client,
        organization_name="Conversation Test Company",
        organization_slug="conversation-test-company",
        full_name="Conversation Test Administrator",
        email="admin@conversation-test.example",
        password="ConversationTest!2026",
    )

    create_response = client.post(
        "/api/v1/conversations",
        headers=headers,
        json={
            "title": "EnterpriseMind Questions",
        },
    )

    assert create_response.status_code == 201

    conversation = create_response.json()

    assert conversation["title"] == "EnterpriseMind Questions"
    assert conversation["id"]
    assert conversation["organization_id"]
    assert conversation["user_id"]
    assert conversation["created_at"]
    assert conversation["updated_at"]

    conversation_id = conversation["id"]

    list_response = client.get(
        "/api/v1/conversations",
        headers=headers,
    )

    assert list_response.status_code == 200

    conversations = list_response.json()

    assert len(conversations) == 1
    assert conversations[0]["id"] == conversation_id
    assert conversations[0]["title"] == "EnterpriseMind Questions"

    detail_response = client.get(
        f"/api/v1/conversations/{conversation_id}",
        headers=headers,
    )

    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == conversation_id

    messages_response = client.get(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=headers,
    )

    assert messages_response.status_code == 200
    assert messages_response.json() == []


def test_user_cannot_access_another_users_conversation(
    client: TestClient,
) -> None:
    """A user cannot access a conversation owned by another user."""

    first_user_headers = register_and_login(
        client,
        organization_name="First Secure Company",
        organization_slug="first-secure-company",
        full_name="First Administrator",
        email="admin@first-secure.example",
        password="FirstSecure!2026",
    )

    create_response = client.post(
        "/api/v1/conversations",
        headers=first_user_headers,
        json={
            "title": "Private Conversation",
        },
    )

    assert create_response.status_code == 201

    conversation_id = create_response.json()["id"]

    second_user_headers = register_and_login(
        client,
        organization_name="Second Secure Company",
        organization_slug="second-secure-company",
        full_name="Second Administrator",
        email="admin@second-secure.example",
        password="SecondSecure!2026",
    )

    detail_response = client.get(
        f"/api/v1/conversations/{conversation_id}",
        headers=second_user_headers,
    )

    assert detail_response.status_code == 404
    assert detail_response.json() == {
        "detail": "Conversation not found.",
    }

    messages_response = client.get(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=second_user_headers,
    )

    assert messages_response.status_code == 404
    assert messages_response.json() == {
        "detail": "Conversation not found.",
    }


def test_user_can_read_messages_in_owned_conversation(
    client: TestClient,
    database_session: Session,
) -> None:
    """Stored messages are returned for the correct conversation."""

    headers = register_and_login(
        client,
        organization_name="Message Test Company",
        organization_slug="message-test-company",
        full_name="Message Test Administrator",
        email="admin@message-test.example",
        password="MessageTest!2026",
    )

    create_response = client.post(
        "/api/v1/conversations",
        headers=headers,
        json={
            "title": "Message History",
        },
    )

    assert create_response.status_code == 201

    conversation = create_response.json()

    conversation_id = uuid.UUID(conversation["id"])
    organization_id = uuid.UUID(
        conversation["organization_id"]
    )

    message = Message(
        organization_id=organization_id,
        conversation_id=conversation_id,
        role="user",
        content="What is EnterpriseMind AI?",
        grounded=None,
        citations=[],
    )

    database_session.add(message)
    database_session.commit()

    response = client.get(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=headers,
    )

    assert response.status_code == 200

    messages = response.json()

    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    assert (
        messages[0]["content"]
        == "What is EnterpriseMind AI?"
    )
    assert messages[0]["grounded"] is None
    assert messages[0]["citations"] == []


def test_deleting_conversation_deletes_its_messages(
    client: TestClient,
    database_session: Session,
) -> None:
    """Deleting a conversation also deletes its messages."""

    headers = register_and_login(
        client,
        organization_name="Deletion Test Company",
        organization_slug="deletion-test-company",
        full_name="Deletion Test Administrator",
        email="admin@deletion-test.example",
        password="DeletionTest!2026",
    )

    create_response = client.post(
        "/api/v1/conversations",
        headers=headers,
        json={
            "title": "Conversation To Delete",
        },
    )

    assert create_response.status_code == 201

    conversation = create_response.json()

    conversation_id = uuid.UUID(conversation["id"])
    organization_id = uuid.UUID(
        conversation["organization_id"]
    )

    message = Message(
        organization_id=organization_id,
        conversation_id=conversation_id,
        role="assistant",
        content="This message should be deleted.",
        grounded=False,
        citations=[],
    )

    database_session.add(message)
    database_session.commit()

    delete_response = client.delete(
        f"/api/v1/conversations/{conversation_id}",
        headers=headers,
    )

    assert delete_response.status_code == 204

    detail_response = client.get(
        f"/api/v1/conversations/{conversation_id}",
        headers=headers,
    )

    assert detail_response.status_code == 404

    database_session.expire_all()

    stored_message = database_session.scalar(
        select(Message).where(
            Message.conversation_id == conversation_id
        )
    )

    assert stored_message is None