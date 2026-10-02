"""허브와 같은 사이드바·상단 바(templates/cc_layout.html)에 넣을 값.

사이드바의 에이전트 목록은 허브의 command_center/agents.json 을 읽기만 해서 쓴다 (못 읽으면 SaveDeal만 보여 준다).
SaveDeal은 별도 서버(5001)라서, 허브 안에서 도는 에이전트(path)는 허브 주소로, 다른 서버(url)는 새 탭으로 연다.
"""
import json
import os
from pathlib import Path

from flask import current_app, url_for

DEFAULT_AGENTS_FILE = Path(__file__).resolve().parents[2] / "command_center" / "agents.json"

# command_center/agents.json 에 등록된 SaveDeal 항목의 id
AGENT_ID = "reservation-churn"

# agents.json 을 못 읽을 때 사이드바에 보여 줄 SaveDeal 기본값
AGENT = {
    "id": AGENT_ID,
    "name": "예약판매 이탈 방지",
    "icon": "calendar-x",
    "color": "red",
}


def load_agents() -> list[dict]:
    path = Path(os.getenv("CC_AGENTS_FILE", DEFAULT_AGENTS_FILE))
    try:
        with path.open(encoding="utf-8") as f:
            agents = json.load(f)
    except (OSError, ValueError):
        agents = []
    if not any(agent.get("id") == AGENT_ID for agent in agents):
        agents = agents + [AGENT]
    return agents


def agent_link(agent: dict) -> tuple[str, bool]:
    """사이드바 링크 → (주소, 새 탭으로 열지 여부). 허브의 agent_link 와 같은 규칙을 SaveDeal 기준으로 적용한다."""
    if agent.get("id") == AGENT_ID:
        return url_for("pages.savedeal"), False
    path = (agent.get("path") or "").strip()
    if path:
        hub = current_app.config["COMMAND_CENTER_URL"].rstrip("/")
        return f"{hub}{path}", False
    url = (agent.get("url") or "").strip()
    return url, bool(url)


def init_layout(app) -> None:
    app.jinja_env.globals["agent_link"] = agent_link

    @app.context_processor
    def inject_layout():
        return {
            "agents": load_agents(),
            "active_agent_id": AGENT_ID,
            "command_center_url": app.config["COMMAND_CENTER_URL"],
        }
