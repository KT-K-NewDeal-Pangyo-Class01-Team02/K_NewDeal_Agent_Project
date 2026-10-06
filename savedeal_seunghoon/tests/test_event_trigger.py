"""대시보드 '이벤트 발생' 버튼 (POST /api/events/trigger)."""
import random

from services.event_trigger import FEATURED_CUSTOMER, SOURCE, EventTrigger


def open_ranks(client) -> dict:
    items = [i for i in client.get("/api/reservations").get_json()["data"]["items"] if i["is_open"]]
    return {item["reservation_id"]: rank for rank, item in enumerate(items, start=1)}


def trigger(client) -> dict:
    response = client.post("/api/events/trigger")
    assert response.status_code == 200
    return response.get_json()["data"]


def test_first_trigger_pushes_featured_customer_to_first(client):
    data = trigger(client)

    assert data["customer_name"] == FEATURED_CUSTOMER
    assert data["featured"] is True
    assert data["after"]["rank"] == 1 and data["before"]["rank"] > 1
    assert open_ranks(client)[data["reservation_id"]] == 1
    assert data["events"] and all(e["result"] == "APPLIED" for e in data["events"])
    assert data["new_issue_codes"]
    assert data["notification"]["kind"] == "EXTERNAL_EVENTS"


def test_next_triggers_add_one_event_to_someone_else(client):
    trigger(client)
    for _ in range(3):
        data = trigger(client)
        assert data["featured"] is False
        assert data["customer_name"] != FEATURED_CUSTOMER
        assert len(data["events"]) == 1


def test_trigger_events_are_recorded_like_external_events(client):
    data = trigger(client)
    detail = client.get(f"/api/reservations/{data['reservation_id']}").get_json()["data"]

    external = [h for h in detail["history"] if h["event_label"] == "외부 이벤트"]
    assert len(external) == len(data["events"])
    assert all(f"출처: {SOURCE}" in h["description"] for h in external)
    recent = client.get("/api/events").get_json()["data"]["items"]
    assert recent[0]["source"] == SOURCE


def test_featured_boost_runs_again_after_data_reset(client):
    trigger(client)
    client.post("/api/demo/reset")
    assert trigger(client)["customer_name"] == FEATURED_CUSTOMER


def test_trigger_is_reproducible_with_seeded_random(app):
    def run():
        with app.app_context():
            from flask import current_app

            return EventTrigger(current_app.config["DB_PATH"], current_app.config["DATA_DIR"], rng=random.Random(7))

    data = run().trigger()
    assert data["after"]["rank"] == 1


def test_recurring_issue_counts_as_retry(client):
    before = client.get("/api/reservations/R2005").get_json()["data"]["retry_count"]
    client.post("/api/events", json={"예약번호": "R2005", "이벤트": "개통 반려", "사유": "재접수 후 재반려"})
    after = client.get("/api/reservations/R2005").get_json()["data"]
    assert after["retry_count"] == before + 1
    assert any("다시 발생" in h["description"] for h in after["history"])
