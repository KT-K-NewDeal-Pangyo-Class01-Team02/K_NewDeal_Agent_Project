from pathlib import Path

from services.device_images import COLOR_IMAGES, MODEL_IMAGES, image_for

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def test_color_image_is_preferred():
    image = image_for({"model": "Galaxy Z Fold8", "color": "Lavender", "storage": "256GB"})
    assert image == {"path": "img/devices/galaxy-z-fold8-lavender.png", "is_representative": False}


def test_model_image_is_used_when_color_missing():
    image = image_for({"model": "GalaxyZ Fold6", "color": "Black", "storage": "256GB"})
    assert image["path"].endswith("galaxy-z-fold6.png")
    assert image["is_representative"] is True


def test_unknown_model_has_no_image():
    assert image_for({"model": "Unknown Phone", "color": "Red", "storage": "64GB"}) is None


def test_every_mapped_file_exists():
    for name in set(COLOR_IMAGES.values()) | set(MODEL_IMAGES.values()):
        assert (STATIC_DIR / "img" / "devices" / name).is_file(), name


def test_list_api_includes_device_image(client):
    items = client.get("/api/reservations").get_json()["data"]["items"]
    fold8 = next(item for item in items if item["device_model"] == "Galaxy Z Fold8")

    assert fold8["device_image"]["url"].startswith("/static/img/devices/galaxy-z-fold8-")
    assert fold8["device_option"]
    assert client.get(fold8["device_image"]["url"]).status_code == 200


def test_every_demo_reservation_has_a_photo(client):
    """mock 예약에는 사진이 있는 기종만 쓴다 (사진이 없거나 품질이 나쁜 기종은 데이터에서 뺐다)."""
    items = client.get("/api/reservations").get_json()["data"]["items"]
    missing = [item["device_label"] for item in items if not item["device_image"]]
    assert missing == []
