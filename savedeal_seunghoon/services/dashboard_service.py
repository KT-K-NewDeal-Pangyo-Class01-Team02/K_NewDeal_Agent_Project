"""예약 운영 대시보드: 필터별 목록, 요약 카드 집계, 우선순위 정렬, 상세 패널 데이터를 만든다.

화면에 보여 줄 문구(상태 이름, 남은 시간, 문제 설명 등)도 여기서 만든다.
프론트 JavaScript는 이 결과를 그대로 그리기만 한다.
"""
from datetime import date, datetime
from pathlib import Path

from repositories.action_history_repository import ActionHistoryRepository
from repositories.proposed_action_repository import ProposedActionRepository
from repositories.reservation_repository import ReservationRepository
from repositories.store_repository import StoreRepository
from services.codes import (
    ACTION_APPROVED,
    ACTION_DISCARDED,
    ACTION_LABELS,
    ACTION_PROPOSED,
    ACTION_STATUS_LABELS,
    CLOSED_STATUSES,
    EVENT_LABELS,
    ISSUE_ACTIVATION_REJECTED,
    ISSUE_CUSTOMER_NO_RESPONSE,
    ISSUE_CUSTOMER_UNKNOWN,
    ISSUE_IDENTITY_FAILED,
    ISSUE_INSTALLMENT_LIMIT,
    ISSUE_LABELS,
    ISSUE_MISSING_DOCUMENTS,
    ISSUE_OVERDUE_PAYMENT,
    ISSUE_STOCK_SHORTAGE,
    LINE_TYPE_LABELS,
    RISK_LABELS,
    STATUS_ACTION_REQUIRED,
    STATUS_COMPLETED,
    STATUS_IN_PROGRESS,
    STATUS_LABELS,
    STATUS_READY,
)
from services.carriers import carrier_change
from services.device_images import image_for
from services.risk_scoring_service import (
    RISK_HIGH,
    calculate_churn_risk,
    calculate_priority,
    hours_since,
    hours_until,
)

FILTER_ALL = "all"
FILTER_NEEDS_ACTION = "needs_action"
FILTER_HIGH_RISK = "high_risk"
FILTER_DUE_TODAY = "due_today"
FILTER_COMPLETED = "completed"

FILTERS = [
    (FILTER_ALL, "전체"),
    (FILTER_NEEDS_ACTION, "처리 필요"),
    (FILTER_HIGH_RISK, "고위험"),
    (FILTER_DUE_TODAY, "오늘 마감"),
    (FILTER_COMPLETED, "완료"),
]
FILTER_KEYS = {key for key, _ in FILTERS}

# ?status= 조회 조건. incomplete: 미완료(완료·취소 제외), completed: 개통 완료만
STATUS_INCOMPLETE = "incomplete"
STATUS_PARAM_COMPLETED = "completed"
STATUS_PARAMS = {STATUS_INCOMPLETE, STATUS_PARAM_COMPLETED}
RISK_PARAMS = {"high", "medium", "low"}

DUE_SOON_HOURS = 6


def _duration_label(hours: float) -> str:
    hours = abs(hours)
    if hours >= 24:
        return f"{int(hours // 24)}일 {int(hours % 24)}시간"
    if hours >= 1:
        return f"{int(hours)}시간"
    return f"{max(1, int(hours * 60))}분"


def deadline_label(deadline: str, now: datetime) -> str:
    left = hours_until(deadline, now)
    if left < 0:
        return f"{_duration_label(left)} 초과"
    return f"{_duration_label(left)} 남음"


def _format_datetime(value: str | None) -> str | None:
    if not value:
        return None
    return datetime.fromisoformat(value).strftime("%m/%d %H:%M")


def _device_image(device: dict) -> dict | None:
    image = image_for(device)
    if image is None:
        return None
    return {"url": f"/static/{image['path']}", "is_representative": image["is_representative"]}


def _is_open(reservation: dict) -> bool:
    return reservation["status"] not in CLOSED_STATUSES


def _is_due_today(reservation: dict, today: date) -> bool:
    return _is_open(reservation) and datetime.fromisoformat(reservation["activation_deadline"]).date() <= today


def _matches(summary: dict, status: str | None, risk: str | None) -> bool:
    if status == STATUS_INCOMPLETE and not summary["is_open"]:
        return False
    if status == STATUS_PARAM_COMPLETED and summary["status"] != STATUS_COMPLETED:
        return False
    # 위험도는 미완료 예약에만 있다 (완료·취소 예약의 risk_level은 None).
    if risk is not None and summary["risk_level"] != risk:
        return False
    return True


class DashboardService:
    def __init__(self, db_path, data_dir: Path, clock=datetime.now):
        self.reservation_repo = ReservationRepository(db_path)
        self.action_repo = ProposedActionRepository(db_path)
        self.history_repo = ActionHistoryRepository(db_path)
        self.store_repo = StoreRepository(data_dir)
        self.clock = clock

    def _store_name(self, store_id: str) -> str:
        store = self.store_repo.find_by_id(store_id)
        return store["name"] if store else store_id

    def issue_summary(self, issue: dict) -> str:
        code, detail = issue["code"], issue.get("detail", {})
        if code == ISSUE_STOCK_SHORTAGE:
            parts = ["방문 매장 재고 없음"]
            if detail.get("restock_date"):
                parts.append(f"재고 확보 예정 {detail['restock_date']}")
            nearby = [n for n in detail.get("nearby_stores", []) if n.get("quantity", 0) > 0]
            if nearby:
                parts.append("인근 " + ", ".join(f"{self._store_name(n['store_id'])} {n['quantity']}대" for n in nearby))
            return " · ".join(parts)
        if code == ISSUE_INSTALLMENT_LIMIT:
            return f"한도 부족액 {detail.get('shortfall_amount', 0):,}원"
        if code == ISSUE_MISSING_DOCUMENTS:
            return "미제출: " + (", ".join(detail.get("documents", [])) or "확인 필요")
        if code == ISSUE_IDENTITY_FAILED:
            return f"{detail.get('method', '본인인증')} 실패 · {detail.get('reason', '사유 확인 필요')}"
        if code == ISSUE_ACTIVATION_REJECTED:
            return f"반려 사유: {detail.get('reason', '확인 필요')}"
        if code == ISSUE_CUSTOMER_NO_RESPONSE:
            last = _format_datetime(detail.get("last_contact_at"))
            return f"마지막 연락 {last} ({detail.get('last_contact_channel', '문자')}) 이후 응답 없음" if last else "응답 없음"
        if code == ISSUE_CUSTOMER_UNKNOWN:
            return "본인인증·서류·할부한도 정보 없음"
        if code == ISSUE_OVERDUE_PAYMENT:
            amount = detail.get("amount")
            return f"미납액 {amount:,}원" if amount else "통신요금 미납"
        return ""

    def _summarize(self, reservation: dict, now: datetime) -> dict:
        churn = calculate_churn_risk(reservation, now)
        priority = calculate_priority(reservation, now, churn)
        is_open = _is_open(reservation)
        device = reservation["device"]
        return {
            "reservation_id": reservation["reservation_id"],
            "customer_name": reservation["customer_name"],
            "customer_phone": reservation["customer_phone"],
            "store_name": self._store_name(reservation["store_id"]),
            "device_label": f"{device['model']} {device['color']} {device['storage']}",
            "device_model": device["model"],
            "device_option": f"{device['color']} · {device['storage']}",
            "device_image": _device_image(device),
            "line_type_label": LINE_TYPE_LABELS.get(reservation["line_type"], reservation["line_type"]),
            "carrier_change": carrier_change(reservation["line_type"], reservation.get("previous_carrier")),
            "status": reservation["status"],
            "status_label": STATUS_LABELS.get(reservation["status"], reservation["status"]),
            "is_open": is_open,
            "issues": [
                {
                    "code": issue["code"],
                    "label": ISSUE_LABELS.get(issue["code"], issue["code"]),
                    "summary": self.issue_summary(issue),
                }
                for issue in reservation["issues"]
            ],
            "churn_risk_score": churn["score"],
            "risk_level": churn["level"] if is_open else None,
            "risk_label": RISK_LABELS[churn["level"]] if is_open else "-",
            "priority_score": priority["score"],
            "activation_deadline": reservation["activation_deadline"],
            "deadline_display": _format_datetime(reservation["activation_deadline"]),
            "deadline_label": deadline_label(reservation["activation_deadline"], now) if is_open else "-",
            "is_overdue": is_open and hours_until(reservation["activation_deadline"], now) < 0,
            "is_due_today": _is_due_today(reservation, now.date()),
            "waiting_label": _duration_label(hours_since(reservation["customer_waiting_since"], now))
            if is_open
            else "-",
            "retry_count": reservation["retry_count"],
            "completed_at_display": _format_datetime(reservation["completed_at"]),
            "_completed_at": reservation["completed_at"] or "",
            "_churn": churn,
            "_priority": priority,
        }

    @staticmethod
    def _public(summary: dict) -> dict:
        return {key: value for key, value in summary.items() if not key.startswith("_")}

    def list_reservations(
        self, filter_key: str = FILTER_ALL, status: str | None = None, risk: str | None = None
    ) -> dict:
        """filter(화면 탭)로 고른 목록에 status·risk 조건을 추가로 적용한다. 정렬은 항상 우선순위 순."""
        if filter_key not in FILTER_KEYS:
            raise ValueError(f"filter는 {sorted(FILTER_KEYS)} 중 하나여야 합니다.")
        if status is not None and status not in STATUS_PARAMS:
            raise ValueError(f"status는 {sorted(STATUS_PARAMS)} 중 하나여야 합니다.")
        if risk is not None and risk not in RISK_PARAMS:
            raise ValueError(f"risk는 {sorted(RISK_PARAMS)} 중 하나여야 합니다.")

        now = self.clock()
        summaries = [self._summarize(r, now) for r in self.reservation_repo.load_all()]
        open_items = [s for s in summaries if s["is_open"]]
        closed_items = [s for s in summaries if not s["is_open"]]

        # 미완료: 우선순위 높은 순, 같으면 마감 빠른 순. 완료: 최근 완료 순으로 아래에 둔다.
        open_items.sort(key=lambda s: (-s["priority_score"], s["activation_deadline"]))
        closed_items.sort(key=lambda s: s["_completed_at"], reverse=True)

        buckets = {
            FILTER_ALL: open_items + closed_items,
            FILTER_NEEDS_ACTION: [
                s for s in open_items if s["status"] in (STATUS_ACTION_REQUIRED, STATUS_IN_PROGRESS)
            ],
            FILTER_HIGH_RISK: [s for s in open_items if s["risk_level"] == RISK_HIGH],
            FILTER_DUE_TODAY: [s for s in open_items if s["is_due_today"]],
            FILTER_COMPLETED: closed_items,
        }

        summary = {
            "open": len(open_items),
            "needs_action": len(buckets[FILTER_NEEDS_ACTION]),
            "high_risk": len(buckets[FILTER_HIGH_RISK]),
            "due_today": len(buckets[FILTER_DUE_TODAY]),
            "ready": len([s for s in open_items if s["status"] == STATUS_READY]),
            "completed_today": len(
                [
                    s
                    for s in closed_items
                    if s["status"] == STATUS_COMPLETED and s["_completed_at"][:10] == now.date().isoformat()
                ]
            ),
        }
        in_progress = len([s for s in open_items if s["status"] == STATUS_IN_PROGRESS])
        overdue = len([s for s in open_items if s["is_overdue"]])
        due_soon = len(
            [s for s in open_items if 0 <= hours_until(s["activation_deadline"], now) <= DUE_SOON_HOURS]
        )
        high_risk_ratio = round(summary["high_risk"] * 100 / summary["open"]) if summary["open"] else 0

        return {
            "filter": filter_key,
            "filters": [
                {"key": key, "label": label, "count": len(buckets[key])} for key, label in FILTERS
            ],
            "summary": summary,
            # KPI 카드 보조 라인. 과거 기록이 없으므로 현재 데이터에서 계산한 값만 쓴다.
            "summary_notes": {
                "open": f"해결 진행 중 {in_progress}건",
                "needs_action": f"마감 초과 {overdue}건",
                "high_risk": f"미완료의 {high_risk_ratio}%",
                "due_today": f"{DUE_SOON_HOURS}시간 이내 {due_soon}건",
                "completed_today": f"개통 대기 {summary['ready']}건",
            },
            # 보조 라인 강조: 바로 처리해야 할 사실이 있을 때만 색을 준다 (없으면 None)
            "summary_note_tones": {
                "needs_action": "danger" if overdue else None,
                "due_today": "warning" if due_soon else None,
            },
            "status": status,
            "risk": risk,
            "items": [self._public(s) for s in buckets[filter_key] if _matches(s, status, risk)],
            "generated_at": now.isoformat(timespec="seconds"),
        }

    def get_detail(self, reservation_id: str) -> dict | None:
        reservation = self.reservation_repo.find_by_id(reservation_id)
        if reservation is None:
            return None

        now = self.clock()
        summary = self._summarize(reservation, now)
        actions = self.action_repo.list_by_reservation(reservation_id)

        def serialize(action: dict) -> dict:
            return {
                "action_id": action["action_id"],
                "issue_code": action["issue_code"],
                "issue_label": ISSUE_LABELS.get(action["issue_code"], action["issue_code"]),
                "action_type": action["action_type"],
                "type_label": ACTION_LABELS.get(action["action_type"], action["action_type"]),
                "title": action["title"],
                "description": action["description"],
                "status": action["status"],
                "status_label": ACTION_STATUS_LABELS.get(action["status"], action["status"]),
                "can_approve": summary["is_open"] and action["status"] == ACTION_PROPOSED,
                "can_record_result": summary["is_open"] and action["status"] == ACTION_APPROVED,
                "decided_at_display": _format_datetime(action["decided_at"]),
            }

        current = [serialize(a) for a in actions if a["status"] in (ACTION_PROPOSED, ACTION_APPROVED)]
        # 진행 중인 해결책을 먼저, 그다음 제안을 문제 원인 순서대로 보여 준다.
        issue_order = {issue["code"]: index for index, issue in enumerate(reservation["issues"])}
        current.sort(key=lambda a: (a["status"] != ACTION_APPROVED, issue_order.get(a["issue_code"], 99), a["action_id"]))
        past = [
            serialize(a)
            for a in reversed(actions)
            if a["status"] not in (ACTION_PROPOSED, ACTION_APPROVED, ACTION_DISCARDED)
        ]

        history = [
            {
                "event_type": item["event_type"],
                "event_label": EVENT_LABELS.get(item["event_type"], item["event_type"]),
                "description": item["description"],
                "created_at_display": _format_datetime(item["created_at"]),
            }
            for item in reversed(self.history_repo.list_by_reservation(reservation_id))
        ]

        detail = self._public(summary)
        detail.update(
            {
                "customer_id": reservation["customer_id"],
                "store_id": reservation["store_id"],
                "desired_activation_date": reservation["desired_activation_date"],
                "created_at_display": _format_datetime(reservation["created_at"]),
                "memo": reservation.get("memo"),
                "memo_insight": reservation.get("memo_insight"),
                "churn_factors": summary["_churn"]["factors"],
                "priority_factors": summary["_priority"]["factors"],
                "actions": current,
                "past_actions": past,
                "history": history,
                "can_complete": reservation["status"] == STATUS_READY,
            }
        )
        return detail
