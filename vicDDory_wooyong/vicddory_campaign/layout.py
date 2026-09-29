"""Command Center 공통 레이아웃(사이드바·상단 바)을 빅또리 앱에 붙인다.

공통 틀은 이승현님 폴더의 `tonghagil_LEESEUNGHYUN/shared/` 에 있다. 여기서는 그걸
**읽어서 쓰기만** 한다 (팀 규칙: 다른 사람 폴더는 수정하지 않는다).

`shared/agents.json` 에 빅또리가 아직 등록되지 않았다면, 사이드바에 보이도록
이 파일에서 메모리상으로만 한 줄 끼워 넣는다. 원본 파일은 건드리지 않는다.
"""
import sys
from pathlib import Path

# vicDDory_wooyong → 저장소 루트 → 공통 틀이 있는 이승현님 폴더
BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parent
SHARED_ROOT = REPO_ROOT / "tonghagil_LEESEUNGHYUN"

AGENT_ID = "vicddory"

# shared/agents.json 에 등록해 달라고 요청할 내용과 똑같이 맞춰 둔다.
AGENT = {
    "id": AGENT_ID,
    "name": "빅또리",
    "description": "직영점 발의 옥외 BTL 캠페인을 3시간 만에 기획하고 성과를 환류합니다.",
    "icon": "qr-code",
    "color": "orange",
    "status": "운영 중",
    "url": "http://localhost:5500",
}


def _load_shared_layout():
    if not (SHARED_ROOT / "shared" / "layout.py").exists():
        raise RuntimeError(
            "Command Center 공통 레이아웃을 찾지 못했어요.\n"
            f"  찾은 위치: {SHARED_ROOT / 'shared'}\n"
            "저장소 전체(tonghagil_LEESEUNGHYUN 폴더 포함)를 받아 뒀는지 확인해 주세요."
        )
    if str(SHARED_ROOT) not in sys.path:
        sys.path.insert(0, str(SHARED_ROOT))
    from shared.layout import init_layout  # noqa: E402  (경로를 넣은 뒤에야 import 된다)

    return init_layout


def init_cc_layout(app):
    """공통 사이드바·상단 바를 붙이고, 사이드바 목록에 빅또리를 보장한다."""
    init_layout = _load_shared_layout()
    init_layout(app, active_agent_id=AGENT_ID)

    @app.context_processor
    def ensure_self_in_sidebar():
        # init_layout 보다 나중에 등록되므로 여기서 돌려주는 agents 가 최종값이 된다.
        from shared.layout import load_agents

        agents = load_agents()
        if not any(a.get("id") == AGENT_ID for a in agents):
            agents = agents + [AGENT]
        return {"agents": agents}
