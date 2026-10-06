"""예약의 문제 원인별로 해결책을 생성하고, 직원의 승인·결과 입력에 따라 예약 상태를 바꾼다.

흐름: 해결책 제안(PROPOSED) → 직원 승인(APPROVED, 가상 실행) → 결과 입력
  - 성공(SUCCEEDED): 해당 문제를 해결 처리하고 진행상태를 다시 계산한다.
  - 실패(FAILED): 재시도 횟수를 올리고, 실패한 안을 뺀 새 대안을 다시 생성한다.
재고 이동, 고객 연락, 개통 재접수 등은 모두 가상 실행이며 실제 외부 시스템을 호출하지 않는다.
"""
from datetime import datetime
from pathlib import Path

from repositories.action_history_repository import ActionHistoryRepository
from repositories.proposed_action_repository import ProposedActionRepository
from repositories.reservation_repository import ReservationRepository
from repositories.store_repository import StoreRepository
from services.codes import (
    ACTION_ACTIVATION_INPUT_FIX,
    ACTION_ALTERNATIVE_DEVICE,
    ACTION_APPROVED,
    ACTION_COLOR_STORAGE_CHANGE,
    ACTION_CUSTOMER_INFO_CHECK,
    ACTION_CUSTOMER_RECONTACT,
    ACTION_DATE_CHANGE,
    ACTION_DISCARDED,
    ACTION_DOCUMENT_REQUEST,
    ACTION_DOWN_PAYMENT,
    ACTION_FAILED,
    ACTION_IDENTITY_RETRY,
    ACTION_INSTALLMENT_ADJUSTMENT,
    ACTION_LABELS,
    ACTION_MANAGER_ESCALATION,
    ACTION_NEARBY_STORE_TRANSFER,
    ACTION_PAYMENT_GUIDE,
    ACTION_PROPOSED,
    ACTION_SUCCEEDED,
    CLOSED_STATUSES,
    EVENT_ACTION_APPROVED,
    EVENT_ACTION_FAILED,
    EVENT_ACTION_SUCCEEDED,
    EVENT_ACTIONS_PROPOSED,
    EVENT_ACTIVATION_COMPLETED,
    EVENT_STATUS_CHANGED,
    ISSUE_ACTIVATION_REJECTED,
    ISSUE_CUSTOMER_NO_RESPONSE,
    ISSUE_CUSTOMER_UNKNOWN,
    ISSUE_IDENTITY_FAILED,
    ISSUE_INSTALLMENT_LIMIT,
    ISSUE_LABELS,
    ISSUE_MISSING_DOCUMENTS,
    ISSUE_OVERDUE_PAYMENT,
    ISSUE_STOCK_SHORTAGE,
    STATUS_ACTION_REQUIRED,
    STATUS_COMPLETED,
    STATUS_IN_PROGRESS,
    STATUS_LABELS,
    STATUS_READY,
)

ACTIVATION_DEADLINE_TIME = "18:00:00"
DEFAULT_TRANSFER_LEAD_DAYS = 1
INSTALLMENT_MONTHS_FROM = 24
INSTALLMENT_MONTHS_TO = 36


class ActionError(Exception):
    """승인·결과 입력을 처리할 수 없을 때. code와 HTTP 상태를 라우트에 넘긴다."""

    def __init__(self, code: str, message: str, http_status: int):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


def _won(amount: int) -> str:
    return f"{amount:,}원"


def _device_label(device: dict) -> str:
    return f"{device['model']} {device['color']} {device['storage']}"


def _option(action_type: str, variant: str, title: str, description: str, detail: dict | None = None) -> dict:
    detail = dict(detail or {})
    detail["option_key"] = f"{action_type}:{variant}"
    return {"action_type": action_type, "title": title, "description": description, "detail": detail}


class ActionService:
    def __init__(self, db_path, data_dir: Path, clock=datetime.now):
        self.reservation_repo = ReservationRepository(db_path)
        self.action_repo = ProposedActionRepository(db_path)
        self.history_repo = ActionHistoryRepository(db_path)
        self.store_repo = StoreRepository(data_dir)
        self.clock = clock

    def _now(self) -> str:
        return self.clock().isoformat(timespec="seconds")

    def _store_name(self, store_id: str) -> str:
        store = self.store_repo.find_by_id(store_id)
        return store["name"] if store else store_id

    # ── 해결책 생성 ────────────────────────────────────────────────

    def build_options(self, reservation: dict, issue: dict) -> list[dict]:
        """문제 원인 하나에 대해 가능한 해결책 후보를 모두 만든다 (DB에 저장하지 않음)."""
        code, detail = issue["code"], issue.get("detail", {})
        device = reservation["device"]
        store_name = self._store_name(reservation["store_id"])
        options = []

        if code == ISSUE_STOCK_SHORTAGE:
            for nearby in detail.get("nearby_stores", []):
                if nearby.get("quantity", 0) <= 0:
                    continue
                nearby_name = self._store_name(nearby["store_id"])
                lead_days = nearby.get("lead_days", DEFAULT_TRANSFER_LEAD_DAYS)
                options.append(
                    _option(
                        ACTION_NEARBY_STORE_TRANSFER,
                        nearby["store_id"],
                        f"{nearby_name} 재고 1대 이동",
                        f"{nearby_name}에 보유 중인 {_device_label(device)} {nearby['quantity']}대 중 1대를 "
                        f"{store_name}으로 이동합니다. 약 {lead_days}일 소요.",
                        {"from_store_id": nearby["store_id"], "lead_days": lead_days},
                    )
                )
            for spec in detail.get("alt_specs", []):
                new_device = {"model": device["model"], "color": spec["color"], "storage": spec["storage"]}
                options.append(
                    _option(
                        ACTION_COLOR_STORAGE_CHANGE,
                        f"{spec['color']}/{spec['storage']}",
                        f"{spec['color']} · {spec['storage']}로 변경 제안",
                        f"{store_name}에 재고가 있는 {_device_label(new_device)}로 변경을 고객에게 제안합니다.",
                        {"device": new_device},
                    )
                )
            alt_device = detail.get("alt_device")
            if alt_device:
                options.append(
                    _option(
                        ACTION_ALTERNATIVE_DEVICE,
                        alt_device["model"],
                        f"{alt_device['model']} 대체 단말 제안",
                        f"즉시 개통 가능한 {_device_label(alt_device)}를 대체 단말로 제안합니다.",
                        {"device": alt_device},
                    )
                )
            restock_date = detail.get("restock_date")
            if restock_date:
                options.append(
                    _option(
                        ACTION_DATE_CHANGE,
                        restock_date,
                        f"수령일 {restock_date}로 변경",
                        f"재고 확보 예정일({restock_date})에 맞춰 수령일 변경을 고객에게 요청합니다.",
                        {"suggested_date": restock_date},
                    )
                )

        elif code == ISSUE_INSTALLMENT_LIMIT:
            shortfall = detail.get("shortfall_amount", 0)
            price = detail.get("device_price")
            options.append(
                _option(
                    ACTION_DOWN_PAYMENT,
                    str(shortfall),
                    f"선납금 {_won(shortfall)} 적용",
                    f"할부한도 부족분 {_won(shortfall)}을 선납금으로 받아 할부 원금을 한도 안으로 낮춥니다.",
                    {"amount": shortfall},
                )
            )
            monthly = ""
            if price:
                monthly = (
                    f" 월 할부금 약 {_won(price // INSTALLMENT_MONTHS_FROM)} → "
                    f"{_won(price // INSTALLMENT_MONTHS_TO)}."
                )
            options.append(
                _option(
                    ACTION_INSTALLMENT_ADJUSTMENT,
                    str(INSTALLMENT_MONTHS_TO),
                    f"할부기간 {INSTALLMENT_MONTHS_FROM}→{INSTALLMENT_MONTHS_TO}개월 조정",
                    f"할부기간을 늘려 한도 재심사를 요청합니다.{monthly}",
                    {"from_months": INSTALLMENT_MONTHS_FROM, "to_months": INSTALLMENT_MONTHS_TO},
                )
            )

        elif code == ISSUE_MISSING_DOCUMENTS:
            documents = detail.get("documents", [])
            names = ", ".join(documents) or "필요 서류"
            options.append(
                _option(
                    ACTION_DOCUMENT_REQUEST,
                    "message",
                    f"{names} 제출 요청 (문자)",
                    f"고객에게 {names} 제출 안내 문자를 보냅니다.",
                    {"documents": documents, "channel": "문자"},
                )
            )
            options.append(
                _option(
                    ACTION_DOCUMENT_REQUEST,
                    "visit",
                    f"{names} 매장 방문 제출 안내",
                    f"고객에게 전화해 {names}를 매장에서 제출하도록 안내합니다.",
                    {"documents": documents, "channel": "전화"},
                )
            )

        elif code == ISSUE_IDENTITY_FAILED:
            method = detail.get("method", "휴대폰 본인인증")
            options.append(
                _option(
                    ACTION_IDENTITY_RETRY,
                    "same",
                    f"{method} 재시도",
                    f"실패 사유({detail.get('reason', '확인 필요')})를 안내하고 {method}을 다시 요청합니다.",
                    {"method": method},
                )
            )
            options.append(
                _option(
                    ACTION_IDENTITY_RETRY,
                    "in_person",
                    "매장 대면 신분증 인증",
                    "비대면 인증 대신 매장 방문 시 신분증 진위확인으로 본인인증을 진행합니다.",
                    {"method": "대면 신분증 확인"},
                )
            )

        elif code == ISSUE_ACTIVATION_REJECTED:
            reason = detail.get("reason", "입력값 오류")
            field = detail.get("field_label", "반려 항목")
            options.append(
                _option(
                    ACTION_ACTIVATION_INPUT_FIX,
                    "fix",
                    f"{field} 수정 후 재접수",
                    f"반려 사유 '{reason}'에 해당하는 {field} 값을 고객 정보와 대조해 고친 뒤 개통을 다시 접수합니다.",
                    {"reason": reason, "field_label": field},
                )
            )

        elif code == ISSUE_CUSTOMER_NO_RESPONSE:
            options.append(
                _option(
                    ACTION_CUSTOMER_RECONTACT,
                    "call",
                    "고객에게 전화 재연락",
                    f"마지막 연락({detail.get('last_contact_channel', '문자')}) 이후 응답이 없어 담당자가 직접 전화합니다.",
                    {"channel": "전화"},
                )
            )
            options.append(
                _option(
                    ACTION_CUSTOMER_RECONTACT,
                    "kakao",
                    "알림톡 재발송 + 수령 일정 확인",
                    "수령 일정과 준비 상황을 담은 알림톡을 다시 보내고 회신을 요청합니다.",
                    {"channel": "알림톡"},
                )
            )

        elif code == ISSUE_CUSTOMER_UNKNOWN:
            options.append(
                _option(
                    ACTION_CUSTOMER_INFO_CHECK,
                    "lookup",
                    "고객 정보 전산 조회 후 등록",
                    "본인인증·제출서류·할부한도 정보가 없어 개통 위험을 판단할 수 없습니다. "
                    "전산에서 고객 정보를 조회해 등록합니다.",
                    {"customer_id": detail.get("customer_id")},
                )
            )

        elif code == ISSUE_OVERDUE_PAYMENT:
            amount = detail.get("amount")
            amount_text = f" {_won(amount)}" if amount else ""
            options.append(
                _option(
                    ACTION_PAYMENT_GUIDE,
                    "guide",
                    f"미납요금{amount_text} 납부 안내",
                    f"미납요금{amount_text} 납부 방법을 안내하고, 납부 확인 후 개통을 진행합니다.",
                    {"amount": amount},
                )
            )

        return self._apply_memo_insight(reservation, options)

    @staticmethod
    def _apply_memo_insight(reservation: dict, options: list[dict]) -> list[dict]:
        """고객 메모에서 읽어 낸 의사(대체 색상 가능, 서류 제출 예정일, 연락 방법)를 해결책 순서·설명에 반영한다."""
        insight = reservation.get("memo_insight") or {}
        if not insight:
            return options
        colors = set(insight.get("flexible_colors") or [])
        contact = insight.get("contact_preference")
        eta = insight.get("document_eta")

        def preferred(option: dict) -> bool:
            detail = option["detail"]
            if option["action_type"] == ACTION_COLOR_STORAGE_CHANGE:
                return detail["device"]["color"] in colors
            if option["action_type"] == ACTION_CUSTOMER_RECONTACT:
                return detail.get("channel") == contact
            if option["action_type"] == ACTION_DOCUMENT_REQUEST:
                return detail.get("channel") == contact
            return False

        for option in options:
            if preferred(option):
                option["title"] += " · 고객 메모 반영"
            if option["action_type"] == ACTION_DOCUMENT_REQUEST and eta:
                option["description"] += f" 고객 메모상 서류 제출 예정일: {eta}."
        # 고객이 원한다고 적은 안을 맨 앞으로 (나머지 순서는 유지)
        return sorted(options, key=lambda option: not preferred(option))

    def propose(self, reservation: dict, issue_codes: list[str] | None = None) -> list[int]:
        """미해결 문제마다 해결책을 만들어 저장한다. 이미 실패한 안은 다시 제안하지 않는다."""
        existing = self.action_repo.list_by_reservation(reservation["reservation_id"])
        now = self._now()
        created = []

        for issue in reservation["issues"]:
            if issue_codes is not None and issue["code"] not in issue_codes:
                continue
            same_issue = [action for action in existing if action["issue_code"] == issue["code"]]
            if any(action["status"] in (ACTION_PROPOSED, ACTION_APPROVED) for action in same_issue):
                continue
            failed_keys = {
                action["detail"].get("option_key") for action in same_issue if action["status"] == ACTION_FAILED
            }
            options = [
                option
                for option in self.build_options(reservation, issue)
                if option["detail"]["option_key"] not in failed_keys
            ]
            if not options:
                escalation = _option(
                    ACTION_MANAGER_ESCALATION,
                    issue["code"],
                    "점장 에스컬레이션",
                    f"{ISSUE_LABELS.get(issue['code'], issue['code'])} 문제에 대한 해결책이 모두 실패했습니다. "
                    "점장에게 예외 처리를 요청합니다.",
                )
                if escalation["detail"]["option_key"] not in failed_keys:
                    options = [escalation]

            for option in options:
                created.append(
                    self.action_repo.insert(
                        {
                            "reservation_id": reservation["reservation_id"],
                            "issue_code": issue["code"],
                            "action_type": option["action_type"],
                            "title": option["title"],
                            "description": option["description"],
                            "detail": option["detail"],
                            "status": ACTION_PROPOSED,
                            "created_at": now,
                        }
                    )
                )
            if options:
                self.history_repo.add(
                    reservation["reservation_id"],
                    EVENT_ACTIONS_PROPOSED,
                    f"{ISSUE_LABELS.get(issue['code'], issue['code'])} 해결책 {len(options)}건을 생성했습니다.",
                    now,
                )
        return created

    # ── 상태 전이 ──────────────────────────────────────────────────

    def refresh_status(self, reservation_id: str) -> str:
        """해결책·문제 상태를 보고 진행상태를 다시 정한다. 바뀌면 처리이력에 남긴다."""
        reservation = self.reservation_repo.find_by_id(reservation_id)
        current = reservation["status"]
        if current in CLOSED_STATUSES:
            return current

        actions = self.action_repo.list_by_reservation(reservation_id)
        if any(action["status"] == ACTION_APPROVED for action in actions):
            new_status = STATUS_IN_PROGRESS
        elif reservation["issues"]:
            new_status = STATUS_ACTION_REQUIRED
        else:
            new_status = STATUS_READY

        if new_status != current:
            now = self._now()
            self.reservation_repo.update(reservation_id, {"status": new_status, "updated_at": now})
            self.history_repo.add(
                reservation_id,
                EVENT_STATUS_CHANGED,
                f"진행상태: {STATUS_LABELS[current]} → {STATUS_LABELS[new_status]}",
                now,
            )
        return new_status

    def _load(self, reservation_id: str, action_id: int) -> tuple[dict, dict]:
        reservation = self.reservation_repo.find_by_id(reservation_id)
        if reservation is None:
            raise ActionError("NOT_FOUND", "예약을 찾을 수 없습니다.", 404)
        action = self.action_repo.find_by_id(action_id)
        if action is None or action["reservation_id"] != reservation_id:
            raise ActionError("NOT_FOUND", "해결책을 찾을 수 없습니다.", 404)
        if reservation["status"] in CLOSED_STATUSES:
            raise ActionError("INVALID_STATE", "이미 종료된 예약입니다.", 409)
        return reservation, action

    def approve(self, reservation_id: str, action_id: int) -> None:
        reservation, action = self._load(reservation_id, action_id)
        if action["status"] != ACTION_PROPOSED:
            raise ActionError("INVALID_STATE", "제안 상태의 해결책만 승인할 수 있습니다.", 409)

        now = self._now()
        self.action_repo.update_status(action_id, ACTION_APPROVED, now)
        # 같은 문제에 대한 나머지 제안은 보류한다. 승인한 안이 실패하면 다시 제안된다.
        for other in self.action_repo.list_by_reservation(reservation_id):
            if other["issue_code"] == action["issue_code"] and other["status"] == ACTION_PROPOSED:
                self.action_repo.update_status(other["action_id"], ACTION_DISCARDED, now)
        self.history_repo.add(
            reservation_id,
            EVENT_ACTION_APPROVED,
            f"[{ACTION_LABELS.get(action['action_type'])}] {action['title']} 승인 · 실행을 시작했습니다.",
            now,
            action_id,
        )
        self.refresh_status(reservation_id)

    def succeed(self, reservation_id: str, action_id: int) -> None:
        reservation, action = self._load(reservation_id, action_id)
        if action["status"] != ACTION_APPROVED:
            raise ActionError("INVALID_STATE", "승인된 해결책만 결과를 입력할 수 있습니다.", 409)

        now = self._now()
        self.action_repo.update_status(action_id, ACTION_SUCCEEDED, now)

        fields = {
            "issues": [issue for issue in reservation["issues"] if issue["code"] != action["issue_code"]],
            "updated_at": now,
        }
        detail = action["detail"]
        if action["action_type"] in (ACTION_COLOR_STORAGE_CHANGE, ACTION_ALTERNATIVE_DEVICE):
            fields["device"] = detail["device"]
        elif action["action_type"] == ACTION_DATE_CHANGE:
            fields["desired_activation_date"] = detail["suggested_date"]
            fields["activation_deadline"] = f"{detail['suggested_date']}T{ACTIVATION_DEADLINE_TIME}"
        self.reservation_repo.update(reservation_id, fields)

        self.history_repo.add(
            reservation_id,
            EVENT_ACTION_SUCCEEDED,
            f"{action['title']} 성공 · {ISSUE_LABELS.get(action['issue_code'], action['issue_code'])} 문제가 해결됐습니다.",
            now,
            action_id,
        )
        self.refresh_status(reservation_id)

    def fail(self, reservation_id: str, action_id: int) -> list[int]:
        reservation, action = self._load(reservation_id, action_id)
        if action["status"] != ACTION_APPROVED:
            raise ActionError("INVALID_STATE", "승인된 해결책만 결과를 입력할 수 있습니다.", 409)

        now = self._now()
        self.action_repo.update_status(action_id, ACTION_FAILED, now)
        self.reservation_repo.update(
            reservation_id, {"retry_count": reservation["retry_count"] + 1, "updated_at": now}
        )
        self.history_repo.add(
            reservation_id,
            EVENT_ACTION_FAILED,
            f"{action['title']} 실패 · 새로운 대안을 생성합니다.",
            now,
            action_id,
        )
        created = self.propose(self.reservation_repo.find_by_id(reservation_id), [action["issue_code"]])
        self.refresh_status(reservation_id)
        return created

    def complete_activation(self, reservation_id: str) -> None:
        reservation = self.reservation_repo.find_by_id(reservation_id)
        if reservation is None:
            raise ActionError("NOT_FOUND", "예약을 찾을 수 없습니다.", 404)
        if reservation["status"] != STATUS_READY:
            raise ActionError("INVALID_STATE", "모든 문제가 해결된 '개통 대기' 예약만 완료 처리할 수 있습니다.", 409)

        now = self._now()
        self.reservation_repo.update(
            reservation_id, {"status": STATUS_COMPLETED, "completed_at": now, "updated_at": now}
        )
        self.history_repo.add(reservation_id, EVENT_ACTIVATION_COMPLETED, "개통을 완료했습니다.", now)
