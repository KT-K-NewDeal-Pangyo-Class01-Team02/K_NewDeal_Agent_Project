"""사용자에게 보이는 화면·해결책·처리이력·메일에 '가상', '데모' 표현이 없어야 한다."""
import re

BANNED = re.compile("가상|데모")


def _visible_text(html: str) -> str:
    """<script>·주석·태그 속성 대신, 화면에 보이는 글자와 title(마우스 올리면 보이는 글)만 모은다."""
    html = re.sub(r"<script.*?</script>|<!--.*?-->", "", html, flags=re.S)
    titles = " ".join(re.findall(r'title="([^"]*)"', html))
    return re.sub(r"<[^>]+>", " ", html) + " " + titles


def test_pages_have_no_demo_wording(client):
    for url in ("/savedeal", "/savedeal/new", "/savedeal/upload"):
        text = _visible_text(client.get(url).get_data(as_text=True))
        assert not BANNED.search(text), url


def test_dashboard_script_has_no_demo_wording_in_strings():
    from pathlib import Path

    source = (Path(__file__).resolve().parent.parent / "static" / "js" / "dashboard.js").read_text(encoding="utf-8")
    strings = re.findall(r'"([^"\n]*)"', source)
    assert not [s for s in strings if BANNED.search(s)]


def test_actions_history_and_mails_have_no_demo_wording(client):
    items = client.get("/api/reservations").get_json()["data"]["items"]
    for item in items:
        detail = client.get(f"/api/reservations/{item['reservation_id']}").get_json()["data"]
        for action in detail["actions"] + detail["past_actions"]:
            assert not BANNED.search(action["title"] + action["description"]), action
        for history in detail["history"]:
            assert not BANNED.search(history["description"]), history

    # 고객 안내 메일(승인), 리포트 메일, 알림 상태 라벨
    detail = client.get("/api/reservations/R2003").get_json()["data"]
    action = next(a for a in detail["actions"] if a["can_approve"])
    approved = client.post(f"/api/reservations/R2003/actions/{action['action_id']}/approve").get_json()["data"]
    client.post("/api/notifications/daily-report")
    for notification in client.get("/api/notifications").get_json()["data"]["items"]:
        text = notification["subject"] + notification["body"] + notification["kind_label"] + notification["status_label"]
        assert not BANNED.search(text), notification
    assert not [h for h in approved["history"] if BANNED.search(h["description"])]


def test_hidden_event_banner_is_not_drawn():
    """이벤트 배너는 hidden 일 때 빈 테두리도 보이면 안 된다 (display:flex 가 hidden 을 덮지 않게)."""
    from pathlib import Path

    css = (Path(__file__).resolve().parent.parent / "static" / "css" / "dashboard.css").read_text(encoding="utf-8")
    assert ".event-banner[hidden]" in css
