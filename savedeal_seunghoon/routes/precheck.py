from flask import Blueprint, current_app, jsonify, request

from schemas.precheck_schema import PrecheckValidationError, validate_precheck_request
from services.precheck_service import PrecheckService

precheck_bp = Blueprint("precheck", __name__, url_prefix="/api")


@precheck_bp.route("/precheck", methods=["POST"])
def precheck():
    payload = request.get_json(silent=True)

    try:
        validate_precheck_request(payload)
    except PrecheckValidationError as exc:
        return (
            jsonify(
                {
                    "success": False,
                    "data": None,
                    "error": {"code": "VALIDATION_ERROR", "message": "; ".join(exc.errors)},
                }
            ),
            400,
        )

    service = PrecheckService(current_app.config["DATA_DIR"], current_app.config["DB_PATH"])
    result = service.run(payload)

    return jsonify({"success": True, "data": result, "error": None}), 200
