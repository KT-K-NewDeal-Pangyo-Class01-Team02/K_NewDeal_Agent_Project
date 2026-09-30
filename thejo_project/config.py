"""더 줘 정책·템플릿 상수.

정책이나 문구가 바뀌면 이 파일만 고치면 된다. 계산 로직(services/)과 화면(templates/)은 건드리지 않는다.
금액은 모두 **원 단위 정수**로 다룬다. 만 원 표기는 화면에서만 한다.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# .env 를 읽는다. command_center/app.py 는 command_center/.env 만 읽으므로 여기서 따로 챙긴다.
# load_dotenv 는 이미 설정된 값을 덮어쓰지 않으니 **먼저 읽은 쪽이 이긴다**.
#   1순위: thejo_project/.env  (더 줘 전용)
#   2순위: 저장소 루트 .env    (팀 공용)
_HERE = Path(__file__).resolve().parent
load_dotenv(_HERE / ".env")
load_dotenv(_HERE.parent / ".env")

# ── 인센티브 정책 ────────────────────────────────────────────────────────
# 월 누적 판매량에 따른 건당 인센티브 구간.
# max_units 가 None 이면 상한 없음. 구간을 달성하면 그 달의 **모든 판매 건**에 상향 단가가 소급 적용된다.
INCENTIVE_TIERS = [
    {"min_units": 1, "max_units": 9, "per_unit": 100_000},
    {"min_units": 10, "max_units": 19, "per_unit": 200_000},
]

# 판매점이 반드시 확보해야 하는 최소 수익. 이 금액을 넘는 부분만 고객 혜택으로 쓸 수 있다.
MINIMUM_SECURED_PROFIT = 700_000


# ── 문자(SMS/LMS) ────────────────────────────────────────────────────────
# 이 바이트 수 이하면 SMS, 넘으면 LMS. 한글은 2바이트로 센다(EUC-KR 기준).
SMS_BYTE_LIMIT = 90

# n8n 문자 발송 워크플로우. 비워 두면 실제 발송 없이 데모 성공을 돌려준다.
# 이 값은 **서버에서만** 읽는다. 절대 템플릿이나 JS 로 내려보내지 않는다.
N8N_SMS_WEBHOOK_URL = os.getenv("N8N_SMS_WEBHOOK_URL", "").strip()
N8N_SMS_TIMEOUT = float(os.getenv("N8N_SMS_TIMEOUT", "10"))

# 문자 템플릿. {중괄호} 변수는 sms_service 가 거래 데이터로 치환한다.
SMS_TEMPLATES = [
    {
        "id": "PLAN_MAINTENANCE",
        "label": "유지조건 안내",
        "body": (
            "{고객명} 고객님, 현재 이용 중인 {요금제명} 요금제를 {유지 종료일}까지 유지하시면 "
            "가입 당시 안내드린 {혜택금액}원 혜택을 유지하실 수 있습니다. "
            "현재 유지기간은 {남은일수}일 남았습니다. "
            "요금제 변경을 원하시거나 유지가 어려우시면 변경 전 {매장전화번호}로 연락 부탁드립니다. 감사합니다."
        ),
    },
    {
        "id": "CLAWBACK_RISK",
        "label": "환수위험 안내",
        "body": (
            "{고객명} 고객님, 가입 당시 제공된 혜택의 유지조건을 안내드립니다. "
            "현재 {요금제명} 요금제의 필수 유지기간이 {남은일수}일 남아 있습니다. "
            "유지기간 전에 요금제를 변경하거나 해지하면 혜택 일부가 환수될 수 있으니, "
            "변경 전 {매장전화번호}로 연락 부탁드립니다."
        ),
    },
    {
        "id": "CONSULT_REQUEST",
        "label": "상담요청 안내",
        "body": (
            "{고객명} 고객님, 가입하신 단말과 요금제 혜택에 대한 확인이 필요하여 안내드립니다. "
            "요금제 변경 또는 해지를 검토하고 계시면 혜택 변경 여부를 확인할 수 있도록 "
            "{매장전화번호}로 연락 부탁드립니다."
        ),
    },
]
