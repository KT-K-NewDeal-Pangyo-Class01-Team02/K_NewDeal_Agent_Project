from flask import Blueprint, current_app, redirect, render_template, url_for

from repositories.customer_repository import CustomerRepository
from repositories.device_repository import DeviceRepository
from repositories.store_repository import StoreRepository
from services.carriers import PREVIOUS_CARRIER_CODES, carrier_info
from services.dashboard_service import FILTERS
from services.device_images import image_for
from services.upload_service import KINDS as UPLOAD_KINDS

pages_bp = Blueprint("pages", __name__)

LINE_TYPES = [
    ("NEW", "신규가입"),
    ("MNP", "번호이동"),
    ("CHANGE", "기기변경"),
]


@pages_bp.route("/", methods=["GET"])
def home():
    # 홈 화면은 공용 Command Center(command_center/)가 담당한다.
    return redirect(url_for("pages.savedeal"))


@pages_bp.route("/savedeal", methods=["GET"])
def savedeal():
    """메인: 예약 운영 대시보드. 목록·상세는 /api/reservations 에서 불러온다."""
    return render_template("savedeal.html", active_nav="agents", filters=FILTERS)


@pages_bp.route("/savedeal/upload", methods=["GET"])
def savedeal_upload():
    """엑셀·CSV 일괄 업로드 (사전예약 명단 · 고객 정보 · 재고 현황)."""
    kinds = [{"key": key, "label": spec["label"], "description": spec["description"],
              "columns": [{"label": header, "required": required} for _, header, required, _ in spec["columns"]]}
             for key, spec in UPLOAD_KINDS.items()]
    return render_template("savedeal_upload.html", active_nav="upload", kinds=kinds)


@pages_bp.route("/savedeal/new", methods=["GET"])
def savedeal_new():
    """신규 예약 등록과 사전검증."""
    data_dir = current_app.config["DATA_DIR"]
    stores = StoreRepository(data_dir).load_all()
    customers = CustomerRepository(data_dir, current_app.config["DB_PATH"]).load_all()
    devices = DeviceRepository(data_dir).load_all()
    for device in devices:
        image = image_for(device)
        device["image_url"] = url_for("static", filename=image["path"]) if image else None

    return render_template(
        "savedeal_new.html",
        active_nav="new",
        stores=stores,
        customers=customers,
        devices=devices,
        line_types=LINE_TYPES,
        previous_carriers=[carrier_info(code) for code in PREVIOUS_CARRIER_CODES],
    )
