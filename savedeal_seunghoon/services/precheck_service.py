from pathlib import Path

from repositories.customer_repository import CustomerRepository
from repositories.device_repository import DeviceRepository
from repositories.store_repository import StoreRepository
from services.activation_risk_service import RISK_HIGH, RISK_LOW
from services.activation_risk_service import ActivationRiskService
from services.alternative_service import AlternativeService
from services.inventory_service import STATUS_AVAILABLE, STATUS_UNAVAILABLE
from services.inventory_service import InventoryService

VERDICT_FEASIBLE = "feasible"
VERDICT_CONDITIONAL = "conditional"
VERDICT_HIGH_RISK = "high_risk"


def _determine_overall_verdict(inventory_status: str, risk_level: str) -> str:
    if risk_level == RISK_HIGH:
        return VERDICT_HIGH_RISK
    if inventory_status == STATUS_UNAVAILABLE:
        return VERDICT_HIGH_RISK
    if inventory_status == STATUS_AVAILABLE and risk_level == RISK_LOW:
        return VERDICT_FEASIBLE
    return VERDICT_CONDITIONAL


class PrecheckService:
    """재고·일정 검증, 개통위험 검증, 대체조건 생성을 조합해 종합 판정을 반환한다.
    이탈 위험 점수화(churn_risk_score)와 Next Best Action 추천(recommended_action)은 이후 단계에서 구현한다."""

    def __init__(self, data_dir: Path, db_path=None):
        self.customer_repo = CustomerRepository(data_dir, db_path)
        self.store_repo = StoreRepository(data_dir)
        self.device_repo = DeviceRepository(data_dir)
        self.inventory_service = InventoryService(data_dir, db_path)
        self.activation_risk_service = ActivationRiskService(data_dir, db_path)
        self.alternative_service = AlternativeService(data_dir, db_path)

    def run(self, request_data: dict) -> dict:
        device = request_data["device"]
        store_id = request_data["store_id"]
        customer_id = request_data["customer_id"]
        desired_date = request_data["desired_activation_date"]

        customer_found = self.customer_repo.find_by_id(customer_id) is not None
        store_found = self.store_repo.find_by_id(store_id) is not None
        device_found = (
            self.device_repo.find_by_spec(device["model"], device["color"], device["storage"]) is not None
        )

        inventory_result = self.inventory_service.check(store_id, device, desired_date)
        risk_result = self.activation_risk_service.check(customer_id, device)
        alternatives = self.alternative_service.generate(store_id, device, inventory_result, risk_result)
        overall_verdict = _determine_overall_verdict(inventory_result["status"], risk_result["risk_level"])

        return {
            "reservation_id": request_data.get("reservation_id"),
            "customer_id": customer_id,
            "store_id": store_id,
            "device": device,
            "desired_activation_date": desired_date,
            "line_type": request_data["line_type"],
            "lookup": {
                "customer_found": customer_found,
                "store_found": store_found,
                "device_found": device_found,
            },
            "inventory_check": inventory_result,
            "activation_risk_check": risk_result,
            "alternatives": alternatives,
            "overall_verdict": overall_verdict,
            "churn_risk_score": None,
            "recommended_action": None,
        }
