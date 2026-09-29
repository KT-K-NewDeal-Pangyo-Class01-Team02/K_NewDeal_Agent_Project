"""거래·고객 정보 조회.

유지 종료일과 남은 일수는 **저장하지 않고 계산한다**. 개통일과 필수 유지일수만 있으면
언제나 같은 답이 나오고, 두 값이 서로 어긋날 일도 없다.
"""
from datetime import timedelta

from thejo_project.data import demo_data, sms_store


def _decorate(raw):
    """거래 원본에 계산값과 문자 발송 상태를 붙인다."""
    tx = dict(raw)
    activation = tx["activation_date"]
    required = tx["required_maintenance_days"]

    tx["maintenance_end_date"] = activation + timedelta(days=required)
    tx["maintained_days"] = max(0, (demo_data.DEMO_TODAY - activation).days)
    tx["remaining_days"] = max(0, (tx["maintenance_end_date"] - demo_data.DEMO_TODAY).days)

    last_sms = sms_store.latest_by_transaction().get(tx["transaction_id"])
    tx["sms_status"] = "발송 완료" if last_sms else "미발송"
    tx["last_sms"] = last_sms
    return tx


def get_transaction(transaction_id):
    """거래 한 건(계산값 포함). 없으면 None."""
    raw = demo_data.get_transaction(transaction_id)
    return _decorate(raw) if raw else None


def get_transactions():
    return [_decorate(raw) for raw in demo_data.get_transactions()]


def to_json(tx):
    """모달이 쓰는 JSON. date 객체를 문자열로 바꾸고, 화면 표기도 함께 담는다."""
    return {
        "transaction_id": tx["transaction_id"],
        "customer_id": tx["customer_id"],
        "customer_name": tx["customer_name"],
        "customer_phone": tx["customer_phone"],
        "device_model": tx["device_model"],
        "plan_name": tx["plan_name"],
        "activation_date": tx["activation_date"].isoformat(),
        "required_maintenance_days": tx["required_maintenance_days"],
        "maintenance_end_date": tx["maintenance_end_date"].isoformat(),
        "maintained_days": tx["maintained_days"],
        "remaining_days": tx["remaining_days"],
        "benefit_amount": tx["benefit_amount"],
        "expected_clawback": tx["expected_clawback"],
        "store_id": tx["store_id"],
        "store_phone": tx["store_phone"],
        "sms_status": tx["sms_status"],
        "last_sms": _sms_summary(tx["last_sms"]),
    }


def _sms_summary(record):
    if not record:
        return None
    return {
        "sms_id": record.get("sms_id"),
        "template_id": record.get("template_id"),
        "sent_at": record.get("sent_at"),
        "message": record.get("message"),
    }
