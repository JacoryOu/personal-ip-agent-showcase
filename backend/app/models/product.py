"""ProductVault model – creator product knowledge base."""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, Field, SQLModel


class ProductVault(SQLModel, table=True):
    __tablename__ = "product_vault"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(index=True)

    product_name: str = Field(default="")
    category: str = Field(default="")
    core_ingredients: str = Field(default="")
    suitable_conditions: str = Field(default="")
    taboos: str = Field(default="")
    personal_usage_experience: str = Field(default="")
    conversion_hooks: str = Field(default="")

    cover_image: Optional[str] = Field(default="")
    gallery_images: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSON().with_variant(JSONB, "postgresql")),
    )
    service_rights_images: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSON().with_variant(JSONB, "postgresql")),
    )

    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# --------------------------------------------------------------------------- #
# Pre-seed helpers
# --------------------------------------------------------------------------- #

DEFAULT_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

PRODUCT_PRESETS = [
    ProductVault(
        id=uuid.UUID("22000000-0000-0000-0000-000000000001"),
        user_id=DEFAULT_USER_ID,
        product_name="新会陈皮五年寿眉老白茶",
        category="养生茶饮",
        core_ingredients="广东新会陈皮（五年陈）、福鼎寿眉老白茶",
        suitable_conditions="脾胃湿寒、消化不良、痰湿体质、饮食积滞",
        taboos="阴虚火旺、孕妇慎用",
        personal_usage_experience="长期饮用后脾胃功能明显改善，腹胀感减少，精力也更稳定",
        conversion_hooks="陈皮越陈越香，解腻化湿效果越好；老白茶温和不刺激，是脾胃虚弱人群的理想日常茶",
        cover_image="https://images.unsplash.com/photo-1576092768241-dec231879fc3?auto=format&fit=crop&w=1200&q=80",
        gallery_images=[
            "https://images.unsplash.com/photo-1544787219-7f47ccb76574?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1597481499750-3e6b22637e12?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1514432324607-a09d9b4aefdd?auto=format&fit=crop&w=800&q=80",
        ],
        service_rights_images=[
            "https://images.unsplash.com/photo-1586281380349-632531db7ed4?auto=format&fit=crop&w=800&q=80",
        ],
        is_active=True,
    ),
    ProductVault(
        id=uuid.UUID("22000000-0000-0000-0000-000000000002"),
        user_id=DEFAULT_USER_ID,
        product_name="茯苓八珍糕",
        category="食疗糕点",
        core_ingredients="茯苓、山药、芡实、莲子、薏仁、白扁豆、党参、白术",
        suitable_conditions="脾虚湿困、食欲不振、大便溏泄、气虚乏力",
        taboos="实热体质、便秘者不宜多食",
        personal_usage_experience="作为日常零食代替甜食，坚持食用两个月后气色和消化明显改善",
        conversion_hooks="八种药食同源食材的经典组合，慈禧太后御用配方，温和调理不伤身",
        cover_image="https://images.unsplash.com/photo-1509440159596-0249088772ff?auto=format&fit=crop&w=1200&q=80",
        gallery_images=[
            "https://images.unsplash.com/photo-1587314168485-3236d6710814?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1555507036-ab1f4038808a?auto=format&fit=crop&w=800&q=80",
        ],
        service_rights_images=[
            "https://images.unsplash.com/photo-1450133064473-71024230f91b?auto=format&fit=crop&w=800&q=80",
        ],
        is_active=True,
    ),
]
