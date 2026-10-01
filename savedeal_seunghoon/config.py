import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# Config 값을 읽기 전에 .env를 불러와야 PORT 등의 설정이 반영된다.
load_dotenv(BASE_DIR / ".env")


def _resolve(path_value) -> Path:
    """상대 경로는 실행 위치가 아니라 이 폴더를 기준으로 해석한다."""
    path = Path(path_value)
    return path if path.is_absolute() else BASE_DIR / path


class Config:
    DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"
    TESTING = False
    DATA_DIR = _resolve(os.getenv("DATA_DIR", "data"))
    DB_PATH = _resolve(os.getenv("DB_PATH", DATA_DIR / "savedeal.db"))
    PORT = int(os.getenv("PORT", "5001"))
    COMMAND_CENTER_URL = os.getenv("COMMAND_CENTER_URL", "http://localhost:5000")

    # n8n → Gmail 알림. N8N_WEBHOOK_URL 이 비어 있으면 실제로 보내지 않고 '데모 기록'만 남긴다.
    N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "").strip()
    N8N_WEBHOOK_SECRET = os.getenv("N8N_WEBHOOK_SECRET", "").strip()
    N8N_SECRET_HEADER = os.getenv("N8N_SECRET_HEADER", "X-SaveDeal-Key").strip()
    N8N_TIMEOUT = float(os.getenv("N8N_TIMEOUT", "8"))
    NOTIFY_EMAIL_TO = os.getenv("NOTIFY_EMAIL_TO", "").strip()

    # OpenAI (ChatGPT API). OPENAI_API_KEY 가 비어 있으면 AI를 부르지 않고 규칙 기반 문구로 동작한다.
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
    OPENAI_TIMEOUT = float(os.getenv("OPENAI_TIMEOUT", "20"))
