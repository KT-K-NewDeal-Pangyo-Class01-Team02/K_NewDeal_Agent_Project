import json
from datetime import date

from config import Config
from repositories.reservation_repository import ReservationRepository
from services.ai_client import AIError
from services.ai_service import AIService, mask_text
from services.reservation_service import ReservationService

TODAY = date(2026, 10, 1)  # 목요일


class FakeClient:
    provider = "openai"
    model = "fake-model"

    def __init__(self, reply=None, error=None):
        self.reply = reply
        self.error = error
        self.calls = []

    def chat(self, system, user, json_mode=False):
        self.calls.append({"system": system, "user": user, "json_mode": json_mode})
        if self.error:
            raise AIError(self.error)
        return self.reply, 850


def test_rule_mode_reads_colors_document_date_and_contact(db_path):
    service = AIService(db_path, {"OPENAI_API_KEY": ""})
    insight = service.interpret_memo("블랙도 괜찮대요. 서류는 월요일에 가져온다고 함, 전화 선호", "R1", TODAY)

    assert service.mode == "rule"
    assert insight["source"] == "rule"
    assert insight["flexible_colors"] == ["Black"]
    assert insight["document_eta"] == "2026-10-05"
    assert insight["contact_preference"] == "전화"
    assert service.recent_logs()[0]["mode"] == "rule"


def test_ai_mode_uses_client_and_logs_model(db_path):
    reply = json.dumps({"flexible_colors": ["Silver"], "document_eta": "2026-10-06", "contact_preference": "문자",
                        "summary": "실버 가능"})
    client = FakeClient(reply)
    service = AIService(db_path, {}, client=client)
    insight = service.interpret_memo("실버도 돼요 010-1234-5678 로 문자 주세요", "R1", TODAY)

    assert insight["source"] == "ai" and insight["model"] == "fake-model" and insight["latency_ms"] == 850
    assert insight["flexible_colors"] == ["Silver"]
    assert client.calls[0]["json_mode"] is True
    assert "010-1234-5678" not in client.calls[0]["user"]  # 전화번호는 가려서 보낸다
    log = service.recent_logs()[0]
    assert (log["mode"], log["model"], log["success"]) == ("ai", "fake-model", True)


def test_ai_failure_falls_back_to_rules(db_path):
    service = AIService(db_path, {}, client=FakeClient(error="크레딧 부족"))
    insight = service.interpret_memo("블랙 괜찮음", "R1", TODAY)

    assert insight["source"] == "rule" and insight["ai_error"] == "크레딧 부족"
    assert insight["flexible_colors"] == ["Black"]
    assert service.recent_logs()[0]["success"] is False


def test_memo_insight_puts_customer_preference_first(db_path):
    service = ReservationService(db_path, Config.DATA_DIR, ai_service=AIService(db_path, {}))
    # 입고 예정일(10/10)보다 이른 희망일 → 재고 미확보
    payload = {"customer_id": "C001", "store_id": "S001", "line_type": "NEW", "desired_activation_date": "2026-10-05",
               "device": {"model": "GalaxyZ Fold6", "color": "Silver", "storage": "512GB"},
               "memo": "실버 없으면 블랙도 괜찮다고 함"}
    reservation_id, _ = service.create(payload, source="upload")

    reservation = ReservationRepository(db_path).find_by_id(reservation_id)
    assert reservation["memo_insight"]["flexible_colors"] == ["Silver", "Black"]
    actions = service.action_service.action_repo.list_by_reservation(reservation_id)
    stock_actions = [a for a in actions if a["issue_code"] == "STOCK_SHORTAGE"]
    assert stock_actions[0]["action_type"] == "COLOR_STORAGE_CHANGE"
    assert "고객 메모 반영" in stock_actions[0]["title"]


def test_notice_and_briefing_rule_mode(db_path, client):
    service = AIService(db_path, {})
    action = {"title": "가족관계증명서 제출 요청 (문자)", "description": "고객에게 안내 문자를 보냅니다 (가상 발송)."}
    notice = service.compose_notice("박*훈", action, "서류 미제출", "R2003")
    assert notice["text"].startswith("박*훈 고객님") and "(가상" not in notice["text"]

    briefing = client.post("/api/reservations/R2007/briefing").get_json()["data"]
    assert briefing["source"] == "rule"
    assert briefing["text"].count("\n") == 2 and "우선순위" in briefing["text"]


def test_mask_text():
    assert mask_text("연락처 010-9876-5432 입니다") == "연락처 010-****-**** 입니다"
