from fastapi.testclient import TestClient


TEST_PASSWORD = "AuditLogTest!2026"


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
            "full_name": "Audit Administrator",
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
    role: str = "employee",
) -> dict[str, str]:
    """Create an employee and return their login headers."""

    create_response = client.post(
        "/api/v1/admin/employees",
        headers=admin_headers,
        json={
            "full_name": "Audit Test Employee",
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
) -> dict:
    """Upload a small PDF for generating an audit record."""

    response = client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={
            "file": (
                filename,
                b"%PDF-1.4\nAudit log test document\n%%EOF",
                "application/pdf",
            ),
        },
    )

    assert response.status_code == 201

    return response.json()


def test_audit_logs_require_authentication(
    client: TestClient,
) -> None:
    """Unauthenticated users cannot access audit logs."""

    response = client.get(
        "/api/v1/admin/audit-logs"
    )

    assert response.status_code == 401


def test_admin_can_view_document_upload_audit_log(
    client: TestClient,
) -> None:
    """An administrator can see a document-upload event."""

    headers, login_data = register_admin(
        client,
        organization_name="Audit View Company",
        organization_slug="audit-view-company",
        email="admin@audit-view.example",
    )

    uploaded_document = upload_test_pdf(
        client,
        headers,
        filename="audit-policy.pdf",
    )

    response = client.get(
        "/api/v1/admin/audit-logs",
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 1
    assert data["limit"] == 50
    assert data["offset"] == 0
    assert len(data["items"]) == 1

    audit_log = data["items"][0]

    assert audit_log["organization_id"] == (
        login_data["organization_id"]
    )
    
    assert audit_log["action"] == "document.uploaded"
    assert audit_log["resource_type"] == "document"
    assert audit_log["resource_id"] == uploaded_document["id"]

    assert audit_log["details"]["original_filename"] == (
        "audit-policy.pdf"
    )


def test_employee_cannot_view_audit_logs(
    client: TestClient,
) -> None:
    """A normal employee cannot access administrator audit logs."""

    organization_slug = "audit-role-company"

    admin_headers, _ = register_admin(
        client,
        organization_name="Audit Role Company",
        organization_slug=organization_slug,
        email="admin@audit-role.example",
    )

    employee_headers = create_employee_and_login(
        client,
        admin_headers=admin_headers,
        organization_slug=organization_slug,
        email="employee@audit-role.example",
        role="employee",
    )

    response = client.get(
        "/api/v1/admin/audit-logs",
        headers=employee_headers,
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Administrator access required.",
    }


def test_audit_logs_are_isolated_by_organization(
    client: TestClient,
) -> None:
    """One organization cannot see another organization's audit logs."""

    first_headers, _ = register_admin(
        client,
        organization_name="First Audit Company",
        organization_slug="first-audit-company",
        email="admin@first-audit.example",
    )

    upload_test_pdf(
        client,
        first_headers,
        filename="first-company-policy.pdf",
    )

    second_headers, _ = register_admin(
        client,
        organization_name="Second Audit Company",
        organization_slug="second-audit-company",
        email="admin@second-audit.example",
    )

    second_response = client.get(
        "/api/v1/admin/audit-logs",
        headers=second_headers,
    )

    assert second_response.status_code == 200

    second_data = second_response.json()

    assert second_data["total"] == 0
    assert second_data["items"] == []


def test_audit_logs_can_be_filtered_by_action(
    client: TestClient,
) -> None:
    """Audit-log results can be filtered by action."""

    headers, _ = register_admin(
        client,
        organization_name="Audit Filter Company",
        organization_slug="audit-filter-company",
        email="admin@audit-filter.example",
    )

    upload_test_pdf(
        client,
        headers,
        filename="filter-policy.pdf",
    )

    matching_response = client.get(
        (
            "/api/v1/admin/audit-logs"
            "?action=document.uploaded"
        ),
        headers=headers,
    )

    assert matching_response.status_code == 200
    assert matching_response.json()["total"] == 1

    missing_response = client.get(
        (
            "/api/v1/admin/audit-logs"
            "?action=document.deleted"
        ),
        headers=headers,
    )

    assert missing_response.status_code == 200
    assert missing_response.json()["total"] == 0
    assert missing_response.json()["items"] == []