"""Command Center 홈: 에이전트 카드를 보여 주고, 카드를 누르면 각 에이전트 앱을 새 탭으로 연다.

실행 (프로젝트 루트에서):  python -m command_center.app
"""
import os
import re

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

from shared.layout import init_layout, load_agents, save_agents

load_dotenv()

ICON_CHOICES = [
    ("image", "이미지"), ("qr-code", "QR 코드"), ("calendar-x", "캘린더"), ("coins", "코인"),
    ("headset", "헤드셋"), ("sparkles", "반짝임"), ("bot", "로봇"),
]
COLOR_CHOICES = [
    ("purple", "보라"), ("blue", "파랑"), ("green", "초록"),
    ("red", "빨강"), ("orange", "주황"), ("teal", "청록"),
]
STATUS_CHOICES = ["운영 중", "준비 중"]

app = Flask(__name__)
init_layout(app)


@app.get("/")
def home():
    return render_template(
        "home.html",
        icon_choices=ICON_CHOICES,
        color_choices=COLOR_CHOICES,
        status_choices=STATUS_CHOICES,
    )


@app.post("/api/agents")
def add_agent():
    """'새 에이전트 추가' 카드에서 입력한 에이전트를 shared/agents.json 에 추가한다."""
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    url = (data.get("url") or "").strip()

    if not name:
        return jsonify(error="에이전트 이름을 입력해 주세요."), 400
    if url and not re.match(r"^https?://", url):
        return jsonify(error="주소는 http:// 또는 https:// 로 시작해야 해요."), 400

    agents = load_agents()
    agent = {
        "id": _new_agent_id(agents),
        "name": name[:20],
        "description": (data.get("description") or "").strip()[:60],
        "icon": _pick(data.get("icon"), [value for value, _ in ICON_CHOICES]),
        "color": _pick(data.get("color"), [value for value, _ in COLOR_CHOICES]),
        "status": _pick(data.get("status"), STATUS_CHOICES),
        "url": url,
    }
    agents.append(agent)
    save_agents(agents)
    return jsonify(agent), 201


def _pick(value, allowed):
    return value if value in allowed else allowed[0]


def _new_agent_id(agents):
    taken = {agent["id"] for agent in agents}
    n = len(agents) + 1
    while f"agent-{n}" in taken:
        n += 1
    return f"agent-{n}"


if __name__ == "__main__":
    app.run(port=int(os.getenv("COMMAND_CENTER_PORT", "5000")), debug=True)
