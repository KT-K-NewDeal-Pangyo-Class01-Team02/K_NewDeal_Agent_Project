"""/savedeal/new 에서 입력한 신규 예약을 사전검증한 뒤 운영 DB에 등록한다.

사전검증 결과(재고·개통위험)를 문제 원인(issues)으로 바꿔 저장하고, 바로 해결책을 생성한다.
"""
from datetime import datetime
from pathlib import Path

from repositories.action_history_repository import ActionHistoryRepository
from repositories.customer_repository import CustomerRepository
from repositories.inventory_repository import InventoryRepository
from repositories.reservation_repository import ReservationRepository
from services.action_service import ACTIVATION_DEADLINE_TIME, ActionService
from services.codes import (
    EVENT_ISSUE_DETECTED,
    EVENT_RESERVATION_CREATED,
    ISSUE_IDENTITY_FAILED,
    ISSUE_INSTALLMENT_LIMIT,
    ISSUE_LABELS,
    ISSUE_MISSING_DOCUMENTS,
    ISSUE_OVERDUE_PAYMENT,
    ISSUE_STOCK_SHORTAGE,
    STATUS_ACTION_REQUIRED,
)
from services.inventory_service import STATUS_AVAILABLE
from services.precheck_service import PrecheckService


def issues_from_precheck(precheck: dict, alt_device: dict | None = None) -> list[dict]:
    """사전검증 결과를 운영용 문제 원인 목록으로 바꾼다."""
    issues = []
    inventory = precheck["inventory_check"]
    if inventory["status"] != STATUS_AVAILABLE:
        issues.append(
            {
                "code": ISSUE_STOCK_SHORTAGE,
                "detail": {
                    "nearby_stores": [
                        {
                            "store_id": option["store_id"],
                            "quantity": option["quantity_on_hand"],
                            "lead_days": option["transfer_lead_days"],
                        }
                        for option in inventory["nearby_options"]
                    ],
                    "alt_specs": [
                        {"color": alt["detail"]["color"], "storage": alt["detail"]["storage"]}
                        for alt in precheck["alternatives"]
                        if alt["type"] == "COLOR_STORAGE_CHANGE"
                    ],
                    "alt_device": alt_device,
                    "restock_date": next(
                        (alt["detail"]["suggested_date"] for alt in precheck["alternatives"] if alt["type"] == "DATE_CHANGE"),
                        None,
                    ),
                },
            }
        )

    checks = precheck["activation_risk_check"]["checks"]
    if checks.get("shortfall_amount"):
        issues.append({"code": ISSUE_INSTALLMENT_LIMIT, "detail": {"shortfall_amount": checks["shortfall_amount"]}})
    if checks.get("missing_documents"):
        issues.append({"code": ISSUE_MISSING_DOCUMENTS, "detail": {"documents": checks["missing_documents"]}})
    if checks.get("identity_verified") is False:
        issues.append(
            {"code": ISSUE_IDENTITY_FAILED, "detail": {"method": "휴대폰 본인인증", "reason": "본인인증 미완료"}}
        )
    if checks.get("overdue_payment"):
        issues.append({"code": ISSUE_OVERDUE_PAYMENT, "detail": {}})
    return issues


class ReservationService:
    def __init__(self, db_path, data_dir: Path, clock=datetime.now):
        self.reservation_repo = ReservationRepository(db_path)
        self.history_repo = ActionHistoryRepository(db_path)
        self.customer_repo = CustomerRepository(data_dir)
        self.inventory_repo = InventoryRepository(data_dir)
        self.precheck_service = PrecheckService(data_dir)
        self.action_service = ActionService(db_path, data_dir, clock)
        self.clock = clock

    def _find_alt_device(self, store_id: str, device: dict) -> dict | None:
        """방문 매장에 재고가 있는 다른 모델을 대체 단말 후보로 고른다."""
        for item in self.inventory_repo.load_all():
            if item["store_id"] == store_id and item["model"] != device["model"] and item["quantity_on_hand"] > 0:
                return {"model": item["model"], "color": item["color"], "storage": item["storage"]}
        return None

    def create(self, payload: dict) -> tuple[str, dict]:
        precheck = self.precheck_service.run(payload)
        device = payload["device"]
        alt_device = None
        if precheck["inventory_check"]["status"] != STATUS_AVAILABLE:
            alt_device = self._find_alt_device(payload["store_id"], device)
        issues = issues_from_precheck(precheck, alt_device)

        customer = self.customer_repo.find_by_id(payload["customer_id"]) or {}
        now = self.clock().isoformat(timespec="seconds")
        reservation_id = self.reservation_repo.next_id()

        self.reservation_repo.insert(
            {
                "reservation_id": reservation_id,
                "customer_id": payload["customer_id"],
                "customer_name": customer.get("name") or f"고객 {payload['customer_id']}",
                "customer_phone": customer.get("phone"),
                "store_id": payload["store_id"],
                "device": device,
                "line_type": payload["line_type"],
                "previous_carrier": payload.get("previous_carrier") if payload["line_type"] == "MNP" else None,
                "desired_activation_date": payload["desired_activation_date"],
                "activation_deadline": f"{payload['desired_activation_date']}T{ACTIVATION_DEADLINE_TIME}",
                "status": STATUS_ACTION_REQUIRED,
                "issues": issues,
                "retry_count": 0,
                "customer_waiting_since": now,
                "created_at": now,
                "updated_at": now,
                "completed_at": None,
            }
        )
        self.history_repo.add(reservation_id, EVENT_RESERVATION_CREATED, "신규 예약을 등록하고 사전검증을 실행했습니다.", now)
        if issues:
            labels = ", ".join(ISSUE_LABELS[issue["code"]] for issue in issues)
            self.history_repo.add(reservation_id, EVENT_ISSUE_DETECTED, f"사전검증에서 문제를 감지했습니다: {labels}", now)

        reservation = self.reservation_repo.find_by_id(reservation_id)
        self.action_service.propose(reservation)
        self.action_service.refresh_status(reservation_id)
        return reservation_id, precheck
