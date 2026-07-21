from fastapi.testclient import TestClient


TEST_PASSWORD = "EmployeeAudit!2026"


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
            "full_name": "Employee Audit Administrator",
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


def create_employee(
    client: TestClient,
    admin_headers: dict[str, str],
    *,
    email: str,
    role: str = "employee",
) -> dict:
    """Create an employee through the administrator endpoint."""

    response = client.post(
        "/api/v1/admin/employees",
        headers=admin_headers,
        json={
            "full_name": "Employee Audit User",
            "email": email,
            "password": TEST_PASSWORD,
            "role": role,
        },
    )

    assert response.status_code == 201

    return response.json()


def login_employee(
    client: TestClient,
    *,
    organization_slug: str,
    email: str,
) -> dict[str, str]:
    """Log in an employee and return authorization headers."""

    response = client.post(
        "/api/v1/auth/login",
        json={
            "organization_slug": organization_slug,
            "email": email,
            "password": TEST_PASSWORD,
        },
    )

    assert response.status_code == 200

    return {
        "Authorization": (
            f"Bearer {response.json()['access_token']}"
        ),
    }


def test_employee_actions_create_audit_logs(
    client: TestClient,
) -> None:
    """Employee lifecycle actions create the expected audit records."""

    admin_headers, login_data = register_admin(
        client,
        organization_name="Employee Audit Company",
        organization_slug="employee-audit-company",
        email="admin@employee-audit.example",
    )

    employee = create_employee(
        client,
        admin_headers,
        email="worker@employee-audit.example",
    )

    user_id = employee["user_id"]

    role_response = client.patch(
        f"/api/v1/admin/employees/{user_id}/role",
        headers=admin_headers,
        json={
            "role": "manager",
        },
    )

    assert role_response.status_code == 200
    assert role_response.json()["role"] == "manager"

    deactivate_response = client.patch(
        f"/api/v1/admin/employees/{user_id}/status",
        headers=admin_headers,
        json={
            "is_active": False,
        },
    )

    assert deactivate_response.status_code == 200
    assert deactivate_response.json()["is_active"] is False

    activate_response = client.patch(
        f"/api/v1/admin/employees/{user_id}/status",
        headers=admin_headers,
        json={
            "is_active": True,
        },
    )

    assert activate_response.status_code == 200
    assert activate_response.json()["is_active"] is True

    audit_response = client.get(
        (
            "/api/v1/admin/audit-logs"
            "?resource_type=employee"
        ),
        headers=admin_headers,
    )

    assert audit_response.status_code == 200

    data = audit_response.json()

    assert data["total"] == 4
    assert len(data["items"]) == 4

    actions = {
        item["action"]
        for item in data["items"]
    }

    assert actions == {
        "employee.created",
        "employee.role_changed",
        "employee.deactivated",
        "employee.activated",
    }

    for audit_log in data["items"]:
        assert audit_log["organization_id"] == (
            login_data["organization_id"]
        )

        assert audit_log["resource_type"] == "employee"
        assert audit_log["resource_id"] == user_id
        assert audit_log["actor_user_id"] == (
            login_data["user_id"]
        )


def test_employee_audit_logs_contain_change_details(
    client: TestClient,
) -> None:
    """Role and status logs contain previous and new values."""

    admin_headers, _ = register_admin(
        client,
        organization_name="Employee Detail Company",
        organization_slug="employee-detail-company",
        email="admin@employee-detail.example",
    )

    employee = create_employee(
        client,
        admin_headers,
        email="worker@employee-detail.example",
        role="employee",
    )

    user_id = employee["user_id"]

    role_response = client.patch(
        f"/api/v1/admin/employees/{user_id}/role",
        headers=admin_headers,
        json={
            "role": "reviewer",
        },
    )

    assert role_response.status_code == 200

    status_response = client.patch(
        f"/api/v1/admin/employees/{user_id}/status",
        headers=admin_headers,
        json={
            "is_active": False,
        },
    )

    assert status_response.status_code == 200

    audit_response = client.get(
        "/api/v1/admin/audit-logs?resource_type=employee",
        headers=admin_headers,
    )

    assert audit_response.status_code == 200

    items = audit_response.json()["items"]

    logs_by_action = {
        item["action"]: item
        for item in items
    }

    role_log = logs_by_action["employee.role_changed"]

    assert role_log["details"]["previous_role"] == "employee"
    assert role_log["details"]["new_role"] == "reviewer"

    status_log = logs_by_action["employee.deactivated"]

    assert (
        status_log["details"]["previous_is_active"]
        is True
    )

    assert (
        status_log["details"]["new_is_active"]
        is False
    )


def test_unchanged_employee_values_do_not_create_extra_logs(
    client: TestClient,
) -> None:
    """Submitting the same role or status does not create duplicate logs."""

    admin_headers, _ = register_admin(
        client,
        organization_name="Employee No Change Company",
        organization_slug="employee-no-change-company",
        email="admin@employee-no-change.example",
    )

    employee = create_employee(
        client,
        admin_headers,
        email="worker@employee-no-change.example",
        role="employee",
    )

    user_id = employee["user_id"]

    same_role_response = client.patch(
        f"/api/v1/admin/employees/{user_id}/role",
        headers=admin_headers,
        json={
            "role": "employee",
        },
    )

    assert same_role_response.status_code == 200

    same_status_response = client.patch(
        f"/api/v1/admin/employees/{user_id}/status",
        headers=admin_headers,
        json={
            "is_active": True,
        },
    )

    assert same_status_response.status_code == 200

    audit_response = client.get(
        "/api/v1/admin/audit-logs?resource_type=employee",
        headers=admin_headers,
    )

    assert audit_response.status_code == 200

    data = audit_response.json()

    assert data["total"] == 1
    assert data["items"][0]["action"] == "employee.created"


def test_employee_cannot_view_employee_audit_logs(
    client: TestClient,
) -> None:
    """A normal employee cannot access organization audit history."""

    organization_slug = "employee-audit-access-company"
    employee_email = "worker@employee-audit-access.example"

    admin_headers, _ = register_admin(
        client,
        organization_name="Employee Audit Access Company",
        organization_slug=organization_slug,
        email="admin@employee-audit-access.example",
    )

    create_employee(
        client,
        admin_headers,
        email=employee_email,
    )

    employee_headers = login_employee(
        client,
        organization_slug=organization_slug,
        email=employee_email,
    )

    response = client.get(
        "/api/v1/admin/audit-logs?resource_type=employee",
        headers=employee_headers,
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Administrator access required.",
    }