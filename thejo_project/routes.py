"""더 줘 Blueprint: Command Center 와 **같은 Flask 프로세스** 안에서 /thejo/ 아래로 붙는다.

등록은 command_center/app.py 가 한다.  app.register_blueprint(thejo_bp)
"""
from flask import Blueprint, jsonify, redirect, render_template, request, url_for

from thejo_project import config
from thejo_project.data import demo_data
from thejo_project.services import (
    insight_service,
    opportunity_service,
    sms_service,
    transaction_service,
    warning_service,
)

# static_url_path 는 url_prefix 뒤에 붙는다. "/static" 으로 두어야 실제 주소가 /thejo/static/... 이 된다.
# ("/thejo/static" 으로 적으면 /thejo/thejo/static/... 이 되어 404 가 난다.)
thejo_bp = Blueprint(
    "thejo",
    __name__,
    url_prefix="/thejo",
    template_folder="templates",
    static_folder="static",
    static_url_path="/static",
)

# 사이드바에서 "더 줘" 항목이 켜져 보이게 한다. command_center/agents.json 의 id 와 같아야 한다.
AGENT_ID = "deo-jwo"


@thejo_bp.app_template_filter("won")
def format_won(value):
    """1100000 → '1,100,000원'"""
    return f"{int(value):,}원"


@thejo_bp.app_template_filter("manwon")
def format_manwon(value):
    """1100000 → '110만', 1150000 → '115만', 50000 → '5만', 0 → '0'"""
    value = int(value)
    if value == 0:
        return "0"
    text = f"{value / 10_000:,.1f}".rstrip("0").rstrip(".")
    return f"{text}만"


# ── 화면 ─────────────────────────────────────────────────────────────────
def _insight_context():
    """인사이트를 쓸 수 있으면 화면에 넘길 값들, 아니면 demo 표시만.

    n8n 조회가 실패해도 여기서 None 이 돌아오므로 화면은 기존 데모 데이터로 그려진다.
    주소에 ?refresh=1 을 붙이면 5분 캐시를 건너뛰고 n8n 에서 다시 받아 온다.
    """
    data = insight_service.get_view_data(
        force_refresh=request.args.get("refresh") == "1"
    )
    if not data:
        return {"insights_source": "demo", "insights_date": None,
                "insight_opportunities": [], "insight_warnings": []}
    return {
        "insights_source": "n8n",
        "insights_date": data["report_date"],
        "insight_opportunities": data["opportunities"],
        "insight_warnings": data["high_risks"],
    }


@thejo_bp.get("/")
def dashboard():
    return render_template(
        "thejo/dashboard.html",
        active_agent_id=AGENT_ID,
        summary=opportunity_service.get_dashboard_summary(),
        warnings=warning_service.get_warning_items(include_acknowledged=False),
        opportunities=opportunity_service.get_profit_opportunities(),
        snapshot=demo_data.get_sales_snapshot(),
        sms_templates=sms_service.template_choices(),
        sms_byte_limit=config.SMS_BYTE_LIMIT,
        **_insight_context(),
    )


@thejo_bp.get("/warnings")
def warnings():
    return render_template(
        "thejo/warnings.html",
        active_agent_id=AGENT_ID,
        warnings=warning_service.get_warning_items(),
        summary=opportunity_service.get_dashboard_summary(),
        sms_templates=sms_service.template_choices(),
        sms_byte_limit=config.SMS_BYTE_LIMIT,
        **_insight_context(),
    )


@thejo_bp.get("/opportunities")
def opportunities():
    insight_ctx = _insight_context()
    summary = opportunity_service.get_dashboard_summary()

    # 시뮬레이터 첫 화면: 카드에서 넘어온 ?insight=<id> 의 기회로 채운다.
    # 인사이트가 없으면(데모) 기존처럼 기본 정책 + 이번 달 판매량으로 채운다.
    sim_notice = None
    rows = insight_ctx["insight_opportunities"]
    if insight_ctx["insights_source"] == "n8n" and rows:
        wanted = (request.args.get("insight") or "").strip()
        row = next((r for r in rows if r["insight_id"] == wanted), None)
        if row is None:
            if wanted:
                sim_notice = "선택한 기회가 최신 데이터에 없어 첫 번째 기회를 보여 드립니다."
            row = rows[0]
        sim = opportunity_service.simulate_insight(row, insight_ctx["insights_date"])
    else:
        sim = opportunity_service.simulate_benefit(summary["units_sold"])

    return render_template(
        "thejo/opportunities.html",
        active_agent_id=AGENT_ID,
        opportunities=opportunity_service.get_profit_opportunities(),
        summary=summary,
        sim=sim,
        sim_notice=sim_notice,
        **insight_ctx,
    )


# ── 경고 조치 ────────────────────────────────────────────────────────────
@thejo_bp.post("/warnings/<warning_id>/ack")
def acknowledge_warning(warning_id):
    """'조치 완료' 버튼. JS 가 꺼져 있어도 동작하도록 폼 전송이면 되돌려 보낸다."""
    ok = warning_service.acknowledge(warning_id)
    if request.headers.get("Accept", "").startswith("application/json"):
        if not ok:
            return jsonify(error="없는 경고입니다."), 404
        return jsonify(id=warning_id, acknowledged=True)
    return redirect(request.referrer or url_for("thejo.warnings"))


# ── 고객 안내 문자 ───────────────────────────────────────────────────────
@thejo_bp.get("/api/transactions/<transaction_id>")
def get_transaction(transaction_id):
    """'거래 확인' 모달이 여는 순간 부르는 API. 거래 정보 + 치환된 문자 템플릿 3개."""
    tx = transaction_service.get_transaction(transaction_id)
    if not tx:
        return jsonify(error="거래를 찾지 못했습니다."), 404
    return jsonify(
        transaction=transaction_service.to_json(tx),
        templates=sms_service.rendered_templates(tx),
        sms_byte_limit=config.SMS_BYTE_LIMIT,
    )


@thejo_bp.post("/api/sms/send")
def send_sms():
    """문자 발송. n8n Webhook URL 은 서버에서만 읽고 절대 응답에 담지 않는다."""
    data = request.get_json(silent=True) or {}

    transaction_id = (data.get("transaction_id") or "").strip()
    message = (data.get("message") or "").strip()
    template_id = (data.get("template_id") or "").strip()

    tx = transaction_service.get_transaction(transaction_id)
    if not tx:
        return jsonify(success=False, error="거래를 찾지 못했습니다."), 404
    if not message:
        return jsonify(success=False, error="보낼 문자 내용을 입력해 주세요."), 400
    if not tx["customer_phone"]:
        return jsonify(success=False, error="고객 전화번호가 없어 전송할 수 없습니다."), 400
    if template_id and template_id not in sms_service.TEMPLATE_BY_ID:
        return jsonify(success=False, error="알 수 없는 문자 템플릿입니다."), 400

    # 화면이 보낸 값을 그대로 믿지 않는다. 고객·거래 정보는 서버 데이터로 다시 채운다.
    payload = {
        "transaction_id": tx["transaction_id"],
        "customer_id": tx["customer_id"],
        "customer_name": tx["customer_name"],
        "customer_phone": tx["customer_phone"],
        "template_id": template_id or None,
        "message": message,
        "plan_name": tx["plan_name"],
        "maintenance_end_date": tx["maintenance_end_date"].isoformat(),
        "remaining_days": tx["remaining_days"],
        "expected_clawback": tx["expected_clawback"],
        "store_id": tx["store_id"],
        "store_phone": tx["store_phone"],
    }

    result, status = sms_service.send_sms(payload)
    if result.get("success"):
        result["message_kind"] = sms_service.message_kind(message)
        result["transaction_id"] = tx["transaction_id"]
    return jsonify(result), status


# ── 시뮬레이션 ───────────────────────────────────────────────────────────
@thejo_bp.get("/api/simulate")
def simulate():
    """혜택 시뮬레이션. 금액 계산은 전부 서버(Python)에서 한다."""
    try:
        units = int(request.args.get("units", ""))
    except ValueError:
        return jsonify(error="판매 건수를 숫자로 보내 주세요."), 400
    if not 0 <= units <= 999:
        return jsonify(error="판매 건수는 0~999 사이여야 합니다."), 400

    # 선택한 기회(카드). 화면이 보낸 금액은 믿지 않고, 서버의 최신 인사이트에서 다시 찾는다.
    insight_id = (request.args.get("insight_id") or "").strip()
    device = (request.args.get("device_model_name") or "").strip()
    plan = (request.args.get("plan_code") or "").strip()
    row, report_date = None, None
    if insight_id or device or plan:
        row, report_date = insight_service.find_opportunity(insight_id, device, plan)
        if row is None:
            return jsonify(error="선택한 기회를 최신 데이터에서 찾지 못했습니다. 페이지를 새로고침해 주세요."), 404
        if (device and device != row["device_model_name"]) or (plan and plan != row["plan_code"]):
            return jsonify(error="선택한 단말기·요금제가 최신 데이터와 다릅니다. 페이지를 새로고침해 주세요."), 409

    return jsonify(opportunity_service.simulate(units, row, report_date))
