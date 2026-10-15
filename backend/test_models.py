"""Smoke test for SQLModel models using SQLite (with JSONB→JSON fallback)."""
from sqlalchemy import JSON, create_engine, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Session, SQLModel

from app.models import DNARecord, Draft, User

# Register a listener that swaps JSONB for JSON so SQLite can handle it.
@event.listens_for(SQLModel.metadata, "column_reflect")
def _reflect_col(inspector, table, column_info):
    if isinstance(column_info["type"], JSONB):
        column_info["type"] = JSON()

# Monkey-patch the JSONB columns to JSON for this in-memory test.
for table in SQLModel.metadata.tables.values():
    for col in table.columns:
        if isinstance(col.type, JSONB):
            col.type = JSON()

engine = create_engine("sqlite:///:memory:", echo=True)
SQLModel.metadata.create_all(engine)

with Session(engine) as session:
    user = User(username="test_user")
    session.add(user)
    session.commit()
    session.refresh(user)
    print("User created:", user.id, user.username)

    draft = Draft(
        user_id=user.id,
        topic="Test Topic",
        original_ai_draft="This is an AI draft.",
    )
    session.add(draft)
    session.commit()
    session.refresh(draft)
    print("Draft created:", draft.id, draft.topic)

    dna = DNARecord(
        user_id=user.id,
        draft_id=draft.id,
    )
    session.add(dna)
    session.commit()
    session.refresh(dna)
    print("DNARecord created:", dna.id)

    # Verify relationships
    session.refresh(user)
    assert len(user.drafts) == 1, f"Expected 1 draft, got {len(user.drafts)}"
    assert user.drafts[0].id == draft.id
    assert len(user.dna_records) == 1, f"Expected 1 dna_record, got {len(user.dna_records)}"
    assert user.dna_records[0].id == dna.id

    # Verify back-references
    assert draft.user.id == user.id, "Draft.user back-reference broken"
    assert dna.user.id == user.id, "DNARecord.user back-reference broken"

    print("All relationship checks PASSED!")
