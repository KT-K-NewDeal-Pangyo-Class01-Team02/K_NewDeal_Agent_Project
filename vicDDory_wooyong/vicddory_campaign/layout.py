"""빅또리 화면의 공통 틀(사이드바·상단 바).

디자인(cc_layout.html, common.css)은 Command Center 허브와 같은 모양의 사본을 이 폴더에 따로 둔다.
허브 디자인이 바뀌어도 빅또리 화면이 같이 깨지지 않게 하려는 것이다.
사이드바의 에이전트 목록만 허브의 agents.json 을 읽어서 쓴다 (읽기 전용, 없으면 빈 목록).
"""
import json
import os
from pathlib import Path

# 저장소 루트의 command_center/agents.json
DEFAULT_AGENTS_FILE = Path(__file__).resolve().parents[2] / "command_center" / "agents.json"

# command_center/agents.json 에 등록해 둔 내 항목의 id 와 똑같이 맞춘다.
AGENT_ID = "aftercare"

# agents.json 을 못 읽을 때 사이드바·화면에서 쓰는 기본값
AGENT = {
    "id": AGENT_ID,
    "name": "빅또리출동!",
    "description": "직영점 발의 옥외 BTL 캠페인을 3시간 만에 기획하고 성과를 환류합니다.",
    "icon": "qr-code",
    "color": "orange",
    "status": "운영 중",
    "url": "http://localhost:5500",
}


def load_agents():
    path = Path(os.getenv("CC_AGENTS_FILE", DEFAULT_AGENTS_FILE))
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def init_cc_layout(app):
    """공통 사이드바·상단 바 값을 템플릿에 넣고, 사이드바 목록에 빅또리를 보장한다."""

    @app.context_processor
    def inject_layout():
        agents = load_agents()
        if not any(a.get("id") == AGENT_ID for a in agents):
            agents = agents + [AGENT]
        # 허브 안에서 도는 에이전트(더 줘 · 통하길)는 url 이 비어 있고 path 만 있다 → 허브 주소 + path 로 찾아간다
        hub = os.getenv("COMMAND_CENTER_URL", "http://localhost:5000").rstrip("/")
        for agent in agents:
            if not (agent.get("url") or "").strip() and (agent.get("path") or "").strip():
                agent["url"] = hub + "/" + agent["path"].strip().lstrip("/")
        return {
            "agents": agents,
            "active_agent_id": AGENT_ID,
            "command_center_url": hub,
            "user_name": os.getenv("CC_USER_NAME", "김지현 매니저"),
        }
