"""
Unit tests for Private Domain IP Hub API (backend/app/api/private_domain.py).
"""

import uuid
from typing import Generator
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from app.main import app
from app.core.db import get_session
from app.models.persona import IPPersona
from app.models.product import ProductVault
from app.api.private_domain import calculate_moments_lines, clean_mechanical_dates

USER_ID = "00000000-0000-0000-0000-000000000001"
USER_UUID = uuid.UUID(USER_ID)


@pytest.fixture(name="session")
def session_fixture() -> Generator[Session, None, None]:
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    import app.models  # noqa: F401
    SQLModel.metadata.create_all(test_engine)

    with Session(test_engine) as sess:
        persona = IPPersona(
            user_id=USER_UUID,
            name="\u4e2d\u533b\u98df\u7597\u8c03\u7406\u5b9e\u8df5\u8005",
            target_audience="\u90fd\u5e02\u5973\u6027",
            tone_style="\u6e29\u6696\u3001\u4e13\u4e1a\u3001\u63a5\u5730\u6c14",
            reader_salutation="\u4eb2\u7231\u7684\u8c03\u517b\u4f19\u4f34",
            origin_story="\u4ece\u81ea\u8eab\u7ecf\u5386\u51fa\u53d1",
            is_active=True,
        )
        product = ProductVault(
            user_id=USER_UUID,
            product_name="\u65b0\u4f1a\u9648\u76ae\u4e94\u5e74\u5bff\u7709\u8001\u767d\u8336",
            category="\u517b\u751f\u8336\u996e",
            core_ingredients="\u5e7f\u4e1c\u65b0\u4f1a\u9648\u76ae\u3001\u798f\u9f0e\u5bff\u7709\u8001\u767d\u8336",
            suitable_conditions="\u813e\u80c3\u6e7f\u5bd2",
            taboos="\u9634\u865a\u706b\u65fa",
            personal_usage_experience="\u6e29\u548c\u6da6\u6cfd\uff0c\u5165\u53e3\u7518\u9187",
            conversion_hooks="\u9648\u76ae\u8d8a\u9648\u8d8a\u9999",
            is_active=True,
        )
        sess.add(persona)
        sess.add(product)
        sess.commit()
        sess.refresh(persona)
        sess.refresh(product)
        yield sess


@pytest.fixture(name="client")
def client_fixture(session: Session) -> Generator[TestClient, None, None]:
    def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ===========================================================================
# 1. Anti-Fold Line Calculation Unit Tests
# ===========================================================================

def test_calculate_moments_lines_short_text():
    text = "\u7b2c\u4e00\u884c\n\u7b2c\u4e8c\u884c\n\u7b2c\u4e09\u884c"
    lines, will_fold, preview = calculate_moments_lines(text)
    assert lines == 3
    assert will_fold is False
    assert preview == text


def test_calculate_moments_lines_long_text():
    text = "1\n2\n3\n4\n5\n6\n7\n8\n9"
    lines, will_fold, preview = calculate_moments_lines(text)
    assert lines >= 7
    assert will_fold is True
    assert "1" in preview
    assert "9" not in preview


def test_clean_mechanical_dates():
    raw = "\u6211\u57282024\u5e743\u670815\u65e5\u5f00\u59cb\u8c03\u7406\uff0c\u5230\u4e862024-04-01\u611f\u89c9\u597d\u591a\u4e86\u3002"
    cleaned = clean_mechanical_dates(raw, "\u4e4b\u524d\u6709\u6bb5\u65f6\u95f4")
    assert "2024\u5e743\u670815\u65e5" not in cleaned
    assert "2024-04-01" not in cleaned
    assert "\u4e4b\u524d\u6709\u6bb5\u65f6\u95f4" in cleaned


# ===========================================================================
# 2. Templates Catalog
# ===========================================================================

def test_list_templates(client: TestClient):
    response = client.get("/api/private-domain/templates")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 5
    categories = [t["category"] for t in data]
    assert "\u4e13\u4e1a\u6c89\u6dc0" in categories
    assert "\u751f\u6d3b\u5207\u7247" in categories
    assert "\u597d\u7269\u81ea\u7528" in categories
    assert "\u4e92\u52a8\u622a\u6d41" in categories
    assert "\u5c81\u6708\u53cd\u601d" in categories

    for item in data:
        assert item["name"]
        assert item["description"]
        assert item["example_topic"]
        assert item["sample_hook"]
        assert item["recommended_timing"]
        assert item["target_goal"]


# ===========================================================================
# 3. Generate Moment for All 5 Categories
# ===========================================================================

@pytest.mark.parametrize(
    "category",
    ["\u4e13\u4e1a\u6c89\u6dc0", "\u751f\u6d3b\u5207\u7247", "\u597d\u7269\u81ea\u7528", "\u4e92\u52a8\u622a\u6d41", "\u5c81\u6708\u53cd\u601d"],
)
def test_generate_moment_all_categories(client: TestClient, category: str):
    response = client.post(
        "/api/private-domain/generate-moment",
        json={
            "category": category,
            "topic": f"\u5173\u4e8e{category}\u7684\u65e5\u5e38\u4f53\u609f",
            "time_narrative_mode": "invisible",
        },
    )
    assert response.status_code == 200
    data = response.json()

    assert "text" in data
    assert "estimated_lines" in data
    assert "will_fold" in data
    assert "fold_preview" in data
    assert "pinned_comment" in data
    assert "visual_card_prompt" in data
    assert "tags" in data

    # Verify anti-fold behavior
    assert data["estimated_lines"] >= 6
    assert data["will_fold"] is True
    assert len(data["fold_preview"]) > 0

    # Verify line 5 curiosity hook
    text_lines = data["text"].split("\n")
    assert len(text_lines) >= 5
    line_5 = text_lines[4]
    assert "\U0001f447" in line_5 or "\u5173\u952e" in line_5 or "\u79d8\u8bc0" in line_5 or "\u5176\u5b9e" in line_5

    # Verify pinned comment soft lead magnet
    assert len(data["pinned_comment"]) > 0
    assert any(k in data["pinned_comment"] for k in ["\u79c1\u4fe1", "\u6263", "\u8bc4\u8bba\u533a", "\u9886", "\u9001", "\u914d\u65b9"])

    # Verify tags and visual prompt
    assert len(data["tags"]) >= 1
    assert len(data["visual_card_prompt"]) > 0


# ===========================================================================
# 4. Time Narrative Modes
# ===========================================================================

def test_generate_moment_time_modes(client: TestClient):
    # 1. Fuzzy mode -> "之前有段时间"
    res_fuzzy = client.post(
        "/api/private-domain/generate-moment",
        json={"category": "生活切片", "time_narrative_mode": "fuzzy"},
    )
    assert res_fuzzy.status_code == 200
    text_fuzzy = res_fuzzy.json()["text"]
    assert "之前有段时间" in text_fuzzy

    # 2. Solar term mode -> "深秋那阵子"
    res_solar = client.post(
        "/api/private-domain/generate-moment",
        json={"category": "专业沉淀", "time_narrative_mode": "solar_term"},
    )
    assert res_solar.status_code == 200
    text_solar = res_solar.json()["text"]
    assert "深秋那阵子" in text_solar

    # 3. Anniversary mode -> "两年前的今天"
    res_anniv = client.post(
        "/api/private-domain/generate-moment",
        json={"category": "岁月反思", "time_narrative_mode": "anniversary"},
    )
    assert res_anniv.status_code == 200
    text_anniv = res_anniv.json()["text"]
    assert "两年前的今天" in text_anniv

    # 4. Invisible mode -> strips dates
    res_inv = client.post(
        "/api/private-domain/generate-moment",
        json={"category": "生活切片", "time_narrative_mode": "invisible"},
    )
    assert res_inv.status_code == 200
    text_inv = res_inv.json()["text"]
    assert "2024" not in text_inv and "2023" not in text_inv and "-" not in text_inv


# ===========================================================================
# 5. Product Vault and Persona Binding
# ===========================================================================

def test_generate_moment_with_product_and_persona(client: TestClient, session: Session):
    persona = session.exec(select(IPPersona)).first()
    product = session.exec(select(ProductVault)).first()

    response = client.post(
        "/api/private-domain/generate-moment",
        json={
            "category": "\u597d\u7269\u81ea\u7528",
            "persona_id": str(persona.id),
            "product_id": str(product.id),
            "topic": "\u81ea\u7528\u8001\u767d\u8336\u5206\u4eab",
        },
    )
    assert response.status_code == 200
    data = response.json()

    # Persona reader salutation should be in opening
    assert persona.reader_salutation in data["text"]
    # Product details should be woven in
    assert product.product_name in data["text"]
    assert "\u81ea\u7528\u7f6e\u9876" in data["pinned_comment"] or "\u8001\u767d\u8336" in data["pinned_comment"]


# ===========================================================================
# 6. Community Script Generation
# ===========================================================================

def test_generate_community_scripts(client: TestClient, session: Session):
    product = session.exec(select(ProductVault)).first()

    # Discussion starter
    res1 = client.post(
        "/api/private-domain/generate-community",
        json={"script_type": "discussion_starter", "topic": "\u75b2\u52b3\u6062\u590d"},
    )
    assert res1.status_code == 200
    d1 = res1.json()
    assert d1["script_type"] == "discussion_starter"
    assert "\u3010\u4eca\u65e5\u8bdd\u9898\u00b7\u56f4\u7089\u591c\u8bdd\u3011" in d1["content"]
    assert len(d1["roles"]) >= 1
    assert d1["recommended_timing"]
    assert d1["call_to_action"]

    # Sale theater
    res2 = client.post(
        "/api/private-domain/generate-community",
        json={"script_type": "sale_theater", "product_id": str(product.id)},
    )
    assert res2.status_code == 200
    d2 = res2.json()
    assert d2["script_type"] == "sale_theater"
    assert "\u3010\u793e\u7fa4\u8f7b\u5267\u573a\u00b7\u81ea\u7528\u79cd\u8349\u3011" in d2["content"]
    assert product.product_name in d2["content"]

    # QA spark
    res3 = client.post(
        "/api/private-domain/generate-community",
        json={"script_type": "qa_spark", "topic": "\u813e\u865a\u795b\u6e7f\u8bef\u533a"},
    )
    assert res3.status_code == 200
    d3 = res3.json()
    assert d3["script_type"] == "qa_spark"
    assert "\u3010\u6668\u95f4\u8ba4\u77e5\u7834\u58c1\u00b7\u5e38\u89c1\u8bef\u533a\u7b54\u7591\u3011" in d3["content"]


# ===========================================================================
# 7. Anti-Fold Enforcer Unit Tests
# ===========================================================================

def test_enforce_anti_fold_formatting_short_text():
    from app.api.private_domain import enforce_anti_fold_formatting
    raw = "一段简单的日常调养短句。"
    enforced = enforce_anti_fold_formatting(raw, salutation="姐妹们", category="专业沉淀")
    lines = enforced.split("\n")
    assert len(lines) >= 6
    assert lines[0].startswith("姐妹们")
    assert "👇" in lines[4]


def test_calculate_moments_lines_multiline_wrap():
    long_p = "这是一段很长很长的段落内容，用于模拟微信朋友圈单段超长文本折叠。" * 6
    lines, will_fold, preview = calculate_moments_lines(long_p)
    assert lines > 6
    assert will_fold is True
    assert "..." in preview


def test_generate_moment_product_fallback(client: TestClient):
    # Testing category 好物自用 without passing product_id
    response = client.post(
        "/api/private-domain/generate-moment",
        json={"category": "好物自用"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "text" in data
    assert len(data["text"]) > 0


def test_generate_moment_with_explicit_product_id(client: TestClient, session: Session):
    # Retrieve pre-seeded product
    product = session.exec(select(ProductVault)).first()
    assert product is not None

    response = client.post(
        "/api/private-domain/generate-moment",
        json={
            "category": "好物自用",
            "product_id": str(product.id),
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "text" in data
    # Verify product name is deeply embedded in moments text
    assert product.product_name in data["text"]
    # Verify pinned comment contains conversion hook or product context
    assert product.product_name in data["pinned_comment"] or (product.conversion_hooks and product.conversion_hooks in data["pinned_comment"])


def test_enforce_anti_fold_short_tier():
    from app.api.private_domain import enforce_anti_fold_formatting
    raw = "第一行开场\n第二行分享心得\n第三行祝大家健康。"
    enforced = enforce_anti_fold_formatting(raw, salutation="姐妹们", category="专业沉淀", length_tier="short")
    lines = enforced.split("\n")
    assert len(lines) <= 5
    assert "👇" not in enforced


def test_generate_moment_short_tier(client: TestClient):
    response = client.post(
        "/api/private-domain/generate-moment",
        json={
            "category": "生活切片",
            "length_tier": "short",
            "raw_experience": "晨起煮一壶老白茶",
            "my_takeaway": "放慢节奏，气血自然充盈",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["will_fold"] is False
    assert data["estimated_lines"] <= 5
    assert data["character_count"] > 0
    assert "老白茶" in data["text"]
    assert any(k in data["text"] for k in ["气血", "充盈", "放慢", "节奏"])


def test_generate_moment_deep_tier(client: TestClient):
    response = client.post(
        "/api/private-domain/generate-moment",
        json={
            "category": "专业沉淀",
            "length_tier": "deep",
            "trigger_type": "study_insight",
            "raw_experience": "黄帝内经脏腑学说",
            "my_takeaway": "百病生于气，调心即调身",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["will_fold"] is True
    assert data["character_count"] >= 150
    assert "黄帝内经脏腑学说" in data["text"]
    assert "百病生于气，调心即调身" in data["text"]
    assert "中医心得" in str(data["tags"])


