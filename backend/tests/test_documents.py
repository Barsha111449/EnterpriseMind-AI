import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def create_account_and_get_token(
    client: TestClient,
) -> str:
    unique_value = uuid.uuid4().hex[:8]

    organization_slug = f"document-test-{unique_value}"
    email = f"admin-{unique_value}@document-test.example"
    password = "DocumentTest!2026"

    registration_response = client.post(
        "/api/v1/register",
        json={
            "organization_name": "Document Test Company",
            "organization_slug": organization_slug,
            "full_name": "Document Test Administrator",
            "email": email,
            "password": password,
        },
    )

    assert registration_response.status_code == 201

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "organization_slug": organization_slug,
            "email": email,
            "password": password,
        },
    )

    assert login_response.status_code == 200

    return login_response.json()["access_token"]


def test_upload_pdf_document(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_upload_directory = tmp_path / "uploads"

    monkeypatch.setattr(
        "backend.app.api.documents.UPLOAD_ROOT",
        test_upload_directory,
    )

    access_token = create_account_and_get_token(client)

    pdf_content = (
        b"%PDF-1.4\n"
        b"EnterpriseMind AI test document\n"
    )

    response = client.post(
        "/api/v1/documents/upload",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
        files={
            "file": (
                "employee-policy.pdf",
                pdf_content,
                "application/pdf",
            ),
        },
    )

    assert response.status_code == 201

    response_data = response.json()

    assert response_data["original_filename"] == "employee-policy.pdf"
    assert response_data["content_type"] == "application/pdf"
    assert response_data["file_size_bytes"] == len(pdf_content)
    assert response_data["status"] == "uploaded"
    assert response_data["error_message"] is None

    saved_files = list(
        test_upload_directory.rglob("*.pdf")
    )

    assert len(saved_files) == 1
    assert saved_files[0].read_bytes() == pdf_content


def test_upload_requires_authentication(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/documents/upload",
        files={
            "file": (
                "employee-policy.pdf",
                b"%PDF-1.4\nTest",
                "application/pdf",
            ),
        },
    )

    assert response.status_code == 401


def test_upload_rejects_unsupported_file_type(
    client: TestClient,
) -> None:
    access_token = create_account_and_get_token(client)

    response = client.post(
        "/api/v1/documents/upload",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
        files={
            "file": (
                "notes.txt",
                b"This file type is not allowed.",
                "text/plain",
            ),
        },
    )

    assert response.status_code == 415

    assert response.json() == {
        "detail": "Only PDF and DOCX files are allowed."
    }
def test_download_document_returns_file(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_upload_directory = tmp_path / "uploads"

    monkeypatch.setattr(
        "backend.app.api.documents.UPLOAD_ROOT",
        test_upload_directory,
    )

    access_token = create_account_and_get_token(client)

    pdf_content = b"%PDF-1.4\nDownload test document"

    upload_response = client.post(
        "/api/v1/documents/upload",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
        files={
            "file": (
                "download-test.pdf",
                pdf_content,
                "application/pdf",
            ),
        },
    )

    assert upload_response.status_code == 201

    document_id = upload_response.json()["id"]

    response = client.get(
        f"/api/v1/documents/{document_id}/download",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
    )

    assert response.status_code == 200
    assert response.content == pdf_content
    assert response.headers["content-type"].startswith(
        "application/pdf"
    )
    assert "download-test.pdf" in response.headers[
        "content-disposition"
    ]


def test_download_document_requires_authentication(
    client: TestClient,
) -> None:
    document_id = uuid.uuid4()

    response = client.get(
        f"/api/v1/documents/{document_id}/download"
    )

    assert response.status_code == 401


def test_download_document_protects_organization_data(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_upload_directory = tmp_path / "uploads"

    monkeypatch.setattr(
        "backend.app.api.documents.UPLOAD_ROOT",
        test_upload_directory,
    )

    first_token = create_account_and_get_token(client)
    second_token = create_account_and_get_token(client)

    upload_response = client.post(
        "/api/v1/documents/upload",
        headers={
            "Authorization": f"Bearer {first_token}",
        },
        files={
            "file": (
                "private-download.pdf",
                b"%PDF-1.4\nPrivate company document",
                "application/pdf",
            ),
        },
    )

    assert upload_response.status_code == 201

    document_id = upload_response.json()["id"]

    response = client.get(
        f"/api/v1/documents/{document_id}/download",
        headers={
            "Authorization": f"Bearer {second_token}",
        },
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Document not found."
    }