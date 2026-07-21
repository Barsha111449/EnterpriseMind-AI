import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk


TEST_PASSWORD = "DocumentDeletion!2026"


def register_admin(
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
            "full_name": "Document Administrator",
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
        "Authorization": f"Bearer {login_data['access_token']}",
    }

    return headers, login_data


def create_employee_and_login(
    client: TestClient,
    *,
    admin_headers: dict[str, str],
    organization_slug: str,
    role: str,
    email: str,
) -> dict[str, str]:
    """Create an employee and return their authorization headers."""

    create_response = client.post(
        "/api/v1/admin/employees",
        headers=admin_headers,
        json={
            "full_name": f"Deletion {role.title()}",
            "email": email,
            "password": TEST_PASSWORD,
            "role": role,
        },
    )

    assert create_response.status_code == 201

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "organization_slug": organization_slug,
            "email": email,
            "password": TEST_PASSWORD,
        },
    )

    assert login_response.status_code == 200

    return {
        "Authorization": (
            f"Bearer {login_response.json()['access_token']}"
        ),
    }


def upload_test_document(
    client: TestClient,
    headers: dict[str, str],
    *,
    filename: str,
) -> dict:
    """Upload a small test PDF."""

    response = client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={
            "file": (
                filename,
                b"%PDF-1.4\nDeletion test document\n%%EOF",
                "application/pdf",
            ),
        },
    )

    assert response.status_code == 201

    return response.json()


def test_document_deletion_requires_authentication(
    client: TestClient,
) -> None:
    """Unauthenticated deletion requests must be rejected."""

    response = client.delete(
        f"/api/v1/documents/{uuid.uuid4()}"
    )

    assert response.status_code == 401


def test_admin_can_delete_document_file_and_chunks(
    client: TestClient,
    database_session: Session,
) -> None:
    """An administrator can delete the database record, file and chunks."""

    admin_headers, login_data = register_admin(
        client,
        organization_name="Document Deletion Company",
        organization_slug="document-deletion-company",
        email="admin@document-deletion.example",
    )

    uploaded_document = upload_test_document(
        client,
        admin_headers,
        filename="deletion-test.pdf",
    )

    document_id = uuid.UUID(uploaded_document["id"])
    organization_id = uuid.UUID(
        login_data["organization_id"]
    )

    document = database_session.scalar(
        select(Document).where(
            Document.id == document_id
        )
    )

    assert document is not None

    file_path = Path(document.storage_path)

    assert file_path.is_file()

    chunk_content = "A document chunk that should be deleted."

    chunk = DocumentChunk(
        organization_id=organization_id,
        document_id=document_id,
        chunk_index=0,
        page_number=1,
        content=chunk_content,
        character_count=len(chunk_content),
        embedding=None,
    )

    database_session.add(chunk)
    database_session.commit()
    database_session.refresh(chunk)

    chunk_id = chunk.id

    delete_response = client.delete(
        f"/api/v1/documents/{document_id}",
        headers=admin_headers,
    )

    assert delete_response.status_code == 204
    assert delete_response.content == b""

    database_session.expire_all()

    deleted_document = database_session.scalar(
        select(Document).where(
            Document.id == document_id
        )
    )

    deleted_chunk = database_session.scalar(
        select(DocumentChunk).where(
            DocumentChunk.id == chunk_id
        )
    )

    assert deleted_document is None
    assert deleted_chunk is None
    assert not file_path.exists()

    get_response = client.get(
        f"/api/v1/documents/{document_id}",
        headers=admin_headers,
    )

    assert get_response.status_code == 404
    assert get_response.json() == {
        "detail": "Document not found.",
    }


@pytest.mark.parametrize(
    "role",
    [
        "manager",
        "employee",
        "reviewer",
    ],
)
def test_non_admin_roles_cannot_delete_documents(
    client: TestClient,
    database_session: Session,
    role: str,
) -> None:
    """Managers, employees and reviewers cannot delete documents."""

    organization_slug = f"{role}-deletion-company"

    admin_headers, _ = register_admin(
        client,
        organization_name=f"{role.title()} Deletion Company",
        organization_slug=organization_slug,
        email=f"admin@{role}-deletion.example",
    )

    role_headers = create_employee_and_login(
        client,
        admin_headers=admin_headers,
        organization_slug=organization_slug,
        role=role,
        email=f"{role}@{role}-deletion.example",
    )

    uploaded_document = upload_test_document(
        client,
        admin_headers,
        filename=f"{role}-protected-document.pdf",
    )

    document_id = uuid.UUID(uploaded_document["id"])

    delete_response = client.delete(
        f"/api/v1/documents/{document_id}",
        headers=role_headers,
    )

    assert delete_response.status_code == 403
    assert delete_response.json() == {
        "detail": "Document deletion access required.",
    }

    database_session.expire_all()

    existing_document = database_session.scalar(
        select(Document).where(
            Document.id == document_id
        )
    )

    assert existing_document is not None
    assert Path(existing_document.storage_path).is_file()

    cleanup_response = client.delete(
        f"/api/v1/documents/{document_id}",
        headers=admin_headers,
    )

    assert cleanup_response.status_code == 204


def test_admin_cannot_delete_another_organizations_document(
    client: TestClient,
    database_session: Session,
) -> None:
    """An administrator cannot delete another organization's document."""

    first_admin_headers, _ = register_admin(
        client,
        organization_name="First Deletion Company",
        organization_slug="first-deletion-company",
        email="admin@first-deletion.example",
    )

    uploaded_document = upload_test_document(
        client,
        first_admin_headers,
        filename="first-company-document.pdf",
    )

    document_id = uuid.UUID(uploaded_document["id"])

    second_admin_headers, _ = register_admin(
        client,
        organization_name="Second Deletion Company",
        organization_slug="second-deletion-company",
        email="admin@second-deletion.example",
    )

    response = client.delete(
        f"/api/v1/documents/{document_id}",
        headers=second_admin_headers,
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Document not found.",
    }

    database_session.expire_all()

    existing_document = database_session.scalar(
        select(Document).where(
            Document.id == document_id
        )
    )

    assert existing_document is not None
    assert Path(existing_document.storage_path).is_file()

    cleanup_response = client.delete(
        f"/api/v1/documents/{document_id}",
        headers=first_admin_headers,
    )

    assert cleanup_response.status_code == 204


def test_admin_receives_404_for_missing_document(
    client: TestClient,
) -> None:
    """An administrator receives 404 for an unknown document."""

    admin_headers, _ = register_admin(
        client,
        organization_name="Missing Document Company",
        organization_slug="missing-document-company",
        email="admin@missing-document.example",
    )

    response = client.delete(
        f"/api/v1/documents/{uuid.uuid4()}",
        headers=admin_headers,
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Document not found.",
    }