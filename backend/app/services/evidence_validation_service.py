from typing import Any


MIN_STRONG_SEMANTIC_SCORE = 0.45
MIN_MODERATE_SEMANTIC_SCORE = 0.30
MIN_SUPPORTING_RERANK_SCORE = 0.0


def safe_float(
    value: Any,
) -> float | None:
    """Convert a score to float without crashing."""

    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def is_candidate_relevant(
    candidate: dict[str, Any],
) -> bool:
    """Decide whether one retrieved chunk is strong enough."""

    semantic_score = safe_float(
        candidate.get("semantic_score")
    )

    keyword_score = safe_float(
        candidate.get("keyword_score")
    )

    rerank_score = safe_float(
        candidate.get("rerank_score")
    )

    has_keyword_match = (
        keyword_score is not None
        and keyword_score > 0.0
    )

    has_strong_semantic_match = (
        semantic_score is not None
        and semantic_score
        >= MIN_STRONG_SEMANTIC_SCORE
    )

    has_supported_semantic_match = (
        semantic_score is not None
        and semantic_score
        >= MIN_MODERATE_SEMANTIC_SCORE
        and rerank_score is not None
        and rerank_score
        >= MIN_SUPPORTING_RERANK_SCORE
    )

    return (
        has_keyword_match
        or has_strong_semantic_match
        or has_supported_semantic_match
    )


def filter_relevant_candidates(
    candidates: list[dict[str, Any]],
    top_k: int,
) -> list[dict[str, Any]]:
    """Remove weak retrieval results before answer generation."""

    if top_k < 1:
        raise ValueError(
            "top_k must be at least 1."
        )

    relevant_candidates = [
        candidate
        for candidate in candidates
        if is_candidate_relevant(candidate)
    ]

    relevant_candidates.sort(
        key=lambda candidate: (
            safe_float(
                candidate.get("rerank_score")
            )
            or float("-inf")
        ),
        reverse=True,
    )

    return relevant_candidates[:top_k]