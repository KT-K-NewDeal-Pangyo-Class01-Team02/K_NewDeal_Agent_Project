from flask import Blueprint, current_app, jsonify, request, send_file
import io

from services.ai_service import AIService
from services.dashboard_service import DashboardService
from services.notification_service import NotificationService
from services.reservation_service import ReservationService
from services.upload_service import KINDS, UploadError, UploadService

uploads_bp = Blueprint("uploads", __name__, url_prefix="/api/uploads")


def _ok(data, status: int = 200):
    return jsonify({"success": True, "data": data, "error": None}), status


def _error(code: str, message: str, status: int):
    return jsonify({"success": False, "data": None, "error": {"code": code, "message": message}}), status


def _service() -> UploadService:
    return UploadService(current_app.config["DB_PATH"], current_app.config["DATA_DIR"])


@uploads_bp.route("/template/<kind>", methods=["GET"])
def download_template(kind):
    if kind not in KINDS:
        return _error("NOT_FOUND", "양식 종류를 찾을 수 없습니다.", 404)
    content = _service().template(kind)
    return send_file(
        io.BytesIO(content),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"savedeal_{kind}_template.xlsx",
    )


@uploads_bp.route("", methods=["GET"])
def list_uploads():
    return _ok({"items": _service().list_batches()})


@uploads_bp.route("", methods=["POST"])
def preview_upload():
    kind = request.form.get("kind", "")
    file = request.files.get("file")
    if file is None or not file.filename:
        return _error("VALIDATION_ERROR", "업로드할 파일을 선택해 주세요.", 400)
    try:
        batch = _service().preview(kind, file.filename, file.read())
    except UploadError as exc:
        return _error("VALIDATION_ERROR", str(exc), 400)
    return _ok(batch, 201)


@uploads_bp.route("/<int:batch_id>/commit", methods=["POST"])
def commit_upload(batch_id):
    db_path, data_dir = current_app.config["DB_PATH"], current_app.config["DATA_DIR"]
    dashboard = DashboardService(db_path, data_dir)
    ai = AIService(db_path, current_app.config)
    try:
        batch = _service().commit(batch_id, ReservationService(db_path, data_dir, ai_service=ai), dashboard)
    except LookupError as exc:
        return _error("NOT_FOUND", str(exc), 404)
    except ValueError as exc:
        return _error("INVALID_STATE", str(exc), 409)

    # 업로드 결과 메일 + 새로 들어온 고위험 예약 경보 (n8n → Gmail, 미연결이면 데모 기록)
    notifier = NotificationService(db_path, current_app.config)
    batch["notification"] = notifier.notify_upload(batch)
    reservation_ids = (batch.get("result") or {}).get("reservation_ids") or []
    if reservation_ids:
        notifier.notify_high_risk([dashboard.get_detail(rid) for rid in reservation_ids])
    return _ok(batch)


@uploads_bp.route("/<int:batch_id>/cancel", methods=["POST"])
def cancel_upload(batch_id):
    try:
        batch = _service().cancel(batch_id)
    except LookupError as exc:
        return _error("NOT_FOUND", str(exc), 404)
    except ValueError as exc:
        return _error("INVALID_STATE", str(exc), 409)
    return _ok(batch)
