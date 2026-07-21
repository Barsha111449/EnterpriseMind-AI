from fastapi.testclient import TestClient


TEST_PASSWORD = "ConversationAudit!2026"


def register_and_login_admin(
    client: TestClient,
    *,
    organization_name: str,
    organization_slug: str,
    email: str,
) -> tuple[dict[str, str], dict]:
    """Register an organization and return administrator login details."""

    register_response = client.post(
        "/api/v1/register",
        json={
            "organization_name": organization_name,
            "organization_slug": organization_slug,
            "full_name": "Conversation Audit Administrator",
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


def create_conversation(
    client: TestClient,
    headers: dict[str, str],
    *,
    title: str,
) -> dict:
    """Create a conversation and return its response."""

    response = client.post(
        "/api/v1/conversations",
        headers=headers,
        json={
            "title": title,
        },
    )

    assert response.status_code == 201

    return response.json()


def test_creating_conversation_creates_audit_log(
    client: TestClient,
) -> None:
    """Creating a conversation records conversation.created."""

    headers, login_data = register_and_login_admin(
        client,
        organization_name="Conversation Create Company",
        organization_slug="conversation-create-company",
        email="admin@conversation-create.example",
    )

    conversation = create_conversation(
        client,
        headers,
        title="Employee Leave Questions",
    )

    response = client.get(
        (
            "/api/v1/admin/audit-logs"
            "?action=conversation.created"
            "&resource_type=conversation"
        ),
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 1
    assert len(data["items"]) == 1

    audit_log = data["items"][0]

    assert audit_log["organization_id"] == (
        login_data["organization_id"]
    )

    assert audit_log["actor_user_id"] == (
        login_data["user_id"]
    )

    assert audit_log["action"] == "conversation.created"
    assert audit_log["resource_type"] == "conversation"
    assert audit_log["resource_id"] == conversation["id"]

    assert (
        audit_log["details"]["conversation_title"]
        == "Employee Leave Questions"
    )

    assert (
        audit_log["details"]["conversation_user_id"]
        == login_data["user_id"]
    )


def test_deleting_conversation_creates_audit_log(
    client: TestClient,
) -> None:
    """Deleting a conversation records conversation.deleted."""

    headers, login_data = register_and_login_admin(
        client,
        organization_name="Conversation Delete Company",
        organization_slug="conversation-delete-company",
        email="admin@conversation-delete.example",
    )

    conversation = create_conversation(
        client,
        headers,
        title="Temporary Conversation",
    )

    conversation_id = conversation["id"]

    delete_response = client.delete(
        f"/api/v1/conversations/{conversation_id}",
        headers=headers,
    )

    assert delete_response.status_code == 204

    audit_response = client.get(
        (
            "/api/v1/admin/audit-logs"
            "?resource_type=conversation"
        ),
        headers=headers,
    )

    assert audit_response.status_code == 200

    data = audit_response.json()

    assert data["total"] == 2
    assert len(data["items"]) == 2

    actions = {
        item["action"]
        for item in data["items"]
    }

    assert actions == {
        "conversation.created",
        "conversation.deleted",
    }

    deleted_log = next(
        item
        for item in data["items"]
        if item["action"] == "conversation.deleted"
    )

    assert deleted_log["organization_id"] == (
        login_data["organization_id"]
    )

    assert deleted_log["actor_user_id"] == (
        login_data["user_id"]
    )

    assert deleted_log["resource_id"] == conversation_id

    assert (
        deleted_log["details"]["conversation_title"]
        == "Temporary Conversation"
    )


def test_conversation_audit_logs_are_organization_isolated(
    client: TestClient,
) -> None:
    """One organization cannot see another organization's logs."""

    first_headers, _ = register_and_login_admin(
        client,
        organization_name="First Conversation Company",
        organization_slug="first-conversation-company",
        email="admin@first-conversation.example",
    )

    create_conversation(
        client,
        first_headers,
        title="First Organization Conversation",
    )

    second_headers, _ = register_and_login_admin(
        client,
        organization_name="Second Conversation Company",
        organization_slug="second-conversation-company",
        email="admin@second-conversation.example",
    )

    response = client.get(
        (
            "/api/v1/admin/audit-logs"
            "?resource_type=conversation"
        ),
        headers=second_headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 0
    assert data["items"] == []