"""빅또리: 직영점 발의 옥외 BTL 캠페인을 3시간 만에 기획하고 성과를 환류하는 콘솔.

실행: vicDDory_wooyong 폴더에서  python -m vicddory_campaign.app
      (VS Code 실행 ▶ 버튼으로 이 파일을 직접 돌려도 된다)
"""
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

if not __package__:
    # 'python app.py' 로 직접 실행해도 vicddory_campaign 패키지를 찾을 수 있게 한다
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flask import Flask, jsonify, render_template, request

from vicddory_campaign import config
from vicddory_campaign.layout import AGENT, AGENT_ID, init_cc_layout
from vicddory_campaign.n8n_client import N8nError, request_json, request_plan

MAX_CONSTRAINTS = 200

# F-01 기회 스캔 대상 매장 (roster · 00_dummy_data 의 store_id 와 같다)
STORES = [
    {"id": "ST-SINCHEON", "name": "신천역점"},
    {"id": "ST-GANGNAM", "name": "강남직영점"},
]

# F-02 운영 시간대 (n8n F02_validate 의 WINDOWS 와 같아야 한다)
OPERATING_HOURS = [
    {"id": "14:00-18:00", "label": "피크 14:00 ~ 18:00 (기본)"},
    {"id": "11:00-15:00", "label": "점심 11:00 ~ 15:00"},
    {"id": "17:00-21:00", "label": "퇴근 17:00 ~ 21:00"},
]
BUDGET_MAX = 1_500_000

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
        stores=STORES,
        f01_connected=bool(config.F01_SCAN_URL),
        operating_hours=OPERATING_HOURS,
        budget_max=BUDGET_MAX,
        default_date=(_today_kst() + timedelta(days=1)).isoformat(),
        f02_connected=bool(config.F02_VALIDATE_URL),
        tonghagil_url=config.TONGHAGIL_URL,
    )


def _today_kst():
    return datetime.now(timezone(timedelta(hours=9))).date()


def _store(store_id):
    return next((s for s in STORES if s["id"] == store_id), None)


@app.post("/api/f02/options")
def f02_options():
    """F-02 폼 채우기: 그날 근무자 · 운영 장소 · 사은품 재고."""
    data = request.get_json(silent=True) or {}
    store, target_date = _store(data.get("store_id")), str(data.get("target_date") or "")
    if not store or len(target_date) != 10:
        return jsonify(error="매장과 운영 일자를 먼저 골라 주세요."), 400
    if not config.F02_VALIDATE_URL:
        return jsonify(_demo_options(store, target_date))
    try:
        result = request_json(config.F02_VALIDATE_URL,
                              {"action": "options", "store_id": store["id"], "target_date": target_date},
                              timeout=config.N8N_TIMEOUT)
    except N8nError as exc:
        return jsonify(error=str(exc)), 502
    return jsonify({**result, "source": "n8n"})


@app.post("/api/f02/validate")
def f02_validate():
    """F-02: 8개 파라미터를 규칙(R-01 2인 1조 · R-02 잔류 인력 · 예산 · 재고)으로 판정한다."""
    data = request.get_json(silent=True) or {}
    store = _store(data.get("store_id"))
    if not store:
        return jsonify(error="운영 매장을 골라 주세요."), 400
    constraints = str(data.get("constraints") or "").strip()
    if len(constraints) > MAX_CONSTRAINTS:
        return jsonify(error=f"제약조건은 {MAX_CONSTRAINTS}자까지 입력할 수 있어요."), 400
    staff_ids = [str(x) for x in (data.get("staff_ids") or []) if x][:4]
    payload = {
        "action": "validate", "store_id": store["id"],
        "target_date": str(data.get("target_date") or ""),
        "operating_hours": str(data.get("operating_hours") or ""),
        "target_group": str(data.get("target_group") or ""),
        "site_id": str(data.get("site_id") or ""),
        "staff_ids": staff_ids,
        "budget": data.get("budget"), "reward_item": str(data.get("reward_item") or ""),
        "reward_qty": data.get("reward_qty"), "constraints": constraints,
        "campaign_id": data.get("campaign_id"),
    }
    if not config.F02_VALIDATE_URL:
        return jsonify(_demo_validate(payload))
    try:
        result = request_json(config.F02_VALIDATE_URL, payload, timeout=config.N8N_TIMEOUT)
    except N8nError as exc:
        return jsonify(error=str(exc)), 502
    if result.get("status") != "success":
        return jsonify(error=result.get("message") or "제약 검증 결과를 받지 못했어요."), 502
    return jsonify({**result, "source": "n8n"})


@app.post("/api/f01/scan")
def f01_scan():
    """F-01: 내일부터 7일의 옥외 캠페인 기회를 점수화해 카드 3건을 받아 온다."""
    data = request.get_json(silent=True) or {}
    store = next((s for s in STORES if s["id"] == data.get("store_id")), None)
    if not store:
        return jsonify(error="기회를 찾을 매장을 선택해 주세요."), 400

    if not config.F01_SCAN_URL:
        time.sleep(0.6)
        return jsonify(_demo_scan(store))

    try:
        result = request_json(config.F01_SCAN_URL, {"store_id": store["id"], "storeName": store["name"]},
                              timeout=config.N8N_TIMEOUT)
    except N8nError as exc:
        return jsonify(error=str(exc)), 502
    if result.get("status") != "success":
        return jsonify(error=result.get("message") or "기회 스캔 결과를 받지 못했어요."), 502
    return jsonify({**result, "source": "n8n"})


@app.post("/api/f01/select")
def f01_select():
    """F-01: 점장이 고른 기회 카드로 캠페인을 연다 (기획 마감 = 선택 후 3시간)."""
    data = request.get_json(silent=True) or {}
    try:
        card_id = int(data.get("card_id"))
    except (TypeError, ValueError):
        return jsonify(error="선택한 카드 번호가 없어요. 기회 스캔을 다시 실행해 주세요."), 400

    if not config.F01_SELECT_URL:
        return jsonify(_demo_select(card_id, data.get("target_date"), data.get("store_id")))

    try:
        result = request_json(config.F01_SELECT_URL, {"card_id": card_id}, timeout=config.N8N_TIMEOUT)
    except N8nError as exc:
        return jsonify(error=str(exc)), 502
    if result.get("status") != "success":
        # 이미 선택된 카드 · 없는 카드 등 (F01_select 의 '오류 응답')
        return jsonify(error=result.get("message") or "카드를 선택하지 못했어요."), 409
    return jsonify({**result, "source": "n8n"})


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
    f02 = data.get("f02")
    if isinstance(f02, dict):
        # 기존 plan-gen 워크플로는 constraints 문장만 읽으므로, 검증된 조건을 문장으로 앞에 붙인다
        payload["constraints"] = _f02_brief(f02, target["label"]) + (f" / 추가 조건: {constraints}" if constraints else "")
        # F-02 검증을 통과한 파라미터 (날짜 · 시간대 · 장소 · 출동 인력 · 예산 · 사은품)
        payload["f02"] = f02
        payload["campaignId"] = data.get("campaign_id")

    if not config.N8N_WEBHOOK_URL:
        time.sleep(1.0)
        return jsonify(plan=_demo_plan(store_name, target["label"], constraints), source="demo")

    try:
        plan = request_plan(config.N8N_WEBHOOK_URL, payload, timeout=config.N8N_TIMEOUT)
    except N8nError as exc:
        return jsonify(error=str(exc)), 502
    return jsonify(plan=plan, source="n8n")


def _f02_brief(f02, target_label):
    """F-02 통과 조건을 plan-gen 이 그대로 따를 문장으로 만든다."""
    staff = " + ".join(f"{p.get('employee_name')}({p.get('employment_type')})" for p in f02.get("staff") or [])
    parts = [
        f"운영 일자 {f02.get('target_date')}" if f02.get("target_date") else "",
        f"운영 시간 {str(f02.get('operating_hours') or '').replace('-', '~')}" if f02.get("operating_hours") else "",
        f"운영 장소 {f02.get('site_name')} (이 장소로 입지를 확정)" if f02.get("site_name") else "",
        f"타깃 {target_label}",
        f"출동 {staff}" if staff else "",
        f"예산 {int(f02['budget']):,}원 이내" if f02.get("budget") else "",
        f"사은품 {f02.get('reward_item')} {f02.get('reward_qty')}개" if f02.get("reward_item") and f02.get("reward_qty") else "",
    ]
    return "[F-02 검증 통과 조건] " + " / ".join(p for p in parts if p)


_DEMO_STAFF = [
    ("E01", "김도윤", "정규직", "10:00", "19:00"), ("E02", "이서연", "정규직", "11:00", "20:00"),
    ("E03", "박준호", "정규직", "10:00", "19:00"), ("E04", "최하은", "정규직", "11:00", "20:00"),
    ("P01", "윤채원", "아르바이트", "10:00", "16:00"), ("P02", "임시우", "아르바이트", "14:00", "20:00"),
    ("P03", "한예린", "아르바이트", "14:00", "20:00"),
]


def _demo_options(store, target_date):
    return {"status": "success", "action": "options", "source": "demo", "store_id": store["id"],
            "target_date": target_date, "roster_found": True,
            "staff": [{"employee_id": f"DEMO-{i}", "employee_name": n, "employment_type": t,
                       "start_time": a, "end_time": b} for i, n, t, a, b in _DEMO_STAFF],
            "sites": [{"site_id": "DEMO-S1", "site_name": "석촌호수 동호 산책로", "distance_to_store_m": 1650},
                      {"site_id": "DEMO-S2", "site_name": "잠실새내역 4번 출구 앞", "distance_to_store_m": 72}],
            "rewards": [{"item_name": "또리 키링", "quantity": 200}]}


def _demo_validate(p):
    """데모: 핵심 규칙(2인 1조 · 알바 단독 배제 · 예산)만 흉내 낸다. 실제 판정은 n8n F02_validate."""
    staff = {f"DEMO-{i}": (n, t) for i, n, t, _, _ in _DEMO_STAFF}
    picked = [staff[x] for x in dict.fromkeys(p["staff_ids"]) if x in staff]
    checks = []
    if len(picked) != 2:
        checks.append(("R-01", "2인 1조 편성", False, "출동 인력은 서로 다른 2명이어야 합니다 (2인 1조)."))
    elif all(t == "아르바이트" for _, t in picked):
        checks.append(("R-01", "2인 1조 편성", False, "아르바이트끼리는 출동할 수 없습니다. 정규직을 1명 이상 넣어 주세요 (알바 단독 배제)."))
    else:
        checks.append(("R-01", "2인 1조 편성", True, " + ".join(f"{n}({t})" for n, t in picked)))
    try:
        budget = int(p["budget"])
    except (TypeError, ValueError):
        budget = 0
    checks.append(("B-01", "집행 예산", 0 < budget <= BUDGET_MAX,
                   f"{budget:,}원" if 0 < budget <= BUDGET_MAX else f"예산은 1원 ~ {BUDGET_MAX:,}원이어야 합니다."))
    rows = [{"code": c, "label": l, "ok": ok, "level": "pass" if ok else "block", "message": m} for c, l, ok, m in checks]
    valid = all(r["ok"] for r in rows)
    return {"status": "success", "action": "validate", "source": "demo", "isValid": valid, "checks": rows,
            "saved": False, "message": "데모 판정" if valid else "\n".join(r["message"] for r in rows if not r["ok"]),
            "f02": {"target_date": p["target_date"], "operating_hours": p["operating_hours"], "budget": budget,
                    "staff": [{"employee_name": n, "employment_type": t} for n, t in picked]}}


def _demo_scan(store):
    """n8n 없이 F-01 화면 흐름을 확인하는 샘플 카드 3건."""
    today = datetime.now(timezone(timedelta(hours=9))).date()
    samples = [(5, "주말", "weekend", 89, 2), (4, "공휴일", "holiday", 87, 1), (6, "공휴일", "holiday", 71, 1)]
    cards = []
    for rank, (days, label, day_type, score, teams) in enumerate(samples, start=1):
        cards.append({
            "card_id": -rank, "rank": rank, "target_date": (today + timedelta(days=days)).isoformat(),
            "day_type": day_type, "score": score, "score_status": "partial",
            "title": f"{label} 공원 가족 나들이 (데모)",
            "summary": "가족 유동이 높은 날입니다. 데모 모드라 실제 기상·행사 데이터는 반영되지 않았습니다.",
            "risk": "데모 데이터입니다.", "tags": ["확인 필요: 기상 지표 없음"], "teams": teams,
            "top_site": {"site_name": "석촌호수 동호 산책로", "distance_to_store_m": 1650},
            "indicators": {
                "footfall": {"label": "유동", "score": 95, "note": "데모"},
                "event": {"label": "행사", "score": 70, "note": "데모"},
                "weather": {"label": "기상", "score": None, "note": "데이터 없음"},
                "promo": {"label": "프로모션", "score": 100, "note": "데모"},
                "staff": {"label": "출동 인력", "score": 100 if teams >= 2 else 70, "note": "데모"},
            },
        })
    return {"status": "success", "source": "demo", "store_id": store["id"], "store_name": store["name"],
            "scannedAt": datetime.now(timezone.utc).isoformat(), "dataTags": [],
            "sources": {"kma": True, "tour": True, "roster": True, "dummy": True, "llm": True, "db": True},
            "cards": cards}


def _demo_select(card_id, target_date, store_id):
    now = datetime.now(timezone.utc)
    return {"status": "success", "source": "demo", "campaign": {
        "campaign_id": "DEMO", "card_id": card_id, "store_id": store_id, "target_date": target_date,
        "selection_status": "selected", "selected_at": now.isoformat(),
        "plan_due_at": (now + timedelta(hours=3)).isoformat(),
    }}


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
