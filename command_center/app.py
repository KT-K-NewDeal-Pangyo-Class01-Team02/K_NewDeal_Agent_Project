"""Command Center 홈(팀 공용 허브): 에이전트 카드를 보여 주고, 카드를 누르면 에이전트 앱으로 보낸다.

에이전트는 두 가지 방식으로 붙는다 (agents.json).
  - `endpoint`: 이 Flask 앱 안에 Blueprint 로 등록된 에이전트. **같은 탭**으로 이동한다. (예: 더 줘 → /thejo/, 통하길 스튜디오 → /studio/, 통하길 QR → /qr/)
  - `url`:      다른 포트에서 따로 도는 서버. 지금까지처럼 **새 탭**으로 연다. (예: 빅또리출동! → :5500)

실행: VS Code 실행(▶) 버튼, 또는 저장소 루트에서  python -m command_center.app   (http://localhost:5000)
"""
import os
import re
import sys
from pathlib import Path

if not __package__:
    # 'python app.py'(VS Code 실행 버튼)로 직접 실행해도 command_center 패키지를 찾을 수 있게 한다
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

from command_center.layout import init_layout, load_agents, save_agents
from thejo_project import thejo_bp  # 더 줘 (정주희) — /thejo/ 아래에서 같은 프로세스로 돈다

try:
    # 통하길 스튜디오 (이승현) — /studio/ 아래에서 같은 프로세스로 돈다
    from tonghagil_LEESEUNGHYUN.tonghagil_studio import studio_bp
except ModuleNotFoundError as exc:
    # 스튜디오용 패키지(requests, google-auth)가 없는 환경에서도 허브와 다른 에이전트는 뜨게 한다
    studio_bp = None
    print(f"[경고] 통하길 스튜디오를 건너뜁니다 ({exc}). "
          "pip install -r tonghagil_LEESEUNGHYUN/requirements.txt 로 설치해 주세요.", file=sys.stderr)
try:
    # 통하길 QR (이승현) — /qr/ 아래에서 같은 프로세스로 돈다
    from tonghagil_LEESEUNGHYUN.tonghagil_qr import qr_bp
except ModuleNotFoundError as exc:
    qr_bp = None
    print(f"[경고] 통하길 QR을 건너뜁니다 ({exc}). "
          "pip install -r tonghagil_LEESEUNGHYUN/requirements.txt 로 설치해 주세요.", file=sys.stderr)

# 선택: command_center/.env (COMMAND_CENTER_PORT, CC_USER_NAME 등). 없으면 기본값을 쓴다.
load_dotenv(Path(__file__).resolve().parent / ".env")

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

# ── 같은 프로세스에서 도는 에이전트 Blueprint ─────────────────────────────
# 팀원이 자기 에이전트를 Blueprint 로 만들면 여기에 한 줄 추가하고,
# agents.json 의 자기 항목에 "endpoint": "<blueprint>.<함수>" 를 적는다.
app.register_blueprint(thejo_bp)
if studio_bp is not None:
    app.register_blueprint(studio_bp)
if qr_bp is not None:
    app.register_blueprint(qr_bp)


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
    """'새 에이전트 추가' 카드에서 입력한 에이전트를 command_center/agents.json 에 추가한다."""
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
