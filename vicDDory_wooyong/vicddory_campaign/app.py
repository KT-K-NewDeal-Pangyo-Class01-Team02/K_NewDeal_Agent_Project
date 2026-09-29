"""빅또리: 직영점 발의 옥외 BTL 캠페인을 3시간 만에 기획하고 성과를 환류하는 콘솔.

실행: vicDDory_wooyong 폴더에서  python -m vicddory_campaign.app
      (VS Code 실행 ▶ 버튼으로 이 파일을 직접 돌려도 된다)
"""
import sys
import time
from pathlib import Path

if not __package__:
    # 'python app.py' 로 직접 실행해도 vicddory_campaign 패키지를 찾을 수 있게 한다
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flask import Flask, jsonify, render_template, request

from vicddory_campaign import config
from vicddory_campaign.layout import AGENT, AGENT_ID, init_cc_layout
from vicddory_campaign.n8n_client import N8nError, request_plan

MAX_CONSTRAINTS = 200

TARGET_GROUPS = [
    {"id": "2030_5G", "label": "2030 청년층 (5G 무제한 요금제)"},
    {"id": "SENIOR_PHONE", "label": "시니어 실속형 스마트폰"},
    {"id": "FAMILY_INTERNET", "label": "가족 결합 인터넷/TV"},
]

# 14단계 환류 대시보드에 보여 줄 지난 캠페인 집계 (추후 POS 연동 예정)
FUNNEL = [
    {"label": "부스 방문 (익명 QR)", "value": "342명", "sub": "지난 캠페인 합계"},
    {"label": "매장 내방율", "value": "28.4%", "sub": "97명 인입"},
    {"label": "POS 최종 개통", "value": "19건", "sub": "내방 대비 19.6%"},
]

INSIGHT = (
    "2030 타깃 요금제 캠페인의 점심 시간대(12~14시) 인입 전환율이 통상치 대비 1.8배 높았습니다. "
    "차기 기획 시 부스 운영 인력을 해당 피크 시간대에 집중 배치할 것을 권장합니다."
)

app = Flask(__name__)
init_cc_layout(app)


@app.get("/")
def home():
    return render_template(
        "campaign.html",
        agent=AGENT,
        target_groups=TARGET_GROUPS,
        funnel=FUNNEL,
        insight=INSIGHT,
        max_constraints=MAX_CONSTRAINTS,
        n8n_connected=bool(config.N8N_WEBHOOK_URL),
    )


@app.post("/api/plan")
def create_plan():
    """캠페인 파라미터를 n8n 으로 넘겨 3시간 기획 확정안을 받아 온다."""
    data = request.get_json(silent=True) or {}
    store_name = (data.get("store_name") or "").strip()
    constraints = (data.get("constraints") or "").strip()
    target = next((t for t in TARGET_GROUPS if t["id"] == data.get("target_group")), TARGET_GROUPS[0])

    if not store_name:
        return jsonify(error="운영 매장을 입력해 주세요."), 400
    if len(store_name) > 40:
        return jsonify(error="운영 매장 이름은 40자까지 입력할 수 있어요."), 400
    if len(constraints) > MAX_CONSTRAINTS:
        return jsonify(error=f"제약조건은 {MAX_CONSTRAINTS}자까지 입력할 수 있어요."), 400

    payload = {
        "storeName": store_name,
        "targetGroup": target["id"],
        "targetGroupLabel": target["label"],
        "constraints": constraints,
        "operation": "2인 1조 (20/10분 사이클)",
    }

    if not config.N8N_WEBHOOK_URL:
        time.sleep(1.0)
        return jsonify(plan=_demo_plan(store_name, target["label"], constraints), source="demo")

    try:
        plan = request_plan(config.N8N_WEBHOOK_URL, payload, timeout=config.N8N_TIMEOUT)
    except N8nError as exc:
        return jsonify(error=str(exc)), 502
    return jsonify(plan=plan, source="n8n")


def _demo_plan(store_name, target_label, constraints):
    """n8n 없이도 화면 흐름을 확인할 수 있게 만드는 샘플 기획안."""
    return "\n".join([
        f"[{store_name}] {target_label} 옥외 BTL 캠페인 확정안 (데모)",
        "",
        "1. 입지 (F-03)",
        "   · 1순위: 매장 정면 대로변 버스정류장 앞 - 점심 유동인구 최다",
        "   · 2순위: 인근 대형마트 출입구 - 주말 가족 단위 방문객",
        "",
        "2. 핵심 카피 (F-04)",
        "   · 메인: \"지금 이 자리에서, 요금제 진단 3분\"",
        "   · 서브: \"QR 한 번이면 매장 방문 전용 혜택까지\"",
        "",
        "3. A4 콜시트 (F-05)",
        "   · 20분 응대 / 10분 정비 사이클, 2인 1조 교대",
        "   · 응대 1순위: 요금제 진단 → QR 스캔 → 매장 유도",
        "",
        f"4. 제약조건 반영: {constraints or '입력 없음'}",
        "",
        "※ 데모 모드입니다. .env 의 N8N_WEBHOOK_URL 을 채우면 실제 기획안이 생성됩니다.",
    ])


if __name__ == "__main__":
    app.run(port=config.VICDDORY_PORT, debug=True)
