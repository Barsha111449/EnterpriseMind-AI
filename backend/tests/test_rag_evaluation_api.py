import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.rag_evaluation import RagEvaluation


TEST_PASSWORD = "RagEvaluationTest!2026"


def register_admin(
    client: TestClient,
    *,
    organization_name: str,
    organization_slug: str,
    email: str,
) -> tuple[dict[str, str], dict]:
    """Register an organization and return administrator details."""

    register_response = client.post(
        "/api/v1/register",
        json={
            "organization_name": organization_name,
            "organization_slug": organization_slug,
            "full_name": "RAG Evaluation Administrator",
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

    access_token = login_response.json()["access_token"]

    headers = {
        "Authorization": f"Bearer {access_token}",
    }

    me_response = client.get(
        "/api/v1/auth/me",
        headers=headers,
    )

    assert me_response.status_code == 200

    return headers, me_response.json()


def create_employee_and_login(
    client: TestClient,
    *,
    admin_headers: dict[str, str],
    organization_slug: str,
    email: str,
) -> dict[str, str]:
    """Create and log in a regular employee."""

    create_response = client.post(
        "/api/v1/admin/employees",
        headers=admin_headers,
        json={
            "full_name": "Evaluation Employee",
            "email": email,
            "password": TEST_PASSWORD,
            "role": "employee",
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


def add_evaluation(
    database_session: Session,
    *,
    organization_id: str,
    user_id: str,
    question: str,
    grounded: bool,
    retrieval_relevance: float,
    response_latency_ms: float,
    retrieved_candidate_count: int,
    relevant_candidate_count: int,
) -> RagEvaluation:
    """Insert one deterministic RAG evaluation record."""

    evaluation = RagEvaluation(
        organization_id=uuid.UUID(organization_id),
        user_id=uuid.UUID(user_id),
        question=question,
        answer=(
            "This is a grounded answer."
            if grounded
            else "I could not find enough evidence "
            "in the available documents."
        ),
        grounded=grounded,
        citation_count=1 if grounded else 0,
        retrieval_relevance=retrieval_relevance,
        citation_coverage=1.0,
        groundedness_consistency=1.0,
        response_latency_ms=response_latency_ms,
        retrieved_candidate_count=(
            retrieved_candidate_count
        ),
        relevant_candidate_count=(
            relevant_candidate_count
        ),
    )

    database_session.add(evaluation)
    database_session.commit()
    database_session.refresh(evaluation)

    return evaluation


def test_rag_evaluations_require_authentication(
    client: TestClient,
) -> None:
    """An unauthenticated user cannot view evaluations."""

    response = client.get(
        "/api/v1/admin/rag-evaluations"
    )

    assert response.status_code == 401


def test_admin_can_list_rag_evaluations(
    client: TestClient,
    database_session: Session,
) -> None:
    """An administrator can list organization evaluations."""

    headers, current_user = register_admin(
        client,
        organization_name="Evaluation List Company",
        organization_slug="evaluation-list-company",
        email="admin@evaluation-list.example",
    )

    first_evaluation = add_evaluation(
        database_session,
        organization_id=current_user["organization_id"],
        user_id=current_user["user_id"],
        question="What is the leave policy?",
        grounded=True,
        retrieval_relevance=0.6,
        response_latency_ms=100.0,
        retrieved_candidate_count=5,
        relevant_candidate_count=2,
    )

    add_evaluation(
        database_session,
        organization_id=current_user["organization_id"],
        user_id=current_user["user_id"],
        question="What is the unknown policy?",
        grounded=False,
        retrieval_relevance=0.2,
        response_latency_ms=200.0,
        retrieved_candidate_count=4,
        relevant_candidate_count=0,
    )

    response = client.get(
        "/api/v1/admin/rag-evaluations",
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert data["limit"] == 50
    assert data["offset"] == 0

    evaluation_ids = {
        item["id"]
        for item in data["items"]
    }

    assert str(first_evaluation.id) in evaluation_ids


def test_rag_evaluations_can_be_filtered_by_grounded_status(
    client: TestClient,
    database_session: Session,
) -> None:
    """The grounded query parameter filters evaluation records."""

    headers, current_user = register_admin(
        client,
        organization_name="Evaluation Filter Company",
        organization_slug="evaluation-filter-company",
        email="admin@evaluation-filter.example",
    )

    add_evaluation(
        database_session,
        organization_id=current_user["organization_id"],
        user_id=current_user["user_id"],
        question="Grounded question",
        grounded=True,
        retrieval_relevance=0.8,
        response_latency_ms=90.0,
        retrieved_candidate_count=5,
        relevant_candidate_count=3,
    )

    add_evaluation(
        database_session,
        organization_id=current_user["organization_id"],
        user_id=current_user["user_id"],
        question="Ungrounded question",
        grounded=False,
        retrieval_relevance=0.0,
        response_latency_ms=50.0,
        retrieved_candidate_count=0,
        relevant_candidate_count=0,
    )

    grounded_response = client.get(
        "/api/v1/admin/rag-evaluations?grounded=true",
        headers=headers,
    )

    assert grounded_response.status_code == 200

    grounded_data = grounded_response.json()

    assert grounded_data["total"] == 1
    assert grounded_data["items"][0]["grounded"] is True

    ungrounded_response = client.get(
        "/api/v1/admin/rag-evaluations?grounded=false",
        headers=headers,
    )

    assert ungrounded_response.status_code == 200

    ungrounded_data = ungrounded_response.json()

    assert ungrounded_data["total"] == 1
    assert ungrounded_data["items"][0]["grounded"] is False


def test_admin_can_view_rag_evaluation_summary(
    client: TestClient,
    database_session: Session,
) -> None:
    """The summary endpoint calculates organization statistics."""

    headers, current_user = register_admin(
        client,
        organization_name="Evaluation Summary Company",
        organization_slug="evaluation-summary-company",
        email="admin@evaluation-summary.example",
    )

    add_evaluation(
        database_session,
        organization_id=current_user["organization_id"],
        user_id=current_user["user_id"],
        question="First question",
        grounded=True,
        retrieval_relevance=0.6,
        response_latency_ms=100.0,
        retrieved_candidate_count=5,
        relevant_candidate_count=2,
    )

    add_evaluation(
        database_session,
        organization_id=current_user["organization_id"],
        user_id=current_user["user_id"],
        question="Second question",
        grounded=False,
        retrieval_relevance=0.2,
        response_latency_ms=200.0,
        retrieved_candidate_count=3,
        relevant_candidate_count=0,
    )

    response = client.get(
        "/api/v1/admin/rag-evaluations/summary",
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total_evaluations"] == 2
    assert data["grounded_count"] == 1
    assert data["ungrounded_count"] == 1
    assert data["grounded_rate"] == 0.5

    assert (
        data["average_retrieval_relevance"]
        == 0.4
    )

    assert (
        data["average_citation_coverage"]
        == 1.0
    )

    assert (
        data["average_groundedness_consistency"]
        == 1.0
    )

    assert (
        data["average_response_latency_ms"]
        == 150.0
    )

    assert (
        data["average_retrieved_candidate_count"]
        == 4.0
    )

    assert (
        data["average_relevant_candidate_count"]
        == 1.0
    )


def test_regular_employee_cannot_view_rag_evaluations(
    client: TestClient,
) -> None:
    """A regular employee does not have analytics permission."""

    organization_slug = "evaluation-role-company"

    admin_headers, _ = register_admin(
        client,
        organization_name="Evaluation Role Company",
        organization_slug=organization_slug,
        email="admin@evaluation-role.example",
    )

    employee_headers = create_employee_and_login(
        client,
        admin_headers=admin_headers,
        organization_slug=organization_slug,
        email="employee@evaluation-role.example",
    )

    response = client.get(
        "/api/v1/admin/rag-evaluations",
        headers=employee_headers,
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Analytics access required.",
    }


def test_rag_evaluations_are_organization_isolated(
    client: TestClient,
    database_session: Session,
) -> None:
    """An organization cannot view another organization's results."""

    first_headers, first_user = register_admin(
        client,
        organization_name="First Evaluation Company",
        organization_slug="first-evaluation-company",
        email="admin@first-evaluation.example",
    )

    add_evaluation(
        database_session,
        organization_id=first_user["organization_id"],
        user_id=first_user["user_id"],
        question="Private organization question",
        grounded=True,
        retrieval_relevance=0.9,
        response_latency_ms=75.0,
        retrieved_candidate_count=5,
        relevant_candidate_count=4,
    )

    second_headers, _ = register_admin(
        client,
        organization_name="Second Evaluation Company",
        organization_slug="second-evaluation-company",
        email="admin@second-evaluation.example",
    )

    response = client.get(
        "/api/v1/admin/rag-evaluations",
        headers=second_headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 0
    assert data["items"] == []

    first_response = client.get(
        "/api/v1/admin/rag-evaluations",
        headers=first_headers,
    )

    assert first_response.status_code == 200
    assert first_response.json()["total"] == 1