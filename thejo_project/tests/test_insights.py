"""인사이트(n8n → Google Sheets daily_insights) 연동 테스트.

외부 호출은 전부 mock 한다. **실제 n8n 을 때리지 않는다.**
저장소 루트에서:  python -m unittest thejo_project.tests.test_insights -v
"""
import json
import unittest
import urllib.error
from unittest import mock

from command_center.app import app
from thejo_project import config
from thejo_project.data import insight_data, sms_store
from thejo_project.services import insight_service

WEBHOOK = "https://n8n.example/webhook/thejo-insights"

OPPORTUNITY = {
    "insight_id": "OPP-2026-10-01-1",
    "report_date": "2026-10-01",
    "category": "추가 수익 기회",
    "severity": "기회",
    "device_model_name": "갤럭시 S26",
    "plan_code": "5GX 레귤러",
    "transaction_id": "",
    "customer_name_masked": "",
    "current_sales": 9,
    "additional_sales_needed": 1,
    "amount": 1100000,
    "reason": "1건 추가 판매 시 10건 구간에 도달합니다.",
    "created_at": "2026-10-01 09:00:00",
}
HIGH_RISK = {
    "insight_id": "RISK-2026-10-01-TX-001",
    "report_date": "2026-10-01",
    "category": "확인해야 할 위험",
    "severity": "높음",
    "device_model_name": "갤럭시 S26",
    "plan_code": "",
    "transaction_id": "TX-202609-018",
    "customer_name_masked": "정O현",
    "current_sales": "",
    "additional_sales_needed": "",
    "amount": 300000,
    "reason": "요금제 유지기간 안에 변경이 예정되어 있어 환수 가능성이 있습니다.",
    "created_at": "2026-10-01 09:00:00",
}
SAMPLE = [OPPORTUNITY, HIGH_RISK]


class InsightBase(unittest.TestCase):
    """URL 을 켜고 캐시를 비운 상태에서 시작한다."""

    def setUp(self):
        insight_data.clear_cache()
        self.addCleanup(insight_data.clear_cache)
        for name, value in (("N8N_INSIGHTS_WEBHOOK_URL", WEBHOOK),
                            ("N8N_INSIGHTS_TOKEN", ""),
                            ("INSIGHTS_CACHE_SECONDS", 300.0),
                            ("INSIGHTS_FAILURE_CACHE_SECONDS", 60.0)):
            patcher = mock.patch.object(config, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        # 안전망: 어떤 테스트도 실제 네트워크로 나가지 않게 막는다.
        # _fetch_and_build 가 예외를 전부 삼키므로, 호출 사실을 기록해 뒤에서 실패시킨다.
        self._network_calls = []

        def _blocked(*args, **kwargs):
            self._network_calls.append(args[:1])
            raise urllib.error.URLError("테스트에서 네트워크가 차단되었습니다")

        blocker = mock.patch.object(insight_data.urllib.request, "urlopen", side_effect=_blocked)
        blocker.start()
        self.addCleanup(blocker.stop)
        self.addCleanup(lambda: self.assertEqual(
            self._network_calls, [], "이 테스트가 실제 네트워크를 호출했습니다. mock 을 확인하세요."))

    def _serve(self, payload):
        """_get_json 을 payload 로 바꿔 끼운다."""
        return mock.patch.object(insight_data, "_get_json", return_value=payload)


class ParsingTest(InsightBase):
    def test_plain_array(self):
        with self._serve(SAMPLE):
            data = insight_data.get_latest_insights()
        self.assertEqual(data["report_date"], "2026-10-01")
        self.assertEqual(len(data["opportunities"]), 1)
        self.assertEqual(len(data["high_risks"]), 1)

    def test_items_wrapper(self):
        with self._serve({"items": SAMPLE}):
            data = insight_data.get_latest_insights()
        self.assertEqual(len(data["opportunities"]), 1)
        self.assertEqual(len(data["high_risks"]), 1)

    def test_amount_is_int(self):
        with self._serve(SAMPLE):
            data = insight_data.get_latest_insights()
        o = data["opportunities"][0]
        self.assertEqual(o["amount"], 1_100_000)
        self.assertEqual(o["current_sales"], 9)
        self.assertEqual(o["additional_sales_needed"], 1)
        # 위험 쪽의 빈 문자열은 0 으로
        self.assertEqual(data["high_risks"][0]["current_sales"], 0)

    def test_messy_numbers(self):
        """콤마·소수·공백·쓰레기 값이 들어와도 죽지 않는다."""
        cases = [("1,100,000", 1_100_000), ("9", 9), (9.0, 9), ("", 0), (None, 0),
                 ("  12 ", 12), ("abc", 0), ("3.7", 3), (True, 0)]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(insight_data._int(raw), expected)

    def test_missing_fields_do_not_crash(self):
        with self._serve([{"insight_id": "X", "report_date": "2026-10-01",
                           "category": "추가 수익 기회"}]):
            data = insight_data.get_latest_insights()
        o = data["opportunities"][0]
        self.assertEqual(o["amount"], 0)
        self.assertEqual(o["device_model_name"], "")
        self.assertEqual(o["reason"], "")

    def test_high_severity_only(self):
        low = dict(HIGH_RISK, insight_id="RISK-LOW", severity="보통")
        with self._serve([HIGH_RISK, low]):
            data = insight_data.get_latest_insights()
        self.assertEqual(len(data["high_risks"]), 1)
        self.assertEqual(data["high_risks"][0]["insight_id"], "RISK-2026-10-01-TX-001")

    def test_duplicate_insight_id_keeps_newest(self):
        older = dict(OPPORTUNITY, amount=1, created_at="2026-10-01 08:00:00")
        newer = dict(OPPORTUNITY, amount=2_000_000, created_at="2026-10-01 09:30:00")
        with self._serve([newer, older]):
            data = insight_data.get_latest_insights()
        self.assertEqual(len(data["opportunities"]), 1)
        self.assertEqual(data["opportunities"][0]["amount"], 2_000_000)

    def test_only_latest_report_date(self):
        yesterday = dict(OPPORTUNITY, insight_id="OPP-OLD", report_date="2026-09-30",
                         amount=1, created_at="2026-09-30 09:00:00")
        with self._serve([yesterday, OPPORTUNITY]):
            data = insight_data.get_latest_insights()
        self.assertEqual(data["report_date"], "2026-10-01")
        self.assertEqual(len(data["opportunities"]), 1)
        self.assertEqual(data["opportunities"][0]["amount"], 1_100_000)


class FailureTest(InsightBase):
    """어떤 실패에서도 None 을 돌려주고 예외를 밖으로 내지 않는다."""

    def test_failures_return_none(self):
        failures = [
            urllib.error.HTTPError(WEBHOOK, 500, "err", {}, None),
            urllib.error.URLError("boom"),
            TimeoutError(),
            json.JSONDecodeError("bad", "", 0),
            ValueError("unexpected"),
        ]
        for exc in failures:
            with self.subTest(exc=type(exc).__name__):
                insight_data.clear_cache()
                with mock.patch.object(insight_data, "_get_json", side_effect=exc):
                    self.assertIsNone(insight_data.get_latest_insights())

    def test_empty_responses_return_none(self):
        for payload in (None, [], {}, {"items": []}, "", 0):
            with self.subTest(payload=payload):
                insight_data.clear_cache()
                with self._serve(payload):
                    self.assertIsNone(insight_data.get_latest_insights())

    def test_no_url_means_no_call(self):
        with mock.patch.object(config, "N8N_INSIGHTS_WEBHOOK_URL", ""), \
             mock.patch.object(insight_data, "_get_json") as get:
            self.assertIsNone(insight_data.get_latest_insights())
        get.assert_not_called()


class RequestTest(InsightBase):
    """요청을 어떻게 보내는지."""

    def test_token_header_sent_when_set(self):
        with mock.patch.object(config, "N8N_INSIGHTS_TOKEN", "s3cret"), \
             mock.patch.object(insight_data.urllib.request, "urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(SAMPLE).encode()
            insight_data.get_latest_insights()
        request = urlopen.call_args[0][0]
        self.assertEqual(request.get_header("X-thejo-token"), "s3cret")
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(urlopen.call_args[1]["timeout"], config.N8N_INSIGHTS_TIMEOUT)

    def test_no_token_header_when_blank(self):
        with mock.patch.object(insight_data.urllib.request, "urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(SAMPLE).encode()
            insight_data.get_latest_insights()
        self.assertIsNone(urlopen.call_args[0][0].get_header("X-thejo-token"))


class CacheTest(InsightBase):
    def test_second_call_uses_cache(self):
        with self._serve(SAMPLE) as get:
            insight_data.get_latest_insights()
            insight_data.get_latest_insights()
            insight_data.get_latest_insights()
        self.assertEqual(get.call_count, 1)

    def test_force_refresh_refetches(self):
        with self._serve(SAMPLE) as get:
            insight_data.get_latest_insights()
            insight_data.get_latest_insights(force_refresh=True)
        self.assertEqual(get.call_count, 2)

    def test_failure_is_cached_too(self):
        """n8n 이 죽었을 때 페이지마다 타임아웃을 기다리지 않는다."""
        with mock.patch.object(insight_data, "_get_json", side_effect=TimeoutError()) as get:
            insight_data.get_latest_insights()
            insight_data.get_latest_insights()
        self.assertEqual(get.call_count, 1)


class ServiceTest(InsightBase):
    """거래 연결."""

    def setUp(self):
        super().setUp()
        sms_store.clear()
        self.addCleanup(sms_store.clear)

    def test_known_transaction_is_attached(self):
        with self._serve(SAMPLE):
            data = insight_service.get_view_data()
        risk = data["high_risks"][0]
        self.assertIsNotNone(risk["transaction"])
        self.assertEqual(risk["transaction"]["transaction_id"], "TX-202609-018")
        self.assertEqual(risk["transaction"]["customer_name"], "정○현")

    def test_unknown_transaction_is_none(self):
        unknown = dict(HIGH_RISK, insight_id="RISK-X", transaction_id="TX-없는거래")
        with self._serve([unknown]):
            data = insight_service.get_view_data()
        self.assertIsNone(data["high_risks"][0]["transaction"])

    def test_blank_transaction_id_is_none(self):
        blank = dict(HIGH_RISK, insight_id="RISK-Y", transaction_id="")
        with self._serve([blank]):
            data = insight_service.get_view_data()
        self.assertIsNone(data["high_risks"][0]["transaction"])

    def test_returns_none_on_failure(self):
        with mock.patch.object(insight_data, "_get_json", side_effect=TimeoutError()):
            self.assertIsNone(insight_service.get_view_data())


class ScreenTest(InsightBase):
    """화면에 실제로 반영되는지. 실패하면 데모 화면이 그대로 떠야 한다."""

    def setUp(self):
        super().setUp()
        sms_store.clear()
        self.addCleanup(sms_store.clear)
        app.config["TESTING"] = True
        self.client = app.test_client()

    def _html(self, path, payload=SAMPLE):
        insight_data.clear_cache()
        with self._serve(payload):
            res = self.client.get(path)
        self.assertEqual(res.status_code, 200)
        return res.get_data(as_text=True)

    def test_insight_cards_render(self):
        for path in ["/thejo/", "/thejo/warnings", "/thejo/opportunities"]:
            with self.subTest(path=path):
                html = self._html(path)
                self.assertIn("Google Sheets 최신 데이터 기준 · 2026-10-01", html)

    def test_opportunity_fields_on_screen(self):
        html = self._html("/thejo/opportunities")
        self.assertIn("갤럭시 S26", html)
        self.assertIn("5GX 레귤러", html)
        self.assertIn("1건 추가 판매 시 10건 구간에 도달합니다.", html)
        self.assertIn("1,100,000원", html)

    def test_warning_fields_on_screen(self):
        html = self._html("/thejo/warnings")
        self.assertIn("TX-202609-018", html)
        self.assertIn("정O현", html)          # 마스킹된 이름
        self.assertIn("300,000원", html)
        self.assertIn("환수 가능성이 있습니다", html)
        self.assertIn("높음", html)

    def test_transaction_button_enabled_for_known_tx(self):
        html = self._html("/thejo/warnings")
        self.assertIn('data-open-sms="TX-202609-018"', html)

    def test_transaction_button_disabled_for_unknown_tx(self):
        unknown = dict(HIGH_RISK, insight_id="RISK-X", transaction_id="TX-없는거래")
        html = self._html("/thejo/warnings", [unknown])
        self.assertNotIn('data-open-sms="TX-없는거래"', html)
        self.assertIn("disabled", html)

    def test_current_sheet_transactions_enable_button(self):
        """2026-10-06 시트의 위험 거래(TX-202610-008/009)는 거래 확인 버튼이 켜져야 한다."""
        rows = [dict(HIGH_RISK, insight_id=f"RISK-1006-{n}", transaction_id=f"TX-202610-00{n}")
                for n in (8, 9)]
        html = self._html("/thejo/warnings", rows)
        self.assertIn('data-open-sms="TX-202610-008"', html)
        self.assertIn('data-open-sms="TX-202610-009"', html)

    def test_no_invented_fields(self):
        """daily_insights 에 없는 값을 만들어 쓰지 않는다."""
        html = self._html("/thejo/warnings")
        self.assertNotIn("유지 잔여", html)
        self.assertNotIn("확인 날짜", html)

    def test_webhook_and_token_never_reach_the_browser(self):
        with mock.patch.object(config, "N8N_INSIGHTS_TOKEN", "s3cret"):
            for path in ["/thejo/", "/thejo/warnings", "/thejo/opportunities"]:
                with self.subTest(path=path):
                    html = self._html(path)
                    self.assertNotIn("s3cret", html)
                    self.assertNotIn("n8n.example", html)
                    self.assertNotIn("N8N_INSIGHTS", html)

    def test_demo_fallback_when_url_missing(self):
        with mock.patch.object(config, "N8N_INSIGHTS_WEBHOOK_URL", ""):
            for path in ["/thejo/", "/thejo/warnings", "/thejo/opportunities"]:
                with self.subTest(path=path):
                    res = self.client.get(path)
                    self.assertEqual(res.status_code, 200)
                    html = res.get_data(as_text=True)
                    self.assertNotIn("Google Sheets 최신 데이터 기준", html)
            # 기존 데모 화면의 계산값이 그대로 보인다
            self.assertIn("40만 원", self.client.get("/thejo/").get_data(as_text=True))

    def test_demo_fallback_on_error_not_500(self):
        """n8n 이 터져도 500 이 아니라 데모 화면."""
        for exc in (TimeoutError(), urllib.error.URLError("boom"),
                    json.JSONDecodeError("bad", "", 0)):
            for path in ["/thejo/", "/thejo/warnings", "/thejo/opportunities"]:
                with self.subTest(exc=type(exc).__name__, path=path):
                    insight_data.clear_cache()
                    with mock.patch.object(insight_data, "_get_json", side_effect=exc):
                        res = self.client.get(path)
                    self.assertEqual(res.status_code, 200)
                    self.assertNotIn("Google Sheets 최신 데이터 기준",
                                     res.get_data(as_text=True))


class ExistingFeaturesTest(InsightBase):
    """인사이트가 켜져 있어도 기존 기능이 그대로 동작한다."""

    def setUp(self):
        super().setUp()
        sms_store.clear()
        self.addCleanup(sms_store.clear)
        app.config["TESTING"] = True
        self.client = app.test_client()
        patcher = mock.patch.object(config, "N8N_SMS_WEBHOOK_URL", "")  # 실제 발송 금지
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_sms_settings_untouched(self):
        self.assertEqual(config.SMS_BYTE_LIMIT, 90)
        self.assertEqual(len(config.SMS_TEMPLATES), 3)
        self.assertEqual(config.N8N_SMS_TIMEOUT, 10.0)

    def test_transaction_api_still_works(self):
        with self._serve(SAMPLE):
            data = self.client.get("/thejo/api/transactions/TX-202609-018").get_json()
        self.assertEqual(data["transaction"]["customer_name"], "정○현")
        self.assertEqual(len(data["templates"]), 3)

    def test_sms_send_still_works(self):
        with self._serve(SAMPLE):
            res = self.client.post("/thejo/api/sms/send", json={
                "transaction_id": "TX-202609-018",
                "template_id": "PLAN_MAINTENANCE",
                "message": "테스트",
            })
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()["success"])

    def test_simulate_still_works(self):
        with self._serve(SAMPLE):
            data = self.client.get("/thejo/api/simulate?units=9").get_json()
        self.assertEqual(data["benefit_budget"], 400_000)

    def test_acknowledge_still_works(self):
        with self._serve(SAMPLE):
            res = self.client.post("/thejo/warnings/w-1/ack",
                                   headers={"Accept": "application/json"})
        self.assertEqual(res.status_code, 200)

    def test_sms_modal_still_present(self):
        with self._serve(SAMPLE):
            html = self.client.get("/thejo/warnings").get_data(as_text=True)
        self.assertIn('id="sms-dialog"', html)
        self.assertIn("유지조건 안내", html)

    def test_filters_still_registered(self):
        self.assertIn("won", app.jinja_env.filters)
        self.assertIn("manwon", app.jinja_env.filters)

    def test_command_center_home_still_links_to_thejo(self):
        html = self.client.get("/").get_data(as_text=True)
        self.assertIn('href="/thejo/"', html)


if __name__ == "__main__":
    unittest.main()
