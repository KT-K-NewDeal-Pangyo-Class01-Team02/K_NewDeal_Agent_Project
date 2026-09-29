from flask import Blueprint, current_app, jsonify, request

from db.connection import reset_database
from schemas.precheck_schema import PrecheckValidationError, validate_precheck_request
from services.action_service import ActionError, ActionService
from services.dashboard_service import FILTER_ALL, DashboardService
from services.reservation_service import ReservationService

reservations_bp = Blueprint("reservations", __name__, url_prefix="/api")


def _ok(data, status: int = 200):
    return jsonify({"success": True, "data": data, "error": None}), status


def _error(code: str, message: str, status: int):
    return jsonify({"success": False, "data": None, "error": {"code": code, "message": message}}), status


def _args():
    return current_app.config["DB_PATH"], current_app.config["DATA_DIR"]


def _detail_or_404(reservation_id: str):
    detail = DashboardService(*_args()).get_detail(reservation_id)
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

    reservation_id, _ = ReservationService(*_args()).create(payload)
    detail = DashboardService(*_args()).get_detail(reservation_id)
    return _ok(detail, 201)


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
    return _run_action(reservation_id, lambda service: service.approve(reservation_id, action_id))


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
