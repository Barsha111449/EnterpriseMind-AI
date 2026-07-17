import uuid

import pytest
from fastapi.testclient import TestClient

from backend.app.schemas.search import (
    HybridSearchResponse,
    HybridSearchResult,
)
from backend.app.services.answer_generation_service import (
    NO_EVIDENCE_ANSWER,
)


def create_account_and_get_token(
    client: TestClient,
) -> str:
    """Create a unique test account and return its token."""

    unique_value = uuid.uuid4().hex[:8]

    organization_slug = (
        f"question-test-{unique_value}"
    )

    email = (
        f"admin-{unique_value}"
        "@question-test.example"
    )

    password = "QuestionTest!2026"

    registration_response = client.post(
        "/api/v1/register",
        json={
            "organization_name": (
                "Question Test Company"
            ),
            "organization_slug": (
                organization_slug
            ),
            "full_name": (
                "Question Test Administrator"
            ),
            "email": email,
            "password": password,
        },
    )

    assert registration_response.status_code == 201

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "organization_slug": (
                organization_slug
            ),
            "email": email,
            "password": password,
        },
    )

    assert login_response.status_code == 200

    return login_response.json()["access_token"]


def test_question_endpoint_requires_authentication(
    client: TestClient,
) -> None:
    """A user without a token must not ask questions."""

    response = client.post(
        "/api/v1/questions/ask",
        json={
            "question": (
                "What is the annual leave policy?"
            ),
            "top_k": 5,
        },
    )

    assert response.status_code == 401


def test_question_endpoint_returns_grounded_answer(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The endpoint should return an answer with citations."""

    chunk_id = uuid.uuid4()
    document_id = uuid.uuid4()

    def fake_hybrid_search(
        search_request,
        current_user,
        database_session,
    ) -> HybridSearchResponse:
        return HybridSearchResponse(
            query=search_request.query,
            result_count=1,
            results=[
                HybridSearchResult(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    original_filename=(
                        "employee-handbook.pdf"
                    ),
                    page_number=2,
                    chunk_index=0,
                    content=(
                        "Employees receive twenty days "
                        "of annual leave each year."
                    ),
                    semantic_score=0.91,
                    keyword_score=0.45,
                    hybrid_score=0.0327,
                    rerank_score=5.2,
                )
            ],
        )

    def fake_generate_grounded_answer(
        question: str,
        context: str,
    ) -> str:
        assert question == (
            "How many annual leave days "
            "do employees receive?"
        )

        assert "employee-handbook.pdf" in context
        assert "twenty days" in context

        return (
            "Employees receive twenty days "
            "of annual leave each year [1]."
        )

    monkeypatch.setattr(
        (
            "backend.app.api.questions."
            "hybrid_search"
        ),
        fake_hybrid_search,
    )

    monkeypatch.setattr(
        (
            "backend.app.api.questions."
            "generate_grounded_answer"
        ),
        fake_generate_grounded_answer,
    )

    access_token = create_account_and_get_token(
        client
    )

    response = client.post(
        "/api/v1/questions/ask",
        headers={
            "Authorization": (
                f"Bearer {access_token}"
            ),
        },
        json={
            "question": (
                "How many annual leave days "
                "do employees receive?"
            ),
            "top_k": 5,
        },
    )

    assert response.status_code == 200

    response_data = response.json()

    assert response_data["grounded"] is True

    assert response_data["answer"] == (
        "Employees receive twenty days "
        "of annual leave each year [1]."
    )

    assert response_data["citation_count"] == 1
    assert len(response_data["citations"]) == 1

    citation = response_data["citations"][0]

    assert citation["citation_number"] == 1
    assert citation["chunk_id"] == str(chunk_id)

    assert citation["document_id"] == str(
        document_id
    )

    assert citation["original_filename"] == (
        "employee-handbook.pdf"
    )

    assert citation["page_number"] == 2
    assert citation["chunk_index"] == 0

    assert citation["rerank_score"] == (
        pytest.approx(5.2)
    )

    assert "twenty days" in citation["excerpt"]


def test_question_endpoint_handles_missing_evidence(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No evidence should produce a safe response."""

    def fake_hybrid_search(
        search_request,
        current_user,
        database_session,
    ) -> HybridSearchResponse:
        return HybridSearchResponse(
            query=search_request.query,
            result_count=0,
            results=[],
        )

    monkeypatch.setattr(
        (
            "backend.app.api.questions."
            "hybrid_search"
        ),
        fake_hybrid_search,
    )

    access_token = create_account_and_get_token(
        client
    )

    response = client.post(
        "/api/v1/questions/ask",
        headers={
            "Authorization": (
                f"Bearer {access_token}"
            ),
        },
        json={
            "question": (
                "What is the submarine policy?"
            ),
            "top_k": 5,
        },
    )

    assert response.status_code == 200

    response_data = response.json()

    assert response_data["answer"] == (
        NO_EVIDENCE_ANSWER
    )

    assert response_data["grounded"] is False
    assert response_data["citation_count"] == 0
    assert response_data["citations"] == []


def test_question_endpoint_respects_top_k(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The endpoint should pass top_k to retrieval."""

    received_top_k: list[int] = []

    def fake_hybrid_search(
        search_request,
        current_user,
        database_session,
    ) -> HybridSearchResponse:
        received_top_k.append(
            search_request.top_k
        )

        return HybridSearchResponse(
            query=search_request.query,
            result_count=0,
            results=[],
        )

    monkeypatch.setattr(
        (
            "backend.app.api.questions."
            "hybrid_search"
        ),
        fake_hybrid_search,
    )

    access_token = create_account_and_get_token(
        client
    )

    response = client.post(
        "/api/v1/questions/ask",
        headers={
            "Authorization": (
                f"Bearer {access_token}"
            ),
        },
        json={
            "question": (
                "What qualifications are mentioned?"
            ),
            "top_k": 3,
        },
    )

    assert response.status_code == 200
    assert received_top_k == [3]


def test_question_endpoint_rejects_weak_evidence(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Weak unrelated evidence must not produce an answer."""

    def fake_hybrid_search(
        search_request,
        current_user,
        database_session,
    ) -> HybridSearchResponse:
        return HybridSearchResponse(
            query=search_request.query,
            result_count=1,
            results=[
                HybridSearchResult(
                    chunk_id=uuid.uuid4(),
                    document_id=uuid.uuid4(),
                    original_filename=(
                        "unrelated-document.pdf"
                    ),
                    page_number=1,
                    chunk_index=0,
                    content=(
                        "This text describes an "
                        "unrelated office furniture "
                        "policy."
                    ),
                    semantic_score=0.08,
                    keyword_score=None,
                    hybrid_score=0.016,
                    rerank_score=-5.0,
                )
            ],
        )

    def fail_if_answer_generation_runs(
        question: str,
        context: str,
    ) -> str:
        raise AssertionError(
            "Answer generation must not run "
            "when the evidence is weak."
        )

    monkeypatch.setattr(
        (
            "backend.app.api.questions."
            "hybrid_search"
        ),
        fake_hybrid_search,
    )

    monkeypatch.setattr(
        (
            "backend.app.api.questions."
            "generate_grounded_answer"
        ),
        fail_if_answer_generation_runs,
    )

    access_token = create_account_and_get_token(
        client
    )

    response = client.post(
        "/api/v1/questions/ask",
        headers={
            "Authorization": (
                f"Bearer {access_token}"
            ),
        },
        json={
            "question": (
                "What is the submarine "
                "operating policy?"
            ),
            "top_k": 5,
        },
    )

    assert response.status_code == 200

    response_data = response.json()

    assert response_data["answer"] == (
        NO_EVIDENCE_ANSWER
    )

    assert response_data["grounded"] is False
    assert response_data["citation_count"] == 0
    assert response_data["citations"] == []