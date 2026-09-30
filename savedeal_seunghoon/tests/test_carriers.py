import sqlite3
from pathlib import Path

from db.connection import connect, init_schema
from services.carriers import carrier_change, carrier_info

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

NEW_MNP = {
    "customer_id": "C001",
    "store_id": "S001",
    "device": {"model": "GalaxyZ Fold6", "color": "Black", "storage": "256GB"},
    "desired_activation_date": "2026-10-05",
    "line_type": "MNP",
}


def test_carrier_change_only_for_number_porting():
    change = carrier_change("MNP", "LGU")
    assert change["from"]["label"] == "LG U+"
    assert change["to"]["code"] == "KT"
    assert change["label"] == "LG U+ → KT"
    assert carrier_change("CHANGE", "LGU") is None
    assert carrier_change("NEW", None) is None


def test_missing_previous_carrier_is_labelled():
    assert carrier_change("MNP", None)["label"] == "기존 통신사 미입력 → KT"


def test_budget_carrier_has_no_logo_and_logos_exist():
    assert carrier_info("MVNO")["logo_url"] is None
    for code in ("KT", "SKT", "LGU"):
        path = carrier_info(code)["logo_url"].removeprefix("/static/")
        assert (STATIC_DIR / path).is_file(), code


def test_old_database_gets_previous_carrier_column(tmp_path):
    db = tmp_path / "old.db"
    raw = sqlite3.connect(db)
    raw.execute("CREATE TABLE reservations (reservation_id TEXT PRIMARY KEY, line_type TEXT NOT NULL)")
    raw.commit()
    raw.close()

    init_schema(db)

    with connect(db) as conn:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(reservations)")}
    assert "previous_carrier" in columns


def test_list_shows_carrier_change_for_mnp_rows(client):
    items = client.get("/api/reservations").get_json()["data"]["items"]
    mnp = [item for item in items if item["line_type_label"] == "번호이동"]
    others = [item for item in items if item["line_type_label"] != "번호이동"]

    assert mnp and all(item["carrier_change"]["to"]["code"] == "KT" for item in mnp)
    assert {item["carrier_change"]["from"]["code"] for item in mnp} >= {"SKT", "LGU", "MVNO"}
    assert all(item["carrier_change"] is None for item in others)


def test_create_mnp_reservation_saves_previous_carrier(client):
    data = client.post("/api/reservations", json={**NEW_MNP, "previous_carrier": "SKT"}).get_json()["data"]
    assert data["carrier_change"]["label"] == "SK텔레콤 → KT"


def test_previous_carrier_ignored_for_other_line_types(client):
    payload = {**NEW_MNP, "line_type": "CHANGE", "previous_carrier": "SKT"}
    data = client.post("/api/reservations", json=payload).get_json()["data"]
    assert data["carrier_change"] is None


def test_invalid_previous_carrier_returns_400(client):
    response = client.post("/api/reservations", json={**NEW_MNP, "previous_carrier": "KT"})
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "VALIDATION_ERROR"
