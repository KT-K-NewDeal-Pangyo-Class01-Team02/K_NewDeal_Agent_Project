"""알림 (SaveDeal → n8n → Gmail). 메일 문구는 여기서 만들고, n8n 은 전달만 한다.

- N8N_WEBHOOK_URL 이 비어 있으면 실제로 보내지 않고 DEMO 로 기록한다 (팀원 컴퓨터·테스트에서도 안전).
- 메일에는 마스킹된 가상 정보(김*수, 010-****-1234)만 담는다.
"""
from datetime import datetime
from pathlib import Path

from db.connection import connect, ensure_database
from repositories.action_history_repository import ActionHistoryRepository
from repositories.reservation_repository import ReservationRepository
from services import n8n_client
from services.codes import (
    ACTION_ALTERNATIVE_DEVICE,
    ACTION_COLOR_STORAGE_CHANGE,
    ACTION_CUSTOMER_RECONTACT,
    ACTION_DATE_CHANGE,
    ACTION_DOCUMENT_REQUEST,
    ACTION_DOWN_PAYMENT,
    ACTION_IDENTITY_RETRY,
    ACTION_INSTALLMENT_ADJUSTMENT,
    ACTION_PAYMENT_GUIDE,
)

KIND_UPLOAD_SUMMARY = "UPLOAD_SUMMARY"
KIND_HIGH_RISK = "HIGH_RISK"
KIND_CUSTOMER_NOTICE = "CUSTOMER_NOTICE"
KIND_DAILY_REPORT = "DAILY_REPORT"
KIND_EXTERNAL_EVENTS = "EXTERNAL_EVENTS"

KIND_LABELS = {
    KIND_UPLOAD_SUMMARY: "업로드 결과",
    KIND_HIGH_RISK: "고위험 경보",
    KIND_CUSTOMER_NOTICE: "고객 안내",
    KIND_DAILY_REPORT: "운영 리포트",
    KIND_EXTERNAL_EVENTS: "외부 이벤트 반영",
}

STATUS_SENT = "SENT"
STATUS_FAILED = "FAILED"
STATUS_DEMO = "DEMO"
STATUS_LABELS = {STATUS_SENT: "발송 완료", STATUS_FAILED: "발송 실패", STATUS_DEMO: "기록만 (메일 미연결)"}

EVENT_NOTIFICATION = "NOTIFICATION"

# 고객에게 안내가 나가는 해결책 (재고 이동·입력값 수정·에스컬레이션 같은 내부 업무는 제외)
CUSTOMER_FACING_ACTIONS = {
    ACTION_DOCUMENT_REQUEST,
    ACTION_CUSTOMER_RECONTACT,
    ACTION_DATE_CHANGE,
    ACTION_COLOR_STORAGE_CHANGE,
    ACTION_ALTERNATIVE_DEVICE,
    ACTION_DOWN_PAYMENT,
    ACTION_INSTALLMENT_ADJUSTMENT,
    ACTION_IDENTITY_RETRY,
    ACTION_PAYMENT_GUIDE,
}

SUBJECT_PREFIX = "[SaveDeal]"
FOOTER = "\n\n— SaveDeal 예약판매 이탈 방지 Agent"


def mask_name(name: str | None) -> str:
    """김민수 → 김*수, 정하 → 정*. 이미 가려진 이름은 그대로."""
    if not name:
        return "고객"
    if "*" in name or len(name) == 1:
        return name
    if len(name) == 2:
        return name[0] + "*"
    return name[0] + "*" * (len(name) - 2) + name[-1]


class NotificationService:
    def __init__(self, db_path, config: dict, clock=datetime.now):
        ensure_database(db_path)
        self.db_path = db_path
        self.config = config
        self.clock = clock
        self.history_repo = ActionHistoryRepository(db_path)
        self.reservation_repo = ReservationRepository(db_path)

    @property
    def mode(self) -> str:
        return "n8n" if self.config.get("N8N_WEBHOOK_URL") else "demo"

    def _now(self) -> str:
        return self.clock().isoformat(timespec="seconds")

    # ── 저장 · 발송 ────────────────────────────────────────────────

    def _create(self, kind: str, subject: str, body: str, reservation_id=None, action_id=None) -> int:
        with connect(self.db_path) as conn:
            cursor = conn.execute(
                """INSERT INTO notifications (kind, reservation_id, action_id, subject, body, status, created_at)
                   VALUES (?, ?, ?, ?, ?, 'PENDING', ?)""",
                (kind, reservation_id, action_id, f"{SUBJECT_PREFIX} {subject}", body + FOOTER, self._now()),
            )
            return cursor.lastrowid

    def _deliver(self, notification_id: int) -> dict:
        row = self._row(notification_id)
        now = self._now()
        status, error = STATUS_DEMO, None
        if self.mode == "n8n":
            payload = {
                "kind": row["kind"],
                "subject": row["subject"],
                "text": row["body"],
                "to": self.config.get("NOTIFY_EMAIL_TO") or None,
                "notification_id": row["notification_id"],
                "idempotency_key": f"savedeal-notification-{row['notification_id']}",
                "reservation_id": row["reservation_id"],
            }
            try:
                n8n_client.send(
                    self.config["N8N_WEBHOOK_URL"],
                    payload,
                    timeout=float(self.config.get("N8N_TIMEOUT", 8)),
                    secret=self.config.get("N8N_WEBHOOK_SECRET", ""),
                    secret_header=self.config.get("N8N_SECRET_HEADER", ""),
                )
                status = STATUS_SENT
            except n8n_client.N8nError as exc:
                status, error = STATUS_FAILED, str(exc)

        with connect(self.db_path) as conn:
            conn.execute(
                """UPDATE notifications SET status = ?, attempts = attempts + 1, last_error = ?,
                   sent_at = CASE WHEN ? = 'SENT' THEN ? ELSE sent_at END WHERE notification_id = ?""",
                (status, error, status, now, notification_id),
            )
        if row["reservation_id"]:
            message = {
                STATUS_SENT: f"{KIND_LABELS[row['kind']]} 메일을 보냈습니다 (n8n → Gmail).",
                STATUS_DEMO: f"{KIND_LABELS[row['kind']]} 메일은 연결된 메일 주소가 없어 발송하지 않고 기록만 남겼습니다.",
                STATUS_FAILED: f"{KIND_LABELS[row['kind']]} 메일 발송에 실패했습니다: {error}",
            }[status]
            self.history_repo.add(row["reservation_id"], EVENT_NOTIFICATION, message, now, row["action_id"])
        return self.serialize(self._row(notification_id))

    def _row(self, notification_id: int) -> dict | None:
        with connect(self.db_path) as conn:
            row = conn.execute("SELECT * FROM notifications WHERE notification_id = ?", (notification_id,)).fetchone()
        return dict(row) if row else None

    def serialize(self, row: dict) -> dict:
        return {
            "notification_id": row["notification_id"],
            "kind": row["kind"],
            "kind_label": KIND_LABELS.get(row["kind"], row["kind"]),
            "reservation_id": row["reservation_id"],
            "subject": row["subject"],
            "body": row["body"],
            "status": row["status"],
            "status_label": STATUS_LABELS.get(row["status"], row["status"]),
            "attempts": row["attempts"],
            "last_error": row["last_error"],
            "created_at": row["created_at"],
            "sent_at": row["sent_at"],
            "can_retry": row["status"] == STATUS_FAILED,
        }

    def retry(self, notification_id: int) -> dict:
        row = self._row(notification_id)
        if row is None:
            raise LookupError("알림을 찾을 수 없습니다.")
        if row["status"] != STATUS_FAILED:
            raise ValueError("발송에 실패한 알림만 다시 보낼 수 있습니다.")
        return self._deliver(notification_id)

    def list_recent(self, limit: int = 20, reservation_id: str | None = None) -> list[dict]:
        query = "SELECT * FROM notifications"
        params: tuple = ()
        if reservation_id:
            query += " WHERE reservation_id = ?"
            params = (reservation_id,)
        query += " ORDER BY notification_id DESC LIMIT ?"
        with connect(self.db_path) as conn:
            rows = conn.execute(query, (*params, limit)).fetchall()
        return [self.serialize(dict(row)) for row in rows]

    # ── 알림 종류 ──────────────────────────────────────────────────

    def notify_upload(self, batch: dict) -> dict:
        result = batch.get("result") or {}
        lines = [
            f"{batch['kind_label']} 업로드가 등록됐습니다.",
            f"- 파일: {batch.get('filename') or '-'}",
            f"- 전체 {batch['total_rows']}행 · 정상 {batch['valid_rows']}행 · 오류 {batch['error_rows']}행",
        ]
        if batch["kind"] == "reservations":
            lines.append(
                f"- 예약 {result.get('created', 0)}건 등록 · 문제 감지 {result.get('with_issues', 0)}건 · "
                f"고위험 {result.get('high_risk', 0)}건 · 오늘 마감 {result.get('due_today', 0)}건"
            )
        else:
            lines.append(f"- 신규 {result.get('created', 0)}건 · 갱신 {result.get('updated', 0)}건")
        subject = f"{batch['kind_label']} 업로드 {batch['valid_rows']}건 등록"
        return self._deliver(self._create(KIND_UPLOAD_SUMMARY, subject, "\n".join(lines)))

    def notify_high_risk(self, details: list[dict]) -> dict | None:
        """새로 생긴 고위험 예약을 직원에게 알린다 (한 통에 모아서)."""
        targets = [d for d in details if d.get("risk_level") == "high"]
        if not targets:
            return None
        lines = [f"고위험 예약 {len(targets)}건이 새로 감지됐습니다. 우선 처리해 주세요.", ""]
        for d in targets:
            issues = ", ".join(issue["label"] for issue in d["issues"]) or "-"
            lines.append(
                f"- {d['reservation_id']} · {mask_name(d['customer_name'])} · {d['device_label']} · "
                f"마감 {d['deadline_label']} · 문제: {issues}"
            )
        reservation_id = targets[0]["reservation_id"] if len(targets) == 1 else None
        result = self._deliver(
            self._create(KIND_HIGH_RISK, f"고위험 예약 {len(targets)}건 감지", "\n".join(lines), reservation_id)
        )
        self.mark_alerted([d["reservation_id"] for d in targets])
        return result

    # ── 고위험 알림 기록 (정기 점검이 같은 예약을 반복해서 알리지 않도록) ──

    def alerted_ids(self) -> set[str]:
        with connect(self.db_path) as conn:
            return {row[0] for row in conn.execute("SELECT reservation_id FROM risk_alerts")}

    def mark_alerted(self, reservation_ids: list[str]) -> None:
        now = self._now()
        with connect(self.db_path) as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO risk_alerts (reservation_id, alerted_at) VALUES (?, ?)",
                [(rid, now) for rid in reservation_ids],
            )

    def clear_alerts_except(self, reservation_ids: set[str]) -> None:
        """고위험에서 내려온 예약은 기록을 지운다. 나중에 다시 고위험이 되면 또 알린다."""
        with connect(self.db_path) as conn:
            for (rid,) in conn.execute("SELECT reservation_id FROM risk_alerts").fetchall():
                if rid not in reservation_ids:
                    conn.execute("DELETE FROM risk_alerts WHERE reservation_id = ?", (rid,))

    def notify_external_events(self, lines: list[str], reservation_id: str | None = None) -> dict | None:
        """외부 이벤트(개통 반려·입고 지연·서류 도착 등)를 반영한 결과를 담당자에게 알린다 (한 통에 모아서)."""
        if not lines:
            return None
        body = "\n".join([f"외부 이벤트 {len(lines)}건을 반영했습니다.", ""] + lines)
        return self._deliver(
            self._create(KIND_EXTERNAL_EVENTS, f"외부 이벤트 {len(lines)}건 반영", body, reservation_id)
        )

    def notify_customer(self, reservation_id: str, action: dict, notice_text: str) -> dict | None:
        """해결책 승인 시 고객 안내문 (고객에게 직접 보내지 않고 담당자 메일로 사본을 보낸다)."""
        if action["action_type"] not in CUSTOMER_FACING_ACTIONS:
            return None
        reservation = self.reservation_repo.find_by_id(reservation_id)
        name = mask_name(reservation["customer_name"])
        body = "\n".join([
            "[고객 안내문] 담당자 확인용 사본입니다. 내용을 확인한 뒤 고객에게 전달해 주세요.",
            f"받는 고객: {name} ({reservation.get('customer_phone') or '-'}) · 예약 {reservation_id}",
            "",
            notice_text,
        ])
        notification_id = self._create(
            KIND_CUSTOMER_NOTICE, f"{name} 고객 안내 · {action['title']}", body, reservation_id, action["action_id"]
        )
        return self._deliver(notification_id)

    def daily_report(self, summary: dict, notes: dict, top_items: list[dict]) -> dict:
        today = self.clock().strftime("%m/%d")
        lines = [
            f"{today} 예약 운영 현황",
            f"- 미완료 {summary['open']}건 · 처리 필요 {summary['needs_action']}건 · 고위험 {summary['high_risk']}건 · "
            f"오늘 마감 {summary['due_today']}건 · 오늘 개통 완료 {summary['completed_today']}건",
            f"- {notes.get('needs_action', '')} · {notes.get('due_today', '')}",
            "",
            "우선 처리할 예약",
        ]
        for index, item in enumerate(top_items[:5], start=1):
            issues = ", ".join(issue["label"] for issue in item["issues"]) or "문제 없음"
            lines.append(
                f"{index}. {item['reservation_id']} · {mask_name(item['customer_name'])} · 우선순위 {item['priority_score']}점 · "
                f"{item['risk_label']} · 마감 {item['deadline_label']} · {issues}"
            )
        return self._deliver(self._create(KIND_DAILY_REPORT, f"{today} 운영 리포트", "\n".join(lines)))
