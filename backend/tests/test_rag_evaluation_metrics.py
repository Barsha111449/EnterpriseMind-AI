from backend.app.evaluation.metrics import (
    calculate_citation_coverage,
    calculate_groundedness_consistency,
    calculate_lexical_overlap,
    calculate_refusal_correctness,
    calculate_retrieval_relevance,
)


NO_EVIDENCE_ANSWER = (
    "I could not find enough evidence "
    "in the available documents."
)


def test_lexical_overlap_detects_matching_words() -> None:
    """Matching question and evidence words produce a positive score."""

    score = calculate_lexical_overlap(
        question="What is the employee leave policy?",
        evidence_text=(
            "The employee leave policy provides "
            "twenty paid leave days."
        ),
    )

    assert score > 0.0
    assert score <= 1.0


def test_retrieval_relevance_handles_empty_evidence() -> None:
    """No retrieved evidence produces a zero relevance score."""

    score = calculate_retrieval_relevance(
        question="What is the refund policy?",
        evidence_texts=[],
    )

    assert score == 0.0


def test_grounded_answer_requires_citations() -> None:
    """A grounded answer without citations is inconsistent."""

    score = calculate_citation_coverage(
        grounded=True,
        citation_count=0,
    )

    assert score == 0.0


def test_valid_grounded_answer_is_consistent() -> None:
    """A grounded answer with citations receives a full score."""

    score = calculate_groundedness_consistency(
        answer=(
            "Employees receive twenty paid "
            "leave days each year."
        ),
        grounded=True,
        citation_count=2,
        no_evidence_answer=NO_EVIDENCE_ANSWER,
    )

    assert score == 1.0


def test_valid_refusal_is_consistent() -> None:
    """A refusal without citations receives a full score."""

    score = calculate_groundedness_consistency(
        answer=NO_EVIDENCE_ANSWER,
        grounded=False,
        citation_count=0,
        no_evidence_answer=NO_EVIDENCE_ANSWER,
    )

    assert score == 1.0


def test_refusal_correctness_when_no_evidence_exists() -> None:
    """The system should refuse when evidence is unavailable."""

    score = calculate_refusal_correctness(
        expected_has_evidence=False,
        answer=NO_EVIDENCE_ANSWER,
        no_evidence_answer=NO_EVIDENCE_ANSWER,
    )

    assert score == 1.0


def test_refusal_is_wrong_when_evidence_exists() -> None:
    """Refusing despite available evidence receives a zero score."""

    score = calculate_refusal_correctness(
        expected_has_evidence=True,
        answer=NO_EVIDENCE_ANSWER,
        no_evidence_answer=NO_EVIDENCE_ANSWER,
    )

    assert score == 0.0