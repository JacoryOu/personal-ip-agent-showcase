"""IPPersona model – represents a creator identity preset."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class IPPersona(SQLModel, table=True):
    __tablename__ = "ip_personas"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(index=True)

    name: str = Field(index=True)
    target_audience: str = Field(default="")
    tone_style: str = Field(default="")
    reader_salutation: str = Field(default="")
    origin_story: str = Field(default="")

    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# --------------------------------------------------------------------------- #
# Pre-seed helpers
# --------------------------------------------------------------------------- #

DEFAULT_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

PERSONA_PRESETS = [
    IPPersona(
        id=uuid.UUID("11000000-0000-0000-0000-000000000001"),
        user_id=DEFAULT_USER_ID,
        name="中医食疗调理实践者",
        target_audience="25-45岁对亚健康改善有需求的都市女性",
        tone_style="温暖、专业、接地气，用生活化语言讲述中医智慧",
        reader_salutation="亲爱的调养伙伴",
        origin_story="从自身体虚调理经历出发，深入研究中医食疗，分享真实有效的调养方案",
        is_active=True,
    ),
    IPPersona(
        id=uuid.UUID("11000000-0000-0000-0000-000000000002"),
        user_id=DEFAULT_USER_ID,
        name="职场女性精力管理者",
        target_audience="28-40岁在职场与家庭之间寻求平衡的职业女性",
        tone_style="高效、实用、共情，传递掌控感与自我提升的力量",
        reader_salutation="亲爱的精力满格姐",
        origin_story="在高压职场中探索精力管理方法，通过健康饮食与生活节律重获活力",
        is_active=True,
    ),
    IPPersona(
        id=uuid.UUID("11000000-0000-0000-0000-000000000003"),
        user_id=DEFAULT_USER_ID,
        name="极简内养IP",
        target_audience="追求简约生活方式、注重内在修养的现代人",
        tone_style="克制、深刻、禅意，以少胜多，引发深思",
        reader_salutation="同行者",
        origin_story="摒弃浮躁与冗余，回归内心的宁静与本真的养生之道",
        is_active=True,
    ),
]
