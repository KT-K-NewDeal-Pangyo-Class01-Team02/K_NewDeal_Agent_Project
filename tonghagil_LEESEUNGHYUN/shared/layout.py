"""Command Center 공통 레이아웃(사이드바·상단 바)을 각 에이전트 Flask 앱에 붙인다.

사용법:
    app = Flask(__name__)
    init_layout(app, active_agent_id="tonghagil-studio")

그 다음 템플릿에서 {% extends "cc_layout.html" %} 로 공통 틀을 쓴다.
사이드바의 에이전트 목록은 shared/agents.json 을 매 요청마다 읽어서 그린다.
"""
import json
import os
from pathlib import Path

from flask import Blueprint
from jinja2 import ChoiceLoader, FileSystemLoader

SHARED_DIR = Path(__file__).resolve().parent
AGENTS_FILE = SHARED_DIR / "agents.json"


def load_agents():
    with AGENTS_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def save_agents(agents):
    with AGENTS_FILE.open("w", encoding="utf-8") as f:
        json.dump(agents, f, ensure_ascii=False, indent=2)
        f.write("\n")


def init_layout(app, active_agent_id=None):
    """공통 템플릿·정적 파일·사이드바 데이터를 앱에 등록한다.

    active_agent_id: 이 앱이 어떤 에이전트인지 (사이드바 강조용). 홈(Command Center)은 None.
    """
    app.jinja_loader = ChoiceLoader([
        app.jinja_loader,
        FileSystemLoader(str(SHARED_DIR / "templates")),
    ])
    app.register_blueprint(Blueprint(
        "shared", __name__,
        static_folder="static",
        static_url_path="/shared-static",
    ))

    @app.context_processor
    def inject_layout():
        return {
            "agents": load_agents(),
            "active_agent_id": active_agent_id,
            "command_center_url": os.getenv("COMMAND_CENTER_URL", "http://localhost:5000"),
            "user_name": os.getenv("CC_USER_NAME", "김지현 매니저"),
        }
