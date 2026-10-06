from flask import Blueprint, current_app, jsonify, request

from services.codes import ISSUE_LABELS

from db.connection import reset_database
from schemas.precheck_schema import PrecheckValidationError, validate_precheck_request
from services.action_service import ActionError, ActionService
from services.ai_service import AIService
from services.dashboard_service import FILTER_ALL, DashboardService
from services.notification_service import NotificationService, mask_name
from services.reservation_service import ReservationService

reservations_bp = Blueprint("reservations", __name__, url_prefix="/api")


def _ok(data, status: int = 200):
    return jsonify({"success": True, "data": data, "error": None}), status


def _error(code: str, message: str, status: int):
    return jsonify({"success": False, "data": None, "error": {"code": code, "message": message}}), status


def _args():
    return current_app.config["DB_PATH"], current_app.config["DATA_DIR"]


def _ai() -> AIService:
    return AIService(current_app.config["DB_PATH"], current_app.config)


def _notifier() -> NotificationService:
    return NotificationService(current_app.config["DB_PATH"], current_app.config)


def _detail(reservation_id: str) -> dict | None:
    detail = DashboardService(*_args()).get_detail(reservation_id)
    if detail is not None:
        detail["notifications"] = _notifier().list_recent(limit=10, reservation_id=reservation_id)
    return detail


def _detail_or_404(reservation_id: str):
    detail = _detail(reservation_id)
    if detail is None:
        return _error("NOT_FOUND", "예약을 찾을 수 없습니다.", 404)
    return _ok(detail)


@reservations_bp.route("/reservations", methods=["GET"])
def list_reservations():
    filter_key = request.args.get("filter", FILTER_ALL)
    try:
        data = DashboardService(*_args()).list_reservations(
            filter_key, status=request.args.get("status"), risk=request.args.get("risk")
        )
    except ValueError as exc:
        return _error("VALIDATION_ERROR", str(exc), 400)
    return _ok(data)


@reservations_bp.route("/reservations", methods=["POST"])
def create_reservation():
    payload = request.get_json(silent=True)
    try:
        validate_precheck_request(payload)
    except PrecheckValidationError as exc:
        return _error("VALIDATION_ERROR", "; ".join(exc.errors), 400)

    reservation_id, _ = ReservationService(*_args(), ai_service=_ai()).create(payload)
    _notifier().notify_high_risk([DashboardService(*_args()).get_detail(reservation_id)])
    return _ok(_detail(reservation_id), 201)


@reservations_bp.route("/reservations/<reservation_id>", methods=["GET"])
def get_reservation(reservation_id):
    return _detail_or_404(reservation_id)


def _run_action(reservation_id: str, operation):
    try:
        operation(ActionService(*_args()))
    except ActionError as exc:
        return _error(exc.code, exc.message, exc.http_status)
    return _detail_or_404(reservation_id)


@reservations_bp.route("/reservations/<reservation_id>/actions/<int:action_id>/approve", methods=["POST"])
def approve_action(reservation_id, action_id):
    def approve_and_notify(service: ActionService):
        service.approve(reservation_id, action_id)
        # 고객에게 안내가 필요한 해결책이면 AI(또는 규칙)로 안내문을 쓰고 n8n → Gmail 로 (가상) 발송한다
        action = service.action_repo.find_by_id(action_id)
        notifier = _notifier()
        if action["action_type"] in notifier_customer_actions():
            reservation = service.reservation_repo.find_by_id(reservation_id)
            name = mask_name(reservation["customer_name"])
            issue_label = ISSUE_LABELS.get(action["issue_code"], action["issue_code"])
            notice = _ai().compose_notice(name, action, issue_label, reservation_id)
            text = notice["text"]
            if notice["source"] == "ai":
                text += f"\n\n(AI 작성 · {notice['model']} · {notice['latency_ms'] / 1000:.1f}초)"
            else:
                text += "\n\n(규칙 기반 문구 · AI 꺼짐)"
            notifier.notify_customer(reservation_id, action, text)

    return _run_action(reservation_id, approve_and_notify)


def notifier_customer_actions():
    from services.notification_service import CUSTOMER_FACING_ACTIONS

    return CUSTOMER_FACING_ACTIONS


@reservations_bp.route("/reservations/<reservation_id>/briefing", methods=["POST"])
def staff_briefing(reservation_id):
    """상세 패널의 'AI 브리핑': 이 예약이 왜 급한지 3줄 요약 (AI 꺼져 있으면 규칙 기반)."""
    detail = DashboardService(*_args()).get_detail(reservation_id)
    if detail is None:
        return _error("NOT_FOUND", "예약을 찾을 수 없습니다.", 404)
    return _ok(_ai().staff_briefing(detail, mask_name(detail["customer_name"])))


@reservations_bp.route("/notifications", methods=["GET"])
def list_notifications():
    return _ok({"items": _notifier().list_recent(limit=20)})


@reservations_bp.route("/notifications/<int:notification_id>/retry", methods=["POST"])
def retry_notification(notification_id):
    try:
        return _ok(_notifier().retry(notification_id))
    except LookupError as exc:
        return _error("NOT_FOUND", str(exc), 404)
    except ValueError as exc:
        return _error("INVALID_STATE", str(exc), 409)


@reservations_bp.route("/notifications/daily-report", methods=["POST"])
def send_daily_report():
    """운영 리포트 메일 (대시보드 버튼 · n8n 스케줄에서 호출)."""
    data = DashboardService(*_args()).list_reservations("all")
    open_items = [item for item in data["items"] if item["is_open"]]
    return _ok(_notifier().daily_report(data["summary"], data["summary_notes"], open_items))


@reservations_bp.route("/integrations", methods=["GET"])
def integrations_status():
    """연동 상태: n8n(Gmail) 연결 여부, AI 사용 여부와 최근 AI 기록."""
    ai = _ai()
    config = current_app.config
    return _ok({
        "n8n": {"mode": _notifier().mode},
        "ai": {"mode": ai.mode, "model": ai.model},
        "ai_logs": ai.recent_logs(limit=8),
        # 외부 이벤트: n8n 이 보내 주는 방식(항상 열려 있음)과 SaveDeal 이 가져오는 방식(N8N_EVENTS_URL)
        "events": {
            "pull": bool(config.get("N8N_EVENTS_URL")),
            "sync_seconds": max(int(config.get("EVENT_SYNC_SECONDS", 60)), 15),
            "inbound_auth": "secret" if config.get("N8N_WEBHOOK_SECRET") else "local-only",
        },
    })


@reservations_bp.route("/reservations/<reservation_id>/actions/<int:action_id>/succeed", methods=["POST"])
def succeed_action(reservation_id, action_id):
    return _run_action(reservation_id, lambda service: service.succeed(reservation_id, action_id))


@reservations_bp.route("/reservations/<reservation_id>/actions/<int:action_id>/fail", methods=["POST"])
def fail_action(reservation_id, action_id):
    return _run_action(reservation_id, lambda service: service.fail(reservation_id, action_id))


@reservations_bp.route("/reservations/<reservation_id>/complete", methods=["POST"])
def complete_reservation(reservation_id):
    return _run_action(reservation_id, lambda service: service.complete_activation(reservation_id))


@reservations_bp.route("/demo/reset", methods=["POST"])
def reset_demo_data():
    """시연용: 운영 DB를 mock 데이터로 다시 채운다."""
    reset_database(current_app.config["DB_PATH"])
    return _ok({"reset": True})
