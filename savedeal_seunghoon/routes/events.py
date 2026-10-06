"""외부 이벤트·정기 점검 API (n8n 이 부른다).

    POST /api/events          n8n → SaveDeal: 외부 이벤트 반영 (한 건 또는 {"events": [...]})
    POST /api/events/sync     가져오기 모드를 지금 바로 실행 (평소에는 서버가 services/event_sync.py 로 주기 실행)
    GET  /api/events          최근 받은 이벤트 (대시보드가 바뀐 게 있는지 확인하는 데 쓴다)
    POST /api/monitor/scan    정기 점검: 새로 고위험이 된 예약 알림
    POST /api/events/trigger  대시보드 '이벤트 발생' 버튼: 외부 이벤트를 바로 만들어 반영 (services/event_trigger.py)

n8n 이 부르는 주소(events, monitor/scan)는 .env 의 N8N_WEBHOOK_SECRET 을 헤더(N8N_SECRET_HEADER)로 보내야 한다.
비밀값을 정하지 않았으면 이 컴퓨터에서 직접 온 요청만 받는다 (ngrok 등 외부 공개 주소로 온 요청은 거절).
"""
import hmac

from flask import Blueprint, current_app, jsonify, request

from services import n8n_client
from services.event_service import EventService
from services.event_sync import EVENT_LOCK, MAX_EVENTS, apply_and_notify, notify_applied, sync_once
from services.event_trigger import EventTrigger, TriggerError
from services.monitor_service import MonitorService

events_bp = Blueprint("events", __name__, url_prefix="/api")

LOCAL_ADDRESSES = {"127.0.0.1", "::1"}
FORWARD_HEADERS = ("X-Forwarded-For", "X-Forwarded-Host", "X-Real-IP", "Forwarded")


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
    return _ok(apply_and_notify(current_app.config, payload))


@events_bp.route("/events/sync", methods=["POST"])
def sync_events():
    """지금 바로 가져오기 (평소에는 서버의 백그라운드 작업이 EVENT_SYNC_SECONDS 마다 한다).
    주소가 없으면 아무것도 하지 않는다. 가져오기 모드에서는 n8n 이 정기 점검 주소를 부를 수 없으므로 함께 점검한다."""
    config = current_app.config
    try:
        return _ok(sync_once(config, scan=bool(config.get("N8N_EVENTS_URL"))))
    except n8n_client.N8nError as exc:
        return _error("N8N_ERROR", str(exc), 502)


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


@events_bp.route("/events/trigger", methods=["POST"])
def trigger_event():
    """대시보드 '이벤트 발생' 버튼. 첫 번째는 정하늘을 1위로, 그다음부터는 무작위 한 명에게 이벤트 하나."""
    try:
        with EVENT_LOCK:
            result = EventTrigger(*_args()).trigger()
            result["notification"] = notify_applied(current_app.config, result["results"])
    except TriggerError as exc:
        return _error("NO_TARGET", str(exc), 409)
    return _ok(result)
