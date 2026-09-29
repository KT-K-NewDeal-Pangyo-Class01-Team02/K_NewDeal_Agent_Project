VALID_PAYLOAD = {
    "customer_id": "C001",
    "store_id": "S001",
    "device": {"model": "GalaxyZ Fold6", "color": "Black", "storage": "256GB"},
    "desired_activation_date": "2026-10-05",
    "line_type": "NEW",
}


def test_precheck_missing_required_field_returns_400(client):
    payload = dict(VALID_PAYLOAD)
    del payload["customer_id"]

    response = client.post("/api/precheck", json=payload)
    assert response.status_code == 400

    body = response.get_json()
    assert body["success"] is False
    assert body["data"] is None
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_precheck_invalid_line_type_returns_400(client):
    payload = dict(VALID_PAYLOAD)
    payload["line_type"] = "INVALID"

    response = client.post("/api/precheck", json=payload)
    assert response.status_code == 400


def test_precheck_unknown_customer_reports_not_found(client):
    payload = dict(VALID_PAYLOAD)
    payload["customer_id"] = "C999"

    response = client.post("/api/precheck", json=payload)
    assert response.status_code == 200
    assert response.get_json()["data"]["lookup"]["customer_found"] is False


# 1. 모든 조건 충족 -> feasible
def test_precheck_feasible_when_all_conditions_met(client):
    response = client.post("/api/precheck", json=VALID_PAYLOAD)
    assert response.status_code == 200

    data = response.get_json()["data"]
    assert data["inventory_check"]["status"] == "available"
    assert data["activation_risk_check"]["risk_level"] == "low"
    assert data["overall_verdict"] == "feasible"
    assert data["alternatives"] == []
    assert data["churn_risk_score"] is None
    assert data["recommended_action"] is None


# 2. 현재 매장 재고 없음, 인근 매장 재고 있음 -> conditional
def test_precheck_conditional_when_nearby_store_has_stock(client):
    payload = {
        **VALID_PAYLOAD,
        "device": {"model": "iPhone 16", "color": "Blue", "storage": "128GB"},
    }

    response = client.post("/api/precheck", json=payload)
    data = response.get_json()["data"]

    assert data["inventory_check"]["status"] == "conditional"
    assert data["overall_verdict"] == "conditional"
    assert any(a["type"] == "NEARBY_STORE_TRANSFER" for a in data["alternatives"])


# 3. 입고일이 고객 희망일보다 늦음 -> conditional
def test_precheck_conditional_when_restock_after_desired_date(client):
    payload = {
        **VALID_PAYLOAD,
        "device": {"model": "GalaxyZ Fold6", "color": "Silver", "storage": "512GB"},
        "desired_activation_date": "2026-10-05",
    }

    response = client.post("/api/precheck", json=payload)
    data = response.get_json()["data"]

    assert data["inventory_check"]["status"] == "conditional"
    assert data["overall_verdict"] == "conditional"
    assert any(a["type"] == "DATE_CHANGE" for a in data["alternatives"])


# 4. 할부한도 부족 -> 선납금 대안 생성
def test_precheck_installment_shortfall_generates_down_payment_alternative(client):
    payload = {**VALID_PAYLOAD, "customer_id": "C004"}

    response = client.post("/api/precheck", json=payload)
    data = response.get_json()["data"]

    assert data["activation_risk_check"]["risk_level"] == "medium"
    assert any(a["type"] == "DOWN_PAYMENT" for a in data["alternatives"])
    assert data["overall_verdict"] == "conditional"


# 5. 미납 고객 -> high_risk
def test_precheck_overdue_customer_is_high_risk(client):
    payload = {**VALID_PAYLOAD, "customer_id": "C002"}

    response = client.post("/api/precheck", json=payload)
    data = response.get_json()["data"]

    assert data["activation_risk_check"]["risk_level"] == "high"
    assert data["overall_verdict"] == "high_risk"


# 6. 필요서류 누락 -> conditional
def test_precheck_missing_documents_generates_document_request_alternative(client):
    payload = {**VALID_PAYLOAD, "customer_id": "C003"}

    response = client.post("/api/precheck", json=payload)
    data = response.get_json()["data"]

    assert data["activation_risk_check"]["risk_level"] == "medium"
    assert any(a["type"] == "DOCUMENT_REQUEST" for a in data["alternatives"])
    assert data["overall_verdict"] == "conditional"


# 7. 재고와 개통위험이 동시에 존재 -> 위험 사유 모두 반환
def test_precheck_returns_all_issues_when_inventory_and_risk_both_fail(client):
    payload = {
        **VALID_PAYLOAD,
        "customer_id": "C002",
        "device": {"model": "iPhone 16", "color": "Blue", "storage": "128GB"},
    }

    response = client.post("/api/precheck", json=payload)
    data = response.get_json()["data"]

    assert data["inventory_check"]["issues"]
    assert data["activation_risk_check"]["issues"]
    assert data["overall_verdict"] == "high_risk"
