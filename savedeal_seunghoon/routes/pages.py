from flask import Blueprint, current_app, redirect, render_template, url_for

from repositories.customer_repository import CustomerRepository
from repositories.device_repository import DeviceRepository
from repositories.store_repository import StoreRepository
from services.dashboard_service import FILTERS

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


@pages_bp.route("/savedeal/new", methods=["GET"])
def savedeal_new():
    """신규 예약 등록과 사전검증."""
    data_dir = current_app.config["DATA_DIR"]
    stores = StoreRepository(data_dir).load_all()
    customers = CustomerRepository(data_dir).load_all()
    devices = DeviceRepository(data_dir).load_all()

    return render_template(
        "savedeal_new.html",
        active_nav="new",
        stores=stores,
        customers=customers,
        devices=devices,
        line_types=LINE_TYPES,
    )
