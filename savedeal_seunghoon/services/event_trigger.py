"""대시보드 '이벤트 발생' 버튼: 외부 이벤트(개통 반려·입고 지연 등)를 바로 만들어 반영한다.

구글시트·n8n 으로 들어오는 이벤트와 똑같은 경로(EventService)로 반영하므로 문제 추가, 해결책 생성,
처리이력, 알림 메일까지 모두 같다. 처리이력의 출처는 '수동 발생'으로 남는다.

- 첫 번째 누름: FEATURED_CUSTOMER(정하늘)에게 이벤트를 무작위로 더해 우선순위 1위가 될 때까지 올린다.
  새 문제만으로 1위가 안 되면 이미 있는 문제를 '다시 발생'시킨다 (예: 재접수 후 재반려 → 재시도 +1).
- 그다음부터: 나머지 미완료 예약 중 한 명을 무작위로 골라 이벤트 하나를 무작위로 더한다.
"""
import random
import uuid
from datetime import datetime, timedelta

from db.connection import connect
from services.dashboard_service import DashboardService
from services.event_service import EVENT_TYPES, OP_RAISE, RESULT_APPLIED, EventService

FEATURED_CUSTOMER = "정하늘"
SOURCE = "수동 발생"
MAX_FEATURED_EVENTS = 8  # 새 문제를 다 더하고도 1위가 안 되면 재발생(재시도 +1)을 2~3번 더 할 여유

# 이벤트 종류별 사유 (무작위로 고른다)
ACTIVATION_REASONS = [("주소 불일치", "주소"), ("명의 정보 불일치", "명의"), ("요금제 코드 오류", "요금제"), ("가입신청서 서명 누락", "서명")]
REASONS = {
    "STOCK_DELAYED": ["물류센터 출고 지연", "인근 점포 재고 이동 취소", "제조사 입고 일정 변경"],
    "DOCUMENTS_MISSING": ["신분증 사본", "가족관계증명서", "재직증명서", "통장 사본"],
    "IDENTITY_FAILED": ["본인인증 시간 초과", "인증 명의 불일치"],
    "CUSTOMER_NO_RESPONSE": ["안내 문자 3회 미응답", "전화 연결 안 됨"],
    "PAYMENT_OVERDUE": ["통신요금 2개월 미납", "소액결제 미납"],
}
RAISE_TYPES = [key for key, spec in EVENT_TYPES.items() if spec["op"] == OP_RAISE]


class TriggerError(Exception):
    pass


class EventTrigger:
    def __init__(self, db_path, data_dir, rng: random.Random | None = None, clock=datetime.now):
        self.db_path = db_path
        self.dashboard = DashboardService(db_path, data_dir, clock)
        self.events = EventService(db_path, data_dir, clock)
        self.rng = rng or random.Random()
        self.clock = clock

    def _open_items(self) -> list[dict]:
        return [item for item in self.dashboard.list_reservations("all")["items"] if item["is_open"]]

    @staticmethod
    def _rank(items: list[dict], reservation_id: str) -> int | None:
        return next((index for index, item in enumerate(items, start=1) if item["reservation_id"] == reservation_id), None)

    def _already_triggered(self, reservation_id: str) -> bool:
        with connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT 1 FROM inbound_events WHERE reservation_id = ? AND source = ? AND result = ? LIMIT 1",
                (reservation_id, SOURCE, RESULT_APPLIED),
            ).fetchone()
        return row is not None

    def _make_event(self, item: dict) -> dict:
        """그 예약에 아직 없는 문제를 우선 고르고, 다 있으면 이미 있는 문제를 다시 발생시킨다."""
        present = {issue["code"] for issue in item["issues"]}
        fresh = [key for key in RAISE_TYPES if EVENT_TYPES[key]["issue"] not in present]
        again = [key for key in RAISE_TYPES if EVENT_TYPES[key]["issue"] in present]
        type_key = self.rng.choice(fresh or again or RAISE_TYPES)
        now = self.clock()
        raw = {
            "event_id": f"manual-{uuid.uuid4().hex[:12]}",
            "예약번호": item["reservation_id"],
            "이벤트": EVENT_TYPES[type_key]["label"],
            "발생시각": now.isoformat(timespec="seconds"),
            "출처": SOURCE,
        }
        if type_key == "ACTIVATION_REJECTED":
            reason, field = self.rng.choice(ACTIVATION_REASONS)
            raw.update({"사유": reason, "반려 항목": field})
        elif type_key == "DOCUMENTS_MISSING":
            document = self.rng.choice(REASONS[type_key])
            raw.update({"사유": f"{document} 보완 필요", "서류": document})
        else:
            raw["사유"] = self.rng.choice(REASONS[type_key])
            if type_key == "STOCK_DELAYED":
                raw["예정일"] = (now + timedelta(days=self.rng.randint(2, 4))).date().isoformat()
        if EVENT_TYPES[type_key]["issue"] in present:
            # 이미 있는 문제가 다시 생긴 것 (재시도 +1). 화면·이력에서 구분되게 사유 앞에 붙인다
            again_label = "재접수 후 재반려" if type_key == "ACTIVATION_REJECTED" else "재발생"
            raw["사유"] = f"{again_label} · {raw['사유']}"
        return raw

    def trigger(self) -> dict:
        items = self._open_items()
        if not items:
            raise TriggerError("이벤트를 더할 미완료 예약이 없습니다.")

        featured = next((item for item in items if item["customer_name"] == FEATURED_CUSTOMER), None)
        boost = (
            featured is not None
            and self._rank(items, featured["reservation_id"]) != 1
            and not self._already_triggered(featured["reservation_id"])
        )
        if boost:
            target = featured
        else:
            others = [item for item in items if item["customer_name"] != FEATURED_CUSTOMER] or items
            target = self.rng.choice(others)

        rid = target["reservation_id"]
        before = {"rank": self._rank(items, rid), "priority": target["priority_score"], "risk": target["risk_label"]}
        issues_before = {issue["code"] for issue in target["issues"]}

        results, current = [], target
        for _ in range(MAX_FEATURED_EVENTS if boost else 1):
            raw = self._make_event(current)
            result = self.events.apply(raw)
            result.update(event_label=raw["이벤트"], reason=raw.get("사유"))
            results.append(result)
            items = self._open_items()
            current = next((item for item in items if item["reservation_id"] == rid), None)
            if current is None or not boost or self._rank(items, rid) == 1:
                break

        after_item = current or self.dashboard.get_detail(rid)
        return {
            "reservation_id": rid,
            "customer_name": target["customer_name"],
            "featured": boost,
            "events": [{"label": r["event_label"], "reason": r["reason"], "result": r["result"]} for r in results],
            "results": results,
            "new_issue_codes": sorted({issue["code"] for issue in after_item["issues"]} - issues_before),
            "before": before,
            "after": {
                "rank": self._rank(items, rid),
                "priority": after_item["priority_score"],
                "risk": after_item["risk_label"],
            },
        }
