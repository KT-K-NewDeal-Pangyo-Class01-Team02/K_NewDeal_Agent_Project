"""통하길 스튜디오 설정. 값은 프로젝트 루트의 .env 에서 읽는다 (.env.example 참고)."""
import os

from dotenv import load_dotenv

load_dotenv()

# n8n 'When chat message received' 노드의 Chat URL (또는 나중에 바꿀 Webhook URL).
# 비워 두면 데모 모드: n8n 없이 샘플 포스터를 만들어 화면 흐름만 확인한다.
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "").strip()

# 이미지 생성 + 드라이브 업로드까지 기다릴 최대 시간(초)
N8N_TIMEOUT = float(os.getenv("N8N_TIMEOUT", "180"))

STUDIO_PORT = int(os.getenv("STUDIO_PORT", "5004"))
