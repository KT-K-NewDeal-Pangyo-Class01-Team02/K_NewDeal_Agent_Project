from pathlib import Path

from repositories.customer_repository import CustomerRepository
from repositories.device_repository import DeviceRepository

RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"


class ActivationRiskService:
    """할부한도, 미납여부, 보유회선, 본인인증, 서류를 확인해 개통반려 위험을 low/medium/high로 분류한다."""

    def __init__(self, data_dir: Path, db_path=None):
        self.customer_repo = CustomerRepository(data_dir, db_path)
        self.device_repo = DeviceRepository(data_dir)

    def check(self, customer_id: str, device: dict) -> dict:
        customer = self.customer_repo.find_by_id(customer_id)

        if customer is None:
            return {
                "risk_level": RISK_HIGH,
                "checks": {
                    "installment_limit_ok": None,
                    "shortfall_amount": None,
                    "overdue_payment": None,
                    "line_limit_ok": None,
                    "identity_verified": None,
                    "missing_documents": [],
                },
                "issues": ["고객 정보를 찾을 수 없습니다."],
            }

        device_info = self.device_repo.find_by_spec(device["model"], device["color"], device["storage"])
        issues = []

        if device_info is None:
            installment_limit_ok = None
            shortfall_amount = None
            issues.append("기기 가격 정보를 찾을 수 없어 할부한도 검증을 생략합니다.")
        else:
            device_price = device_info["price"]
            installment_limit_ok = device_price <= customer["installment_limit"]
            shortfall_amount = max(0, device_price - customer["installment_limit"])
            if not installment_limit_ok:
                issues.append(
                    f"할부한도 부족: 단말가 {device_price:,}원 / 한도 {customer['installment_limit']:,}원"
                )

        overdue_payment = customer["overdue_payment"]
        if overdue_payment:
            issues.append("통신요금 미납 내역이 있습니다.")

        line_limit_ok = customer["existing_lines_count"] < customer["max_lines_allowed"]
        if not line_limit_ok:
            issues.append(
                f"보유 회선 수 초과: {customer['existing_lines_count']}/{customer['max_lines_allowed']}"
            )

        identity_verified = customer["identity_verified"]
        if not identity_verified:
            issues.append("본인인증이 완료되지 않았습니다.")

        missing_documents = [
            doc for doc in customer["required_documents"] if doc not in customer["submitted_documents"]
        ]
        if missing_documents:
            issues.append(f"제출 서류 누락: {', '.join(missing_documents)}")

        if overdue_payment or not identity_verified or not line_limit_ok:
            risk_level = RISK_HIGH
        elif installment_limit_ok is False or missing_documents:
            risk_level = RISK_MEDIUM
        else:
            risk_level = RISK_LOW

        return {
            "risk_level": risk_level,
            "checks": {
                "installment_limit_ok": installment_limit_ok,
                "shortfall_amount": shortfall_amount,
                "overdue_payment": overdue_payment,
                "line_limit_ok": line_limit_ok,
                "identity_verified": identity_verified,
                "missing_documents": missing_documents,
            },
            "issues": issues,
        }
