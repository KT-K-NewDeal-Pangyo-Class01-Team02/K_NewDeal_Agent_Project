"""Command Center 공통 틀(사이드바·상단 바)과 에이전트 목록(agents.json).

agents.json 이 홈 카드와 사이드바 메뉴를 만든다. 팀원은 자기 에이전트 줄만 고친다.
"""
import json
import os
from pathlib import Path

from flask import url_for
from werkzeug.routing import BuildError

AGENTS_FILE = Path(__file__).resolve().parent / "agents.json"


def load_agents():
    with AGENTS_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def save_agents(agents):
    with AGENTS_FILE.open("w", encoding="utf-8") as f:
        json.dump(agents, f, ensure_ascii=False, indent=2)
        f.write("\n")


def agent_link(agent):
    """에이전트 카드가 어디로 가야 하는지 돌려준다. → (주소, 새 탭으로 열지 여부)

    - `endpoint` 가 있으면 **같은 Flask 앱 안의 라우트**다. 같은 탭으로 이동한다. (예: 더 줘 → thejo.dashboard)
    - `url` 만 있으면 다른 포트에서 도는 별도 서버다. 지금까지처럼 새 탭으로 연다.
    - 둘 다 없으면 빈 주소. 홈 화면이 "주소 미등록" 안내를 띄운다.
    """
    endpoint = (agent.get("endpoint") or "").strip()
    if endpoint:
        try:
            return url_for(endpoint), False
        except BuildError:
            # 해당 에이전트 Blueprint 가 아직 등록되지 않았다. url 로 넘어간다.
            pass
    url = (agent.get("url") or "").strip()
    return url, bool(url)


def init_layout(app):
    """cc_layout.html 이 쓰는 값(사이드바 에이전트 목록, 사용자 이름 등)을 템플릿에 넣는다."""
    app.jinja_env.globals["agent_link"] = agent_link

    @app.context_processor
    def inject_layout():
        return {
            "agents": load_agents(),
            "active_agent_id": None,
            "command_center_url": os.getenv("COMMAND_CENTER_URL", "http://localhost:5000"),
            "user_name": os.getenv("CC_USER_NAME", "김지현 매니저"),
        }
