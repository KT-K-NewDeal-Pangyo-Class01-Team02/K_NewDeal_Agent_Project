"""통하길 스튜디오 화면의 공통 틀(사이드바·상단 바).

디자인(cc_layout.html, common.css)은 Command Center 허브와 같은 모양의 사본을 이 폴더에 따로 둔다.
허브 디자인이 바뀌어도 스튜디오 화면이 같이 깨지지 않게 하려는 것이다.
사이드바의 에이전트 목록만 허브의 agents.json 을 읽어서 쓴다 (읽기 전용, 없으면 빈 목록).
"""
import json
import os
from pathlib import Path

# 저장소 루트의 command_center/agents.json
DEFAULT_AGENTS_FILE = Path(__file__).resolve().parents[2] / "command_center" / "agents.json"


def command_center_url():
    return os.getenv("COMMAND_CENTER_URL", "http://localhost:5000").rstrip("/")


def load_agents():
    """허브의 에이전트 목록. 허브 안에서 도는 에이전트(url 없이 path 만 있는 더 줘 등)는 허브 주소를 붙여 준다."""
    path = Path(os.getenv("CC_AGENTS_FILE", DEFAULT_AGENTS_FILE))
    try:
        with path.open(encoding="utf-8") as f:
            agents = json.load(f)
    except (OSError, ValueError):
        return []
    hub = command_center_url()
    for agent in agents:
        if not (agent.get("url") or "").strip() and (agent.get("path") or "").strip():
            agent["url"] = hub + "/" + agent["path"].strip().lstrip("/")
    return agents


def init_layout(app, active_agent_id):
    @app.context_processor
    def inject_layout():
        return {
            "agents": load_agents(),
            "active_agent_id": active_agent_id,
            "command_center_url": command_center_url(),
            "user_name": os.getenv("CC_USER_NAME", "김지현 매니저"),
        }
