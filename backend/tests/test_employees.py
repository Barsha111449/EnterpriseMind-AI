from fastapi.testclient import TestClient


def register_and_login_admin(
    client: TestClient,
    *,
    organization_name: str,
    organization_slug: str,
    email: str,
) -> tuple[dict[str, str], dict]:
    """Register and log in an organization administrator."""

    password = "EmployeeTest!2026"

    register_response = client.post(
        "/api/v1/register",
        json={
            "organization_name": organization_name,
            "organization_slug": organization_slug,
            "full_name": "Organization Administrator",
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

    return headers, login_data


def create_employee(
    client: TestClient,
    headers: dict[str, str],
    *,
    email: str,
    role: str = "employee",
) -> dict:
    """Create one employee through the admin endpoint."""

    response = client.post(
        "/api/v1/admin/employees",
        headers=headers,
        json={
            "full_name": "Test Employee",
            "email": email,
            "password": "EmployeeUser!2026",
            "role": role,
        },
    )

    assert response.status_code == 201

    return response.json()


def test_employee_management_requires_authentication(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/v1/admin/employees"
    )

    assert response.status_code == 401


def test_admin_can_create_and_list_employees(
    client: TestClient,
) -> None:
    headers, admin_data = register_and_login_admin(
        client,
        organization_name="Employee Test Company",
        organization_slug="employee-test-company",
        email="admin@employee-test.example",
    )

    employee = create_employee(
        client,
        headers,
        email="worker@employee-test.example",
        role="manager",
    )

    assert employee["role"] == "manager"
    assert employee["is_active"] is True
    assert (
        employee["organization_id"]
        == admin_data["organization_id"]
    )

    response = client.get(
        "/api/v1/admin/employees",
        headers=headers,
    )

    assert response.status_code == 200

    employees = response.json()

    assert len(employees) == 2

    employee_emails = {
        item["email"]
        for item in employees
    }

    assert "admin@employee-test.example" in employee_emails
    assert "worker@employee-test.example" in employee_emails


def test_non_admin_cannot_manage_employees(
    client: TestClient,
) -> None:
    admin_headers, _ = register_and_login_admin(
        client,
        organization_name="Role Test Company",
        organization_slug="role-test-company",
        email="admin@role-test.example",
    )

    create_employee(
        client,
        admin_headers,
        email="employee@role-test.example",
    )

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "organization_slug": "role-test-company",
            "email": "employee@role-test.example",
            "password": "EmployeeUser!2026",
        },
    )

    assert login_response.status_code == 200

    employee_headers = {
        "Authorization": (
            f"Bearer {login_response.json()['access_token']}"
        ),
    }

    response = client.get(
        "/api/v1/admin/employees",
        headers=employee_headers,
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Administrator access required.",
    }


def test_admin_can_change_role_and_status(
    client: TestClient,
) -> None:
    headers, _ = register_and_login_admin(
        client,
        organization_name="Update Employee Company",
        organization_slug="update-employee-company",
        email="admin@update-employee.example",
    )

    employee = create_employee(
        client,
        headers,
        email="worker@update-employee.example",
    )

    user_id = employee["user_id"]

    role_response = client.patch(
        f"/api/v1/admin/employees/{user_id}/role",
        headers=headers,
        json={
            "role": "reviewer",
        },
    )

    assert role_response.status_code == 200
    assert role_response.json()["role"] == "reviewer"

    status_response = client.patch(
        f"/api/v1/admin/employees/{user_id}/status",
        headers=headers,
        json={
            "is_active": False,
        },
    )

    assert status_response.status_code == 200
    assert status_response.json()["is_active"] is False


def test_admin_cannot_deactivate_self(
    client: TestClient,
) -> None:
    headers, admin_data = register_and_login_admin(
        client,
        organization_name="Self Protection Company",
        organization_slug="self-protection-company",
        email="admin@self-protection.example",
    )

    response = client.patch(
        (
            "/api/v1/admin/employees/"
            f"{admin_data['user_id']}/status"
        ),
        headers=headers,
        json={
            "is_active": False,
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "You cannot deactivate your own account.",
    }


def test_organization_cannot_manage_another_organizations_employee(
    client: TestClient,
) -> None:
    first_headers, _ = register_and_login_admin(
        client,
        organization_name="First Employee Company",
        organization_slug="first-employee-company",
        email="admin@first-employee.example",
    )

    employee = create_employee(
        client,
        first_headers,
        email="worker@first-employee.example",
    )

    second_headers, _ = register_and_login_admin(
        client,
        organization_name="Second Employee Company",
        organization_slug="second-employee-company",
        email="admin@second-employee.example",
    )

    response = client.patch(
        (
            "/api/v1/admin/employees/"
            f"{employee['user_id']}/role"
        ),
        headers=second_headers,
        json={
            "role": "manager",
        },
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Employee not found.",
    }