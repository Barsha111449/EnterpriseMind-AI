from functools import lru_cache
from typing import Any

from sentence_transformers import CrossEncoder


RERANKER_MODEL_NAME = (
    "cross-encoder/ms-marco-MiniLM-L6-v2"
)


@lru_cache(maxsize=1)
def get_reranker_model() -> CrossEncoder:
    """Load and reuse the cross-encoder reranking model."""

    return CrossEncoder(
        RERANKER_MODEL_NAME
    )


def rerank_candidates(
    query: str,
    candidates: list[dict[str, Any]],
    top_k: int,
) -> list[dict[str, Any]]:
    """Rerank retrieved chunks against the user's query."""

    query_text = query.strip()

    if not query_text:
        raise ValueError(
            "The reranking query cannot be empty."
        )

    if top_k < 1:
        raise ValueError(
            "top_k must be at least 1."
        )

    if not candidates:
        return []

    sentence_pairs = [
        (
            query_text,
            str(candidate["content"]),
        )
        for candidate in candidates
    ]

    model = get_reranker_model()

    scores = model.predict(
        sentence_pairs,
        show_progress_bar=False,
    )

    reranked_candidates: list[
        dict[str, Any]
    ] = []

    for candidate, score in zip(
        candidates,
        scores,
        strict=True,
    ):
        reranked_candidate = candidate.copy()

        reranked_candidate[
            "rerank_score"
        ] = float(score)

        reranked_candidates.append(
            reranked_candidate
        )

    reranked_candidates.sort(
        key=lambda candidate: candidate[
            "rerank_score"
        ],
        reverse=True,
    )

    return reranked_candidates[:top_k]