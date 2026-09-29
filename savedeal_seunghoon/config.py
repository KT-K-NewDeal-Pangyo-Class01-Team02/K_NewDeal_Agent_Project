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
