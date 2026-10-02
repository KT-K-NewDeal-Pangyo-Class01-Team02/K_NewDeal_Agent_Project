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


def public_urls():
    """공개 모드(ngrok 등)에서 쓸 {에이전트 id: 공개 주소}. 평소에는 빈 dict.

    별도 서버 에이전트의 url 은 agents.json 에 localhost 로 적혀 있어서, 밖에서 들어온 사람이 누르면 안 열린다.
    공개 모드에서는 start_all.local.ps1(PC 마다 따로, git 에 안 올라감)이 url 만 공개 주소로 바꾼 사본을 만들고
    환경 변수 CC_AGENTS_FILE 로 알려 준다. SaveDeal·빅또리가 사이드바를 그릴 때 읽는 것과 같은 파일이다.
    agents.json 자체는 바꾸지 않는다. 팀원 PC 에서는 localhost 여야 하고, 홈의 '에이전트 추가'가 이 파일에 저장한다.
    """
    path = os.getenv("CC_AGENTS_FILE", "").strip()
    if not path:
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return {a.get("id"): (a.get("url") or "").strip() for a in json.load(f)}
    except (OSError, ValueError):
        return {}


def agent_link(agent):
    """에이전트 카드가 어디로 가야 하는지 돌려준다. → (주소, 새 탭으로 열지 여부)

    - `endpoint` 가 있으면 **같은 Flask 앱 안의 라우트**다. 같은 탭으로 이동한다. (예: 더 줘 → thejo.dashboard)
    - `path` 는 같은 라우트의 허브 기준 주소(예: "/thejo/")다. 허브 밖의 에이전트 앱들이 사이드바에서
      `허브 주소 + path` 로 찾아갈 때 쓰고, 여기서는 endpoint 를 못 찾았을 때의 대비로만 쓴다.
    - `url` 만 있으면 다른 포트에서 도는 별도 서버다. 지금까지처럼 새 탭으로 연다.
      공개 모드면 agents.json 의 url 대신 공개 주소를 쓴다 (public_urls).
    - 셋 다 없으면 빈 주소. 홈 화면이 "주소 미등록" 안내를 띄운다.
    """
    endpoint = (agent.get("endpoint") or "").strip()
    if endpoint:
        try:
            return url_for(endpoint), False
        except BuildError:
            # 해당 에이전트 Blueprint 가 아직 등록되지 않았다. path → url 순서로 넘어간다.
            pass
    path = (agent.get("path") or "").strip()
    if path:
        return path, False
    url = public_urls().get(agent.get("id")) or (agent.get("url") or "").strip()
    return url, bool(url)


def init_layout(app):
    """cc_layout.html 이 쓰는 값(사이드바 에이전트 목록, 사용자 이름 등)을 템플릿에 넣는다."""
    app.jinja_env.globals["agent_link"] = agent_link

    @app.context_processor
    def inject_layout():
        return {
            "agents": load_agents(),
            "active_agent_id": None,
            # 허브 안 화면은 상대 주소로 홈에 간다. ngrok 등 공개 주소로 들어와도 localhost 로 새지 않는다.
            "command_center_url": url_for("home"),
            "user_name": os.getenv("CC_USER_NAME", "김지현 매니저"),
        }
