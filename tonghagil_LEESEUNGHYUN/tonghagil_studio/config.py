"""통하길 스튜디오 설정. 값은 tonghagil_LEESEUNGHYUN/.env 에서 읽는다 (.env.example 참고).

스튜디오는 허브와 같은 프로세스에서 돈다. 그래서 .env 를 os.environ 에 풀어 놓지 않고(load_dotenv 안 씀)
이 파일 안에서만 읽는다. 허브나 다른 에이전트의 설정과 섞이지 않게 하려는 것이다.
같은 프로세스의 다른 에이전트가 N8N_WEBHOOK_URL 같은 흔한 이름을 환경 변수에 올려도 스튜디오는 자기 .env 값을 쓴다.
.env 에 없는 값만 환경 변수에서 찾는다.
"""
import os
import re
from pathlib import Path

from dotenv import dotenv_values

# tonghagil_LEESEUNGHYUN 폴더. .env 의 상대 경로는 이 폴더 기준으로 해석한다.
BASE_DIR = Path(__file__).resolve().parent.parent

_ENV_FILE = {key: value for key, value in dotenv_values(BASE_DIR / ".env").items() if value is not None}


def _get(name, default=""):
    return _ENV_FILE.get(name, os.environ.get(name, default))


# n8n Webhook 노드의 운영 주소(Production URL).
# 비워 두면 데모 모드: n8n 없이 샘플 포스터를 만들어 화면 흐름만 확인한다.
N8N_WEBHOOK_URL = _get("N8N_WEBHOOK_URL").strip()

# 이미지 생성 + 드라이브 업로드까지 기다릴 최대 시간(초)
N8N_TIMEOUT = float(_get("N8N_TIMEOUT") or "180")

# n8n Webhook 의 Header Auth 비밀 키. 설정하면 요청 헤더(N8N_SECRET_HEADER)에 담아 보낸다.
N8N_WEBHOOK_SECRET = _get("N8N_WEBHOOK_SECRET").strip()
N8N_SECRET_HEADER = _get("N8N_SECRET_HEADER").strip() or "X-Tonghagil-Key"


def _folder_id(value):
    """폴더 ID 또는 폴더 주소(…/drive/folders/<ID>?usp=…)를 받아 ID만 돌려준다."""
    value = value.strip()
    match = re.search(r"folders/([\w-]+)", value)
    value = match.group(1) if match else value
    return value if re.fullmatch(r"[\w-]{10,}", value) else ""


# 갤러리로 쓸 구글 드라이브 폴더. 비워 두면 샘플(더미) 포스터를 보여 준다.
DRIVE_FOLDER_ID = _folder_id(_get("DRIVE_FOLDER_ID"))

# 구글 클라우드 서비스 계정 키(JSON) 파일 경로
GOOGLE_SERVICE_ACCOUNT_FILE = BASE_DIR / (_get("GOOGLE_SERVICE_ACCOUNT_FILE").strip() or "credentials/service-account.json")

# 드라이브 폴더 목록을 다시 읽기 전까지 기다리는 시간(초)
DRIVE_CACHE_SECONDS = int(_get("DRIVE_CACHE_SECONDS") or "60")
