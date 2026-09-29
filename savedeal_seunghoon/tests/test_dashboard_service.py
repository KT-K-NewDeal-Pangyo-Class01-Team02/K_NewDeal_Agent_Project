import pytest

from config import Config
from services.dashboard_service import DashboardService


@pytest.fixture
def dashboard(db_path):
    return DashboardService(db_path, Config.DATA_DIR)


def test_mock_data_covers_required_cases(dashboard):
    items = dashboard.list_reservations("all")["items"]
    issue_codes = {issue["code"] for item in items for issue in item["issues"]}

    assert len(items) >= 15
    assert {
        "STOCK_SHORTAGE",
        "INSTALLMENT_LIMIT",
        "MISSING_DOCUMENTS",
        "CUSTOMER_NO_RESPONSE",
        "ACTIVATION_REJECTED",
    } <= issue_codes
    statuses = {item["status"] for item in items}
    assert {"ACTION_REQUIRED", "COMPLETED"} <= statuses
    assert any(item["risk_level"] == "high" for item in items)


def test_open_reservations_sorted_by_priority_and_closed_at_bottom(dashboard):
    items = dashboard.list_reservations("all")["items"]
    open_scores = [item["priority_score"] for item in items if item["is_open"]]
    open_flags = [item["is_open"] for item in items]

    assert open_scores == sorted(open_scores, reverse=True)
    assert open_flags == sorted(open_flags, reverse=True)


def test_filters_return_matching_items(dashboard):
    completed = dashboard.list_reservations("completed")["items"]
    high_risk = dashboard.list_reservations("high_risk")["items"]
    due_today = dashboard.list_reservations("due_today")["items"]
    needs_action = dashboard.list_reservations("needs_action")["items"]

    assert completed and all(not item["is_open"] for item in completed)
    assert high_risk and all(item["risk_level"] == "high" for item in high_risk)
    assert due_today and all(item["is_due_today"] for item in due_today)
    assert all(item["status"] in ("ACTION_REQUIRED", "IN_PROGRESS") for item in needs_action)


def test_filter_counts_match_items(dashboard):
    result = dashboard.list_reservations("all")
    for filter_info in result["filters"]:
        assert filter_info["count"] == len(dashboard.list_reservations(filter_info["key"])["items"])


def test_invalid_filter_raises(dashboard):
    with pytest.raises(ValueError):
        dashboard.list_reservations("unknown")


def test_detail_contains_panel_sections(dashboard):
    detail = dashboard.get_detail("R2007")

    assert detail["customer_name"]
    assert detail["status_label"]
    assert detail["issues"] and detail["issues"][0]["summary"]
    assert detail["churn_risk_score"] > 0
    assert detail["deadline_label"]
    assert detail["history"]
    assert detail["actions"] and all(action["can_approve"] for action in detail["actions"])
    assert detail["past_actions"] and all(a["status"] == "FAILED" for a in detail["past_actions"])
    assert detail["retry_count"] == 2


def test_detail_of_unknown_reservation_is_none(dashboard):
    assert dashboard.get_detail("R9999") is None
