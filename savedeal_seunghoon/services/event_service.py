"""외부 이벤트 반영: 개통 전산·물류·서류 접수처럼 SaveDeal 밖에서 생긴 일을 예약에 반영한다.

흐름: (개통 전산 / 물류 / 구글시트) → n8n → POST /api/events → 여기
  - 문제 발생 이벤트(개통 반려, 재고 확보 지연 …): 문제를 추가하고 해결책을 만든다.
    같은 문제로 이미 승인해 진행 중인 해결책이 있으면 '실패'로 처리하고 다른 대안을 다시 만든다.
  - 문제 해소 이벤트(서류 제출, 재고 도착 …): 문제를 해결 처리한다. 진행 중이던 해결책은 성공, 남은 제안은 보류.
  - 개통 완료 / 예약 취소: 예약을 종료한다.
같은 이벤트가 여러 번 와도 한 번만 반영한다 (external_id 기준). n8n 이 구글시트 전체를 주기적으로 보내도 안전하다.
판정·해결책 생성은 기존 규칙(ActionService)을 그대로 쓴다.
"""
import hashlib
import json
from datetime import date, datetime
from pathlib import Path

from db.connection import connect
from repositories.action_history_repository import ActionHistoryRepository
from repositories.inventory_repository import InventoryRepository
from repositories.proposed_action_repository import ProposedActionRepository
from repositories.reservation_repository import ReservationRepository
from services.action_service import DEFAULT_TRANSFER_LEAD_DAYS, ActionService
from services.codes import (
    ACTION_APPROVED,
    ACTION_DISCARDED,
    ACTION_PROPOSED,
    ACTION_SUCCEEDED,
    CLOSED_STATUSES,
    EVENT_ACTIVATION_COMPLETED,
    EVENT_EXTERNAL,
    EVENT_ISSUE_DETECTED,
    EVENT_RESERVATION_CANCELLED,
    ISSUE_ACTIVATION_REJECTED,
    ISSUE_CUSTOMER_NO_RESPONSE,
    ISSUE_IDENTITY_FAILED,
    ISSUE_LABELS,
    ISSUE_MISSING_DOCUMENTS,
    ISSUE_OVERDUE_PAYMENT,
    ISSUE_STOCK_SHORTAGE,
    STATUS_CANCELLED,
    STATUS_COMPLETED,
)

OP_RAISE = "raise"        # 문제 발생
OP_RESOLVE = "resolve"    # 문제 해소
OP_COMPLETE = "complete"  # 개통 완료
OP_CANCEL = "cancel"      # 예약 취소

# 이벤트 종류. aliases 는 구글시트에 한글로 적어도 알아듣게 하려는 것 (띄어쓰기 무시)
EVENT_TYPES = {
    "ACTIVATION_REJECTED": {"label": "개통 반려", "op": OP_RAISE, "issue": ISSUE_ACTIVATION_REJECTED,
                            "aliases": ["개통 반려", "개통 거절"]},
    "STOCK_DELAYED": {"label": "재고 확보 지연", "op": OP_RAISE, "issue": ISSUE_STOCK_SHORTAGE,
                      "aliases": ["재고 확보 지연", "입고 지연", "재고 이동 지연", "배송 지연", "입고 취소", "재고 부족"]},
    "DOCUMENTS_MISSING": {"label": "서류 보완 요청", "op": OP_RAISE, "issue": ISSUE_MISSING_DOCUMENTS,
                          "aliases": ["서류 보완 요청", "서류 보완", "서류 미제출", "서류 반려"]},
    "IDENTITY_FAILED": {"label": "본인인증 실패", "op": OP_RAISE, "issue": ISSUE_IDENTITY_FAILED,
                        "aliases": ["본인인증 실패", "인증 실패"]},
    "CUSTOMER_NO_RESPONSE": {"label": "고객 미응답", "op": OP_RAISE, "issue": ISSUE_CUSTOMER_NO_RESPONSE,
                             "aliases": ["고객 미응답", "미응답", "연락 두절"]},
    "PAYMENT_OVERDUE": {"label": "요금 미납", "op": OP_RAISE, "issue": ISSUE_OVERDUE_PAYMENT,
                        "aliases": ["요금 미납", "미납"]},
    "ACTIVATION_ACCEPTED": {"label": "개통 재접수 승인", "op": OP_RESOLVE, "issue": ISSUE_ACTIVATION_REJECTED,
                            "aliases": ["개통 재접수 승인", "재접수 승인", "재접수 완료", "반려 해소"]},
    "STOCK_ARRIVED": {"label": "재고 도착", "op": OP_RESOLVE, "issue": ISSUE_STOCK_SHORTAGE,
                      "aliases": ["재고 도착", "입고 완료", "재고 확보", "배송 완료", "재고 이동 완료"]},
    "DOCUMENTS_SUBMITTED": {"label": "서류 제출 완료", "op": OP_RESOLVE, "issue": ISSUE_MISSING_DOCUMENTS,
                            "aliases": ["서류 제출 완료", "서류 제출", "서류 도착", "서류 완료"]},
    "IDENTITY_VERIFIED": {"label": "본인인증 완료", "op": OP_RESOLVE, "issue": ISSUE_IDENTITY_FAILED,
                          "aliases": ["본인인증 완료", "본인인증 성공", "인증 완료"]},
    "CUSTOMER_RESPONDED": {"label": "고객 응답", "op": OP_RESOLVE, "issue": ISSUE_CUSTOMER_NO_RESPONSE,
                           "aliases": ["고객 응답", "고객 회신", "연락 완료"]},
    "PAYMENT_CONFIRMED": {"label": "미납 납부 확인", "op": OP_RESOLVE, "issue": ISSUE_OVERDUE_PAYMENT,
                          "aliases": ["미납 납부 확인", "납부 완료", "미납 해소"]},
    "ACTIVATION_COMPLETED": {"label": "개통 완료", "op": OP_COMPLETE, "aliases": ["개통 완료", "개통 성공"]},
    "RESERVATION_CANCELLED": {"label": "예약 취소", "op": OP_CANCEL, "aliases": ["예약 취소", "고객 취소", "취소"]},
}

RESULT_APPLIED = "APPLIED"
RESULT_SKIPPED = "SKIPPED"
RESULT_ERROR = "ERROR"
RESULT_DUPLICATE = "DUPLICATE"  # 저장하지 않고 응답에만 쓴다
RESULT_LABELS = {RESULT_APPLIED: "반영", RESULT_SKIPPED: "건너뜀", RESULT_ERROR: "오류", RESULT_DUPLICATE: "이미 반영됨"}

# 구글시트 머리글(한글)도 받는다. 앞뒤·중간 띄어쓰기는 무시한다.
FIELD_ALIASES = {
    "event_id": ["event_id", "id", "이벤트id"],
    "reservation_id": ["reservation_id", "예약번호"],
    "type": ["type", "event", "event_type", "이벤트", "이벤트종류"],
    "reason": ["reason", "사유", "내용"],
    "occurred_at": ["occurred_at", "timestamp", "발생시각", "시각", "일시"],
    "documents": ["documents", "서류", "서류명"],
    "date": ["date", "예정일", "입고예정일"],
    "field": ["field", "반려항목", "항목"],
    "source": ["source", "출처"],
}


def _squash(text) -> str:
    return "".join(str(text).split()).lower()


def _type_key(value) -> str | None:
    wanted = _squash(value)
    for key, spec in EVENT_TYPES.items():
        if wanted == key.lower() or wanted in (_squash(alias) for alias in spec["aliases"]):
            return key
    return None


def normalize(raw: dict) -> dict:
    """n8n·구글시트에서 온 한 줄을 표준 형식으로 바꾼다. 빈 칸은 없는 것으로 본다."""
    by_name = {_squash(k): v for k, v in raw.items() if v not in (None, "")}
    event = {}
    for field, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            if alias in by_name:
                event[field] = str(by_name[alias]).strip()
                break
    if "documents" in event:
        event["documents"] = [d.strip() for d in event["documents"].replace("/", ",").split(",") if d.strip()]
    if "reservation_id" in event:
        event["reservation_id"] = event["reservation_id"].upper()
    event["type_key"] = _type_key(event["type"]) if event.get("type") else None
    event["source"] = event.get("source") or "n8n"
    return event


def external_id(event: dict) -> str:
    """같은 이벤트를 알아보는 키. 이벤트ID가 없으면 내용으로 만든다 (같은 줄을 여러 번 보내도 한 번만 반영)."""
    if event.get("event_id"):
        return f"id:{event['event_id']}"
    parts = [event.get(k) or "" for k in ("reservation_id", "type_key", "type", "occurred_at", "reason", "date", "field")]
    parts.append(",".join(event.get("documents") or []))
    return "hash:" + hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:20]


def _valid_date(value) -> str | None:
    try:
        return date.fromisoformat(str(value)[:10]).isoformat()
    except (TypeError, ValueError):
        return None


class EventError(Exception):
    """반영할 수 없는 이벤트 (오류로 기록)."""


class EventSkipped(EventError):
    """반영할 필요가 없는 이벤트 (건너뜀으로 기록). 예: 이미 종료된 예약, 이미 해결된 문제."""


class EventService:
    def __init__(self, db_path, data_dir: Path, clock=datetime.now):
        self.db_path = db_path
        self.reservation_repo = ReservationRepository(db_path)
        self.action_repo = ProposedActionRepository(db_path)
        self.history_repo = ActionHistoryRepository(db_path)
        self.inventory_repo = InventoryRepository(data_dir, db_path)
        self.action_service = ActionService(db_path, data_dir, clock)
        self.clock = clock

    def _now(self) -> str:
        return self.clock().isoformat(timespec="seconds")

    # ── 기록 ──────────────────────────────────────────────────────

    def _seen(self, key: str) -> dict | None:
        with connect(self.db_path) as conn:
            row = conn.execute("SELECT * FROM inbound_events WHERE external_id = ?", (key,)).fetchone()
        return dict(row) if row else None

    def _record(self, key: str, event: dict, raw: dict, result: str, message: str) -> None:
        with connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO inbound_events
                   (external_id, source, reservation_id, event_type, payload, result, message, received_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (key, event.get("source"), event.get("reservation_id"), event.get("type_key") or event.get("type"),
                 json.dumps(raw, ensure_ascii=False, default=str), result, message, self._now()),
            )

    def recent(self, limit: int = 20) -> dict:
        with connect(self.db_path) as conn:
            rows = conn.execute("SELECT * FROM inbound_events ORDER BY event_id DESC LIMIT ?", (limit,)).fetchall()
            last_id = conn.execute("SELECT COALESCE(MAX(event_id), 0) FROM inbound_events").fetchone()[0]
        items = []
        for row in rows:
            item = dict(row)
            item.pop("payload")
            spec = EVENT_TYPES.get(item["event_type"] or "")
            item["event_label"] = spec["label"] if spec else (item["event_type"] or "-")
            item["result_label"] = RESULT_LABELS.get(item["result"], item["result"])
            items.append(item)
        return {"last_id": last_id, "items": items}

    # ── 반영 ──────────────────────────────────────────────────────

    def apply_batch(self, raw_events: list) -> list[dict]:
        results = []
        for raw in raw_events:
            if not isinstance(raw, dict):
                results.append({"result": RESULT_ERROR, "message": "이벤트는 JSON 객체여야 합니다."})
                continue
            results.append(self.apply(raw))
        return results

    def apply(self, raw: dict) -> dict:
        event = normalize(raw)
        key = external_id(event)
        base = {"external_id": key, "reservation_id": event.get("reservation_id"), "type": event.get("type_key")}

        previous = self._seen(key)
        if previous is not None:
            return {**base, "result": RESULT_DUPLICATE, "message": f"이미 받은 이벤트입니다 ({previous['received_at']})."}

        try:
            message = self._apply(event)
            result = RESULT_APPLIED
        except EventError as exc:
            # 받을 수 없는 이벤트도 기록해 둔다. n8n 이 같은 줄을 다시 보내도 오류 기록이 쌓이지 않는다.
            result, message = (RESULT_SKIPPED if isinstance(exc, EventSkipped) else RESULT_ERROR), str(exc)
        self._record(key, event, raw, result, message)
        return {**base, "result": result, "message": message}

    def _apply(self, event: dict) -> str:
        if not event.get("reservation_id"):
            raise EventError("예약번호가 없습니다.")
        if not event.get("type"):
            raise EventError("이벤트 종류가 없습니다.")
        spec = EVENT_TYPES.get(event["type_key"] or "")
        if spec is None:
            raise EventError(f"알 수 없는 이벤트입니다: {event['type']}")
        reservation = self.reservation_repo.find_by_id(event["reservation_id"])
        if reservation is None:
            raise EventError(f"예약을 찾을 수 없습니다: {event['reservation_id']}")
        if reservation["status"] in CLOSED_STATUSES:
            raise EventSkipped("이미 종료된 예약입니다.")

        operation = {OP_RAISE: self._raise, OP_RESOLVE: self._resolve, OP_COMPLETE: self._complete, OP_CANCEL: self._cancel}
        return operation[spec["op"]](reservation, spec, event)

    def _note(self, spec: dict, event: dict) -> str:
        reason = f" · 사유: {event['reason']}" if event.get("reason") else ""
        return f"{spec['label']}{reason} (출처: {event['source']})"

    def _raise(self, reservation: dict, spec: dict, event: dict) -> str:
        rid, code, now = reservation["reservation_id"], spec["issue"], self._now()
        detail = self._issue_detail(reservation, code, event)
        self.history_repo.add(rid, EVENT_EXTERNAL, self._note(spec, event), now)

        issues = reservation["issues"]
        existing = next((issue for issue in issues if issue["code"] == code), None)
        if existing is None:
            issues.append({"code": code, "detail": detail})
        else:
            existing["detail"] = {**existing.get("detail", {}), **detail}
        self.reservation_repo.update(rid, {"issues": issues, "updated_at": now})

        actions = [a for a in self.action_repo.list_by_reservation(rid) if a["issue_code"] == code]
        approved = [a for a in actions if a["status"] == ACTION_APPROVED]
        label = ISSUE_LABELS[code]
        if approved:
            # 진행 중이던 해결책이 현장에서 통하지 않은 것 → 실패 처리하고 다른 대안을 만든다
            for action in approved:
                self.action_service.fail(rid, action["action_id"])
            message = f"{label}: 진행 중이던 해결책을 실패 처리하고 새 대안을 만들었습니다."
        else:
            # 새 정보(반려 사유, 입고 예정일 등)로 제안을 다시 만든다
            for action in actions:
                if action["status"] == ACTION_PROPOSED:
                    self.action_repo.update_status(action["action_id"], ACTION_DISCARDED, now)
            if existing is None:
                self.history_repo.add(rid, EVENT_ISSUE_DETECTED, f"외부 이벤트로 문제를 감지했습니다: {label}", now)
                message = f"{label} 문제를 등록하고 해결책을 만들었습니다."
            else:
                # 같은 문제가 다시 생겼다 = 그사이 시도한 처리가 통하지 않았다 (예: 재접수 후 재반려) → 재시도 +1
                retry_count = self.reservation_repo.find_by_id(rid)["retry_count"] + 1
                self.reservation_repo.update(rid, {"retry_count": retry_count, "updated_at": now})
                self.history_repo.add(rid, EVENT_ISSUE_DETECTED, f"{label} 문제가 다시 발생했습니다 (재시도 {retry_count}회).", now)
                message = f"{label} 문제가 다시 발생해 재시도 횟수를 올리고 해결책을 다시 만들었습니다."
            self.action_service.propose(self.reservation_repo.find_by_id(rid), [code])
        self.action_service.refresh_status(rid)
        return message

    def _resolve(self, reservation: dict, spec: dict, event: dict) -> str:
        rid, code, now = reservation["reservation_id"], spec["issue"], self._now()
        if not any(issue["code"] == code for issue in reservation["issues"]):
            raise EventSkipped(f"{ISSUE_LABELS[code]} 문제가 없는 예약입니다.")

        self.history_repo.add(rid, EVENT_EXTERNAL, self._note(spec, event), now)
        self.reservation_repo.update(
            rid, {"issues": [i for i in reservation["issues"] if i["code"] != code], "updated_at": now}
        )
        for action in self.action_repo.list_by_reservation(rid):
            if action["issue_code"] != code:
                continue
            if action["status"] == ACTION_APPROVED:
                self.action_repo.update_status(action["action_id"], ACTION_SUCCEEDED, now)
            elif action["status"] == ACTION_PROPOSED:
                self.action_repo.update_status(action["action_id"], ACTION_DISCARDED, now)
        self.action_service.refresh_status(rid)
        return f"{ISSUE_LABELS[code]} 문제를 해결 처리했습니다."

    def _close_open_actions(self, rid: str, now: str) -> None:
        for action in self.action_repo.list_by_reservation(rid):
            if action["status"] in (ACTION_PROPOSED, ACTION_APPROVED):
                self.action_repo.update_status(action["action_id"], ACTION_DISCARDED, now)

    def _complete(self, reservation: dict, spec: dict, event: dict) -> str:
        rid, now = reservation["reservation_id"], self._now()
        left = [ISSUE_LABELS.get(i["code"], i["code"]) for i in reservation["issues"]]
        self.history_repo.add(rid, EVENT_EXTERNAL, self._note(spec, event), now)
        self._close_open_actions(rid, now)
        self.reservation_repo.update(
            rid, {"status": STATUS_COMPLETED, "issues": [], "completed_at": now, "updated_at": now}
        )
        note = f" 남아 있던 문제({', '.join(left)})는 전산 개통 완료로 종료했습니다." if left else ""
        self.history_repo.add(rid, EVENT_ACTIVATION_COMPLETED, f"개통을 완료했습니다 (개통 전산 기준).{note}", now)
        return "개통 완료로 예약을 종료했습니다."

    def _cancel(self, reservation: dict, spec: dict, event: dict) -> str:
        rid, now = reservation["reservation_id"], self._now()
        self._close_open_actions(rid, now)
        self.reservation_repo.update(rid, {"status": STATUS_CANCELLED, "updated_at": now})
        self.history_repo.add(rid, EVENT_RESERVATION_CANCELLED, self._note(spec, event), now)
        return "예약을 취소 처리했습니다."

    # ── 문제 내용 ─────────────────────────────────────────────────

    def _issue_detail(self, reservation: dict, code: str, event: dict) -> dict:
        reason = event.get("reason")
        if code == ISSUE_ACTIVATION_REJECTED:
            return {"reason": reason or "개통 전산 반려", "field_label": event.get("field") or "반려 항목"}
        if code == ISSUE_MISSING_DOCUMENTS:
            return {"documents": event.get("documents") or [reason or "보완 서류"]}
        if code == ISSUE_IDENTITY_FAILED:
            return {"method": "휴대폰 본인인증", "reason": reason or "본인인증 실패"}
        if code == ISSUE_CUSTOMER_NO_RESPONSE:
            return {"last_contact_channel": "문자", "last_contact_at": event.get("occurred_at") or self._now()}
        if code == ISSUE_STOCK_SHORTAGE:
            return self._stock_detail(reservation, event)
        return {}

    def _stock_detail(self, reservation: dict, event: dict) -> dict:
        """재고 대안을 지금 재고 현황에서 다시 찾는다: 인근 점포 같은 단말, 매장의 다른 색상·용량, 다른 모델."""
        device, store_id = reservation["device"], reservation["store_id"]
        items = self.inventory_repo.load_all()
        same = [i for i in items if (i["model"], i["color"], i["storage"]) == (device["model"], device["color"], device["storage"])]
        restock = _valid_date(event.get("date")) or next(
            (i.get("expected_restock_date") for i in same if i["store_id"] == store_id and i.get("expected_restock_date")),
            None,
        )
        alt_device = next(
            ({"model": i["model"], "color": i["color"], "storage": i["storage"]}
             for i in items if i["store_id"] == store_id and i["model"] != device["model"] and i["quantity_on_hand"] > 0),
            None,
        )
        return {
            "nearby_stores": [
                {"store_id": i["store_id"], "quantity": i["quantity_on_hand"], "lead_days": DEFAULT_TRANSFER_LEAD_DAYS}
                for i in same
                if i["store_id"] != store_id and i["quantity_on_hand"] > 0
            ],
            "alt_specs": [
                {"color": i["color"], "storage": i["storage"]}
                for i in items
                if i["store_id"] == store_id and i["model"] == device["model"] and i["quantity_on_hand"] > 0
                and (i["color"], i["storage"]) != (device["color"], device["storage"])
            ],
            "alt_device": alt_device,
            "restock_date": restock,
            "reason": event.get("reason"),
        }
