"""외부 이벤트·정기 점검 API (n8n 이 부른다).

    POST /api/events          n8n → SaveDeal: 외부 이벤트 반영 (한 건 또는 {"events": [...]})
    POST /api/events/sync     가져오기 모드: SaveDeal → n8n(N8N_EVENTS_URL) 에서 이벤트를 받아 반영 + 정기 점검
    GET  /api/events          최근 받은 이벤트 (대시보드가 바뀐 게 있는지 확인하는 데 쓴다)
    POST /api/monitor/scan    정기 점검: 새로 고위험이 된 예약 알림

n8n 이 부르는 주소(events, monitor/scan)는 .env 의 N8N_WEBHOOK_SECRET 을 헤더(N8N_SECRET_HEADER)로 보내야 한다.
비밀값을 정하지 않았으면 이 컴퓨터에서 직접 온 요청만 받는다 (ngrok 등 외부 공개 주소로 온 요청은 거절).
"""
import hmac

from flask import Blueprint, current_app, jsonify, request

from services import n8n_client
from services.dashboard_service import DashboardService
from services.event_service import RESULT_APPLIED, EventService
from services.monitor_service import MonitorService
from services.notification_service import NotificationService, mask_name

events_bp = Blueprint("events", __name__, url_prefix="/api")

LOCAL_ADDRESSES = {"127.0.0.1", "::1"}
FORWARD_HEADERS = ("X-Forwarded-For", "X-Forwarded-Host", "X-Real-IP", "Forwarded")
MAX_EVENTS = 500


def _ok(data, status: int = 200):
    return jsonify({"success": True, "data": data, "error": None}), status


def _error(code: str, message: str, status: int):
    return jsonify({"success": False, "data": None, "error": {"code": code, "message": message}}), status


def _args():
    return current_app.config["DB_PATH"], current_app.config["DATA_DIR"]


def _auth_error():
    """n8n 이 부르는 주소의 인증. 통과하면 None, 아니면 오류 응답."""
    secret = current_app.config.get("N8N_WEBHOOK_SECRET", "")
    if secret:
        header = current_app.config.get("N8N_SECRET_HEADER") or "X-SaveDeal-Key"
        if hmac.compare_digest(request.headers.get(header, ""), secret):
            return None
        return _error("UNAUTHORIZED", f"인증에 실패했습니다. {header} 헤더에 N8N_WEBHOOK_SECRET 값을 넣어 주세요.", 401)
    is_local = request.remote_addr in LOCAL_ADDRESSES and not any(h in request.headers for h in FORWARD_HEADERS)
    if is_local:
        return None
    return _error("FORBIDDEN", "외부에서 이벤트를 받으려면 .env 에 N8N_WEBHOOK_SECRET 을 설정해 주세요.", 403)


def _apply_and_notify(raw_events: list) -> dict:
    """이벤트를 반영하고, 반영된 것이 있으면 담당자에게 한 통으로 알린다."""
    results = EventService(*_args()).apply_batch(raw_events)
    applied = [r for r in results if r["result"] == RESULT_APPLIED]

    notification = None
    if applied:
        dashboard = DashboardService(*_args())
        lines, high = [], []
        for item in applied:
            detail = dashboard.get_detail(item["reservation_id"])
            risk = f"{detail['risk_label']} {detail['churn_risk_score']}점 · " if detail["is_open"] else ""
            lines.append(
                f"- {item['reservation_id']} · {mask_name(detail['customer_name'])} · {item['message']} "
                f"→ {risk}{detail['status_label']}"
            )
            if detail["risk_level"] == "high":
                high.append(item["reservation_id"])
        notifier = NotificationService(current_app.config["DB_PATH"], current_app.config)
        reservation_id = applied[0]["reservation_id"] if len({r["reservation_id"] for r in applied}) == 1 else None
        notification = notifier.notify_external_events(lines, reservation_id)
        # 이 메일로 고위험 사실을 이미 알렸으므로 정기 점검이 다시 알리지 않게 한다
        notifier.mark_alerted(high)

    counts = {}
    for r in results:
        counts[r["result"]] = counts.get(r["result"], 0) + 1
    return {"received": len(results), "counts": counts, "results": results, "notification": notification}


@events_bp.route("/events", methods=["POST"])
def receive_events():
    denied = _auth_error()
    if denied:
        return denied
    payload = request.get_json(silent=True)
    if isinstance(payload, dict) and "events" in payload:
        payload = payload["events"]
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list) or not payload:
        return _error("VALIDATION_ERROR", "이벤트 한 건(JSON 객체)이나 목록, 또는 {\"events\": [...]} 를 보내 주세요.", 400)
    if len(payload) > MAX_EVENTS:
        return _error("VALIDATION_ERROR", f"한 번에 {MAX_EVENTS}건까지 보낼 수 있습니다.", 400)
    return _ok(_apply_and_notify(payload))


@events_bp.route("/events/sync", methods=["POST"])
def sync_events():
    """가져오기 모드. 대시보드가 주기적으로 부른다. 주소가 없으면 아무것도 하지 않는다."""
    url = current_app.config.get("N8N_EVENTS_URL", "")
    if not url:
        return _ok({"enabled": False, "received": 0, "counts": {}, "results": [], "notification": None})
    config = current_app.config
    try:
        raw_events = n8n_client.fetch_events(
            url,
            timeout=float(config.get("N8N_TIMEOUT", 8)),
            secret=config.get("N8N_WEBHOOK_SECRET", ""),
            secret_header=config.get("N8N_SECRET_HEADER", ""),
        )
    except n8n_client.N8nError as exc:
        return _error("N8N_ERROR", str(exc), 502)
    result = _apply_and_notify(raw_events[:MAX_EVENTS])
    # 가져오기 모드에서는 n8n 이 정기 점검 주소도 부를 수 없으므로 여기서 함께 점검한다 (이미 알린 예약은 다시 알리지 않음)
    result["scan"] = MonitorService(*_args(), config).scan()
    return _ok({"enabled": True, **result})


@events_bp.route("/events", methods=["GET"])
def list_events():
    limit = min(max(request.args.get("limit", 20, type=int), 1), 100)
    return _ok(EventService(*_args()).recent(limit))


@events_bp.route("/monitor/scan", methods=["POST"])
def monitor_scan():
    denied = _auth_error()
    if denied:
        return denied
    return _ok(MonitorService(*_args(), current_app.config).scan())
