"""시연용 mock 예약 데이터. 시각은 시드를 넣는 순간을 기준으로 계산해, 언제 실행해도
'오늘 마감', '마감 초과', '고객 대기 N시간' 같은 상황이 그대로 재현된다.

직접 다시 채우려면 (savedeal_seunghoon 폴더에서):  python -m db.seed
"""
from datetime import datetime, time, timedelta

from config import Config
from repositories.action_history_repository import ActionHistoryRepository
from repositories.reservation_repository import ReservationRepository
from services.action_service import ACTIVATION_DEADLINE_TIME, ActionService
from services.codes import (
    ACTION_PROPOSED,
    EVENT_ACTIVATION_COMPLETED,
    EVENT_ISSUE_DETECTED,
    EVENT_RESERVATION_CANCELLED,
    EVENT_RESERVATION_CREATED,
    ISSUE_ACTIVATION_REJECTED,
    ISSUE_CUSTOMER_NO_RESPONSE,
    ISSUE_IDENTITY_FAILED,
    ISSUE_INSTALLMENT_LIMIT,
    ISSUE_LABELS,
    ISSUE_MISSING_DOCUMENTS,
    ISSUE_OVERDUE_PAYMENT,
    ISSUE_STOCK_SHORTAGE,
    STATUS_ACTION_REQUIRED,
    STATUS_CANCELLED,
    STATUS_COMPLETED,
)

FOLD_BLACK = {"model": "GalaxyZ Fold6", "color": "Black", "storage": "256GB"}
FOLD_SILVER = {"model": "GalaxyZ Fold6", "color": "Silver", "storage": "512GB"}
IPHONE_BLUE = {"model": "iPhone 16", "color": "Blue", "storage": "128GB"}
IPHONE_PRO = {"model": "iPhone 16 Pro", "color": "Desert Titanium", "storage": "256GB"}
S25_ULTRA = {"model": "Galaxy S25 Ultra", "color": "Titanium Gray", "storage": "256GB"}


def _cases(now: datetime) -> list[dict]:
    """deadline: ("hours", n)은 지금부터 n시간 뒤(오늘을 넘기지 않음), ("days", n)은 n일 뒤 18시."""
    fold_silver_shortage = {
        "nearby_stores": [],
        "alt_specs": [{"color": "Black", "storage": "256GB"}],
        "alt_device": IPHONE_BLUE,
        "restock_date": (now.date() + timedelta(days=11)).isoformat(),
    }
    return [
        {
            "id": "R2001", "name": "김민수", "store": "S001", "device": FOLD_SILVER, "line": "MNP",
            "deadline": ("hours", 4), "waited": 30,
            "issues": [(ISSUE_STOCK_SHORTAGE, {**fold_silver_shortage, "nearby_stores": [{"store_id": "S002", "quantity": 2}]})],
        },
        {
            "id": "R2002", "name": "이서연", "store": "S001", "device": FOLD_BLACK, "line": "CHANGE",
            "deadline": ("days", 1), "waited": 10,
            "issues": [(ISSUE_INSTALLMENT_LIMIT, {"shortfall_amount": 350000, "device_price": 1800000})],
        },
        {
            "id": "R2003", "name": "박지훈", "store": "S002", "device": IPHONE_BLUE, "line": "NEW",
            "deadline": ("days", 2), "waited": 20,
            "issues": [(ISSUE_MISSING_DOCUMENTS, {"documents": ["가족관계증명서"]})],
        },
        {
            "id": "R2004", "name": "최유진", "store": "S002", "device": IPHONE_PRO, "line": "MNP",
            "deadline": ("days", 1), "waited": 52,
            "issues": [
                (
                    ISSUE_CUSTOMER_NO_RESPONSE,
                    {"last_contact_at": (now - timedelta(hours=50)).isoformat(timespec="seconds"), "last_contact_channel": "문자"},
                )
            ],
        },
        {
            "id": "R2005", "name": "정하늘", "store": "S001", "device": S25_ULTRA, "line": "MNP",
            "deadline": ("hours", 3), "waited": 26,
            "issues": [(ISSUE_ACTIVATION_REJECTED, {"reason": "가입자 생년월일 불일치", "field_label": "생년월일"})],
        },
        {
            "id": "R2006", "name": "강도윤", "store": "S002", "device": IPHONE_BLUE, "line": "CHANGE",
            "deadline": ("days", 1), "waited": 8, "fail": [ISSUE_IDENTITY_FAILED],
            "issues": [(ISSUE_IDENTITY_FAILED, {"method": "PASS 앱 인증", "reason": "명의 불일치"})],
        },
        {
            "id": "R2007", "name": "윤서아", "store": "S001", "device": FOLD_SILVER, "line": "MNP",
            "deadline": ("hours", -2), "waited": 60, "fail": [ISSUE_STOCK_SHORTAGE, ISSUE_STOCK_SHORTAGE],
            "issues": [
                (ISSUE_STOCK_SHORTAGE, {**fold_silver_shortage, "nearby_stores": [{"store_id": "S002", "quantity": 1}]}),
                (ISSUE_INSTALLMENT_LIMIT, {"shortfall_amount": 600000, "device_price": 2000000}),
                (
                    ISSUE_CUSTOMER_NO_RESPONSE,
                    {"last_contact_at": (now - timedelta(hours=26)).isoformat(timespec="seconds"), "last_contact_channel": "알림톡"},
                ),
            ],
        },
        {
            "id": "R2008", "name": "임현우", "store": "S002", "device": IPHONE_PRO, "line": "NEW",
            "deadline": ("days", 5), "waited": 4,
            "issues": [
                (ISSUE_OVERDUE_PAYMENT, {"amount": 87000}),
                (ISSUE_MISSING_DOCUMENTS, {"documents": ["신분증 사본"]}),
            ],
        },
        {
            "id": "R2009", "name": "한지민", "store": "S001", "device": FOLD_SILVER, "line": "CHANGE",
            "deadline": ("days", 4), "waited": 12,
            "issues": [(ISSUE_STOCK_SHORTAGE, fold_silver_shortage)],
        },
        {
            "id": "R2010", "name": "오준서", "store": "S001", "device": FOLD_BLACK, "line": "NEW",
            "deadline": ("days", 1), "waited": 5, "issues": [],
        },
        {
            "id": "R2011", "name": "서예린", "store": "S001", "device": IPHONE_BLUE, "line": "MNP",
            "deadline": ("hours", 10), "waited": 18, "approve": ISSUE_STOCK_SHORTAGE,
            "issues": [
                (
                    ISSUE_STOCK_SHORTAGE,
                    {"nearby_stores": [{"store_id": "S002", "quantity": 5}], "alt_specs": [], "alt_device": FOLD_BLACK, "restock_date": None},
                )
            ],
        },
        {
            "id": "R2012", "name": "신동현", "store": "S002", "device": S25_ULTRA, "line": "CHANGE",
            "deadline": ("days", 6), "waited": 3,
            "issues": [(ISSUE_ACTIVATION_REJECTED, {"reason": "요금제 코드 오류", "field_label": "요금제 코드"})],
        },
        {
            "id": "R2013", "name": "배성호", "store": "S001", "device": FOLD_BLACK, "line": "MNP",
            "deadline": ("hours", 7), "waited": 28,
            "issues": [
                (ISSUE_MISSING_DOCUMENTS, {"documents": ["위임장", "대리인 신분증"]}),
                (ISSUE_IDENTITY_FAILED, {"method": "휴대폰 본인인증", "reason": "인증번호 시간 초과"}),
            ],
        },
        {"id": "R2014", "name": "권나연", "store": "S001", "device": FOLD_BLACK, "line": "CHANGE", "completed": 3, "issues": []},
        {"id": "R2015", "name": "황민재", "store": "S002", "device": IPHONE_BLUE, "line": "NEW", "completed": 26, "issues": []},
        {"id": "R2016", "name": "송지우", "store": "S002", "device": IPHONE_PRO, "line": "MNP", "completed": 50, "issues": []},
        {"id": "R2017", "name": "조은비", "store": "S001", "device": S25_ULTRA, "line": "CHANGE", "cancelled": 20, "issues": []},
    ]


def _deadline(now: datetime, spec: tuple[str, int]) -> datetime:
    kind, amount = spec
    if kind == "days":
        day = now.date() + timedelta(days=amount)
        return datetime.combine(day, time.fromisoformat(ACTIVATION_DEADLINE_TIME))
    end_of_today = datetime.combine(now.date(), time(23, 30))
    return min(now + timedelta(hours=amount), end_of_today)


def seed_demo_data(db_path, data_dir=None, now: datetime | None = None) -> None:
    data_dir = data_dir or Config.DATA_DIR
    now = (now or datetime.now()).replace(microsecond=0)
    reservation_repo = ReservationRepository(db_path)
    history_repo = ActionHistoryRepository(db_path)
    # 시드에서 일어난 승인·실패는 조금 전에 있었던 일로 기록한다.
    clock = {"now": now - timedelta(hours=1)}
    action_service = ActionService(db_path, data_dir, clock=lambda: clock["now"])

    for index, case in enumerate(_cases(now)):
        closed_hours_ago = case.get("completed") or case.get("cancelled")
        if closed_hours_ago:
            closed_at = now - timedelta(hours=closed_hours_ago)
            created_at = closed_at - timedelta(days=2)
            deadline = datetime.combine(closed_at.date(), time.fromisoformat(ACTIVATION_DEADLINE_TIME))
        else:
            created_at = now - timedelta(hours=case["waited"])
            deadline = _deadline(now, case["deadline"])

        status = STATUS_ACTION_REQUIRED
        if case.get("completed"):
            status = STATUS_COMPLETED
        elif case.get("cancelled"):
            status = STATUS_CANCELLED

        created = created_at.isoformat(timespec="seconds")
        reservation_repo.insert(
            {
                "reservation_id": case["id"],
                "customer_id": f"C{101 + index}",
                "customer_name": case["name"],
                "customer_phone": f"010-****-{1200 + index * 37:04d}",
                "store_id": case["store"],
                "device": case["device"],
                "line_type": case["line"],
                "desired_activation_date": deadline.date().isoformat(),
                "activation_deadline": deadline.isoformat(timespec="seconds"),
                "status": status,
                "issues": [{"code": code, "detail": detail} for code, detail in case["issues"]],
                "retry_count": 0,
                "customer_waiting_since": created,
                "created_at": created,
                "updated_at": created,
                "completed_at": closed_at.isoformat(timespec="seconds") if case.get("completed") else None,
            }
        )
        history_repo.add(case["id"], EVENT_RESERVATION_CREATED, "예약이 등록됐습니다.", created)

        if case.get("completed"):
            history_repo.add(case["id"], EVENT_ACTIVATION_COMPLETED, "개통을 완료했습니다.", closed_at.isoformat(timespec="seconds"))
            continue
        if case.get("cancelled"):
            history_repo.add(
                case["id"], EVENT_RESERVATION_CANCELLED, "고객 요청으로 예약이 취소됐습니다.", closed_at.isoformat(timespec="seconds")
            )
            continue

        if case["issues"]:
            labels = ", ".join(ISSUE_LABELS[code] for code, _ in case["issues"])
            history_repo.add(case["id"], EVENT_ISSUE_DETECTED, f"문제를 감지했습니다: {labels}", created)
        action_service.propose(reservation_repo.find_by_id(case["id"]))

        # 재시도 사례: 첫 번째 제안을 승인했다가 실패한 이력을 만든다.
        for issue_code in case.get("fail", []):
            action = _first_action(action_service, case["id"], issue_code, ACTION_PROPOSED)
            action_service.approve(case["id"], action["action_id"])
            action_service.fail(case["id"], action["action_id"])

        # 진행 중 사례: 첫 번째 제안을 승인해 가상 실행 중인 상태로 둔다.
        if case.get("approve"):
            action = _first_action(action_service, case["id"], case["approve"], ACTION_PROPOSED)
            action_service.approve(case["id"], action["action_id"])

        action_service.refresh_status(case["id"])


def _first_action(action_service: ActionService, reservation_id: str, issue_code: str, status: str) -> dict:
    return next(
        action
        for action in action_service.action_repo.list_by_reservation(reservation_id)
        if action["issue_code"] == issue_code and action["status"] == status
    )


if __name__ == "__main__":
    from db.connection import reset_database

    reset_database(Config.DB_PATH)
    print(f"mock 예약 데이터를 다시 채웠습니다: {Config.DB_PATH}")
