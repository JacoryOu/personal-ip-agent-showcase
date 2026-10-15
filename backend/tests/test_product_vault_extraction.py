"""
Unit tests for Product Vault reverse extraction and CRUD management.
Tests:
1. POST /api/dna/v2/products/extract-from-text (with mock ModelGateway)
2. PATCH /api/dna/v2/products/{product_id} (field update and is_active toggle)
3. DELETE /api/dna/v2/products/{product_id}
4. Edge cases: empty text, invalid JSON fences, non-existent product, is_active filtering
"""

from __future__ import annotations

import json
import uuid
from typing import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from app.core.db import get_session
from app.main import app
from app.models.product import ProductVault

# ---------------------------------------------------------------------------
# Test Setup
# ---------------------------------------------------------------------------

@pytest.fixture(name="test_engine")
def engine_fixture():
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    import app.models  # noqa: F401
    SQLModel.metadata.create_all(eng)
    return eng


@pytest.fixture(name="session")
def session_fixture(test_engine) -> Generator[Session, None, None]:
    with Session(test_engine) as sess:
        yield sess


@pytest.fixture(name="client")
def client_fixture(session: Session) -> Generator[TestClient, None, None]:
    def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


USER_ID = "00000000-0000-0000-0000-000000000001"
USER_UUID = uuid.UUID(USER_ID)

MOCK_PRODUCT_EXTRACTED_JSON = json.dumps({
    "product_name": "五年陈新会小青柑",
    "category": "柑普茶饮",
    "core_ingredients": "广东新会核心产区茶枝柑、云南勐海五年陈宫廷普洱",
    "suitable_conditions": "长期用脑、久坐积食、脾胃不舒、应酬多烟酒者",
    "taboos": "胃溃疡发作期慎饮，严重失眠者傍晚后不宜多饮",
    "personal_usage_experience": "我自己每天下午雷打不动泡一颗，柑香清润扑鼻，连喝三道茶汤后整个胃肠都通畅温热，下午办公头脑极清醒。",
    "conversion_hooks": "私信发送'品鉴'，免费领取一份两颗装独立封装尝鲜试饮礼。"
}, ensure_ascii=False)


def _make_mock_gateway(content: str = MOCK_PRODUCT_EXTRACTED_JSON):
    gw = MagicMock()
    mock_client = MagicMock()
    choice = MagicMock()
    choice.message.content = content
    response = MagicMock()
    response.choices = [choice]

    mock_client.chat.completions = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=response)

    gw.get_client_for_role = MagicMock(return_value=mock_client)
    gw.get_model_for_role = MagicMock(return_value="mock-diff-model")
    return gw


# ===========================================================================
# 1. Product Extraction Tests (POST /api/dna/v2/products/extract-from-text)
# ===========================================================================

class TestProductExtractFromText:
    def test_extract_without_auto_save(self, client: TestClient, session: Session):
        """Verify extraction parses raw product material without persisting to DB."""
        gw = _make_mock_gateway()
        raw_text = "这是广东新会核心产区的小青柑，里面装的是云南勐海的五年陈宫廷普洱熟茶。特别解腻顺气..."

        with patch("app.api.dna_v2.get_model_gateway", return_value=gw):
            resp = client.post("/api/dna/v2/products/extract-from-text", json={
                "text": raw_text,
                "user_id": USER_ID,
                "auto_save": False,
            })

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["success"] is True
        assert data["saved"] is False

        product = data["product"]
        assert product["product_name"] == "五年陈新会小青柑"
        assert product["category"] == "柑普茶饮"
        assert "茶枝柑" in product["core_ingredients"]
        assert "脾胃不舒" in product["suitable_conditions"]
        assert "胃溃疡" in product["taboos"]
        assert "我自己每天下午" in product["personal_usage_experience"]
        assert "尝鲜试饮礼" in product["conversion_hooks"]

        # Ensure database is clean
        db_products = session.exec(select(ProductVault).where(ProductVault.user_id == USER_UUID)).all()
        assert len(db_products) == 0

    def test_extract_with_auto_save_snake_case(self, client: TestClient, session: Session):
        """Verify extraction with auto_save: True persists to database with correct user_id."""
        gw = _make_mock_gateway()
        raw_text = "产品宣传文案：新会小青柑，核心产地直采..."

        with patch("app.api.dna_v2.get_model_gateway", return_value=gw):
            resp = client.post("/api/dna/v2/products/extract-from-text", json={
                "text": raw_text,
                "user_id": USER_ID,
                "auto_save": True,
            })

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["success"] is True
        assert data["saved"] is True

        product = data["product"]
        assert product["product_name"] == "五年陈新会小青柑"
        assert product["is_active"] is True

        # Verify DB persistence
        db_products = session.exec(select(ProductVault).where(ProductVault.user_id == USER_UUID)).all()
        assert len(db_products) == 1
        saved_p = db_products[0]
        assert saved_p.product_name == "五年陈新会小青柑"
        assert saved_p.is_active is True
        assert "胃溃疡" in saved_p.taboos
        assert "尝鲜试饮礼" in saved_p.conversion_hooks

    def test_extract_with_auto_save_camel_case(self, client: TestClient, session: Session):
        """Verify autoSave (camelCase from frontend) is also supported."""
        gw = _make_mock_gateway()
        raw_text = "产品详情页介绍..."

        with patch("app.api.dna_v2.get_model_gateway", return_value=gw):
            resp = client.post("/api/dna/v2/products/extract-from-text", json={
                "text": raw_text,
                "user_id": USER_ID,
                "autoSave": True,
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["saved"] is True

        db_products = session.exec(select(ProductVault).where(ProductVault.user_id == USER_UUID)).all()
        assert len(db_products) == 1

    def test_extract_with_markdown_fences_and_reasoning_tags(self, client: TestClient):
        """Verify extractor handles reasoning blocks (<think>...</think>) and ```json fences."""
        noisy = f"<think>正在思考如何提炼私域心智...</think>\n为您提炼出以下产品心智档案：\n```json\n{MOCK_PRODUCT_EXTRACTED_JSON}\n```\n希望对您的私域转化有所帮助！"
        gw = _make_mock_gateway(noisy)

        with patch("app.api.dna_v2.get_model_gateway", return_value=gw):
            resp = client.post("/api/dna/v2/products/extract-from-text", json={
                "text": "杂乱文案内容...",
                "user_id": USER_ID,
                "auto_save": False,
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["product"]["product_name"] == "五年陈新会小青柑"

    def test_extract_empty_or_whitespace_text_rejected(self, client: TestClient):
        """Empty or whitespace text should return 422."""
        resp1 = client.post("/api/dna/v2/products/extract-from-text", json={"text": ""})
        assert resp1.status_code == 422

        resp2 = client.post("/api/dna/v2/products/extract-from-text", json={"text": "   \n\t  "})
        assert resp2.status_code == 422

    def test_extract_llm_error_returns_500(self, client: TestClient):
        """When the LLM call fails, the endpoint returns a 500 that does not
        leak the upstream exception text.

        Security line B: the raw SDK/runtime message must never reach the
        client. The public body only carries a stable code, a safe message
        and the request id that ties back to the server-side log line.
        """
        gw = MagicMock()
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=RuntimeError("Gateway timeout"))
        gw.get_client_for_role = MagicMock(return_value=mock_client)
        gw.get_model_for_role = MagicMock(return_value="mock-model")

        with patch("app.api.dna_v2.get_model_gateway", return_value=gw):
            resp = client.post("/api/dna/v2/products/extract-from-text", json={
                "text": "正常文案...",
            })

        assert resp.status_code == 500
        body = resp.json()
        assert "Gateway timeout" not in resp.text
        assert body["error"]["code"] == "INTERNAL_ERROR"
        assert body["error"]["message"] == "Internal server error."
        assert body["error"]["request_id"]
        assert resp.headers.get("X-Request-ID") == body["error"]["request_id"]


    def test_extract_with_array_fields_normalized_to_chinese_delimiters(self, client: TestClient):
        """Verify list fields from LLM are joined with Chinese enumeration punctuation '、'."""
        array_payload = json.dumps({
            "product_name": "新会五年老白茶",
            "category": ["养生茶", "药膳饮"],
            "core_ingredients": ["新会核心陈皮", "五年寿眉老白茶", "高山日晒白茶"],
            "suitable_conditions": ["脾胃虚寒", "经常熬夜", "消化不良"],
            "taboos": ["严重胃酸过多", "孕产妇慎用"],
            "personal_usage_experience": "我每天饭后必煮一壶，身心温润。",
            "conversion_hooks": ["私信领3日试饮体验装", "朋友圈点赞送冲泡指南"]
        }, ensure_ascii=False)
        gw = _make_mock_gateway(array_payload)

        with patch("app.api.dna_v2.get_model_gateway", return_value=gw):
            resp = client.post("/api/dna/v2/products/extract-from-text", json={
                "text": "原料介绍...",
                "user_id": USER_ID,
            })

        assert resp.status_code == 200
        p = resp.json()["product"]
        assert p["category"] == "养生茶、药膳饮"
        assert p["core_ingredients"] == "新会核心陈皮、五年寿眉老白茶、高山日晒白茶"
        assert p["suitable_conditions"] == "脾胃虚寒、经常熬夜、消化不良"
        assert p["taboos"] == "严重胃酸过多、孕产妇慎用"
        assert p["conversion_hooks"] == "私信领3日试饮体验装、朋友圈点赞送冲泡指南"

    def test_extract_with_chinese_synonym_keys(self, client: TestClient):
        """Verify Chinese synonym keys (品名, 核心成分, 禁忌, 自用感受, etc.) are parsed properly."""
        chinese_keys_payload = json.dumps({
            "品名": "同仁堂茯苓八珍糕",
            "品类": "滋补糕点",
            "核心成分": "道地茯苓、怀山药、芡实",
            "适合体质": "脾虚湿困者",
            "禁忌与劝退人群": "实热体质忌服",
            "自用感受": "口感微甜不腻，连吃两周感觉整个人轻盈了许多。",
            "转化引子": "加微信赠送《四季健脾食疗手册》"
        }, ensure_ascii=False)
        gw = _make_mock_gateway(chinese_keys_payload)

        with patch("app.api.dna_v2.get_model_gateway", return_value=gw):
            resp = client.post("/api/dna/v2/products/extract-from-text", json={
                "text": "八珍糕详情介绍...",
                "user_id": USER_ID,
            })

        assert resp.status_code == 200
        p = resp.json()["product"]
        assert p["product_name"] == "同仁堂茯苓八珍糕"
        assert p["category"] == "滋补糕点"
        assert p["core_ingredients"] == "道地茯苓、怀山药、芡实"
        assert p["suitable_conditions"] == "脾虚湿困者"
        assert p["taboos"] == "实热体质忌服"
        assert "口感微甜不腻" in p["personal_usage_experience"]
        assert "四季健脾食疗手册" in p["conversion_hooks"]

    def test_extract_with_list_wrapped_json_response(self, client: TestClient):
        """Verify extractor handles LLM output enclosed in an outer list [ { ... } ]."""
        list_payload = json.dumps([{
            "product_name": "古树红茶",
            "category": "红茶",
            "core_ingredients": "临沧百年古树茶青",
            "suitable_conditions": "手脚冰凉人群",
            "taboos": "高热发烧者慎饮",
            "personal_usage_experience": "冬日午后必饮，甘润暖胃。",
            "conversion_hooks": "私信领茶样"
        }], ensure_ascii=False)
        gw = _make_mock_gateway(list_payload)

        with patch("app.api.dna_v2.get_model_gateway", return_value=gw):
            resp = client.post("/api/dna/v2/products/extract-from-text", json={
                "text": "古树红茶介绍",
            })

        assert resp.status_code == 200
        assert resp.json()["product"]["product_name"] == "古树红茶"

    def test_extract_with_plain_text_fallback_without_500(self, client: TestClient):
        """Verify LLM returning plain text key-values (no JSON) is gracefully parsed via fallback."""
        plain_text_output = """为您萃取如下产品心智：
- 产品品名：老树白茶饼
- 品类：紧压白茶
- 核心成分：福鼎大白茶高山原料
- 适用人群：经常面对电脑的办公族
- 禁忌劝退人群：空腹不宜浓饮
- 第一人称真实自用体验：我喝了三年，茶汤清甜透亮。
- 低阻力转化引流钩子：回复白茶免费领取品尝包
"""
        gw = _make_mock_gateway(plain_text_output)

        with patch("app.api.dna_v2.get_model_gateway", return_value=gw):
            resp = client.post("/api/dna/v2/products/extract-from-text", json={
                "text": "老树白茶相关资料...",
            })

        assert resp.status_code == 200
        p = resp.json()["product"]
        assert p["product_name"] == "老树白茶饼"
        assert p["category"] == "紧压白茶"
        assert "福鼎大白茶" in p["core_ingredients"]
        assert "经常面对电脑" in p["suitable_conditions"]
        assert "空腹不宜" in p["taboos"]
        assert "我喝了三年" in p["personal_usage_experience"]
        assert "免费领取品尝包" in p["conversion_hooks"]


# ===========================================================================
# 2. Product Update, Delete, Toggle and CRUD Tests
# ===========================================================================

class TestProductCRUDAndToggle:
    def test_create_and_get_product(self, client: TestClient):
        """Test standard product creation and direct retrieval."""
        create_resp = client.post("/api/dna/v2/products", json={
            "product_name": "温润红豆薏米丸",
            "category": "食疗养生",
            "core_ingredients": "赤小豆、炒薏米、芡实、红枣",
            "suitable_conditions": "体虚湿重、晨起水肿、舌苔厚腻",
            "taboos": "孕妇慎用、严重阴虚津亏者不宜",
            "personal_usage_experience": "我吃了一个月，早起脸不胀了。",
            "conversion_hooks": "私信领去湿气食疗方",
            "user_id": USER_ID,
        })
        assert create_resp.status_code == 201, create_resp.text
        created = create_resp.json()
        pid = created["id"]
        assert created["is_active"] is True

        get_resp = client.get(f"/api/dna/v2/products/{pid}")
        assert get_resp.status_code == 200
        assert get_resp.json()["product_name"] == "温润红豆薏米丸"

    def test_update_product_fields(self, client: TestClient):
        """Test partial field update via PATCH."""
        create_resp = client.post("/api/dna/v2/products", json={
            "product_name": "旧名字",
            "category": "旧品类",
            "taboos": "旧禁忌",
            "user_id": USER_ID,
        })
        pid = create_resp.json()["id"]

        patch_resp = client.patch(f"/api/dna/v2/products/{pid}", json={
            "product_name": "新名字",
            "taboos": "哺乳期慎用，脾胃大寒者减半",
            "conversion_hooks": "评论区回复888领样品",
        })
        assert patch_resp.status_code == 200
        updated = patch_resp.json()
        assert updated["product_name"] == "新名字"
        assert updated["category"] == "旧品类"  # Unchanged
        assert updated["taboos"] == "哺乳期慎用，脾胃大寒者减半"
        assert updated["conversion_hooks"] == "评论区回复888领样品"

    def test_toggle_product_active_state(self, client: TestClient):
        """Test toggling is_active field via PATCH."""
        create_resp = client.post("/api/dna/v2/products", json={
            "product_name": "季节限定茶",
            "user_id": USER_ID,
        })
        pid = create_resp.json()["id"]
        assert create_resp.json()["is_active"] is True

        # Deactivate
        deact_resp = client.patch(f"/api/dna/v2/products/{pid}", json={"is_active": False})
        assert deact_resp.status_code == 200
        assert deact_resp.json()["is_active"] is False

        # Reactivate
        react_resp = client.patch(f"/api/dna/v2/products/{pid}", json={"is_active": True})
        assert react_resp.status_code == 200
        assert react_resp.json()["is_active"] is True

    def test_delete_product(self, client: TestClient, session: Session):
        """Test product deletion and 404 on subsequent lookups."""
        create_resp = client.post("/api/dna/v2/products", json={
            "product_name": "待下架产品",
            "user_id": USER_ID,
        })
        pid = create_resp.json()["id"]

        del_resp = client.delete(f"/api/dna/v2/products/{pid}")
        assert del_resp.status_code == 200
        assert del_resp.json()["success"] is True

        # Verify not found on subsequent get
        get_resp = client.get(f"/api/dna/v2/products/{pid}")
        assert get_resp.status_code == 404

        # Verify deleted from DB
        db_p = session.get(ProductVault, uuid.UUID(pid))
        assert db_p is None

    def test_update_nonexistent_product_returns_404(self, client: TestClient):
        fake_id = str(uuid.uuid4())
        resp = client.patch(f"/api/dna/v2/products/{fake_id}", json={"product_name": "不存在"})
        assert resp.status_code == 404

    def test_delete_nonexistent_product_returns_404(self, client: TestClient):
        fake_id = str(uuid.uuid4())
        resp = client.delete(f"/api/dna/v2/products/{fake_id}")
        assert resp.status_code == 404

    def test_list_products_with_is_active_filter(self, client: TestClient):
        """Verify list endpoint filtering by is_active."""
        client.post("/api/dna/v2/products", json={"product_name": "活跃产品1", "is_active": True, "user_id": USER_ID})
        client.post("/api/dna/v2/products", json={"product_name": "活跃产品2", "is_active": True, "user_id": USER_ID})
        client.post("/api/dna/v2/products", json={"product_name": "已归档产品", "is_active": False, "user_id": USER_ID})

        # All products
        all_resp = client.get(f"/api/dna/v2/products?user_id={USER_ID}")
        assert all_resp.status_code == 200
        assert len(all_resp.json()) == 3

        # Active only
        active_resp = client.get(f"/api/dna/v2/products?user_id={USER_ID}&is_active=true")
        assert active_resp.status_code == 200
        active_names = [p["product_name"] for p in active_resp.json()]
        assert "活跃产品1" in active_names
        assert "活跃产品2" in active_names
        assert "已归档产品" not in active_names

        # Inactive only
        inactive_resp = client.get(f"/api/dna/v2/products?user_id={USER_ID}&is_active=false")
        assert inactive_resp.status_code == 200
        inactive_names = [p["product_name"] for p in inactive_resp.json()]
        assert "已归档产品" in inactive_names
        assert len(inactive_names) == 1
    def test_create_and_patch_with_camel_case(self, client: TestClient):
        """Verify ProductCreate and ProductUpdate handle camelCase properties from frontend."""
        # Create with camelCase
        create_resp = client.post("/api/dna/v2/products", json={
            "productName": "驼峰品名测试",
            "coreIngredients": "驼峰原料1、原料2",
            "suitableConditions": "驼峰体质",
            "personalUsageExperience": "驼峰自用体验",
            "conversionHooks": "驼峰钩子",
            "isActive": True,
            "userId": USER_ID,
        })
        assert create_resp.status_code == 201
        created = create_resp.json()
        pid = created["id"]
        assert created["product_name"] == "驼峰品名测试"
        assert created["core_ingredients"] == "驼峰原料1、原料2"
        assert created["is_active"] is True

        # Patch with camelCase isActive: False
        patch_resp = client.patch(f"/api/dna/v2/products/{pid}", json={
            "productName": "驼峰品名已更新",
            "isActive": False,
        })
        assert patch_resp.status_code == 200
        updated = patch_resp.json()
        assert updated["product_name"] == "驼峰品名已更新"
        assert updated["is_active"] is False
