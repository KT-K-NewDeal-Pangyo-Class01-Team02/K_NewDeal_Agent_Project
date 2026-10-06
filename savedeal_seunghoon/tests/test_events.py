"""외부 이벤트(n8n → SaveDeal)와 정기 점검 API."""
import pytest

from services import n8n_client
from services.event_service import external_id, normalize


def post_events(client, events, headers=None):
    return client.post("/api/events", json={"events": events}, headers=headers or {})


def detail(client, reservation_id):
    return client.get(f"/api/reservations/{reservation_id}").get_json()["data"]


# ── 형식 ──────────────────────────────────────────────────────────

def test_normalize_accepts_korean_sheet_headers():
    event = normalize({" 예약번호 ": "r2011", "이벤트": " 개통  반려", "사유": "주소 불일치", "서류": "신분증, 가족관계증명서", "빈칸": ""})
    assert event["reservation_id"] == "R2011"
    assert event["type_key"] == "ACTIVATION_REJECTED"
    assert event["reason"] == "주소 불일치"
    assert event["documents"] == ["신분증", "가족관계증명서"]
    assert event["source"] == "n8n"


def test_external_id_uses_event_id_or_content():
    assert external_id(normalize({"event_id": "A-1", "예약번호": "R2001", "이벤트": "입고 지연"})) == "id:A-1"
    same = [normalize({"예약번호": "R2001", "이벤트": "입고 지연", "발생시각": "10:00"}) for _ in range(2)]
    other = normalize({"예약번호": "R2001", "이벤트": "입고 지연", "발생시각": "11:00"})
    assert external_id(same[0]) == external_id(same[1]) != external_id(other)


# ── 문제 발생 ─────────────────────────────────────────────────────

def test_activation_rejected_adds_issue_and_proposes_fix(client):
    response = post_events(client, [{"예약번호": "R2003", "이벤트": "개통 반려", "사유": "주소 불일치", "반려 항목": "주소"}])
    data = response.get_json()["data"]

    assert response.status_code == 200
    assert data["counts"] == {"APPLIED": 1}
    after = detail(client, "R2003")
    assert "ACTIVATION_REJECTED" in [issue["code"] for issue in after["issues"]]
    assert any(action["title"] == "주소 수정 후 재접수" for action in after["actions"])
    assert any(h["event_label"] == "외부 이벤트" and "주소 불일치" in h["description"] for h in after["history"])


def test_raise_on_in_progress_issue_fails_approved_action_and_retries(client):
    before = detail(client, "R2011")
    approved = [a for a in before["actions"] if a["status"] == "APPROVED"]
    assert approved and approved[0]["issue_code"] == "STOCK_SHORTAGE"

    post_events(client, [{"예약번호": "R2011", "이벤트": "재고 이동 지연", "사유": "물류 지연", "예정일": "2026-12-01"}])

    after = detail(client, "R2011")
    assert after["retry_count"] == before["retry_count"] + 1
    assert approved[0]["action_id"] in [a["action_id"] for a in after["past_actions"] if a["status"] == "FAILED"]
    assert after["actions"] and all(a["status"] == "PROPOSED" for a in after["actions"])
    assert after["status"] == "ACTION_REQUIRED"


# ── 문제 해소 · 종료 ──────────────────────────────────────────────

def test_documents_submitted_resolves_issue(client):
    post_events(client, [{"예약번호": "R2003", "이벤트": "서류 제출"}])

    after = detail(client, "R2003")
    assert after["issues"] == []
    assert after["status"] == "READY"
    assert after["actions"] == []


def test_resolve_without_matching_issue_is_skipped(client):
    data = post_events(client, [{"예약번호": "R2003", "이벤트": "재고 도착"}]).get_json()["data"]
    assert data["counts"] == {"SKIPPED": 1}
    assert data["notification"] is None


def test_activation_completed_and_cancelled_close_reservation(client):
    post_events(client, [
        {"예약번호": "R2003", "이벤트": "개통 완료"},
        {"예약번호": "R2004", "이벤트": "고객 취소", "사유": "타사 개통"},
    ])

    assert detail(client, "R2003")["status"] == "COMPLETED"
    cancelled = detail(client, "R2004")
    assert cancelled["status"] == "CANCELLED"
    assert cancelled["actions"] == []
    # 종료된 예약에 온 이벤트는 건너뛴다
    data = post_events(client, [{"예약번호": "R2004", "이벤트": "개통 반려"}]).get_json()["data"]
    assert data["counts"] == {"SKIPPED": 1}


# ── 중복 · 오류 · 알림 ────────────────────────────────────────────

def test_same_event_is_applied_once(client):
    event = {"예약번호": "R2005", "이벤트": "개통 재접수 승인", "발생시각": "2026-10-06 10:00"}
    first = post_events(client, [event]).get_json()["data"]
    second = post_events(client, [event, event]).get_json()["data"]

    assert first["counts"] == {"APPLIED": 1}
    assert second["counts"] == {"DUPLICATE": 2}
    assert second["notification"] is None


def test_invalid_events_are_reported_not_applied(client):
    data = post_events(client, [
        {"예약번호": "R9999", "이벤트": "개통 반려"},
        {"예약번호": "R2001", "이벤트": "알 수 없는 일"},
        {"이벤트": "개통 반려"},
        "문자열",
    ]).get_json()["data"]

    assert [r["result"] for r in data["results"]] == ["ERROR"] * 4
    assert data["notification"] is None


def test_applied_events_send_one_summary_mail(client):
    data = post_events(client, [
        {"예약번호": "R2003", "이벤트": "개통 반려", "사유": "주소 불일치"},
        {"예약번호": "R2005", "이벤트": "개통 재접수 승인"},
    ]).get_json()["data"]

    notification = data["notification"]
    assert notification["kind"] == "EXTERNAL_EVENTS"
    assert notification["status"] == "DEMO"
    assert "R2003" in notification["body"] and "R2005" in notification["body"]
    assert "*" in notification["body"]  # 이름은 마스킹


def test_single_event_object_and_bad_payload(client):
    assert client.post("/api/events", json={"예약번호": "R2003", "이벤트": "서류 제출"}).status_code == 200
    assert client.post("/api/events", json=[]).status_code == 400
    assert client.post("/api/events", data="not json").status_code == 400


def test_recent_events_api(client):
    post_events(client, [{"예약번호": "R2003", "이벤트": "서류 제출"}])
    data = client.get("/api/events").get_json()["data"]
    assert data["last_id"] == 1
    assert data["items"][0]["event_label"] == "서류 제출 완료"
    assert data["items"][0]["result_label"] == "반영"


# ── 인증 ──────────────────────────────────────────────────────────

def test_without_secret_only_local_requests_are_accepted(client):
    event = [{"예약번호": "R2003", "이벤트": "서류 제출"}]
    forwarded = post_events(client, event, {"X-Forwarded-For": "203.0.113.5"})
    assert forwarded.status_code == 403
    assert client.post("/api/monitor/scan", headers={"X-Forwarded-For": "203.0.113.5"}).status_code == 403


@pytest.fixture
def secret_client(app):
    app.config["N8N_WEBHOOK_SECRET"] = "test-secret"
    return app.test_client()


def test_secret_header_is_required_when_configured(secret_client):
    event = [{"예약번호": "R2003", "이벤트": "서류 제출"}]
    assert post_events(secret_client, event).status_code == 401
    assert post_events(secret_client, event, {"X-SaveDeal-Key": "wrong"}).status_code == 401
    ok = post_events(secret_client, event, {"X-SaveDeal-Key": "test-secret", "X-Forwarded-For": "203.0.113.5"})
    assert ok.status_code == 200


# ── 가져오기 모드 ─────────────────────────────────────────────────

def test_sync_does_nothing_without_url(client):
    data = client.post("/api/events/sync").get_json()["data"]
    assert data["enabled"] is False


def test_sync_pulls_events_from_n8n(app, monkeypatch):
    app.config["N8N_EVENTS_URL"] = "https://example.n8n.cloud/webhook/savedeal-events"
    calls = []

    def fake_send(url, payload, timeout, secret="", secret_header=""):
        calls.append(url)
        return [{"json": {"예약번호": "R2003", "이벤트": "서류 제출", "발생시각": "09:00"}}]

    monkeypatch.setattr(n8n_client, "send", fake_send)
    client = app.test_client()

    first = client.post("/api/events/sync").get_json()["data"]
    second = client.post("/api/events/sync").get_json()["data"]

    assert calls == [app.config["N8N_EVENTS_URL"]] * 2
    assert first["counts"] == {"APPLIED": 1}
    assert second["counts"] == {"DUPLICATE": 1}
    # 가져오기 때마다 정기 점검도 한다 (처음에만 알림)
    assert first["scan"]["new_alerts"] and second["scan"]["new_alerts"] == []


def test_sync_ignores_empty_sheet_items(app, monkeypatch):
    app.config["N8N_EVENTS_URL"] = "https://example.n8n.cloud/webhook/savedeal-events"
    monkeypatch.setattr(n8n_client, "send", lambda *args, **kwargs: [{}, {"json": {}}])
    data = app.test_client().post("/api/events/sync").get_json()["data"]
    assert data["received"] == 0
    assert data["notification"] is None


def test_sync_reports_n8n_error(app, monkeypatch):
    app.config["N8N_EVENTS_URL"] = "https://example.n8n.cloud/webhook/savedeal-events"

    def broken(*args, **kwargs):
        raise n8n_client.N8nError("n8n에 연결하지 못했습니다.")

    monkeypatch.setattr(n8n_client, "send", broken)
    response = app.test_client().post("/api/events/sync")
    assert response.status_code == 502


# ── 정기 점검 ─────────────────────────────────────────────────────

def test_scan_alerts_new_high_risk_once(client):
    first = client.post("/api/monitor/scan").get_json()["data"]
    second = client.post("/api/monitor/scan").get_json()["data"]

    assert first["high_risk"] >= 1
    assert sorted(first["new_alerts"]) == first["new_alerts"] and first["new_alerts"]
    assert first["notification"]["kind"] == "HIGH_RISK"
    assert second["new_alerts"] == []
    assert second["notification"] is None


def test_scan_skips_reservations_already_alerted_elsewhere(client):
    from flask import current_app
    from services.notification_service import NotificationService

    with client.application.app_context():
        NotificationService(current_app.config["DB_PATH"], current_app.config).mark_alerted(["R2001"])
    scan = client.post("/api/monitor/scan").get_json()["data"]
    assert "R2001" not in scan["new_alerts"]


def test_reservation_dropping_out_of_high_risk_can_alert_again(client):
    assert "R2001" in client.post("/api/monitor/scan").get_json()["data"]["new_alerts"]
    post_events(client, [{"예약번호": "R2001", "이벤트": "재고 도착"}])  # 문제 해소 → 고위험에서 내려옴
    assert detail(client, "R2001")["risk_level"] != "high"
    client.post("/api/monitor/scan")  # 알림 기록이 지워진다

    with client.application.app_context():
        from flask import current_app
        from services.notification_service import NotificationService

        assert "R2001" not in NotificationService(current_app.config["DB_PATH"], current_app.config).alerted_ids()


def test_integrations_reports_event_mode(client):
    events = client.get("/api/integrations").get_json()["data"]["events"]
    assert events["pull"] is False
    assert events["background"] is False  # 테스트에서는 백그라운드 작업이 돌지 않는다
    assert events["inbound_auth"] == "local-only"


# ── 백그라운드 자동 확인 ──────────────────────────────────────────

def test_background_sync_starts_only_as_a_server():
    from services.event_sync import should_start

    base = {"EVENT_SYNC_SECONDS": 60, "N8N_EVENTS_URL": "https://example.n8n.cloud/webhook/savedeal-events"}
    assert should_start(base, environ={}) is True
    assert should_start({**base, "TESTING": True}, environ={}) is False
    assert should_start({**base, "EVENT_SYNC_SECONDS": 0}, environ={}) is False
    assert should_start({"EVENT_SYNC_SECONDS": 60}, environ={}) is False  # n8n 주소가 하나도 없음
    assert should_start({"EVENT_SYNC_SECONDS": 60, "N8N_WEBHOOK_URL": "https://x"}, environ={}) is True  # 점검만
    # 디버그 자동 재시작: 감시만 하는 부모 프로세스에서는 끄고, 실제 서버(자식)에서만 켠다
    assert should_start({**base, "DEBUG": True}, environ={}) is False
    assert should_start({**base, "DEBUG": True}, environ={"WERKZEUG_RUN_MAIN": "true"}) is True


def test_background_cycle_pulls_events_and_records_status(app, monkeypatch):
    from services import event_sync

    app.config["N8N_EVENTS_URL"] = "https://example.n8n.cloud/webhook/savedeal-events"
    monkeypatch.setattr(
        n8n_client, "send", lambda *args, **kwargs: [{"예약번호": "R2003", "이벤트": "서류 제출", "발생시각": "09:00"}]
    )
    monkeypatch.setattr(event_sync, "STATUS", dict(event_sync.STATUS))

    event_sync.run_cycle(app)

    assert event_sync.STATUS["last_error"] is None
    assert event_sync.STATUS["last_applied"] == 1
    assert event_sync.STATUS["last_run"]
    assert detail(app.test_client(), "R2003")["issues"] == []


def test_background_cycle_survives_n8n_errors(app, monkeypatch):
    from services import event_sync

    app.config["N8N_EVENTS_URL"] = "https://example.n8n.cloud/webhook/savedeal-events"

    def broken(*args, **kwargs):
        raise n8n_client.N8nError("n8n에 연결하지 못했습니다.")

    monkeypatch.setattr(n8n_client, "send", broken)
    monkeypatch.setattr(event_sync, "STATUS", dict(event_sync.STATUS))

    event_sync.run_cycle(app)  # 예외가 밖으로 나오지 않는다

    assert event_sync.STATUS["last_error"] == "n8n에 연결하지 못했습니다."


def test_demo_reset_clears_event_records(client):
    post_events(client, [{"예약번호": "R2003", "이벤트": "서류 제출"}])
    client.post("/api/monitor/scan")
    client.post("/api/demo/reset")
    assert client.get("/api/events").get_json()["data"] == {"last_id": 0, "items": []}
    assert client.post("/api/monitor/scan").get_json()["data"]["new_alerts"]
