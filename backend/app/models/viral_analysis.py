"""SQLModel persistence for viral / benchmark article semantic analyses.

Kept in a NEW model file (rather than appended to existing model definitions) so
concurrent work on other model files does not conflict. Registration happens in
``app/models/__init__.py`` so ``init_db()`` creates the table automatically.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, Field, SQLModel


class ViralSemanticAnalysisRecord(SQLModel, table=True):
    """One persisted semantic breakdown of one viral / benchmark article."""

    __tablename__ = "viral_semantic_analyses"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    # Optional provenance. Kept nullable so an analysis can be produced from a
    # pasted article without inventing a user or material row.
    user_id: Optional[uuid.UUID] = Field(default=None, foreign_key="users.id", index=True)
    material_id: Optional[uuid.UUID] = Field(default=None, foreign_key="materials.id", index=True)

    source_title: str = Field(default="")
    # sha256 of the normalized source text; lets callers de-duplicate analyses.
    source_content_hash: str = Field(index=True, default="")
    source_platform: Optional[str] = Field(default=None, index=True)
    source_url: Optional[str] = Field(default=None)

    # 'completed' today. Reserved for future 'failed' / 'partial' states.
    status: str = Field(default="completed", index=True)
    # 'llm' (model produced the semantics) or 'fallback' (deterministic-only).
    extraction_mode: str = Field(default="llm", index=True)

    # Serialized ViralSemanticAnalysis.
    analysis_data: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON().with_variant(JSONB, "postgresql")),
    )
    warnings: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSON().with_variant(JSONB, "postgresql")),
    )

    model_name: Optional[str] = Field(default=None)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
