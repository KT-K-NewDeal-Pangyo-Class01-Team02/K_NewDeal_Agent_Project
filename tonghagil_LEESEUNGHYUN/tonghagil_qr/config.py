"""통하길 QR 설정. 값은 tonghagil_LEESEUNGHYUN/.env 에서 읽는다 (.env.example 의 '통하길 QR' 부분 참고).

통하길 스튜디오와 같은 .env 를 쓰고, 키 이름은 모두 QR_ 로 시작한다.
허브와 같은 프로세스에서 돌기 때문에 .env 를 os.environ 에 풀지 않고 여기서만 읽는다(스튜디오 config.py 와 같은 방식).
.env 에 없는 값만 환경 변수에서 찾는다.
"""
import os
from pathlib import Path

from dotenv import dotenv_values

# tonghagil_LEESEUNGHYUN 폴더. .env 의 상대 경로는 이 폴더 기준으로 해석한다.
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(__file__).resolve().parent / "data"

_ENV_FILE = {key: value for key, value in dotenv_values(BASE_DIR / ".env").items() if value is not None}


def _get(name, default=""):
    return _ENV_FILE.get(name, os.environ.get(name, default))


def _path(name, default):
    value = _get(name).strip()
    return BASE_DIR / value if value else default


# 행사 정보 (행사명·부스·혜택·구역·스탬프 지점)
EVENT_FILE = _path("QR_EVENT_FILE", DATA_DIR / "event.json")

# 방문객·스탬프·쿠폰 기록 (SQLite). git 에 올라가지 않는다.
DB_FILE = _path("QR_DB_FILE", DATA_DIR / "qr.db")

# QR 코드에 넣을 공개 주소. 비워 두면 지금 접속한 주소를 쓴다.
# ngrok 을 연결하면 https://<내 도메인>.ngrok-free.app 처럼 넣는다 (휴대폰은 localhost 를 못 연다).
PUBLIC_BASE_URL = _get("QR_PUBLIC_BASE_URL").strip().rstrip("/")

# 카카오맵 JavaScript 키 (developers.kakao.com → 내 애플리케이션 → 앱 키). 비워 두면 그림 약도를 쓴다.
# 브라우저로 나가는 공개용 키라 화면 소스에 보인다. 대신 카카오 콘솔에 등록한 도메인에서만 동작한다.
KAKAO_MAP_KEY = _get("QR_KAKAO_MAP_KEY").strip()

# 부스 담당자 화면(/qr/staff/) 비밀번호. 비워 두면 1234 (시연용).
STAFF_PIN = _get("QR_STAFF_PIN").strip() or "1234"
STAFF_PIN_IS_DEFAULT = not _get("QR_STAFF_PIN").strip()

# 안내 챗봇을 처리할 n8n Webhook 운영 주소. 비워 두면 고정 답변("테스트 단계입니다")을 돌려준다.
CHAT_WEBHOOK_URL = _get("QR_CHAT_WEBHOOK_URL").strip()
CHAT_WEBHOOK_SECRET = _get("QR_CHAT_WEBHOOK_SECRET").strip()
CHAT_SECRET_HEADER = _get("QR_CHAT_SECRET_HEADER").strip() or "X-Tonghagil-Key"
CHAT_TIMEOUT = float(_get("QR_CHAT_TIMEOUT") or "30")

# 담당자 화면(/qr/staff/)의 관리자 에이전트용 n8n Webhook 운영 주소. 방문객용과 다른 워크플로다.
# 비워 두면 고정 답변을 돌려준다. 비밀 값을 따로 안 적으면 방문객용 값을 같이 쓴다 (헤더 이름·제한 시간은 공통).
STAFF_CHAT_WEBHOOK_URL = _get("QR_STAFF_CHAT_WEBHOOK_URL").strip()
STAFF_CHAT_WEBHOOK_SECRET = _get("QR_STAFF_CHAT_WEBHOOK_SECRET").strip() or CHAT_WEBHOOK_SECRET
