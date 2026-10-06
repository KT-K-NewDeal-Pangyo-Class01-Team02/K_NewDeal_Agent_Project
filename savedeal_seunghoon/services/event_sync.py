"""외부 이벤트 가져오기·반영·정기 점검을 한곳에 모은다. API(routes/events.py)와 백그라운드 작업이 함께 쓴다.

백그라운드 작업: SaveDeal 서버가 켜져 있는 동안 EVENT_SYNC_SECONDS(기본 60초)마다
  ① n8n(N8N_EVENTS_URL)에서 외부 이벤트를 가져와 반영하고  ② 정기 점검(새 고위험 알림)을 한다.
브라우저(대시보드)를 열어 두지 않아도 돈다. 같은 이벤트는 한 번만 반영되므로 여러 번 돌아도 안전하다.
"""
import logging
import os
import threading
import time
from datetime import datetime

from services import n8n_client
from services.dashboard_service import DashboardService
from services.event_service import RESULT_APPLIED, EventService
from services.monitor_service import MonitorService
from services.notification_service import NotificationService, mask_name

MAX_EVENTS = 500
FIRST_RUN_DELAY_SECONDS = 5
MIN_INTERVAL_SECONDS = 15

log = logging.getLogger("savedeal.event_sync")

# 백그라운드 작업 상태 (연동 상태 칩에 보여 준다)
STATUS = {"running": False, "interval": None, "last_run": None, "last_error": None, "last_applied": 0}


def _paths(config):
    return config["DB_PATH"], config["DATA_DIR"]


def apply_and_notify(config, raw_events: list) -> dict:
    """이벤트를 반영하고, 반영된 것이 있으면 담당자에게 한 통으로 알린다."""
    results = EventService(*_paths(config)).apply_batch(raw_events)
    applied = [r for r in results if r["result"] == RESULT_APPLIED]

    notification = None
    if applied:
        dashboard = DashboardService(*_paths(config))
        lines, high = [], []
        for item in applied:
            detail = dashboard.get_detail(item["reservation_id"])
            risk = f"{detail['risk_label']} {detail['churn_risk_score']}점 · " if detail["is_open"] else ""
            lines.append(
                f"- {item['reservation_id']} · {mask_name(detail['customer_name'])} · {item['message']} "
                f"→ {risk}{detail['status_label']}"
            )
            if detail["risk_level"] == "high":
                high.append(item["reservation_id"])
        notifier = NotificationService(config["DB_PATH"], config)
        reservation_id = applied[0]["reservation_id"] if len({r["reservation_id"] for r in applied}) == 1 else None
        notification = notifier.notify_external_events(lines, reservation_id)
        # 이 메일로 고위험 사실을 이미 알렸으므로 정기 점검이 다시 알리지 않게 한다
        notifier.mark_alerted(high)

    counts = {}
    for r in results:
        counts[r["result"]] = counts.get(r["result"], 0) + 1
    return {"received": len(results), "counts": counts, "results": results, "notification": notification}


def sync_once(config, scan: bool = True) -> dict:
    """n8n 에서 이벤트를 가져와 반영하고(주소가 있을 때), 정기 점검을 한다. n8n 오류는 N8nError 로 올린다."""
    url = config.get("N8N_EVENTS_URL", "")
    result = {"enabled": bool(url), "received": 0, "counts": {}, "results": [], "notification": None}
    if url:
        raw_events = n8n_client.fetch_events(
            url,
            timeout=float(config.get("N8N_TIMEOUT", 8)),
            secret=config.get("N8N_WEBHOOK_SECRET", ""),
            secret_header=config.get("N8N_SECRET_HEADER", ""),
        )
        result.update(apply_and_notify(config, raw_events[:MAX_EVENTS]))
    if scan:
        result["scan"] = MonitorService(*_paths(config), config).scan()
    return result


# ── 백그라운드 작업 ──────────────────────────────────────────────

def should_start(config, environ=os.environ) -> bool:
    """서버로 실행될 때만 켠다. 테스트, 간격 0, n8n 주소가 하나도 없을 때는 끈다.
    디버그 모드(자동 재시작)에서는 실제로 요청을 받는 자식 프로세스에서만 켠다."""
    if config.get("TESTING") or int(config.get("EVENT_SYNC_SECONDS", 60)) <= 0:
        return False
    if not (config.get("N8N_EVENTS_URL") or config.get("N8N_WEBHOOK_URL")):
        return False
    if config.get("DEBUG") and environ.get("WERKZEUG_RUN_MAIN") != "true":
        return False
    return True


def run_cycle(app) -> None:
    """한 번 돌고 결과를 STATUS 에 남긴다. 어떤 오류가 나도 다음 주기는 계속 돈다."""
    with app.app_context():
        try:
            result = sync_once(app.config)
            STATUS.update(last_error=None, last_applied=result["counts"].get(RESULT_APPLIED, 0))
        except n8n_client.N8nError as exc:
            if STATUS["last_error"] != str(exc):
                log.warning("외부 이벤트 가져오기 실패: %s", exc)
            STATUS["last_error"] = str(exc)
        except Exception:  # noqa: BLE001 - 백그라운드 작업은 멈추지 않는다
            log.exception("외부 이벤트 자동 확인 중 오류")
            STATUS["last_error"] = "내부 오류가 났습니다. 서버 로그를 확인해 주세요."
        STATUS["last_run"] = datetime.now().isoformat(timespec="seconds")


def start_background_sync(app) -> bool:
    if STATUS["running"] or not should_start(app.config):
        return False
    interval = max(int(app.config.get("EVENT_SYNC_SECONDS", 60)), MIN_INTERVAL_SECONDS)

    def loop():
        time.sleep(FIRST_RUN_DELAY_SECONDS)
        while True:
            run_cycle(app)
            time.sleep(interval)

    STATUS.update(running=True, interval=interval)
    threading.Thread(target=loop, name="savedeal-event-sync", daemon=True).start()
    log.info("외부 이벤트 자동 확인을 시작합니다 (%s초마다).", interval)
    return True
