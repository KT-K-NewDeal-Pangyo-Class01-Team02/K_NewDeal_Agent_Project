from config import Config
from services.inventory_service import InventoryService

STORE_ID = "S001"


def test_available_when_current_store_has_stock():
    service = InventoryService(Config.DATA_DIR)
    device = {"model": "GalaxyZ Fold6", "color": "Black", "storage": "256GB"}

    result = service.check(STORE_ID, device, "2026-10-05")

    assert result["status"] == "available"
    assert result["schedule_match"] is True
    assert result["issues"] == []


def test_conditional_when_nearby_store_has_stock():
    service = InventoryService(Config.DATA_DIR)
    device = {"model": "iPhone 16", "color": "Blue", "storage": "128GB"}

    result = service.check(STORE_ID, device, "2026-10-05")

    assert result["status"] == "conditional"
    assert result["source_store_id"] == "S002"
    assert len(result["nearby_options"]) == 1
    assert result["nearby_options"][0]["store_id"] == "S002"


def test_conditional_when_restock_later_than_desired_date():
    service = InventoryService(Config.DATA_DIR)
    device = {"model": "GalaxyZ Fold6", "color": "Silver", "storage": "512GB"}

    result = service.check(STORE_ID, device, "2026-10-05")

    assert result["status"] == "conditional"
    assert result["expected_available_date"] == "2026-10-10"
    assert result["issues"]


def test_available_when_restock_on_or_before_desired_date():
    service = InventoryService(Config.DATA_DIR)
    device = {"model": "GalaxyZ Fold6", "color": "Silver", "storage": "512GB"}

    result = service.check(STORE_ID, device, "2026-10-15")

    assert result["status"] == "available"


def test_unavailable_when_no_stock_anywhere():
    service = InventoryService(Config.DATA_DIR)
    device = {"model": "Unknown Model", "color": "X", "storage": "1GB"}

    result = service.check(STORE_ID, device, "2026-10-05")

    assert result["status"] == "unavailable"
    assert result["nearby_options"] == []
