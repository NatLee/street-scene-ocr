import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from street_scene_ocr.api import SERVED_BY_HEADER, create_app
from street_scene_ocr.config import Settings

from .conftest import FakeEngine, png_bytes


@pytest.fixture
def client(settings, manager):
    return TestClient(create_app(settings, manager))


def upload(client, path="/api/ocr", name="sign.png", data=None, **form):
    files = {"file": (name, data if data is not None else png_bytes(), "image/png")}
    return client.post(path, files=files, data=form)


def test_engines_lists_installed_and_missing(client):
    body = client.get("/api/engines").json()
    assert body["default_engine"] == "fake"
    assert body["default_min_confidence"] == 0.3
    assert body["max_upload_mb"] == 16
    assert body["allowed_extensions"] == ["png", "jpg", "jpeg"]
    engines = {e["name"]: e for e in body["engines"]}
    assert engines["fake"]["installed"] and not engines["fake"]["loaded"]
    assert not engines["missing"]["installed"]
    assert engines["missing"]["missing"] == ["street_scene_ocr_module_that_does_not_exist"]


def test_ocr_returns_regions_in_reading_order_with_threshold_flags(client):
    response = upload(client)
    assert response.status_code == 200
    body = response.json()
    assert [r["text"] for r in body["regions"]] == ["安和", "水果行"]
    assert [r["confident"] for r in body["regions"]] == [False, True]
    assert body["text"] == "水果行"
    assert body["regions"][1]["bbox"] == [20.0, 50.0, 120.0, 80.0]
    assert body["stages_ms"] == {"detection": 1.0, "recognition": 2.0}
    assert (body["width"], body["height"], body["engine"], body["device"]) == (200, 100, "fake", "cpu")
    assert response.headers[SERVED_BY_HEADER] == body["served_by"]


def test_lower_threshold_accepts_more(client):
    body = upload(client, min_confidence="0.2").json()
    assert body["min_confidence"] == 0.2
    assert body["text"] == "安和\n水果行"


def test_big_images_are_shrunk_for_the_engine_and_boxes_scaled_back(settings, manager):
    small = Settings(**{**vars(settings), "max_image_side": 100})
    manager.settings = small
    client = TestClient(create_app(small, manager))
    body = upload(client, data=png_bytes(400, 200)).json()
    assert FakeEngine.seen_shapes[-1] == (50, 100, 3)
    assert body["regions"][1]["bbox"] == [40.0, 100.0, 240.0, 160.0]
    assert (body["width"], body["height"]) == (400, 200)


def test_exif_rotation_is_applied_before_reading(client):
    exif = Image.Exif()
    exif[0x0112] = 6  # "rotate 90 degrees clockwise to display"
    data = png_bytes(200, 100, fmt="JPEG", exif=exif.tobytes())
    body = upload(client, name="phone.jpg", data=data).json()
    assert (body["width"], body["height"]) == (100, 200)


@pytest.mark.parametrize(
    ("name", "data", "status", "detail"),
    [
        ("notes.txt", b"hello", 400, "Allowed image types are -> png, jpg, jpeg"),
        ("fake.png", b"not an image", 422, "the file is not a readable image"),
    ],
)
def test_bad_uploads_are_rejected(client, name, data, status, detail):
    response = upload(client, name=name, data=data)
    assert response.status_code == status
    assert response.json()["detail"] == detail


def test_upload_size_limit(settings, manager):
    tiny = Settings(**{**vars(settings), "max_upload_mb": 1})
    client = TestClient(create_app(tiny, manager))
    response = upload(client, data=b"0" * (1024 * 1024 + 1))
    assert response.status_code == 413


@pytest.mark.parametrize(
    ("engine", "status", "fragment"),
    [("nope", 404, "unknown engine"), ("missing", 409, "not installed"), ("broken", 500, "model exploded")],
)
def test_engine_errors_map_to_http_status(client, engine, status, fragment):
    response = upload(client, engine=engine)
    assert response.status_code == status
    assert fragment in response.json()["detail"]


def test_annotated_png(client):
    response = upload(client, path="/api/ocr/annotated")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert Image.open(io.BytesIO(response.content)).size == (200, 100)


def test_upload_page_openapi_and_health(client):
    page = client.get("/")
    assert page.status_code == 200 and "street-scene-ocr" in page.text
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/samples/index.json").status_code == 200
    schema = client.get("/openapi.json").json()
    assert {"/api/ocr", "/api/ocr/annotated", "/api/engines", "/healthz"} <= set(schema["paths"])
    assert client.get("/healthz").json()["status"] == "ok"


def test_to_traditional_flag_is_reported_and_defaults_off(client):
    assert upload(client).json()["to_traditional"] is False
    body = upload(client, to_traditional="true").json()
    assert body["to_traditional"] is True
    assert body["text"] == "水果行"  # already Traditional: unchanged
    assert client.get("/api/engines").json()["default_to_traditional"] is False
