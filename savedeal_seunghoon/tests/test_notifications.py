import io

import pytest
import requests
from openpyxl import Workbook

from config import Config
from services.dashboard_service import DashboardService
from services.notification_service import NotificationService, mask_name

N8N_CONFIG = {"N8N_WEBHOOK_URL": "https://n8n.example/webhook/savedeal", "N8N_WEBHOOK_SECRET": "s3cret",
              "N8N_SECRET_HEADER": "X-SaveDeal-Key", "N8N_TIMEOUT": 3, "NOTIFY_EMAIL_TO": "me@example.com"}


class FakeResponse:
    def __init__(self, status_code=200, data=None):
        self.status_code = status_code
        self._data = data or {"ok": True}

    def json(self):
        return self._data


@pytest.fixture
def sent(monkeypatch):
    calls = []

    def fake_post(url, json=None, headers=None, timeout=None):
        calls.append({"url": url, "json": json, "headers": headers})
        return FakeResponse()

    monkeypatch.setattr(requests, "post", fake_post)
    return calls


def test_mask_name():
    assert mask_name("김민수") == "김*수"
    assert mask_name("정하") == "정*"
    assert mask_name("남궁민수") == "남**수"
    assert mask_name(None) == "고객"


def test_demo_mode_records_without_sending(db_path):
    service = NotificationService(db_path, {"N8N_WEBHOOK_URL": ""})
    result = service.daily_report({"open": 1, "needs_action": 1, "high_risk": 0, "due_today": 0, "completed_today": 0}, {}, [])

    assert service.mode == "demo"
    assert result["status"] == "DEMO"
    assert "[SaveDeal]" in result["subject"]


def test_n8n_mode_sends_payload_with_secret_header(db_path, sent):
    service = NotificationService(db_path, N8N_CONFIG)
    detail = DashboardService(db_path, Config.DATA_DIR).get_detail("R2007")
    result = service.notify_high_risk([detail])

    assert result["status"] == "SENT"
    assert sent[0]["headers"] == {"X-SaveDeal-Key": "s3cret"}
    payload = sent[0]["json"]
    assert payload["kind"] == "HIGH_RISK" and payload["to"] == "me@example.com"
    assert "윤*아" in payload["text"] and "윤서아" not in payload["text"]  # 이름은 마스킹해서 보낸다


def test_failure_then_retry(db_path, monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResponse(status_code=404))
    service = NotificationService(db_path, N8N_CONFIG)
    failed = service.daily_report({"open": 0, "needs_action": 0, "high_risk": 0, "due_today": 0, "completed_today": 0}, {}, [])
    assert failed["status"] == "FAILED" and failed["can_retry"] is True
    assert "운영 주소" in failed["last_error"]

    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResponse())
    retried = service.retry(failed["notification_id"])
    assert retried["status"] == "SENT" and retried["attempts"] == 2
    with pytest.raises(ValueError):
        service.retry(failed["notification_id"])


def test_approve_customer_facing_action_sends_notice(client):
    detail = client.get("/api/reservations/R2003").get_json()["data"]
    action = next(a for a in detail["actions"] if a["action_type"] == "DOCUMENT_REQUEST")

    after = client.post(f"/api/reservations/R2003/actions/{action['action_id']}/approve").get_json()["data"]
    notice = after["notifications"][0]
    assert notice["kind"] == "CUSTOMER_NOTICE" and notice["status"] == "DEMO"
    assert "박*훈 고객님" in notice["body"] and "규칙 기반" in notice["body"]
    assert any(h["event_type"] == "NOTIFICATION" for h in after["history"])


def test_approve_internal_action_sends_nothing(client):
    detail = client.get("/api/reservations/R2001").get_json()["data"]
    action = next(a for a in detail["actions"] if a["action_type"] == "NEARBY_STORE_TRANSFER")
    after = client.post(f"/api/reservations/R2001/actions/{action['action_id']}/approve").get_json()["data"]
    assert after["notifications"] == []


def test_upload_commit_sends_summary_and_high_risk(client):
    book = Workbook()
    sheet = book.active
    sheet.append(["고객번호*", "매장코드*", "모델*", "색상*", "용량*", "가입유형*", "희망 수령일*"])
    sheet.append(["C002", "S001", "iPhone 16", "Blue", "128GB", "신규가입", "2026-10-03"])  # 미납·본인인증 실패 고객
    buffer = io.BytesIO()
    book.save(buffer)
    batch = client.post("/api/uploads", data={"kind": "reservations", "file": (io.BytesIO(buffer.getvalue()), "a.xlsx")},
                        content_type="multipart/form-data").get_json()["data"]
    done = client.post(f"/api/uploads/{batch['batch_id']}/commit").get_json()["data"]

    assert done["notification"]["kind"] == "UPLOAD_SUMMARY"
    kinds = [n["kind"] for n in client.get("/api/notifications").get_json()["data"]["items"]]
    assert "HIGH_RISK" in kinds


def test_daily_report_and_integrations_endpoints(client):
    report = client.post("/api/notifications/daily-report").get_json()["data"]
    assert report["kind"] == "DAILY_REPORT" and "우선 처리할 예약" in report["body"]

    status = client.get("/api/integrations").get_json()["data"]
    assert status["n8n"]["mode"] == "demo" and status["ai"]["mode"] == "rule"
