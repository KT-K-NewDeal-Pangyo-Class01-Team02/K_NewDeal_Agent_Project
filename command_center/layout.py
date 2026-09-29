"""Command Center 공통 틀(사이드바·상단 바)과 에이전트 목록(agents.json).

agents.json 이 홈 카드와 사이드바 메뉴를 만든다. 팀원은 자기 에이전트 줄만 고친다.
"""
import json
import os
from pathlib import Path

AGENTS_FILE = Path(__file__).resolve().parent / "agents.json"


def load_agents():
    with AGENTS_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def save_agents(agents):
    with AGENTS_FILE.open("w", encoding="utf-8") as f:
        json.dump(agents, f, ensure_ascii=False, indent=2)
        f.write("\n")


def init_layout(app):
    """cc_layout.html 이 쓰는 값(사이드바 에이전트 목록, 사용자 이름 등)을 템플릿에 넣는다."""

    @app.context_processor
    def inject_layout():
        return {
            "agents": load_agents(),
            "active_agent_id": None,
            "command_center_url": os.getenv("COMMAND_CENTER_URL", "http://localhost:5000"),
            "user_name": os.getenv("CC_USER_NAME", "김지현 매니저"),
        }
