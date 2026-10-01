from config import Config
from repositories.customer_repository import CustomerRepository
from repositories.inventory_repository import InventoryRepository

NEW_RESERVATION = {
    "store_id": "S001",
    "device": {"model": "GalaxyZ Fold6", "color": "Black", "storage": "256GB"},
    "desired_activation_date": "2026-10-05",
    "line_type": "NEW",
}


def test_db_holds_json_customers_and_demo_customers(db_path):
    customers = CustomerRepository(Config.DATA_DIR, db_path)

    assert customers.find_by_id("C001")["name"] == "김지수"
    # mock 예약 R2003(서류 미제출)의 고객은 서류가 빠져 있다
    c103 = customers.find_by_id("C103")
    assert "가족관계증명서" in c103["required_documents"]
    assert "가족관계증명서" not in c103["submitted_documents"]
    assert c103["identity_verified"] is True


def test_customer_upsert_updates_existing(db_path):
    customers = CustomerRepository(Config.DATA_DIR, db_path)
    customers.upsert({"customer_id": "C001", "overdue_payment": True})

    assert customers.find_by_id("C001")["overdue_payment"] is True
    assert customers.find_by_id("C001")["name"] == "김지수"


def test_inventory_in_db_matches_json(db_path):
    db_items = {item["sku"] for item in InventoryRepository(Config.DATA_DIR, db_path).load_all()}
    json_items = {item["sku"] for item in InventoryRepository(Config.DATA_DIR).load_all()}
    assert db_items == json_items


def test_precheck_reads_customer_changes_from_db(client, db_path):
    CustomerRepository(Config.DATA_DIR, db_path).upsert({"customer_id": "C001", "overdue_payment": True})
    payload = {**NEW_RESERVATION, "customer_id": "C001"}

    data = client.post("/api/precheck", json=payload).get_json()["data"]
    assert data["activation_risk_check"]["checks"]["overdue_payment"] is True


def test_unknown_customer_is_flagged_not_high_risk(client):
    data = client.post("/api/reservations", json={**NEW_RESERVATION, "customer_id": "C999"}).get_json()["data"]

    assert [issue["code"] for issue in data["issues"]] == ["CUSTOMER_UNKNOWN"]
    assert any(action["action_type"] == "CUSTOMER_INFO_CHECK" for action in data["actions"])
    assert data["risk_level"] != "high"


def test_reset_restores_reference_data(client, db_path):
    CustomerRepository(Config.DATA_DIR, db_path).upsert({"customer_id": "C001", "overdue_payment": True})
    client.post("/api/demo/reset")
    assert CustomerRepository(Config.DATA_DIR, db_path).find_by_id("C001")["overdue_payment"] is False
