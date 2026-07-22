import re
from collections.abc import Sequence


WORD_PATTERN = re.compile(r"[a-zA-Z0-9]+")


def tokenize_text(text: str) -> set[str]:
    """
    Convert text into a normalized set of words.

    This is used for the first baseline retrieval metric.
    """

    return {
        token.lower()
        for token in WORD_PATTERN.findall(text)
    }


def calculate_lexical_overlap(
    question: str,
    evidence_text: str,
) -> float:
    """
    Measure how many question words appear in one evidence passage.

    The score is between 0.0 and 1.0.
    """

    question_tokens = tokenize_text(question)

    if not question_tokens:
        return 0.0

    evidence_tokens = tokenize_text(evidence_text)

    matching_tokens = (
        question_tokens.intersection(evidence_tokens)
    )

    score = (
        len(matching_tokens)
        / len(question_tokens)
    )

    return round(score, 4)


def calculate_retrieval_relevance(
    question: str,
    evidence_texts: Sequence[str],
) -> float:
    """
    Calculate the average lexical relevance of retrieved evidence.

    This is a deterministic baseline metric. Later, we will add
    embedding-based and model-based evaluation.
    """

    if not evidence_texts:
        return 0.0

    scores = [
        calculate_lexical_overlap(
            question=question,
            evidence_text=evidence_text,
        )
        for evidence_text in evidence_texts
    ]

    average_score = sum(scores) / len(scores)

    return round(average_score, 4)


def calculate_citation_coverage(
    *,
    grounded: bool,
    citation_count: int,
) -> float:
    """
    Check whether citation behavior matches the grounded status.

    A grounded answer should contain at least one citation.
    An ungrounded refusal should contain no citations.
    """

    if grounded:
        return 1.0 if citation_count > 0 else 0.0

    return 1.0 if citation_count == 0 else 0.0


def calculate_groundedness_consistency(
    *,
    answer: str,
    grounded: bool,
    citation_count: int,
    no_evidence_answer: str,
) -> float:
    """
    Check whether answer, grounded flag and citations agree.

    Valid grounded result:
    - not a refusal
    - grounded is True
    - at least one citation

    Valid refusal result:
    - refusal answer
    - grounded is False
    - no citations
    """

    normalized_answer = answer.strip()
    normalized_refusal = no_evidence_answer.strip()

    is_refusal = (
        normalized_answer == normalized_refusal
    )

    valid_grounded_answer = (
        not is_refusal
        and grounded
        and citation_count > 0
    )

    valid_refusal = (
        is_refusal
        and not grounded
        and citation_count == 0
    )

    return (
        1.0
        if valid_grounded_answer or valid_refusal
        else 0.0
    )


def calculate_refusal_correctness(
    *,
    expected_has_evidence: bool,
    answer: str,
    no_evidence_answer: str,
) -> float:
    """
    Check whether the system correctly answered or refused.

    expected_has_evidence=True:
        the system should provide an answer.

    expected_has_evidence=False:
        the system should return the refusal answer.
    """

    is_refusal = (
        answer.strip()
        == no_evidence_answer.strip()
    )

    if expected_has_evidence:
        return 0.0 if is_refusal else 1.0

    return 1.0 if is_refusal else 0.0