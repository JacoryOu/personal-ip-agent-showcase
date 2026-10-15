"""Viewpoint-conflict detection between candidate text and Thinking DNA."""

import re
from typing import Any, Dict, List, Optional
import uuid

from sqlmodel import Session

from app.core.db import engine
from app.domain.cognitive.models import TraitStatus
from app.services.cognitive_service import CognitiveService

def detect_viewpoint_conflicts(
    cls,
    session: Optional[Session] = None,
    user_id: Optional[str | uuid.UUID] = None,
    statement: Optional[str] = None,
    statements: Optional[List[str]] = None,
    draft_content: Optional[str] = None,
) -> Dict[str, Any]:
    """Detects viewpoint conflicts between candidate opinions/draft content
    and user's existing Thinking DNA traits (or internal conflicts among traits).
    Robustly analyzes modality polarity, clause boundaries, and antonym pairings.
    """
    def _execute(sess: Session) -> Dict[str, Any]:
        profile = CognitiveService.get_or_create_user_profile(sess, user_id)
        active_traits = [
            t for t in profile.traits
            if t.status in (TraitStatus.ACTIVE, TraitStatus.PINNED)
        ]

        candidates: List[str] = []
        if statement and statement.strip():
            candidates.append(statement.strip())
        if statements:
            for s in statements:
                if s and isinstance(s, str) and s.strip():
                    candidates.append(s.strip())
        if draft_content and draft_content.strip():
            raw_sentences = re.split(r"[。！？!?\n]+", draft_content.strip())
            for s in raw_sentences:
                s_clean = s.strip()
                if 6 <= len(s_clean) <= 120 and any(k in s_clean for k in [
                    "必须", "应当", "应该", "支持", "赞成",
                    "反对", "拒绝", "不能", "不可", "不要",
                    "本质", "主张", "核心", "彻底", "永远",
                    "唯一", "绝非", "提倡", "坚持", "放弃"
                ]):
                    candidates.append(s_clean)

        antonym_pairs = [
            ("去中心化", "中心化"),
            ("长期主义", "短期套利"),
            ("长期", "短期"),
            ("自研", "外包"),
            ("收费", "免费"),
            ("开源", "闭源"),
            ("小而美", "规模化"),
            ("保守", "激进"),
            ("独立思考", "盲从"),
            ("all in", "观望"),
            ("单干", "团队"),
        ]

        composite_terms = {
            "中心化": ["去中心化"],
            "短期": ["短期套利"],
            "长期": ["长期主义"],
        }

        def has_term(term: str, text: str) -> bool:
            if term not in text:
                return False
            longer_compounds = composite_terms.get(term, [])
            if not longer_compounds:
                return True
            cleaned = text
            for lc in longer_compounds:
                if lc in cleaned:
                    cleaned = cleaned.replace(lc, " ")
            return term in cleaned

        def extract_clause_for_concept(text: str, concept: str) -> str:
            clauses = re.split(r"[,，;；。!?！？\n]+", text)
            for c in clauses:
                if concept in c:
                    return c
            return text

        def extract_stance_on_concept(text: str, concept: str) -> int:
            clause = extract_clause_for_concept(text, concept)

            # Double negation check
            if any(dn in clause for dn in ["不得不", "不能不", "未尝不可"]):
                return 1

            neg_modals = [
                "反对", "拒绝", "否定", "批判", "淘汰", "禁止", "放弃",
                "不能", "不可", "不要", "不应", "不该", "无需", "不必",
                "绝非", "并非", "毫无价值", "伪概念", "抵制", "不建议"
            ]
            pos_modals = [
                "必须", "应当", "应该", "支持", "赞成", "赞同", "提倡",
                "坚定", "坚持", "拥抱", "推崇", "倡导", "利好", "专注", "聚焦", "主张"
            ]

            has_neg = any(m in clause for m in neg_modals)
            has_pos = any(m in clause for m in pos_modals)

            if has_neg and not has_pos:
                return -1
            if has_pos and not has_neg:
                return 1
            if has_neg and has_pos:
                if any(w in clause for w in ["反对", "拒绝", "禁止", "抵制", "淘汰", "放弃"]):
                    return -1
                if any(w in clause for w in ["不能", "不可", "不要", "不应", "不该", "并非", "绝非"]):
                    return -1
                return 1
            return 1

        conflicts: List[Dict[str, Any]] = []

        def check_pair(trait_stmt: str, cand_stmt: str, trait_obj: CognitiveTrait):
            if trait_stmt.strip() == cand_stmt.strip():
                return

            # 1. Antonym analysis
            for w1, w2 in antonym_pairs:
                h1_t = has_term(w1, trait_stmt)
                h2_t = has_term(w2, trait_stmt)
                h1_c = has_term(w1, cand_stmt)
                h2_c = has_term(w2, cand_stmt)

                # Cross antonym match: trait has w1, cand has w2
                if h1_t and h2_c:
                    s_t = extract_stance_on_concept(trait_stmt, w1)
                    s_c = extract_stance_on_concept(cand_stmt, w2)
                    # Both favor opposing concepts or both oppose opposing concepts -> CONFLICT
                    if s_t * s_c > 0:
                        conflicts.append({
                            "existing_trait": {
                                "id": trait_obj.id,
                                "dimension": trait_obj.dimension.value,
                                "statement": trait_obj.statement,
                                "confidence_score": trait_obj.confidence_score,
                                "status": trait_obj.status.value,
                            },
                            "conflicting_statement": cand_stmt,
                            "conflict_type": "antonym_opposition",
                            "topic_overlap": [w1, w2],
                            "reason": f"现有DNA特征主张「{w1}」，但候选观点主张相反概念「{w2}」，两者立场截然对立。",
                            "suggested_action": "suppress_trait" if trait_obj.confidence_score < 2.0 else "keep_nuanced",
                            "severity": "high",
                        })
                        return
                elif h2_t and h1_c:
                    s_t = extract_stance_on_concept(trait_stmt, w2)
                    s_c = extract_stance_on_concept(cand_stmt, w1)
                    if s_t * s_c > 0:
                        conflicts.append({
                            "existing_trait": {
                                "id": trait_obj.id,
                                "dimension": trait_obj.dimension.value,
                                "statement": trait_obj.statement,
                                "confidence_score": trait_obj.confidence_score,
                                "status": trait_obj.status.value,
                            },
                            "conflicting_statement": cand_stmt,
                            "conflict_type": "antonym_opposition",
                            "topic_overlap": [w2, w1],
                            "reason": f"现有DNA特征主张「{w2}」，但候选观点主张相反概念「{w1}」，两者立场截然对立。",
                            "suggested_action": "suppress_trait" if trait_obj.confidence_score < 2.0 else "keep_nuanced",
                            "severity": "high",
                        })
                        return

                # Same concept across pair: opposite stances on same concept -> CONFLICT
                elif h1_t and h1_c:
                    s_t = extract_stance_on_concept(trait_stmt, w1)
                    s_c = extract_stance_on_concept(cand_stmt, w1)
                    if s_t * s_c < 0:
                        conflicts.append({
                            "existing_trait": {
                                "id": trait_obj.id,
                                "dimension": trait_obj.dimension.value,
                                "statement": trait_obj.statement,
                                "confidence_score": trait_obj.confidence_score,
                                "status": trait_obj.status.value,
                            },
                            "conflicting_statement": cand_stmt,
                            "conflict_type": "direct_contradiction",
                            "topic_overlap": [w1],
                            "reason": f"现有DNA主张「{trait_stmt}」，与候选观点「{cand_stmt}」在核心概念「{w1}」上态度正负对立。",
                            "suggested_action": "update_trait" if trait_obj.confidence_score < 1.5 else "keep_nuanced",
                            "severity": "high",
                        })
                        return
                elif h2_t and h2_c:
                    s_t = extract_stance_on_concept(trait_stmt, w2)
                    s_c = extract_stance_on_concept(cand_stmt, w2)
                    if s_t * s_c < 0:
                        conflicts.append({
                            "existing_trait": {
                                "id": trait_obj.id,
                                "dimension": trait_obj.dimension.value,
                                "statement": trait_obj.statement,
                                "confidence_score": trait_obj.confidence_score,
                                "status": trait_obj.status.value,
                            },
                            "conflicting_statement": cand_stmt,
                            "conflict_type": "direct_contradiction",
                            "topic_overlap": [w2],
                            "reason": f"现有DNA主张「{trait_stmt}」，与候选观点「{cand_stmt}」在核心概念「{w2}」上态度正负对立。",
                            "suggested_action": "update_trait" if trait_obj.confidence_score < 1.5 else "keep_nuanced",
                            "severity": "high",
                        })
                        return

            # 2. General topic overlap contradiction check
            terms_a = set(re.findall(r"[a-zA-Z0-9_]{2,}", trait_stmt.lower()))
            terms_a.update(re.findall(r"[一-龥]{2,}", trait_stmt))
            terms_b = set(re.findall(r"[a-zA-Z0-9_]{2,}", cand_stmt.lower()))
            terms_b.update(re.findall(r"[一-龥]{2,}", cand_stmt))

            stopwords = {
                "我们", "他们", "这个", "那个", "如果", "但是", "因为", "所以", "为了", "一个",
                "必须", "应当", "应该", "可以", "需要", "完全", "全面", "架构", "技术", "服务", "进行"
            }
            overlap = {w for w in terms_a.intersection(terms_b) if w not in stopwords}
            similarity = cls._compute_similarity(trait_stmt, cand_stmt)

            if overlap or similarity >= 0.4:
                for term in sorted(overlap, key=len, reverse=True):
                    s_t = extract_stance_on_concept(trait_stmt, term)
                    s_c = extract_stance_on_concept(cand_stmt, term)
                    if s_t * s_c < 0:
                        conflicts.append({
                            "existing_trait": {
                                "id": trait_obj.id,
                                "dimension": trait_obj.dimension.value,
                                "statement": trait_obj.statement,
                                "confidence_score": trait_obj.confidence_score,
                                "status": trait_obj.status.value,
                            },
                            "conflicting_statement": cand_stmt,
                            "conflict_type": "direct_contradiction",
                            "topic_overlap": list(overlap)[:5],
                            "reason": f"现有DNA主张「{trait_stmt}」，与候选观点「{cand_stmt}」在核心概念「{term}」上态度正负对立。",
                            "suggested_action": "update_trait" if trait_obj.confidence_score < 1.5 else "keep_nuanced",
                            "severity": "high" if len(overlap) >= 2 else "medium",
                        })
                        return

        if candidates:
            for cand in candidates:
                for trait in active_traits:
                    check_pair(trait.statement, cand, trait)
        else:
            for i in range(len(active_traits)):
                for j in range(i + 1, len(active_traits)):
                    check_pair(active_traits[i].statement, active_traits[j].statement, active_traits[i])

        return {
            "has_conflicts": len(conflicts) > 0,
            "conflicts_count": len(conflicts),
            "conflicts": conflicts,
            "analyzed_statements_count": len(candidates) if candidates else len(active_traits),
            "total_active_traits_checked": len(active_traits),
        }

    if session:
        return _execute(session)
    else:
        with Session(engine) as sess:
            return _execute(sess)
