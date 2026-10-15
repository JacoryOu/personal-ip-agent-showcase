# -*- coding: utf-8 -*-
"""Service for Ingesting Audience Feedback and Evolving Cognitive Thinking DNA Assets."""

from datetime import datetime, timezone
import logging
import re
from typing import Any, Dict, List, Optional
import uuid

from sqlmodel import Session, select

from app.core.model_gateway import ModelGateway, ModelRole, extract_json_from_text
from app.models.dna_record import DNARecord
from app.models.draft import Draft
from app.models.feedback import DraftFeedback
from app.models.material import Material
from app.models.user import User
from app.schemas.draft_schemas import (
    BoostedTraitInfo,
    FeedbackExtractResponse,
    FeedbackItemResponse,
)
from app.services.cognitive_service import CognitiveService, _parse_user_id

logger = logging.getLogger(__name__)


def _parse_draft_uuid(draft_id: str | uuid.UUID) -> uuid.UUID:
    """Parses draft_id into UUID, gracefully generating deterministic UUID5 if non-hex string provided."""
    if isinstance(draft_id, uuid.UUID):
        return draft_id
    try:
        return uuid.UUID(str(draft_id))
    except ValueError:
        return uuid.uuid5(uuid.NAMESPACE_DNS, str(draft_id))


class FeedbackService:
    @classmethod
    def record_feedback(
        cls,
        draft_id: str | uuid.UUID,
        comments_text: str,
        metrics: Optional[Dict[str, Any]] = None,
        user_id: Optional[str | uuid.UUID] = None,
        session: Optional[Session] = None,
    ) -> DraftFeedback:
        """Records reader feedback and comments for a draft."""
        d_id = _parse_draft_uuid(draft_id)
        draft = session.get(Draft, d_id)
        if not draft:
            raise ValueError(f"Draft with ID '{draft_id}' not found.")

        target_uid = _parse_user_id(user_id) or draft.user_id
        feedback = DraftFeedback(
            id=uuid.uuid4(),
            draft_id=d_id,
            user_id=target_uid,
            comments_text=comments_text.strip(),
            metrics=metrics or {},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(feedback)
        session.commit()
        session.refresh(feedback)
        return feedback

    @classmethod
    async def extract_feedback_insights(
        cls,
        draft_id: str | uuid.UUID,
        comments_text: Optional[str] = None,
        feedback_id: Optional[str | uuid.UUID] = None,
        metrics: Optional[Dict[str, Any]] = None,
        user_id: Optional[str | uuid.UUID] = None,
        session: Session = None,
        model_gateway: Optional[ModelGateway] = None,
    ) -> FeedbackExtractResponse:
        """
        Analyzes audience feedback via LLM to:
        1. Extract new inspiration fragments / contrarian counter-arguments -> auto-saved into MaterialVault as personal notes.
        2. Extract resonant ideas -> calculates confidence score boost for associated ThinkingDNA elements.
        3. Extract controversy points and summarize evolution.
        """
        d_id = _parse_draft_uuid(draft_id)
        draft = session.get(Draft, d_id)
        if not draft:
            raise ValueError(f"Draft with ID '{draft_id}' not found.")

        target_uid = _parse_user_id(user_id) or draft.user_id

        # 1. Resolve feedback record
        feedback: Optional[DraftFeedback] = None
        if feedback_id:
            if isinstance(feedback_id, uuid.UUID):
                fb_uuid = feedback_id
            else:
                try:
                    fb_uuid = uuid.UUID(str(feedback_id))
                except ValueError:
                    fb_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, str(feedback_id))
            feedback = session.get(DraftFeedback, fb_uuid)

        raw_comments = (comments_text or "").strip()
        if not raw_comments and feedback:
            raw_comments = feedback.comments_text

        if not raw_comments:
            raise ValueError("No comments text provided for feedback analysis.")

        if not feedback:
            feedback = DraftFeedback(
                id=uuid.uuid4(),
                draft_id=d_id,
                user_id=target_uid,
                comments_text=raw_comments,
                metrics=metrics or {},
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(feedback)
            session.commit()
            session.refresh(feedback)

        # 2. Extract insights via LLM or fallback analyzer
        draft_content_snippet = (draft.user_final_draft or draft.original_ai_draft or "")[:1200]
        insights = await cls._analyze_feedback_with_llm(
            topic=draft.topic,
            draft_snippet=draft_content_snippet,
            comments_text=raw_comments,
            metrics=metrics or feedback.metrics or {},
            model_gateway=model_gateway,
        )

        resonant_ideas = insights.get("resonant_ideas") or []
        controversy_points = insights.get("controversy_points") or []
        raw_inspiration_notes = insights.get("inspiration_notes") or []
        evolution_summary = insights.get("evolution_summary") or "读者反馈已成功融入认知资产库。"

        # 3. Auto-save inspiration notes into MaterialVault (personal notes)
        created_materials: List[Dict[str, Any]] = []
        saved_mat_ids: List[str] = []

        for item in raw_inspiration_notes:
            if isinstance(item, str):
                note_title = item[:40]
                note_content = item
            elif isinstance(item, dict):
                note_title = item.get("title") or item.get("content", "")[:40] or "灵感反思碎片"
                note_content = item.get("content") or item.get("title") or ""
            else:
                continue

            if not note_content.strip():
                continue

            mat = Material(
                id=uuid.uuid4(),
                user_id=target_uid,
                material_type="personal",
                source_platform="audience_feedback",
                source_author="读者群英 / 评论区",
                title=f"【读者共鸣灵感】{note_title}",
                cleaned_content=note_content.strip(),
                raw_content=note_content.strip(),
                tags=["读者反馈", "灵感反思", draft.topic[:16]],
                status="inbox",
                meta_info={
                    "source_draft_id": str(draft.id),
                    "draft_topic": draft.topic,
                    "origin": "audience_feedback_extraction",
                    "feedback_id": str(feedback.id),
                },
            )
            session.add(mat)
            session.commit()
            session.refresh(mat)

            saved_mat_ids.append(str(mat.id))
            created_materials.append({
                "id": str(mat.id),
                "title": mat.title,
                "cleaned_content": mat.cleaned_content,
                "material_type": mat.material_type,
                "tags": mat.tags,
            })

        # 4. Evolve CognitiveProfile and ThinkingDNA confidence scores
        boosted_raw = CognitiveService.evolve_traits_from_feedback(
            session=session,
            user_id=target_uid,
            resonant_ideas=resonant_ideas,
            source_draft_id=str(draft.id),
            delta=0.5,
        )

        boosted_traits = [
            BoostedTraitInfo(
                id=b["id"],
                statement=b["statement"],
                dimension=b["dimension"],
                old_confidence=b["old_confidence"],
                new_confidence=b["new_confidence"],
                boost_amount=b.get("boost_amount", 0.5),
                reason=b.get("reason"),
            )
            for b in boosted_raw
        ]

        # 4.1 Persist / update evolved Thinking DNA into SQLite dna_records table
        profile = CognitiveService.get_or_create_user_profile(session, target_uid)
        evolved_dna = profile.export_thinking_dna(
            summary=f"Evolved from audience feedback on: {draft.topic[:50]}"
        )
        dna_payload = evolved_dna.model_dump()
        dna_payload["boosted_traits"] = [
            b.model_dump() if hasattr(b, "model_dump") else dict(b) for b in boosted_traits
        ]
        dna_payload["evolution_metrics"] = metrics or feedback.metrics or {}
        dna_payload["evolution_summary"] = evolution_summary

        existing_dna_rec = session.exec(
            select(DNARecord).where(DNARecord.draft_id == d_id)
        ).first()
        if existing_dna_rec:
            existing_dna_rec.dna_data = dna_payload
            session.add(existing_dna_rec)
        else:
            evolution_record = DNARecord(
                id=uuid.uuid4(),
                user_id=target_uid,
                draft_id=d_id,
                dna_data=dna_payload,
                created_at=datetime.now(timezone.utc),
            )
            session.add(evolution_record)

        # 5. Persist extracted results into DraftFeedback entity
        feedback.extracted_insights = {
            "resonant_ideas": resonant_ideas,
            "controversy_points": controversy_points,
            "inspiration_notes": [m["title"] for m in created_materials],
            "evolution_summary": evolution_summary,
        }
        feedback.boosted_dna_traits = boosted_raw
        feedback.saved_material_ids = saved_mat_ids
        feedback.updated_at = datetime.now(timezone.utc)
        session.add(feedback)
        session.commit()
        session.refresh(feedback)

        return FeedbackExtractResponse(
            feedback_id=str(feedback.id),
            draft_id=str(draft.id),
            resonant_ideas=resonant_ideas,
            controversy_points=controversy_points,
            inspiration_notes=[m["cleaned_content"] for m in created_materials],
            created_materials=created_materials,
            boosted_traits=boosted_traits,
            evolution_summary=evolution_summary,
        )

    @classmethod
    def list_feedbacks(
        cls,
        draft_id: str | uuid.UUID,
        session: Session,
    ) -> List[FeedbackItemResponse]:
        """Lists all feedback records and extracted insights for the specified draft."""
        d_id = _parse_draft_uuid(draft_id)
        items = session.exec(
            select(DraftFeedback)
            .where(DraftFeedback.draft_id == d_id)
            .order_by(DraftFeedback.created_at.desc())
        ).all()

        return [
            FeedbackItemResponse(
                id=str(f.id),
                draft_id=str(f.draft_id),
                user_id=str(f.user_id),
                comments_text=f.comments_text,
                metrics=f.metrics or {},
                extracted_insights=f.extracted_insights,
                boosted_dna_traits=f.boosted_dna_traits,
                saved_material_ids=f.saved_material_ids,
                created_at=f.created_at.isoformat() if f.created_at else None,
                updated_at=f.updated_at.isoformat() if f.updated_at else None,
            )
            for f in items
        ]

    @classmethod
    async def _analyze_feedback_with_llm(
        cls,
        topic: str,
        draft_snippet: str,
        comments_text: str,
        metrics: Dict[str, Any],
        model_gateway: Optional[ModelGateway] = None,
    ) -> Dict[str, Any]:
        """Calls ModelGateway (or fallback analytical parser) to extract structured insights."""
        gateway = model_gateway or ModelGateway()
        system_prompt = (
            "你是一位资深内容受众反馈分析专家与认知IP演化架构师。\n"
            "你的任务是深入研读读者对于文章的真实评论与反馈，提炼三个维度的结构化洞察：\n"
            "1. resonant_ideas (读者强烈共鸣认同的核心观点/金句，提取为简短有力的论点陈述，1-4条)\n"
            "2. controversy_points (读者有分歧、提出质疑或反驳的争议点，0-3条)\n"
            "3. inspiration_notes (从读者评论激发的全新选题构思、逆向反思切入点或未展开深度话题，每条包含 title 与 content，1-3条)\n"
            "4. evolution_summary (1句总结受众反馈对作者认知IP风格的演化促进作用)\n\n"
            "必须严格输出合法 JSON 格式，字段键包含：resonant_ideas, controversy_points, inspiration_notes, evolution_summary。"
        )

        user_content = (
            f"【文章选题】：{topic}\n"
            f"【正文片段】：\n{draft_snippet}\n\n"
            f"【受众互动数据】：{metrics}\n"
            f"【读者评论与反馈文本】：\n{comments_text}"
        )

        try:
            client = gateway.get_client_for_role(ModelRole.DIFF)
            model_name = gateway.get_model_for_role(ModelRole.DIFF)
            response = await client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.3,
            )
            raw_text = response.choices[0].message.content or ""
            parsed = extract_json_from_text(raw_text)
            if isinstance(parsed, dict) and "resonant_ideas" in parsed:
                return parsed
        except Exception as e:
            logger.warning(f"LLM feedback extraction failed: {e}. Utilizing intelligent rule-based heuristic extraction.")

        # Heuristic fallback parser
        return cls._heuristic_feedback_analysis(topic, comments_text)

    @classmethod
    def _heuristic_feedback_analysis(cls, topic: str, comments_text: str) -> Dict[str, Any]:
        """Rule-based heuristic parsing of reader feedback when LLM is unavailable or offline."""
        lines = [line.strip().lstrip("-•*1234567890.、 ") for line in comments_text.splitlines() if line.strip()]

        resonant = []
        controversy = []
        inspirations = []

        agree_keywords = ["太对了", "很有启发", "醍醐灌顶", "深有同感", "共鸣", "扎心", "非常赞同", "真相", "确实", "好文", "一针见血", "收藏了"]
        disagree_keywords = ["但是", "并不觉得", "过于偏激", "不同意", "现实中不是这样", "反例", "质疑", "片面", "扯淡", "抬杠"]

        for line in lines:
            if any(k in line for k in agree_keywords) and len(line) >= 6:
                clean_stmt = re.sub(r"^(太对了|深有同感|非常赞同|确实|好文|真棒)[,，!！ ]*", "", line).strip()
                if clean_stmt:
                    resonant.append(clean_stmt)
            elif any(k in line for k in disagree_keywords) and len(line) >= 6:
                controversy.append(line)
            elif len(line) >= 15:
                # Capture insightful comments as inspirations
                inspirations.append({
                    "title": f"读者关于「{line[:18]}...」的反思",
                    "content": line,
                })

        if not resonant and lines:
            resonant.append(lines[0])
        if not inspirations and lines:
            inspirations.append({
                "title": f"从受众视角深挖「{topic[:18]}」",
                "content": f"受众反馈提及：{lines[0]}。可在下一期文章中探讨反面视角与边界条件。",
            })

        return {
            "resonant_ideas": resonant[:4],
            "controversy_points": controversy[:3],
            "inspiration_notes": inspirations[:3],
            "evolution_summary": f"基于 {len(lines)} 条受众评论，萃取了高共鸣认知并沉淀了反思灵感。",
        }


__all__ = ["FeedbackService"]
