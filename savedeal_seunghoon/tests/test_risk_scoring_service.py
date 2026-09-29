from datetime import datetime, timedelta

from services.risk_scoring_service import calculate_churn_risk, calculate_priority

NOW = datetime(2026, 9, 29, 12, 0, 0)


def make_reservation(**overrides):
    reservation = {
        "status": "ACTION_REQUIRED",
        "issues": [],
        "retry_count": 0,
        "activation_deadline": (NOW + timedelta(days=5)).isoformat(),
        "customer_waiting_since": NOW.isoformat(),
    }
    reservation.update(overrides)
    return reservation


def test_overdue_customer_with_many_issues_scores_high():
    reservation = make_reservation(
        issues=[{"code": "STOCK_SHORTAGE"}, {"code": "INSTALLMENT_LIMIT"}, {"code": "CUSTOMER_NO_RESPONSE"}],
        activation_deadline=(NOW - timedelta(hours=2)).isoformat(),
        customer_waiting_since=(NOW - timedelta(hours=60)).isoformat(),
        retry_count=2,
    )

    churn = calculate_churn_risk(reservation, NOW)
    priority = calculate_priority(reservation, NOW)

    assert churn["level"] == "high"
    assert churn["score"] <= 100
    assert any(f["label"] == "개통 마감 초과" for f in priority["factors"])


def test_deadline_near_ranks_above_same_issue_far_deadline():
    issues = [{"code": "MISSING_DOCUMENTS"}]
    near = make_reservation(issues=issues, activation_deadline=(NOW + timedelta(hours=3)).isoformat())
    far = make_reservation(issues=issues, activation_deadline=(NOW + timedelta(days=6)).isoformat())

    assert calculate_priority(near, NOW)["score"] > calculate_priority(far, NOW)["score"]


def test_retry_count_raises_priority():
    issues = [{"code": "IDENTITY_FAILED"}]
    fresh = make_reservation(issues=issues)
    retried = make_reservation(issues=issues, retry_count=2)

    assert calculate_priority(retried, NOW)["score"] > calculate_priority(fresh, NOW)["score"]
    assert calculate_churn_risk(retried, NOW)["score"] > calculate_churn_risk(fresh, NOW)["score"]


def test_activation_rejection_and_stock_add_priority_factors():
    reservation = make_reservation(issues=[{"code": "ACTIVATION_REJECTED"}, {"code": "STOCK_SHORTAGE"}])
    labels = {f["label"] for f in calculate_priority(reservation, NOW)["factors"]}

    assert {"개통 반려", "재고 미확보"} <= labels


def test_closed_reservation_has_zero_scores():
    reservation = make_reservation(status="COMPLETED", issues=[{"code": "STOCK_SHORTAGE"}])

    assert calculate_priority(reservation, NOW)["score"] == 0
    assert calculate_churn_risk(reservation, NOW)["score"] == 0


def test_no_issues_means_no_churn_risk():
    reservation = make_reservation(
        activation_deadline=(NOW + timedelta(hours=2)).isoformat(),
        customer_waiting_since=(NOW - timedelta(hours=50)).isoformat(),
    )

    assert calculate_churn_risk(reservation, NOW) == {"score": 0, "level": "low", "factors": []}
