"""Benchmark deconstruction and dialogue-clash capture.

External benchmark articles are turned into blueprint skeletons and clash
points WITHOUT touching ``CognitiveProfile.traits`` (zero cognitive
pollution); genuine user rebuttals are captured through the Mem0 lifecycle.
"""

from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional
import uuid

from sqlmodel import Session

from app.core.db import engine
from app.core.skill_engine import get_skill_manager
from app.domain.cognitive.models import (
    CognitiveDimension,
    CognitiveProfile,
)
from app.models.dna_record import DNARecord
from app.models.user import User
from app.services.cognitive_service import CognitiveService
from app.services.memory_common import Mem0Operation, _parse_user_id

def deconstruct_benchmark(
    cls,
    content: str,
    user_id: Optional[str | uuid.UUID] = None,
    session: Optional[Session] = None,
    title: Optional[str] = None,
    source_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Deconstructs an external benchmark article into Blueprint Skeletons & Clash Points.

    CRITICAL ARCHITECTURAL GUARANTEE:
    Does NOT alter CognitiveProfile.traits. Prevents cognitive pollution from external authors.
    """
    if not content or not content.strip():
        raise ValueError("Benchmark article content cannot be empty.")

    # 1. Mine structural blueprint and debate clash points
    skill_manager = get_skill_manager()
    miner_result = skill_manager.execute_skill_sync(
        "viewpoint_insight_miner",
        {"content": content, "analysis_type": "benchmark"},
    )

    extracted = miner_result.output if miner_result.success and isinstance(miner_result.output, dict) else {}
    blueprint = extracted.get("blueprint", {})
    clash_points = extracted.get("clash_points", [])

    # Enrich blueprint metadata
    blueprint_record = {
        "id": str(uuid.uuid4()),
        "title": title or blueprint.get("title") or "Deconstructed Benchmark Article",
        "source_url": source_url,
        "hook_style": blueprint.get("hook_style", "开门见山提出问题或悬念"),
        "structural_stages": blueprint.get("structural_stages", [
            "提出核心痛点与悬念",
            "深入剖析根因与逻辑",
            "给出具体解法与策略",
            "升华总结与行动号召",
        ]),
        "emotional_arc": blueprint.get("emotional_arc", "困惑/痛点 ➔ 认知重构 ➔ 笃定/赋能行动"),
        "pacing": blueprint.get("pacing", "前 20% 快速切入，中段 60% 展开论证，后 20% 总结升华"),
        "word_count": len(content),
        "clash_points_count": len(clash_points),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    def _persist_blueprint(sess: Session) -> Dict[str, Any]:
        parsed_uid = _parse_user_id(user_id)
        if parsed_uid:
            user = sess.get(User, parsed_uid)
            if not user:
                user = User(id=parsed_uid, username=f"user_{str(parsed_uid)[:8]}")
                sess.add(user)
                sess.commit()
                sess.refresh(user)
        else:
            user = CognitiveService.get_or_create_default_user(sess)

        # Store in User.profile_data["benchmark_blueprints"]
        current_data = dict(user.profile_data or {})
        blueprints = current_data.get("benchmark_blueprints", [])
        blueprints.insert(0, blueprint_record)
        current_data["benchmark_blueprints"] = blueprints[:50]  # retain latest 50
        user.profile_data = current_data
        sess.add(user)
        sess.commit()
        sess.refresh(user)

        return {
            "success": True,
            "blueprint": blueprint_record,
            "clash_points": clash_points,
            "message": "Benchmark article deconstructed into blueprint and clash points without cognitive profile alteration.",
        }

    if session:
        return _persist_blueprint(session)
    else:
        with Session(engine) as sess:
            return _persist_blueprint(sess)

def record_dialogue_clash(
    cls,
    messages: List[Dict[str, str]],
    user_id: Optional[str | uuid.UUID] = None,
    debate_topic: Optional[str] = None,
    session: Optional[Session] = None,
) -> Dict[str, Any]:
    """Extracts the user's authentic opinions and rebuttals from a debate/clash session,
    incorporating them as pure Thinking DNA into the CognitiveProfile.
    """
    if not messages:
        raise ValueError("Messages cannot be empty.")

    # Extract all user statements
    user_texts = [
        m.get("content", "").strip()
        for m in messages
        if m.get("role") in ("user", "self", "me") and m.get("content", "").strip()
    ]
    if not user_texts:
        # Fallback: inspect any non-empty content
        user_texts = [m.get("content", "").strip() for m in messages if m.get("content", "").strip()]

    combined_user_text = chr(10).join(user_texts)
    if not combined_user_text:
        raise ValueError("No user statements found to extract.")

    # Extract user stances
    skill_manager = get_skill_manager()
    miner_result = skill_manager.execute_skill_sync(
        "viewpoint_insight_miner",
        {"content": combined_user_text, "analysis_type": "dialogue"},
    )
    extracted = miner_result.output if miner_result.success and isinstance(miner_result.output, dict) else {}
    user_stances = extracted.get("user_stances", [])
    if not user_stances:
        # Heuristic sentence split
        user_stances = [s.strip() for s in re.split(r'[。！？!?\n]+', combined_user_text) if len(s.strip()) > 8][:4]

    def _execute_clash(sess: Session) -> Dict[str, Any]:
        profile = CognitiveService.get_or_create_user_profile(sess, user_id)
        user_uuid = uuid.UUID(str(profile.user_id))
        user = sess.get(User, user_uuid) or CognitiveService.get_or_create_default_user(sess)

        actions = {Mem0Operation.ADD: [], Mem0Operation.UPDATE: [], Mem0Operation.NOOP: []}

        for stance in user_stances:
            formatted_stance = f"针对【{debate_topic}】的反驳/主张：{stance}" if debate_topic else stance
            op, trait = cls.apply_mem0_lifecycle(
                profile,
                CognitiveDimension.VIEWPOINT_STANCE,
                formatted_stance,
            )
            actions[op].append({
                "dimension": "viewpoint_stance",
                "statement": trait.statement,
                "id": trait.id,
            })

        CognitiveService.save_profile(sess, user, profile)

        # Record DNA audit
        dna_record = DNARecord(
            user_id=user.id,
            dna_data={
                "viewpoint_stances": user_stances,
                "debate_topic": debate_topic,
                "summary": f"Dialogue clash DNA extraction: {len(user_stances)} stances recorded.",
                "actions_summary": {k: len(v) for k, v in actions.items()},
            },
        )
        sess.add(dna_record)
        sess.commit()
        sess.refresh(dna_record)

        return {
            "success": True,
            "dna_record_id": str(dna_record.id),
            "recorded_stances": user_stances,
            "mem0_actions": actions,
            "total_traits_count": len(profile.traits),
        }

    if session:
        return _execute_clash(session)
    else:
        with Session(engine) as sess:
            return _execute_clash(sess)
