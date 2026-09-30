"""더 줘 테스트. 추가 패키지 없이 표준 unittest 로 돈다.

저장소 루트에서:  python -m unittest thejo_project.tests.test_thejo -v
"""
import json
import unittest
from unittest import mock

from command_center.app import app
from command_center.layout import load_agents
from thejo_project import config
from thejo_project.data import sms_store
from thejo_project.services import sms_service, transaction_service, warning_service
from thejo_project.services.incentive_service import (
    calculate_available_benefit_budget,
    calculate_monthly_incentive,
    calculate_next_tier_gain,
    per_unit_incentive,
    units_to_next_tier,
)
from thejo_project.services.opportunity_service import get_dashboard_summary, get_profit_opportunities

TX_ID = "TX-202609-018"


class IncentiveTierTest(unittest.TestCase):
    """인센티브 구간 계산."""

    def test_per_unit_by_tier(self):
        self.assertEqual(per_unit_incentive(1), 100_000)
        self.assertEqual(per_unit_incentive(9), 100_000)
        self.assertEqual(per_unit_incentive(10), 200_000)
        self.assertEqual(per_unit_incentive(19), 200_000)

    def test_monthly_incentive_is_retroactive(self):
        self.assertEqual(calculate_monthly_incentive(9), 900_000)
        self.assertEqual(calculate_monthly_incentive(10), 2_000_000)

    def test_zero_and_out_of_range(self):
        self.assertEqual(calculate_monthly_incentive(0), 0)
        self.assertEqual(calculate_monthly_incentive(-3), 0)
        self.assertEqual(per_unit_incentive(20), 0)

    def test_units_to_next_tier(self):
        self.assertEqual(units_to_next_tier(9), 1)
        self.assertEqual(units_to_next_tier(19), 0)

    def test_next_tier_gain(self):
        self.assertEqual(calculate_next_tier_gain(9), 1_100_000)
        self.assertEqual(calculate_next_tier_gain(19), 0)

    def test_available_benefit_budget_is_400k(self):
        """요구 사항의 핵심 숫자: 110만 - 70만 = 40만 원."""
        self.assertEqual(calculate_available_benefit_budget(9), 400_000)

    def test_budget_never_negative(self):
        self.assertEqual(calculate_available_benefit_budget(9, 5_000_000), 0)

    def test_policy_is_injectable(self):
        tiers = [
            {"min_units": 1, "max_units": 4, "per_unit": 50_000},
            {"min_units": 5, "max_units": None, "per_unit": 150_000},
        ]
        self.assertEqual(calculate_monthly_incentive(5, tiers), 750_000)
        self.assertEqual(calculate_next_tier_gain(4, tiers), 550_000)
        self.assertEqual(per_unit_incentive(999, tiers), 150_000)


class TransactionTest(unittest.TestCase):
    """거래 데이터: 유지 종료일과 남은 일수는 저장값이 아니라 계산값이다."""

    def setUp(self):
        sms_store.clear()

    def tearDown(self):
        sms_store.clear()

    def test_spec_transaction_fields(self):
        tx = transaction_service.get_transaction(TX_ID)
        self.assertEqual(tx["customer_id"], "C-018")
        self.assertEqual(tx["customer_name"], "정○현")
        self.assertEqual(tx["customer_phone"], "010-1234-5678")
        self.assertEqual(tx["device_model"], "Galaxy Z Fold")
        self.assertEqual(tx["plan_name"], "초이스 프리미엄")
        self.assertEqual(tx["activation_date"].isoformat(), "2026-09-18")
        self.assertEqual(tx["required_maintenance_days"], 180)
        self.assertEqual(tx["benefit_amount"], 300_000)
        self.assertEqual(tx["expected_clawback"], 300_000)
        self.assertEqual(tx["store_id"], "STORE-01")
        self.assertEqual(tx["store_phone"], "02-1234-5678")

    def test_maintenance_dates_are_computed(self):
        tx = transaction_service.get_transaction(TX_ID)
        # 개통일 + 필수 유지일수 = 유지 종료일
        self.assertEqual(tx["maintenance_end_date"].isoformat(), "2027-03-17")
        # 기준일(2026-10-18) 기준 남은 유지일수
        self.assertEqual(tx["remaining_days"], 150)
        self.assertEqual(tx["maintained_days"], 30)
        # 유지한 일수 + 남은 일수 = 필수 유지일수
        self.assertEqual(tx["maintained_days"] + tx["remaining_days"], 180)

    def test_unknown_transaction(self):
        self.assertIsNone(transaction_service.get_transaction("TX-없음"))

    def test_every_warning_links_to_a_transaction(self):
        for w in warning_service.get_warning_items():
            with self.subTest(warning=w["id"]):
                self.assertIsNotNone(w["transaction"], f"{w['id']} 의 거래를 찾지 못함")


class SmsTemplateTest(unittest.TestCase):
    """템플릿 치환과 SMS/LMS 판정."""

    def setUp(self):
        sms_store.clear()
        self.tx = transaction_service.get_transaction(TX_ID)

    def tearDown(self):
        sms_store.clear()

    def test_no_placeholder_left(self):
        for template in config.SMS_TEMPLATES:
            with self.subTest(template=template["id"]):
                body = sms_service.render_template(template["id"], self.tx)
                self.assertNotIn("{", body, "치환되지 않은 변수가 남아 있음")
                self.assertNotIn("}", body)

    def test_maintenance_template_values(self):
        body = sms_service.render_template("PLAN_MAINTENANCE", self.tx)
        self.assertIn("정○현 고객님", body)
        self.assertIn("초이스 프리미엄", body)
        self.assertIn("2027년 3월 17일", body)
        self.assertIn("300,000원", body)
        self.assertIn("150일", body)
        self.assertIn("02-1234-5678", body)

    def test_clawback_template_values(self):
        body = sms_service.render_template("CLAWBACK_RISK", self.tx)
        self.assertIn("정○현 고객님", body)
        self.assertIn("150일", body)
        self.assertIn("02-1234-5678", body)

    def test_consult_template_values(self):
        body = sms_service.render_template("CONSULT_REQUEST", self.tx)
        self.assertIn("정○현 고객님", body)
        self.assertIn("02-1234-5678", body)

    def test_templates_differ_per_transaction(self):
        other = transaction_service.get_transaction("TX-202609-003")
        a = sms_service.render_template("CLAWBACK_RISK", self.tx)
        b = sms_service.render_template("CLAWBACK_RISK", other)
        self.assertNotEqual(a, b)
        self.assertIn("이○우", b)
        self.assertNotIn("정○현", b)

    def test_unknown_template(self):
        with self.assertRaises(KeyError):
            sms_service.render_template("NOPE", self.tx)

    def test_byte_count_korean_is_two(self):
        self.assertEqual(sms_service.message_bytes("abc"), 3)
        self.assertEqual(sms_service.message_bytes("가나다"), 6)
        self.assertEqual(sms_service.message_bytes(""), 0)

    def test_sms_lms_boundary(self):
        self.assertEqual(sms_service.message_kind("가" * 45), "SMS")   # 90바이트
        self.assertEqual(sms_service.message_kind("가" * 46), "LMS")   # 92바이트
        # 실제 템플릿은 길어서 LMS
        self.assertEqual(sms_service.message_kind(sms_service.render_template("PLAN_MAINTENANCE", self.tx)), "LMS")


class SmsSendTest(unittest.TestCase):
    """발송: 데모 모드 · n8n 성공 · n8n 실패 · 기록 영속."""

    def setUp(self):
        sms_store.clear()
        warning_service.reset_acknowledgements()
        app.config["TESTING"] = True
        self.client = app.test_client()

        # 테스트는 **절대 실제 n8n 을 호출하지 않는다.**
        # .env 에 N8N_SMS_WEBHOOK_URL 이 있어도 기본은 데모 모드로 고정한다.
        # n8n 경로를 보는 테스트는 각자 이 값을 다시 patch 한다.
        patcher = mock.patch.object(config, "N8N_SMS_WEBHOOK_URL", "")
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        sms_store.clear()

    def _send(self, **overrides):
        body = {"transaction_id": TX_ID, "template_id": "PLAN_MAINTENANCE", "message": "테스트 문자입니다."}
        body.update(overrides)
        return self.client.post("/thejo/api/sms/send", json=body)

    def test_demo_mode(self):
        res = self._send()
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertTrue(data["demo"])
        self.assertEqual(data["message"], "데모 모드로 문자 발송 요청이 처리되었습니다.")

    def test_demo_mode_never_calls_network(self):
        """데모 모드에서는 네트워크를 건드리지 않는다."""
        with mock.patch.object(sms_service, "_post_json") as post:
            self._send()
        post.assert_not_called()

    def test_record_is_persisted(self):
        self._send()
        records = sms_store.load_all()
        self.assertEqual(len(records), 1)
        r = records[0]
        for field in ("sms_id", "transaction_id", "customer_id", "customer_phone", "template_id",
                      "message", "sms_status", "requested_at", "sent_at", "error_message", "n8n_response"):
            self.assertIn(field, r)
        self.assertEqual(r["transaction_id"], TX_ID)
        self.assertEqual(r["customer_id"], "C-018")
        self.assertEqual(r["customer_phone"], "010-1234-5678")
        self.assertEqual(r["sms_status"], "발송 완료")
        self.assertIsNone(r["error_message"])

    def test_status_survives_reload(self):
        """새로고침해도 '발송 완료' 가 남아야 한다."""
        self.assertEqual(transaction_service.get_transaction(TX_ID)["sms_status"], "미발송")
        self._send()
        self.assertEqual(transaction_service.get_transaction(TX_ID)["sms_status"], "발송 완료")
        html = self.client.get("/thejo/warnings").get_data(as_text=True)
        self.assertIn("문자 안내 완료", html)

    def test_rejects_empty_message(self):
        res = self._send(message="   ")
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.get_json()["success"])
        self.assertEqual(sms_store.load_all(), [])

    def test_rejects_unknown_transaction(self):
        self.assertEqual(self._send(transaction_id="TX-없음").status_code, 404)

    def test_rejects_unknown_template(self):
        self.assertEqual(self._send(template_id="NOPE").status_code, 400)

    def test_server_rebuilds_customer_data(self):
        """화면이 보낸 고객 정보는 무시하고 서버 데이터를 쓴다."""
        self._send(customer_phone="010-0000-0000", customer_name="해커")
        r = sms_store.load_all()[0]
        self.assertEqual(r["customer_phone"], "010-1234-5678")

    def test_n8n_success(self):
        with mock.patch.object(config, "N8N_SMS_WEBHOOK_URL", "https://n8n.example/webhook/sms"), \
             mock.patch.object(sms_service, "_post_json", return_value={"ok": True}) as post:
            res = self._send()
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertFalse(data["demo"])
        post.assert_called_once()
        # 요구사항 5번의 페이로드가 그대로 n8n 으로 간다
        payload = post.call_args[0][1]
        for field in ("transaction_id", "customer_id", "customer_name", "customer_phone", "template_id",
                      "message", "plan_name", "maintenance_end_date", "remaining_days",
                      "expected_clawback", "store_id", "store_phone"):
            self.assertIn(field, payload)
        self.assertEqual(payload["remaining_days"], 150)
        self.assertEqual(payload["maintenance_end_date"], "2027-03-17")
        # 제한시간 10초
        self.assertEqual(post.call_args[0][2], config.N8N_SMS_TIMEOUT)

    def test_n8n_failure_records_error(self):
        with mock.patch.object(config, "N8N_SMS_WEBHOOK_URL", "https://n8n.example/webhook/sms"), \
             mock.patch.object(sms_service, "_post_json", side_effect=TimeoutError()):
            res = self._send()
        self.assertEqual(res.status_code, 502)
        self.assertFalse(res.get_json()["success"])
        r = sms_store.load_all()[0]
        self.assertEqual(r["sms_status"], "발송 실패")
        self.assertTrue(r["error_message"])
        # 실패했으니 카드 상태는 그대로 미발송
        self.assertEqual(transaction_service.get_transaction(TX_ID)["sms_status"], "미발송")

    def test_webhook_url_never_reaches_the_browser(self):
        with mock.patch.object(config, "N8N_SMS_WEBHOOK_URL", "https://secret.example/webhook/abc"), \
             mock.patch.object(sms_service, "_post_json", return_value={}):
            body = self._send().get_data(as_text=True)
            page = self.client.get("/thejo/warnings").get_data(as_text=True)
            js_res = self.client.get("/thejo/static/js/thejo.js")
            js = js_res.get_data(as_text=True)
            js_res.close()  # 정적 파일 응답은 파일 핸들을 쥐고 있다
        for text in (body, page, js):
            self.assertNotIn("secret.example", text)
            self.assertNotIn("N8N_SMS_WEBHOOK_URL", text)


class TransactionApiTest(unittest.TestCase):
    """모달이 쓰는 거래 조회 API."""

    def setUp(self):
        sms_store.clear()
        app.config["TESTING"] = True
        self.client = app.test_client()

    def tearDown(self):
        sms_store.clear()

    def test_returns_transaction_and_templates(self):
        data = self.client.get(f"/thejo/api/transactions/{TX_ID}").get_json()
        tx = data["transaction"]
        self.assertEqual(tx["customer_name"], "정○현")
        self.assertEqual(tx["remaining_days"], 150)
        self.assertEqual(tx["maintenance_end_date"], "2027-03-17")
        self.assertEqual(tx["sms_status"], "미발송")
        self.assertEqual(len(data["templates"]), 3)
        self.assertEqual(data["sms_byte_limit"], 90)
        for t in data["templates"]:
            self.assertIn("정○현", t["body"])

    def test_json_is_serialisable(self):
        """date 객체가 남아 있으면 jsonify 가 터진다."""
        raw = self.client.get(f"/thejo/api/transactions/{TX_ID}").get_data(as_text=True)
        json.loads(raw)

    def test_other_transaction_gives_other_customer(self):
        data = self.client.get("/thejo/api/transactions/TX-202609-025").get_json()
        self.assertEqual(data["transaction"]["customer_name"], "박○수")

    def test_unknown_transaction(self):
        self.assertEqual(self.client.get("/thejo/api/transactions/TX-없음").status_code, 404)


class DashboardDataTest(unittest.TestCase):
    def setUp(self):
        sms_store.clear()
        warning_service.reset_acknowledgements()

    def tearDown(self):
        sms_store.clear()

    def test_summary_values(self):
        s = get_dashboard_summary()
        self.assertEqual(s["units_sold"], 9)
        self.assertEqual(s["monthly_incentive"], 900_000)
        self.assertEqual(s["expected_clawback"], 300_000)
        self.assertEqual(s["risk_exposure"], 550_000)
        self.assertEqual(s["estimated_margin"], 350_000)
        self.assertEqual(s["units_to_next_tier"], 1)
        self.assertEqual(s["benefit_budget"], 400_000)

    def test_demo_warnings_cover_required_cases(self):
        items = warning_service.get_warning_items()
        self.assertEqual(len(items), 3)
        by_kind = {w["kind"]: w for w in items}
        self.assertEqual(by_kind["clawback"]["expected_loss"], 300_000)
        self.assertEqual(by_kind["settlement"]["expected_loss"], 200_000)
        self.assertEqual(by_kind["margin"]["expected_loss"], 50_000)
        self.assertEqual(by_kind["clawback"]["days_left"], 12)

    def test_acknowledge_removes_from_active_risk(self):
        self.assertTrue(warning_service.acknowledge("w-1"))
        self.assertEqual(get_dashboard_summary()["expected_clawback"], 0)
        self.assertFalse(warning_service.acknowledge("nope"))

    def test_opportunity_numbers(self):
        o = get_profit_opportunities()[0]
        self.assertEqual(o["units_needed"], 1)
        self.assertEqual(o["tier_gain"], 1_100_000)
        self.assertEqual(o["benefit_budget"], 400_000)

    def test_max_tier_has_no_opportunity(self):
        self.assertEqual(get_profit_opportunities(units=19), [])


class RouteTest(unittest.TestCase):
    """Command Center 와 더 줘가 한 앱에서 함께 뜨는지."""

    def setUp(self):
        sms_store.clear()
        warning_service.reset_acknowledgements()
        app.config["TESTING"] = True
        self.client = app.test_client()

    def tearDown(self):
        sms_store.clear()

    def test_routes_return_200(self):
        for path in ["/", "/thejo/", "/thejo/warnings", "/thejo/opportunities"]:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_home_links_to_thejo_in_same_tab(self):
        html = self.client.get("/").get_data(as_text=True)
        self.assertIn('href="/thejo/"', html)
        self.assertNotIn('href="/thejo/" target="_blank"', html)

    def test_external_agents_still_open_in_new_tab(self):
        """다른 팀원의 별도 서버 카드는 지금까지처럼 새 탭. 카드가 추가돼도 자동으로 검사한다."""
        html = self.client.get("/").get_data(as_text=True)
        external = [a for a in load_agents() if (a.get("url") or "").strip()]
        self.assertTrue(external, "외부 서버 에이전트가 하나도 없어 검사할 게 없음")
        for agent in external:
            with self.subTest(agent=agent["id"]):
                self.assertIn(f'href="{agent["url"]}" target="_blank"', html)

    def test_agents_without_address_still_show_notice(self):
        html = self.client.get("/").get_data(as_text=True)
        for agent in load_agents():
            if not (agent.get("url") or "").strip() and not (agent.get("endpoint") or "").strip():
                with self.subTest(agent=agent["id"]):
                    self.assertIn(f'data-no-url="{agent["name"]}"', html)

    def test_dashboard_can_go_back_home(self):
        html = self.client.get("/thejo/").get_data(as_text=True)
        self.assertIn("Command Center로 돌아가기", html)

    def test_dashboard_shows_computed_amounts(self):
        html = self.client.get("/thejo/").get_data(as_text=True)
        self.assertIn("110만 원", html)
        self.assertIn("40만 원", html)

    def test_warning_card_buttons(self):
        html = self.client.get("/thejo/").get_data(as_text=True)
        self.assertIn("거래 확인", html)
        self.assertIn("조치 완료", html)
        self.assertIn('data-open-sms="TX-202609-018"', html)

    def test_sms_modal_is_present(self):
        for path in ["/thejo/", "/thejo/warnings"]:
            with self.subTest(path=path):
                html = self.client.get(path).get_data(as_text=True)
                self.assertIn('id="sms-dialog"', html)
                self.assertIn("유지조건 안내", html)
                self.assertIn("환수위험 안내", html)
                self.assertIn("상담요청 안내", html)
                self.assertIn('data-send-url="/thejo/api/sms/send"', html)

    def test_static_files_served(self):
        for path in ["/static/common.css", "/thejo/static/css/thejo.css",
                     "/thejo/static/js/thejo.js", "/thejo/static/images/all-clear.svg"]:
            with self.subTest(path=path):
                res = self.client.get(path)
                self.assertEqual(res.status_code, 200)
                res.close()

    def test_simulate_endpoint(self):
        data = self.client.get("/thejo/api/simulate?units=9").get_json()
        self.assertEqual(data["benefit_budget"], 400_000)
        self.assertEqual(self.client.get("/thejo/api/simulate?units=abc").status_code, 400)


if __name__ == "__main__":
    unittest.main()
