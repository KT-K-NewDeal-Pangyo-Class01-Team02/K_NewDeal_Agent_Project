NEW_RESERVATION = {
    "customer_id": "C004",
    "store_id": "S001",
    "device": {"model": "iPhone 16", "color": "Blue", "storage": "128GB"},
    "desired_activation_date": "2026-10-05",
    "line_type": "MNP",
}


def test_list_reservations_default_filter(client):
    response = client.get("/api/reservations")
    body = response.get_json()

    assert response.status_code == 200
    assert body["success"] is True
    assert body["data"]["filter"] == "all"
    assert len(body["data"]["items"]) >= 15
    assert {"open", "needs_action", "high_risk", "due_today"} <= set(body["data"]["summary"])


def test_list_reservations_invalid_filter_returns_400(client):
    response = client.get("/api/reservations?filter=nope")

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "VALIDATION_ERROR"


def test_get_reservation_detail_and_404(client):
    assert client.get("/api/reservations/R2001").get_json()["data"]["reservation_id"] == "R2001"

    response = client.get("/api/reservations/R9999")
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "NOT_FOUND"


def _first_action(client, reservation_id):
    return client.get(f"/api/reservations/{reservation_id}").get_json()["data"]["actions"][0]


def test_approve_then_fail_regenerates_and_refreshes_priority(client):
    before = client.get("/api/reservations/R2003").get_json()["data"]
    action = before["actions"][0]

    approved = client.post(f"/api/reservations/R2003/actions/{action['action_id']}/approve").get_json()["data"]
    assert approved["status"] == "IN_PROGRESS"
    assert approved["actions"][0]["can_record_result"] is True

    failed = client.post(f"/api/reservations/R2003/actions/{action['action_id']}/fail").get_json()["data"]
    assert failed["status"] == "ACTION_REQUIRED"
    assert failed["retry_count"] == before["retry_count"] + 1
    assert failed["priority_score"] > before["priority_score"]
    assert all(a["action_id"] != action["action_id"] for a in failed["actions"])
    assert failed["actions"], "실패 후 새 대안이 생성되어야 한다"


def test_approve_then_succeed_then_complete(client):
    action = _first_action(client, "R2002")
    client.post(f"/api/reservations/R2002/actions/{action['action_id']}/approve")

    succeeded = client.post(f"/api/reservations/R2002/actions/{action['action_id']}/succeed").get_json()["data"]
    assert succeeded["status"] == "READY"
    assert succeeded["can_complete"] is True

    completed = client.post("/api/reservations/R2002/complete").get_json()["data"]
    assert completed["status"] == "COMPLETED"
    completed_ids = [
        item["reservation_id"]
        for item in client.get("/api/reservations?filter=completed").get_json()["data"]["items"]
    ]
    assert "R2002" in completed_ids


def test_approving_processed_action_returns_409(client):
    action = _first_action(client, "R2003")
    client.post(f"/api/reservations/R2003/actions/{action['action_id']}/approve")

    response = client.post(f"/api/reservations/R2003/actions/{action['action_id']}/approve")
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "INVALID_STATE"


def test_action_of_other_reservation_returns_404(client):
    action = _first_action(client, "R2003")
    response = client.post(f"/api/reservations/R2002/actions/{action['action_id']}/approve")
    assert response.status_code == 404


def test_create_reservation_runs_precheck_and_proposes_actions(client):
    response = client.post("/api/reservations", json=NEW_RESERVATION)
    data = response.get_json()["data"]

    assert response.status_code == 201
    assert data["customer_name"] == "최민호"
    issue_codes = {issue["code"] for issue in data["issues"]}
    assert {"STOCK_SHORTAGE", "INSTALLMENT_LIMIT"} <= issue_codes
    action_types = {action["action_type"] for action in data["actions"]}
    assert {"NEARBY_STORE_TRANSFER", "DOWN_PAYMENT"} <= action_types

    listed = [item["reservation_id"] for item in client.get("/api/reservations").get_json()["data"]["items"]]
    assert data["reservation_id"] in listed


def test_create_reservation_without_issues_is_ready(client):
    payload = {**NEW_RESERVATION, "customer_id": "C001", "device": {"model": "GalaxyZ Fold6", "color": "Black", "storage": "256GB"}}
    data = client.post("/api/reservations", json=payload).get_json()["data"]

    assert data["issues"] == []
    assert data["status"] == "READY"


def test_create_reservation_validation_error(client):
    response = client.post("/api/reservations", json={"customer_id": "C001"})
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "VALIDATION_ERROR"


def test_demo_reset_restores_mock_data(client):
    client.post("/api/reservations", json=NEW_RESERVATION)
    assert client.post("/api/demo/reset").status_code == 200

    items = client.get("/api/reservations").get_json()["data"]["items"]
    assert len(items) == 17


def _items(client, query):
    response = client.get(f"/api/reservations?{query}")
    assert response.status_code == 200
    return response.get_json()["data"]["items"]


def test_status_incomplete_returns_open_reservations_by_priority(client):
    items = _items(client, "status=incomplete")
    scores = [item["priority_score"] for item in items]

    assert items and all(item["is_open"] for item in items)
    assert scores == sorted(scores, reverse=True)


def test_status_completed_returns_only_completed(client):
    items = _items(client, "status=completed")
    assert items and all(item["status"] == "COMPLETED" for item in items)


def test_risk_high_returns_only_high_risk_open_reservations(client):
    items = _items(client, "risk=high")
    assert items and all(item["risk_level"] == "high" and item["is_open"] for item in items)


def test_status_and_risk_can_be_combined(client):
    assert _items(client, "status=incomplete&risk=high") == _items(client, "risk=high")


def test_invalid_status_or_risk_returns_400(client):
    assert client.get("/api/reservations?status=done").status_code == 400
    assert client.get("/api/reservations?risk=extreme").status_code == 400
