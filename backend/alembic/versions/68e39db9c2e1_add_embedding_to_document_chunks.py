"""add embedding to document chunks

Revision ID: 68e39db9c2e1
Revises: 2413099bcc0c
"""

from typing import Sequence, Union

from alembic import op
import pgvector.sqlalchemy
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "68e39db9c2e1"

down_revision: Union[
    str,
    Sequence[str],
    None,
] = "2413099bcc0c"

branch_labels: Union[
    str,
    Sequence[str],
    None,
] = None

depends_on: Union[
    str,
    Sequence[str],
    None,
] = None


def upgrade() -> None:
    """Add the embedding vector column."""

    op.execute(
        "CREATE EXTENSION IF NOT EXISTS vector"
    )

    op.add_column(
        "document_chunks",
        sa.Column(
            "embedding",
            pgvector.sqlalchemy.vector.VECTOR(
                dim=384
            ),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Remove the embedding vector column."""

    op.drop_column(
        "document_chunks",
        "embedding",
    )