"""Creation Domain Models."""

from datetime import datetime, timezone
from typing import List, Optional
import uuid

from pydantic import BaseModel, Field

from app.schemas.diff_schemas import ViewpointJudgment
from app.schemas.draft_schemas import DraftOutput
from app.schemas.outline_schemas import Outline, OutlineOutput


class CreationWorkspace(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    topic: str
    additional_context: Optional[str] = None
    outlines: Optional[OutlineOutput] = None
    selected_outline_option: Optional[str] = None
    draft: Optional[DraftOutput] = None
    user_final_draft: Optional[str] = None
    judgments: List[ViewpointJudgment] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def select_outline(self, option: str) -> Outline:
        if not self.outlines:
            raise ValueError("Cannot select outline: outlines have not been generated.")

        opt = option.strip().upper()
        if opt == "A":
            self.selected_outline_option = "A"
            self.updated_at = datetime.now(timezone.utc)
            return self.outlines.outline_a
        elif opt == "B":
            self.selected_outline_option = "B"
            self.updated_at = datetime.now(timezone.utc)
            return self.outlines.outline_b
        else:
            raise ValueError(f"Invalid outline option '{option}'. Must be 'A' or 'B'.")

    def apply_viewpoint_judgment(
        self,
        viewpoint_id: str,
        selected_key: str,
        selected_text: str,
        custom_note: Optional[str] = None,
    ) -> ViewpointJudgment:
        claim = ""
        if self.draft and self.draft.core_viewpoints:
            for vp in self.draft.core_viewpoints:
                if vp.id == viewpoint_id:
                    claim = vp.claim
                    break
        if not claim:
            claim = selected_text

        for existing in self.judgments:
            if existing.viewpoint_id == viewpoint_id:
                existing.selected_key = selected_key
                existing.selected_text = selected_text
                existing.custom_note = custom_note
                if claim:
                    existing.claim = claim
                self.updated_at = datetime.now(timezone.utc)
                return existing

        judgment = ViewpointJudgment(
            viewpoint_id=viewpoint_id,
            claim=claim,
            selected_key=selected_key,
            selected_text=selected_text,
            custom_note=custom_note,
        )
        self.judgments.append(judgment)
        self.updated_at = datetime.now(timezone.utc)
        return judgment

    def has_cognitive_divergence(self) -> bool:
        for j in self.judgments:
            if j.selected_key != "agree" or (j.custom_note and j.custom_note.strip()):
                return True

        if self.draft and self.user_final_draft is not None:
            if self.draft.content.strip() != self.user_final_draft.strip():
                return True

        return False
