"""빅또리 설정. 값은 .env 에서 읽는다 (.env.example 참고)."""
import os
from pathlib import Path

from dotenv import load_dotenv

# vicDDory_wooyong 폴더
BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

# BTL 기획서를 만들어 주는 n8n 웹훅 주소.
# 비워 두면 데모 모드로 뜬다 (n8n 없이 샘플 기획안으로 화면 흐름만 확인).
N8N_WEBHOOK_URL = os.getenv(
    "N8N_WEBHOOK_URL",
    "https://fairytalegames.app.n8n.cloud/webhook/plan-gen",
).strip()

# n8n 응답을 기다릴 최대 시간(초)
N8N_TIMEOUT = float(os.getenv("N8N_TIMEOUT", "120"))

# Command Center 는 5000, 통하길 스튜디오는 5004, 빅또리는 5500
VICDDORY_PORT = int(os.getenv("VICDDORY_PORT", "5500"))


def _webhook_base(url):
    """'https://.../webhook/plan-gen' → 'https://.../webhook'"""
    if "/webhook/" in url:
        return url[: url.index("/webhook/") + len("/webhook")]
    return url.rsplit("/", 1)[0] if url else ""


# F 기능별 n8n 웹훅은 이 주소 뒤에 경로를 붙여 부른다 (예: .../webhook/f01-scan).
# 비워 두면 N8N_WEBHOOK_URL 에서 '/webhook' 까지를 잘라 쓴다. 둘 다 비면 F 기능도 데모 모드.
N8N_BASE_URL = (os.getenv("N8N_BASE_URL") or _webhook_base(N8N_WEBHOOK_URL)).strip().rstrip("/")

F01_SCAN_URL = f"{N8N_BASE_URL}/f01-scan" if N8N_BASE_URL else ""
F01_SELECT_URL = f"{N8N_BASE_URL}/f01-select" if N8N_BASE_URL else ""
F02_VALIDATE_URL = f"{N8N_BASE_URL}/f02-validate" if N8N_BASE_URL else ""
# F-02 통과 후 기획안: F-03 입지 → F-04 카피 → F-05 콜시트 (없으면 기존 plan-gen 사용)
WF_PLAN_URL = f"{N8N_BASE_URL}/wf-plan" if N8N_BASE_URL else ""

# 통하길 스튜디오(이승현, 포트 5004): 입지 이미지 자리에서 포스터 제작 화면으로 링크만 건다.
TONGHAGIL_URL = os.getenv("TONGHAGIL_URL", "http://localhost:5004").rstrip("/")
