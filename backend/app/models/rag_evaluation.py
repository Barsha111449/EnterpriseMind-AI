import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.base import Base


class RagEvaluation(Base):
    """Store quality measurements for one RAG question and answer."""

    __tablename__ = "rag_evaluations"

    __table_args__ = (
        Index(
            "ix_rag_evaluations_organization_created_at",
            "organization_id",
            "created_at",
        ),
        Index(
            "ix_rag_evaluations_organization_grounded",
            "organization_id",
            "grounded",
        ),
        CheckConstraint(
            (
                "retrieval_relevance >= 0 "
                "AND retrieval_relevance <= 1"
            ),
            name="ck_rag_evaluations_retrieval_relevance",
        ),
        CheckConstraint(
            (
                "citation_coverage >= 0 "
                "AND citation_coverage <= 1"
            ),
            name="ck_rag_evaluations_citation_coverage",
        ),
        CheckConstraint(
            (
                "groundedness_consistency >= 0 "
                "AND groundedness_consistency <= 1"
            ),
            name="ck_rag_evaluations_groundedness_consistency",
        ),
        CheckConstraint(
            "citation_count >= 0",
            name="ck_rag_evaluations_citation_count",
        ),
        CheckConstraint(
            "response_latency_ms >= 0",
            name="ck_rag_evaluations_response_latency",
        ),
        CheckConstraint(
            "retrieved_candidate_count >= 0",
            name="ck_rag_evaluations_retrieved_count",
        ),
        CheckConstraint(
            "relevant_candidate_count >= 0",
            name="ck_rag_evaluations_relevant_count",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "organizations.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    question: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    answer: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    grounded: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )

    citation_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    retrieval_relevance: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    citation_coverage: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    groundedness_consistency: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    response_latency_ms: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    retrieved_candidate_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    relevant_candidate_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )