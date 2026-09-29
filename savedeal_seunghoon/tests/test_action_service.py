import pytest

from config import Config
from repositories.action_history_repository import ActionHistoryRepository
from repositories.proposed_action_repository import ProposedActionRepository
from repositories.reservation_repository import ReservationRepository
from services.action_service import ActionError, ActionService


@pytest.fixture
def service(db_path):
    return ActionService(db_path, Config.DATA_DIR)


def actions_of(db_path, reservation_id, status=None, issue_code=None):
    return [
        a
        for a in ProposedActionRepository(db_path).list_by_reservation(reservation_id)
        if (status is None or a["status"] == status) and (issue_code is None or a["issue_code"] == issue_code)
    ]


def proposed_types(db_path, reservation_id, issue_code):
    return {a["action_type"] for a in actions_of(db_path, reservation_id, "PROPOSED", issue_code)}


def test_stock_shortage_proposes_stock_alternatives(db_path):
    types = proposed_types(db_path, "R2001", "STOCK_SHORTAGE")
    assert {"NEARBY_STORE_TRANSFER", "COLOR_STORAGE_CHANGE", "ALTERNATIVE_DEVICE", "DATE_CHANGE"} <= types


def test_installment_limit_proposes_down_payment_and_term_adjustment(db_path):
    assert proposed_types(db_path, "R2002", "INSTALLMENT_LIMIT") == {"DOWN_PAYMENT", "INSTALLMENT_ADJUSTMENT"}


@pytest.mark.parametrize(
    "reservation_id, issue_code, action_type",
    [
        ("R2003", "MISSING_DOCUMENTS", "DOCUMENT_REQUEST"),
        ("R2013", "IDENTITY_FAILED", "IDENTITY_RETRY"),
        ("R2005", "ACTIVATION_REJECTED", "ACTIVATION_INPUT_FIX"),
        ("R2004", "CUSTOMER_NO_RESPONSE", "CUSTOMER_RECONTACT"),
    ],
)
def test_each_issue_gets_matching_action(db_path, reservation_id, issue_code, action_type):
    assert action_type in proposed_types(db_path, reservation_id, issue_code)


def test_approve_changes_action_and_reservation_status(db_path, service):
    action = actions_of(db_path, "R2002", "PROPOSED", "INSTALLMENT_LIMIT")[0]

    service.approve("R2002", action["action_id"])

    assert ProposedActionRepository(db_path).find_by_id(action["action_id"])["status"] == "APPROVED"
    assert ReservationRepository(db_path).find_by_id("R2002")["status"] == "IN_PROGRESS"
    # 같은 문제의 다른 제안은 보류되어 더 이상 승인 대상이 아니다.
    assert actions_of(db_path, "R2002", "PROPOSED", "INSTALLMENT_LIMIT") == []
    events = [h["event_type"] for h in ActionHistoryRepository(db_path).list_by_reservation("R2002")]
    assert "ACTION_APPROVED" in events
    assert "STATUS_CHANGED" in events


def test_success_resolves_issue_and_moves_to_ready(db_path, service):
    action = actions_of(db_path, "R2002", "PROPOSED", "INSTALLMENT_LIMIT")[0]
    service.approve("R2002", action["action_id"])

    service.succeed("R2002", action["action_id"])

    reservation = ReservationRepository(db_path).find_by_id("R2002")
    assert reservation["issues"] == []
    assert reservation["status"] == "READY"


def test_success_of_device_change_updates_reservation_device(db_path, service):
    action = next(a for a in actions_of(db_path, "R2001", "PROPOSED") if a["action_type"] == "COLOR_STORAGE_CHANGE")
    service.approve("R2001", action["action_id"])
    service.succeed("R2001", action["action_id"])

    assert ReservationRepository(db_path).find_by_id("R2001")["device"] == action["detail"]["device"]


def test_failure_increments_retry_and_regenerates_without_failed_option(db_path, service):
    action = next(a for a in actions_of(db_path, "R2001", "PROPOSED") if a["action_type"] == "NEARBY_STORE_TRANSFER")
    before = ReservationRepository(db_path).find_by_id("R2001")["retry_count"]
    service.approve("R2001", action["action_id"])

    new_ids = service.fail("R2001", action["action_id"])

    reservation = ReservationRepository(db_path).find_by_id("R2001")
    assert reservation["retry_count"] == before + 1
    assert reservation["status"] == "ACTION_REQUIRED"
    assert new_ids
    regenerated = proposed_types(db_path, "R2001", "STOCK_SHORTAGE")
    assert "NEARBY_STORE_TRANSFER" not in regenerated
    assert "COLOR_STORAGE_CHANGE" in regenerated


def test_escalation_when_every_option_failed(db_path, service):
    action = actions_of(db_path, "R2005", "PROPOSED", "ACTIVATION_REJECTED")[0]
    service.approve("R2005", action["action_id"])
    service.fail("R2005", action["action_id"])

    assert proposed_types(db_path, "R2005", "ACTIVATION_REJECTED") == {"MANAGER_ESCALATION"}


def test_cannot_approve_twice(db_path, service):
    action = actions_of(db_path, "R2003", "PROPOSED")[0]
    service.approve("R2003", action["action_id"])

    with pytest.raises(ActionError) as exc:
        service.approve("R2003", action["action_id"])
    assert exc.value.http_status == 409


def test_cannot_record_result_before_approval(db_path, service):
    action = actions_of(db_path, "R2003", "PROPOSED")[0]
    with pytest.raises(ActionError):
        service.fail("R2003", action["action_id"])


def test_complete_only_when_ready(db_path, service):
    with pytest.raises(ActionError):
        service.complete_activation("R2003")

    service.complete_activation("R2010")
    reservation = ReservationRepository(db_path).find_by_id("R2010")
    assert reservation["status"] == "COMPLETED"
    assert reservation["completed_at"] is not None
