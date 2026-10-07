"""더 줘 데모 데이터 (DB 연결 전 임시).

여기는 **데이터 접근 계층**이다. 계산은 하지 않는다. 계산은 services/ 에만 둔다.
나중에 CSV·Google Sheets·DB 로 바꿀 때 이 파일의 get_* 함수 본문만 교체하면 된다.
금액은 원 단위 정수.
"""
from datetime import date, timedelta

# 데모 기준일. 실제 데이터가 붙으면 date.today() 로 바꾼다.
# 지금 고정해 두는 이유: 화면의 "남은 일수"가 실행 날짜에 따라 흔들리면 테스트가 깨진다.
# 이 날짜여야 TX-202609-018 의 잔여 유지일수가 요구사항대로 정확히 150일이 된다.
DEMO_TODAY = date(2026, 10, 18)

# 이번 달 판매 현황
_SALES_SNAPSHOT = {
    "month": "2026-10",
    "units_sold": 9,
}

# 거래·고객 정보. Warning 카드의 transaction_id 로 여기를 찾는다.
# maintenance_end_date / remaining_days 는 저장하지 않고 activation_date +
# required_maintenance_days 로 계산한다 (services/transaction_service.py).
_TRANSACTIONS = [
    {
        "transaction_id": "TX-202609-018",
        "customer_id": "C-018",
        "customer_name": "정○현",
        "customer_phone": "010-1234-5678",
        "device_model": "Galaxy Z Fold",
        "plan_name": "초이스 프리미엄",
        "activation_date": date(2026, 9, 18),
        "required_maintenance_days": 180,
        "benefit_amount": 300_000,
        "expected_clawback": 300_000,
        "store_id": "STORE-01",
        "store_phone": "02-1234-5678",
    },
    {
        "transaction_id": "TX-202609-003",
        "customer_id": "C-003",
        "customer_name": "이○우",
        "customer_phone": "010-2345-6789",
        "device_model": "iPhone 17 Pro",
        "plan_name": "5G 스탠다드",
        "activation_date": date(2026, 9, 3),
        "required_maintenance_days": 180,
        "benefit_amount": 200_000,
        "expected_clawback": 200_000,
        "store_id": "STORE-01",
        "store_phone": "02-1234-5678",
    },
    {
        "transaction_id": "TX-202609-025",
        "customer_id": "C-025",
        "customer_name": "박○수",
        "customer_phone": "010-3456-7890",
        "device_model": "Galaxy S26",
        "plan_name": "5G 라이트",
        "activation_date": date(2026, 9, 25),
        "required_maintenance_days": 180,
        "benefit_amount": 50_000,
        "expected_clawback": 50_000,
        "store_id": "STORE-01",
        "store_phone": "02-1234-5678",
    },
    # ── 2026-10-06 부터 Google Sheets 위험 인사이트에 나오는 거래 ──
    # 시트(daily_insights)에는 거래 ID·마스킹 이름·단말·영향 금액만 있다.
    # 전화번호·요금제·개통일은 시트에 없어 **데모 값**이다. 실제 거래 데이터가 생기면 교체한다.
    # 전화번호는 실제 사람에게 문자가 가지 않도록 개통될 수 없는 010-0000-xxxx 를 쓴다.
    {
        "transaction_id": "TX-202610-008",
        "customer_id": "C-008",
        "customer_name": "정O현",
        "customer_phone": "010-0000-0008",
        "device_model": "갤럭시 S26",
        "plan_name": "5GX 레귤러",
        "activation_date": date(2026, 10, 1),
        "required_maintenance_days": 180,   # 시트 사유: "요금제 유지기간 180일"
        "benefit_amount": 320_000,
        "expected_clawback": 320_000,       # 시트 amount
        "store_id": "STORE-01",
        "store_phone": "02-1234-5678",
    },
    {
        "transaction_id": "TX-202610-009",
        "customer_id": "C-009",
        "customer_name": "박O수",
        "customer_phone": "010-0000-0009",
        "device_model": "아이폰 17 Pro 256GB",
        "plan_name": "5GX 프리미엄",
        "activation_date": date(2026, 10, 2),
        "required_maintenance_days": 180,
        "benefit_amount": 40_000,           # 시트 사유: "예상 수익 40,000원"
        "expected_clawback": 30_000,        # 시트 amount (최소 기준 대비 부족액)
        "store_id": "STORE-01",
        "store_phone": "02-1234-5678",
    },
]

# 위험 경고. kind: clawback(환수) / settlement(정산 불일치) / margin(마진 미달)
# 고객 정보는 여기에 두지 않는다. transaction_id 로 위 거래를 참조한다.
_WARNINGS = [
    {
        "id": "w-1",
        "transaction_id": "TX-202609-018",
        "level": "high",
        "kind": "clawback",
        "reason": "요금제 유지기간 미충족 가능성",
        "expected_loss": 300_000,
        "check_date": DEMO_TODAY + timedelta(days=12),
        "action": "고객에게 유지조건 안내 문자를 보내고, 요금제 변경 예약이 걸려 있는지 확인하세요.",
        "detail": (
            "고객센터에 요금제 하향을 문의한 이력이 있습니다. 정책상 요금제를 필수 유지기간 동안 "
            "유지해야 인센티브가 확정됩니다. 유지기간 안에 요금제를 하향하면 이미 지급된 "
            "인센티브 30만 원이 환수됩니다."
        ),
    },
    {
        "id": "w-2",
        "transaction_id": "TX-202609-003",
        "level": "medium",
        "kind": "settlement",
        "reason": "실제 정산액과 예상 정산액 불일치",
        "expected_loss": 200_000,
        "check_date": DEMO_TODAY + timedelta(days=6),
        "action": "정산서의 정책 코드와 개통 시 적용한 정책이 같은지 대조하고, 다르면 대리점에 이의를 제기하세요.",
        "detail": (
            "이번 달 예상 정산액보다 실제 입금액이 20만 원 적습니다. "
            "개통 당시 적용한 특별 정책이 정산에 반영되지 않았을 가능성이 있습니다. "
            "이의 제기 기한은 정산일로부터 30일입니다."
        ),
    },
    {
        "id": "w-3",
        "transaction_id": "TX-202609-025",
        "level": "high",
        "kind": "margin",
        "reason": "고객 혜택 제공 후 최소 마진 기준 미달",
        "expected_loss": 50_000,
        "check_date": DEMO_TODAY + timedelta(days=1),
        "action": "지원금을 5만 원 줄이거나, 부가서비스를 함께 유치해 마진을 메우세요.",
        "detail": (
            "이 건은 고객 지원금을 올려 잡아 최소 마진 기준보다 5만 원이 부족합니다. "
            "이번 달 마감 전에 조정하지 않으면 그대로 손실로 남습니다."
        ),
    },
]

# 수익 기회. 계산에 필요한 **입력값**만 둔다. 증가액·혜택 가능액은 services 가 계산한다.
_OPPORTUNITIES = [
    {
        "id": "o-1",
        "title": "인센티브 구간 상향",
        "kind": "tier_upgrade",
        "note": "이번 달 마감까지 3일 남았습니다.",
    },
]


def get_sales_snapshot():
    """이번 달 판매 현황."""
    return dict(_SALES_SNAPSHOT)


def get_warnings():
    """위험 경고 원본 목록."""
    return [dict(w) for w in _WARNINGS]


def get_transactions():
    """거래·고객 원본 목록."""
    return [dict(t) for t in _TRANSACTIONS]


def get_transaction(transaction_id):
    """거래 한 건. 없으면 None."""
    for raw in _TRANSACTIONS:
        if raw["transaction_id"] == transaction_id:
            return dict(raw)
    return None


def get_opportunities():
    """수익 기회 원본 목록."""
    return [dict(o) for o in _OPPORTUNITIES]
