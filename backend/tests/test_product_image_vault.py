from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Generator
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from app.core.db import get_session
from app.api.dna_v2 import PRODUCT_UPLOAD_DIR
from app.main import app
from app.models.product import ProductVault, PRODUCT_PRESETS


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


def _make_mock_gateway(content: str):
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


class TestProductImageUpload:
    """Tests for POST /api/dna/v2/products/upload-image and static file serving."""

    def test_upload_image_png_success_and_static_serving(self, client: TestClient):
        fake_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRtest_lifestyle_photo"
        files = {
            "file": ("cup_tea.png", io.BytesIO(fake_content), "image/png"),
        }
        resp = client.post("/api/dna/v2/products/upload-image", files=files)
        assert resp.status_code == 200, resp.text
        data = resp.json()

        assert data["success"] is True
        assert data["filename"].endswith(".png")
        assert data["url"] == f"/uploads/products/{data['filename']}"

        # Verify file exists on local filesystem
        saved_file = PRODUCT_UPLOAD_DIR / data["filename"]
        try:
            assert saved_file.exists()
            assert saved_file.read_bytes() == fake_content

            # Verify static file serving via mounted /uploads
            serve_resp = client.get(data["url"])
            assert serve_resp.status_code == 200
            assert serve_resp.content == fake_content
        finally:
            if saved_file.exists():
                saved_file.unlink()

    def test_upload_image_jpeg_and_webp_formats(self, client: TestClient):
        # JPEG
        jpeg_content = b"\xff\xd8\xff\xe0\x00\x10JFIFfakejpeg"
        files_jpg = {
            "file": ("tea_set.jpg", io.BytesIO(jpeg_content), "image/jpeg"),
        }
        resp_jpg = client.post("/api/dna/v2/products/upload-image", files=files_jpg)
        assert resp_jpg.status_code == 200
        jpg_filename = resp_jpg.json()["filename"]
        assert jpg_filename.endswith(".jpg")
        p_jpg = PRODUCT_UPLOAD_DIR / jpg_filename
        if p_jpg.exists():
            p_jpg.unlink()

        # WebP
        webp_content = b"RIFF\x00\x00\x00\x00WEBPVP8 "
        files_webp = {
            "file": ("service_poster.webp", io.BytesIO(webp_content), "image/webp"),
        }
        resp_webp = client.post("/api/dna/v2/products/upload-image", files=files_webp)
        assert resp_webp.status_code == 200
        webp_filename = resp_webp.json()["filename"]
        assert webp_filename.endswith(".webp")
        p_webp = PRODUCT_UPLOAD_DIR / webp_filename
        if p_webp.exists():
            p_webp.unlink()

    def test_upload_image_invalid_mime_type(self, client: TestClient):
        files = {
            "file": ("document.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf"),
        }
        resp = client.post("/api/dna/v2/products/upload-image", files=files)
        # Uniform error contract: 422 + VALIDATION_ERROR, not a raw detail blob.
        assert resp.status_code == 422
        body = resp.json()
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert "Invalid image type" in body["error"]["message"]

    def test_upload_image_oversized_rejected(self, client: TestClient):
        # 10MB + 1 byte
        oversized = b"A" * (10 * 1024 * 1024 + 1)
        files = {
            "file": ("huge.jpg", io.BytesIO(oversized), "image/jpeg"),
        }
        resp = client.post("/api/dna/v2/products/upload-image", files=files)
        assert resp.status_code == 422
        body = resp.json()
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert "exceeds maximum allowed size" in body["error"]["message"]


class TestProductVaultImageLinkage:
    """Tests for ProductVault model image storage, CRUD, and serialization."""

    def test_create_product_with_images_snake_case(self, client: TestClient, session: Session):
        payload = {
            "user_id": USER_ID,
            "product_name": "Premium Aged White Tea",
            "category": "Health Tea",
            "core_ingredients": "Fuding White Tea 10-Year Aged",
            "suitable_conditions": "Weak spleen and stomach",
            "taboos": "Severe gastric ulcer",
            "personal_usage_experience": "Daily ritual cup of warm tea.",
            "conversion_hooks": "DM to receive free sample packet",
            "cover_image": "https://example.com/cover.jpg",
            "gallery_images": [
                "https://example.com/tea1.jpg",
                "https://example.com/tea2.jpg",
            ],
            "service_rights_images": [
                "https://example.com/guarantee1.jpg",
            ],
        }
        resp = client.post("/api/dna/v2/products", json=payload)
        assert resp.status_code == 201, resp.text
        data = resp.json()

        assert data["cover_image"] == "https://example.com/cover.jpg"
        assert data["gallery_images"] == [
            "https://example.com/tea1.jpg",
            "https://example.com/tea2.jpg",
        ]
        assert data["service_rights_images"] == [
            "https://example.com/guarantee1.jpg",
        ]

        # Verify DB persistence
        db_p = session.get(ProductVault, uuid.UUID(data["id"]))
        assert db_p is not None
        assert db_p.cover_image == "https://example.com/cover.jpg"
        assert len(db_p.gallery_images) == 2
        assert len(db_p.service_rights_images) == 1

    def test_create_product_with_images_camel_case(self, client: TestClient, session: Session):
        payload = {
            "userId": USER_ID,
            "productName": "Royal Herbal Cake",
            "category": "Herbal Snacks",
            "coreIngredients": "Poria, Atractylodes, Codonopsis",
            "coverImage": "https://example.com/pastry_cover.jpg",
            "galleryImages": [
                "https://example.com/slice1.jpg",
            ],
            "serviceRightsImages": [
                "https://example.com/cert.jpg",
                "https://example.com/service.jpg",
            ],
        }
        resp = client.post("/api/dna/v2/products", json=payload)
        assert resp.status_code == 201, resp.text
        data = resp.json()

        assert data["cover_image"] == "https://example.com/pastry_cover.jpg"
        assert data["gallery_images"] == ["https://example.com/slice1.jpg"]
        assert len(data["service_rights_images"]) == 2

    def test_patch_update_product_images(self, client: TestClient, session: Session):
        # Create without images
        prod = ProductVault(
            user_id=USER_UUID,
            product_name="Product Without Images",
            category="Uncategorized",
            cover_image="",
            gallery_images=[],
            service_rights_images=[],
        )
        session.add(prod)
        session.commit()
        session.refresh(prod)

        # Patch with snake_case
        patch_payload = {
            "cover_image": "https://example.com/new_cover.jpg",
            "gallery_images": ["https://example.com/new_gal1.jpg"],
            "service_rights_images": ["https://example.com/new_right1.jpg"],
        }
        resp = client.patch(f"/api/dna/v2/products/{prod.id}", json=patch_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["cover_image"] == "https://example.com/new_cover.jpg"
        assert data["gallery_images"] == ["https://example.com/new_gal1.jpg"]
        assert data["service_rights_images"] == ["https://example.com/new_right1.jpg"]

        # Patch with camelCase
        patch_camel = {
            "coverImage": "https://example.com/updated_cover.jpg",
            "galleryImages": ["https://example.com/g1.jpg", "https://example.com/g2.jpg"],
        }
        resp_c = client.patch(f"/api/dna/v2/products/{prod.id}", json=patch_camel)
        assert resp_c.status_code == 200
        data_c = resp_c.json()
        assert data_c["cover_image"] == "https://example.com/updated_cover.jpg"
        assert len(data_c["gallery_images"]) == 2
        # service_rights_images untouched
        assert data_c["service_rights_images"] == ["https://example.com/new_right1.jpg"]

    def test_extract_product_from_text_carries_image_metadata(self, client: TestClient, session: Session):
        mock_json = json.dumps({
            "product_name": "Small Green Citrus Tea",
            "category": "Citrus Pu'er",
            "core_ingredients": "Xinhui Citrus Peel",
            "suitable_conditions": "Indigestion",
            "taboos": "Hyperacidity",
            "personal_usage_experience": "Fresh and sweet aftertaste.",
            "conversion_hooks": "Join group for free gift"
        })

        gw = _make_mock_gateway(mock_json)

        with patch("app.api.dna_v2.get_model_gateway", return_value=gw):
            resp = client.post("/api/dna/v2/products/extract-from-text", json={
                "text": "Extract citrus tea description",
                "user_id": USER_ID,
                "auto_save": True,
                "cover_image": "https://example.com/extracted_cover.jpg",
                "gallery_images": ["https://example.com/ext1.jpg"],
                "service_rights_images": ["https://example.com/ext_cert.jpg"],
            })

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["success"] is True
        product = data["product"]
        assert product["cover_image"] == "https://example.com/extracted_cover.jpg"
        assert product["gallery_images"] == ["https://example.com/ext1.jpg"]
        assert product["service_rights_images"] == ["https://example.com/ext_cert.jpg"]

        # Check DB
        db_p = session.exec(select(ProductVault).where(ProductVault.product_name == "Small Green Citrus Tea")).first()
        assert db_p is not None
        assert db_p.cover_image == "https://example.com/extracted_cover.jpg"
        assert db_p.gallery_images == ["https://example.com/ext1.jpg"]
        assert db_p.service_rights_images == ["https://example.com/ext_cert.jpg"]

    def test_product_presets_image_integrity(self):
        """Ensure default system presets contain high quality aesthetic images."""
        assert len(PRODUCT_PRESETS) >= 2
        for p in PRODUCT_PRESETS:
            assert p.cover_image, f"Preset {p.product_name} missing cover_image"
            assert p.cover_image.startswith("http"), f"Preset {p.product_name} cover_image invalid"
            assert len(p.gallery_images) >= 2, f"Preset {p.product_name} gallery_images should have at least 2 items"
            assert len(p.service_rights_images) >= 1, f"Preset {p.product_name} service_rights_images should have at least 1 item"
