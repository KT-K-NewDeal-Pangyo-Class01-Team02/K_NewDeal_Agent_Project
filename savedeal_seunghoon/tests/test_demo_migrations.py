from db.connection import connect
from db.demo_migrations import DEMO_DATA_VERSION, get_version, set_version, upgrade
from repositories.reservation_repository import ReservationRepository

OLD_S25 = ("Galaxy S25 Ultra", "Titanium Gray", "256GB")


def make_old_db(db_path):
    """예전 버전 DB 흉내: R2005·R2012 를 예전 단말로, 버전 기록은 1."""
    with connect(db_path) as conn:
        conn.execute("UPDATE reservations SET device_model=?, device_color=?, device_storage=? "
                     "WHERE reservation_id IN ('R2005', 'R2012')", OLD_S25)
    set_version(db_path, 1)


def test_new_database_is_already_latest(db_path):
    assert get_version(db_path) == DEMO_DATA_VERSION
    assert upgrade(db_path) == {}


def test_upgrade_fixes_old_demo_devices(db_path):
    make_old_db(db_path)

    applied = upgrade(db_path)

    repo = ReservationRepository(db_path)
    assert repo.find_by_id("R2005")["device"]["model"] == "iPhone 18 Pro"
    assert repo.find_by_id("R2012")["device"]["model"] == "Galaxy Z Fold8"
    assert applied == {2: 2}
    assert get_version(db_path) == DEMO_DATA_VERSION
    assert upgrade(db_path) == {}  # 한 번만 실행된다


def test_upgrade_leaves_changed_or_user_data_alone(db_path):
    make_old_db(db_path)
    with connect(db_path) as conn:
        # 사용자가 이미 다른 단말로 바꾼 mock 예약
        conn.execute("UPDATE reservations SET device_model='iPhone 16', device_color='Blue', device_storage='128GB' "
                     "WHERE reservation_id = 'R2012'")

    upgrade(db_path)

    assert ReservationRepository(db_path).find_by_id("R2012")["device"]["model"] == "iPhone 16"


def test_database_without_version_record_is_upgraded(db_path):
    make_old_db(db_path)
    with connect(db_path) as conn:
        conn.execute("DELETE FROM app_meta")  # 이 기능이 생기기 전에 만들어진 DB

    upgrade(db_path)

    assert ReservationRepository(db_path).find_by_id("R2005")["device"]["model"] == "iPhone 18 Pro"
