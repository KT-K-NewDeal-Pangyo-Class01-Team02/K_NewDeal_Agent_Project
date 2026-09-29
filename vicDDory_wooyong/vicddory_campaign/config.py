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
