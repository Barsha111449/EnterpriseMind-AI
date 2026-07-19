import uuid

from fastapi.testclient import TestClient


TEST_PASSWORD = "DocumentPermission!2026"


def register_admin(
    client: TestClient,
    *,
    organization_name: str,
    organization_slug: str,
    email: str,
) -> tuple[dict[str, str], dict]:
    """Create an organization and log in its administrator."""

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
        "Authorization": (
            f"Bearer {login_data['access_token']}"
        ),
    }

    return headers, login_data


def create_employee_and_login(
    client: TestClient,
    *,
    admin_headers: dict[str, str],
    organization_slug: str,
    email: str,
    role: str,
) -> dict[str, str]:
    """Create one employee and return their login headers."""

    create_response = client.post(
        "/api/v1/admin/employees",
        headers=admin_headers,
        json={
            "full_name": f"Test {role.title()}",
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


def upload_test_pdf(
    client: TestClient,
    headers: dict[str, str],
    *,
    filename: str,
):
    """Upload a small PDF-like test file."""

    return client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={
            "file": (
                filename,
                b"%PDF-1.4\nTest document\n%%EOF",
                "application/pdf",
            ),
        },
    )


def test_admin_and_manager_can_upload_documents(
    client: TestClient,
) -> None:
    """Administrators and managers may upload documents."""

    organization_slug = "document-upload-company"

    admin_headers, _ = register_admin(
        client,
        organization_name="Document Upload Company",
        organization_slug=organization_slug,
        email="admin@document-upload.example",
    )

    manager_headers = create_employee_and_login(
        client,
        admin_headers=admin_headers,
        organization_slug=organization_slug,
        email="manager@document-upload.example",
        role="manager",
    )

    admin_response = upload_test_pdf(
        client,
        admin_headers,
        filename="admin-document.pdf",
    )

    manager_response = upload_test_pdf(
        client,
        manager_headers,
        filename="manager-document.pdf",
    )

    assert admin_response.status_code == 201
    assert manager_response.status_code == 201

    assert (
        admin_response.json()["original_filename"]
        == "admin-document.pdf"
    )

    assert (
        manager_response.json()["original_filename"]
        == "manager-document.pdf"
    )


def test_employee_and_reviewer_cannot_upload_documents(
    client: TestClient,
) -> None:
    """Employees and reviewers must receive 403 for uploads."""

    organization_slug = "restricted-upload-company"

    admin_headers, _ = register_admin(
        client,
        organization_name="Restricted Upload Company",
        organization_slug=organization_slug,
        email="admin@restricted-upload.example",
    )

    employee_headers = create_employee_and_login(
        client,
        admin_headers=admin_headers,
        organization_slug=organization_slug,
        email="employee@restricted-upload.example",
        role="employee",
    )

    reviewer_headers = create_employee_and_login(
        client,
        admin_headers=admin_headers,
        organization_slug=organization_slug,
        email="reviewer@restricted-upload.example",
        role="reviewer",
    )

    employee_response = upload_test_pdf(
        client,
        employee_headers,
        filename="employee-document.pdf",
    )

    reviewer_response = upload_test_pdf(
        client,
        reviewer_headers,
        filename="reviewer-document.pdf",
    )

    assert employee_response.status_code == 403
    assert reviewer_response.status_code == 403

    expected_body = {
        "detail": "Document upload access required.",
    }

    assert employee_response.json() == expected_body
    assert reviewer_response.json() == expected_body


def test_all_roles_can_list_documents(
    client: TestClient,
) -> None:
    """Every active organization role may list company documents."""

    organization_slug = "document-list-company"

    admin_headers, _ = register_admin(
        client,
        organization_name="Document List Company",
        organization_slug=organization_slug,
        email="admin@document-list.example",
    )

    manager_headers = create_employee_and_login(
        client,
        admin_headers=admin_headers,
        organization_slug=organization_slug,
        email="manager@document-list.example",
        role="manager",
    )

    employee_headers = create_employee_and_login(
        client,
        admin_headers=admin_headers,
        organization_slug=organization_slug,
        email="employee@document-list.example",
        role="employee",
    )

    reviewer_headers = create_employee_and_login(
        client,
        admin_headers=admin_headers,
        organization_slug=organization_slug,
        email="reviewer@document-list.example",
        role="reviewer",
    )

    upload_response = upload_test_pdf(
        client,
        admin_headers,
        filename="shared-document.pdf",
    )

    assert upload_response.status_code == 201

    for headers in (
        admin_headers,
        manager_headers,
        employee_headers,
        reviewer_headers,
    ):
        response = client.get(
            "/api/v1/documents",
            headers=headers,
        )

        assert response.status_code == 200
        assert len(response.json()) == 1
        assert (
            response.json()[0]["original_filename"]
            == "shared-document.pdf"
        )


def test_processing_permissions_are_enforced(
    client: TestClient,
) -> None:
    """Only administrators and managers reach document processing."""

    organization_slug = "processing-permission-company"

    admin_headers, _ = register_admin(
        client,
        organization_name="Processing Permission Company",
        organization_slug=organization_slug,
        email="admin@processing-permission.example",
    )

    manager_headers = create_employee_and_login(
        client,
        admin_headers=admin_headers,
        organization_slug=organization_slug,
        email="manager@processing-permission.example",
        role="manager",
    )

    employee_headers = create_employee_and_login(
        client,
        admin_headers=admin_headers,
        organization_slug=organization_slug,
        email="employee@processing-permission.example",
        role="employee",
    )

    reviewer_headers = create_employee_and_login(
        client,
        admin_headers=admin_headers,
        organization_slug=organization_slug,
        email="reviewer@processing-permission.example",
        role="reviewer",
    )

    missing_document_id = uuid.uuid4()

    admin_response = client.post(
        (
            "/api/v1/documents/"
            f"{missing_document_id}/process"
        ),
        headers=admin_headers,
    )

    manager_response = client.post(
        (
            "/api/v1/documents/"
            f"{missing_document_id}/process"
        ),
        headers=manager_headers,
    )

    employee_response = client.post(
        (
            "/api/v1/documents/"
            f"{missing_document_id}/process"
        ),
        headers=employee_headers,
    )

    reviewer_response = client.post(
        (
            "/api/v1/documents/"
            f"{missing_document_id}/process"
        ),
        headers=reviewer_headers,
    )

    # Admin and manager pass the permission check,
    # then receive 404 because the document does not exist.
    assert admin_response.status_code == 404
    assert manager_response.status_code == 404

    # Employee and reviewer are stopped by permissions first.
    assert employee_response.status_code == 403
    assert reviewer_response.status_code == 403

    expected_body = {
        "detail": "Document processing access required.",
    }

    assert employee_response.json() == expected_body
    assert reviewer_response.json() == expected_body