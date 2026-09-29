"""통하길 스튜디오 설정. 값은 .env 에서 읽는다 (.env.example 참고)."""
import os
import re
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# tonghagil_LEESEUNGHYUN 폴더. .env 의 상대 경로는 이 폴더 기준으로 해석한다.
BASE_DIR = Path(__file__).resolve().parent.parent

# n8n 'When chat message received' 노드의 Chat URL (또는 나중에 바꿀 Webhook URL).
# 비워 두면 데모 모드: n8n 없이 샘플 포스터를 만들어 화면 흐름만 확인한다.
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "").strip()

# 이미지 생성 + 드라이브 업로드까지 기다릴 최대 시간(초)
N8N_TIMEOUT = float(os.getenv("N8N_TIMEOUT", "180"))

STUDIO_PORT = int(os.getenv("STUDIO_PORT", "5004"))


def _folder_id(value):
    """폴더 ID 또는 폴더 주소(…/drive/folders/<ID>?usp=…)를 받아 ID만 돌려준다."""
    value = value.strip()
    match = re.search(r"folders/([\w-]+)", value)
    value = match.group(1) if match else value
    return value if re.fullmatch(r"[\w-]{10,}", value) else ""


# 갤러리로 쓸 구글 드라이브 폴더. 비워 두면 샘플(더미) 포스터를 보여 준다.
DRIVE_FOLDER_ID = _folder_id(os.getenv("DRIVE_FOLDER_ID", ""))

# 구글 클라우드 서비스 계정 키(JSON) 파일 경로
GOOGLE_SERVICE_ACCOUNT_FILE = BASE_DIR / os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "credentials/service-account.json")

# 드라이브 폴더 목록을 다시 읽기 전까지 기다리는 시간(초)
DRIVE_CACHE_SECONDS = int(os.getenv("DRIVE_CACHE_SECONDS", "60"))
