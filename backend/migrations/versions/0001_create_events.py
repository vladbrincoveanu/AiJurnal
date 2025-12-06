"""create events table

Revision ID: 0001_create_events
Revises:
Create Date: 2024-01-01 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision = "0001_create_events"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "events",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("source_app", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("url_or_path", sa.String(length=1024), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("metadata", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("embedding", Vector(1536), nullable=True),
    )
    op.create_index(
        "ix_events_url_or_path",
        "events",
        ["url_or_path"],
        unique=False,
    )
    op.create_index(
        "ix_events_embedding_hnsw",
        "events",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index(
        "ix_events_metadata_gin",
        "events",
        ["metadata"],
        unique=False,
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_events_metadata_gin", table_name="events")
    op.drop_index("ix_events_embedding_hnsw", table_name="events")
    op.drop_index("ix_events_url_or_path", table_name="events")
    op.drop_table("events")
