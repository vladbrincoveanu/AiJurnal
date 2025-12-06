from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class SourceType(str, enum.Enum):
    chat = "chat"
    web = "web"
    file = "file"
    note = "note"


class EventBase(SQLModel):
    created_at: datetime = Field(default_factory=datetime.utcnow)
    source_type: SourceType
    source_app: str
    title: Optional[str] = None
    url_or_path: Optional[str] = Field(default=None, index=True)
    content: str
    summary: Optional[str] = None
    metadata_: Optional[dict[str, Any]] = Field(
        default=None,
        sa_column=Column("metadata", JSONB, nullable=True),
        alias="metadata",
    )
    embedding: Optional[list[float]] = Field(
        default=None,
        sa_column=Column(Vector(1536), nullable=True),
    )

    class Config:
        allow_population_by_field_name = True


class Event(EventBase, table=True):
    __tablename__ = "events"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)


class EventCreate(EventBase):
    pass


class EventRead(EventBase):
    id: UUID


# Indexes for vector search and metadata queries
Index(
    "ix_events_embedding_hnsw",
    Event.__table__.c.embedding,
    postgresql_using="hnsw",
    postgresql_with={"m": 16, "ef_construction": 64},
    postgresql_ops={"embedding": "vector_cosine_ops"},
)
Index(
    "ix_events_metadata_gin",
    Event.__table__.c.metadata,
    postgresql_using="gin",
)
