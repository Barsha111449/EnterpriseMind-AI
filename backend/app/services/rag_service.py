from dataclasses import dataclass
from typing import Any

from backend.app.schemas.questions import AnswerCitation


MAX_EXCERPT_LENGTH = 500
MAX_CONTEXT_CHUNK_LENGTH = 3000


@dataclass(frozen=True)
class PreparedEvidence:
    """Context and citations prepared for question answering."""

    context: str
    citations: list[AnswerCitation]


def normalize_text(text: str) -> str:
    """Remove unnecessary spaces and blank lines."""

    return " ".join(text.split())


def truncate_text(
    text: str,
    maximum_length: int,
) -> str:
    """Shorten text while keeping it readable."""

    normalized_text = normalize_text(text)

    if len(normalized_text) <= maximum_length:
        return normalized_text

    return (
        normalized_text[: maximum_length - 3].rstrip()
        + "..."
    )


def prepare_evidence(
    candidates: list[dict[str, Any]],
    top_k: int,
) -> PreparedEvidence:
    """Prepare reranked chunks as LLM context and citations."""

    if top_k < 1:
        raise ValueError(
            "top_k must be at least 1."
        )

    if not candidates:
        return PreparedEvidence(
            context="",
            citations=[],
        )

    selected_candidates = candidates[:top_k]

    citations: list[AnswerCitation] = []
    context_sections: list[str] = []

    for citation_number, candidate in enumerate(
        selected_candidates,
        start=1,
    ):
        content = str(
            candidate.get("content", "")
        ).strip()

        if not content:
            continue

        required_fields = {
            "chunk_id",
            "document_id",
            "original_filename",
            "chunk_index",
        }

        missing_fields = [
            field_name
            for field_name in required_fields
            if field_name not in candidate
        ]

        if missing_fields:
            raise ValueError(
                "Candidate is missing required fields: "
                + ", ".join(missing_fields)
            )

        page_number = candidate.get(
            "page_number"
        )

        rerank_score = float(
            candidate.get(
                "rerank_score",
                0.0,
            )
        )

        excerpt = truncate_text(
            content,
            MAX_EXCERPT_LENGTH,
        )

        citation = AnswerCitation(
            citation_number=citation_number,
            chunk_id=candidate["chunk_id"],
            document_id=candidate["document_id"],
            original_filename=str(
                candidate["original_filename"]
            ),
            page_number=page_number,
            chunk_index=int(
                candidate["chunk_index"]
            ),
            excerpt=excerpt,
            rerank_score=round(
                rerank_score,
                6,
            ),
        )

        citations.append(citation)

        page_label = (
            str(page_number)
            if page_number is not None
            else "Not available"
        )

        context_content = truncate_text(
            content,
            MAX_CONTEXT_CHUNK_LENGTH,
        )

        context_sections.append(
            "\n".join(
                [
                    f"[SOURCE {citation_number}]",
                    (
                        "Filename: "
                        f"{candidate['original_filename']}"
                    ),
                    f"Page: {page_label}",
                    (
                        "Chunk index: "
                        f"{candidate['chunk_index']}"
                    ),
                    f"Text: {context_content}",
                ]
            )
        )

    return PreparedEvidence(
        context="\n\n".join(
            context_sections
        ),
        citations=citations,
    )


def build_grounding_instruction() -> str:
    """Return instructions that prevent unsupported answers."""

    return (
        "Answer only from the supplied sources. "
        "Do not use outside knowledge. "
        "Cite supporting sources using labels such as [1] "
        "and [2]. If the sources do not contain enough "
        "information, clearly say that the available "
        "documents do not provide enough evidence."
    )