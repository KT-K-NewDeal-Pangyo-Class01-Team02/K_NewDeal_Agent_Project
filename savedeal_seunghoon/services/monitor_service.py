"""정기 점검: n8n 스케줄(예: 매시간)이 POST /api/monitor/scan 을 부르면 실행한다.

점수는 조회할 때마다 다시 계산되므로, 시간이 흘러 마감이 다가오거나 대기 시간이 길어진 예약은 저절로 고위험이 된다.
하지만 아무도 화면을 열지 않으면 알 수 없으므로, 새로 고위험이 된 예약만 골라 알림 메일을 보낸다.
이미 알린 예약은 다시 알리지 않는다 (고위험에서 내려왔다가 다시 올라가면 또 알린다).
"""
from datetime import datetime
from pathlib import Path

from services.dashboard_service import DashboardService
from services.notification_service import NotificationService


class MonitorService:
    def __init__(self, db_path, data_dir: Path, config: dict, clock=datetime.now):
        self.dashboard = DashboardService(db_path, data_dir, clock)
        self.notifier = NotificationService(db_path, config, clock)

    def scan(self) -> dict:
        items = self.dashboard.list_reservations("all")["items"]
        open_items = [item for item in items if item["is_open"]]
        high_ids = {item["reservation_id"] for item in open_items if item["risk_level"] == "high"}

        self.notifier.clear_alerts_except(high_ids)
        alerted = self.notifier.alerted_ids()
        new_ids = sorted(high_ids - alerted)
        notification = None
        if new_ids:
            notification = self.notifier.notify_high_risk([self.dashboard.get_detail(rid) for rid in new_ids])
        return {
            "checked": len(open_items),
            "high_risk": len(high_ids),
            "new_alerts": new_ids,
            "notification": notification,
        }
