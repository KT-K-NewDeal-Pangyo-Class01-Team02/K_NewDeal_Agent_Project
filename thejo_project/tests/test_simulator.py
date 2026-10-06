"""추가 수익 기회 카드 ↔ 혜택 시뮬레이션 연결 테스트.

외부 호출(n8n)은 전부 mock 한다. 카드 데이터는 2026-10-06 실제 시트 값과 같게 맞춰 두었다.
저장소 루트에서:  python -m unittest thejo_project.tests.test_simulator -v
"""
import re
import unittest
from unittest import mock

from flask import url_for

from command_center.app import app
from thejo_project import config
from thejo_project.data import insight_data, sms_store
from thejo_project.tests.test_insights import InsightBase


def _opp(insight_id, device, plan, current, needed, amount, target):
    return {
        "insight_id": insight_id, "report_date": "2026-10-06", "category": "추가 수익 기회",
        "severity": "기회", "device_model_name": device, "plan_code": plan,
        "transaction_id": "", "customer_name_masked": "", "current_sales": current,
        "additional_sales_needed": needed, "amount": amount,
        "reason": f"{needed}건 추가 판매 시 {target}건 구간에 도달합니다.",
        "created_at": "2026-10-06 09:00:00",
    }


# (id, 단말, 요금제, 현재, 추가, amount, 목표, 기대 혜택 가능액, 최소수익 미달?)
CARDS = [
    ("OPP-2026-10-06-갤럭시 S26-PLAN-LITE-1", "갤럭시 S26", "PLAN-LITE", 7, 3, 1_430_000, 10, 730_000, False),
    ("OPP-2026-10-06-갤럭시 Z Fold8-PLAN-PREMIUM-1", "갤럭시 Z Fold8", "PLAN-PREMIUM", 1, 2, 770_000, 3, 70_000, False),
    ("OPP-2026-10-06-아이폰 17 Pro 256GB-PLAN-PREMIUM-1", "아이폰 17 Pro 256GB", "PLAN-PREMIUM", 1, 4, 600_000, 5, 0, True),
    ("OPP-2026-10-06-갤럭시 S26-PLAN-PREMIUM-1", "갤럭시 S26", "PLAN-PREMIUM", 1, 4, 560_000, 5, 0, True),
]
SAMPLE = [_opp(c[0], c[1], c[2], c[3], c[4], c[5], c[6]) for c in CARDS]
FLOOR = 700_000


def _input_value(html):
    """시뮬레이터 '이번 달 판매 건수' 입력란의 초기값."""
    m = re.search(r'name="units"[^>]*?value="(\d+)"', html)
    return int(m.group(1)) if m else None


def _sim_section(html):
    return html[html.index('id="simulator"'):]


class SimulatorBase(InsightBase):
    def setUp(self):
        super().setUp()
        sms_store.clear()
        self.addCleanup(sms_store.clear)
        app.config["TESTING"] = True
        self.client = app.test_client()
        serve = mock.patch.object(insight_data, "_get_json", return_value=SAMPLE)
        serve.start()
        self.addCleanup(serve.stop)

    def page(self, insight_id=None):
        path = "/thejo/opportunities"
        if insight_id is not None:
            with app.test_request_context():
                path = url_for("thejo.opportunities", insight=insight_id)
        res = self.client.get(path)
        self.assertEqual(res.status_code, 200)
        return res.get_data(as_text=True)

    def api(self, **params):
        return self.client.get("/thejo/api/simulate", query_string=params)


class CardToSimulatorTest(SimulatorBase):
    """1·2·3번 검증: 카드를 고르면 그 카드 값으로 시뮬레이터가 시작한다."""

    def test_each_card_starts_with_its_own_values(self):
        for cid, device, plan, current, needed, amount, target, budget, short in CARDS:
            with self.subTest(card=f"{device} / {plan}"):
                html = self.page(cid)
                sim = _sim_section(html)
                self.assertEqual(_input_value(html), current)            # 판매 건수 초기값
                self.assertIn(f"{device} · {plan}", sim)                 # 단말·요금제 표시
                self.assertIn(f'data-insight-id="{cid}"', sim)           # 선택 상태
                self.assertRegex(sim, rf'data-sim="units">{current}<')
                self.assertRegex(sim, rf'data-sim="units_needed">{needed}<')
                self.assertRegex(sim, rf'data-sim="target_units">{target}<')
                self.assertIn(f"{amount:,}원", sim)
                self.assertIn(f"{budget:,}원", sim)

    def test_cards_do_not_share_values(self):
        """첫 카드 값이나 데모 9가 모든 카드에 쓰이면 안 된다."""
        starts = [_input_value(self.page(c[0])) for c in CARDS]
        self.assertEqual(starts, [7, 1, 1, 1])
        self.assertNotIn(9, starts)
        titles = []
        for c in CARDS:
            sim = _sim_section(self.page(c[0]))
            titles.append(re.search(r'data-sim="title">([^<]+)<', sim).group(1))
        self.assertEqual(len(set(titles)), 4)

    def test_selected_card_is_marked(self):
        html = self.page(CARDS[1][0])
        selected = re.findall(r'tj-insight is-selected"\s+data-insight-card="([^"]+)"', html)
        self.assertEqual(selected, [CARDS[1][0]])

    def test_every_card_button_carries_its_own_data(self):
        html = self.page()
        with app.test_request_context():
            for cid, device, plan, current, *_ in CARDS:
                with self.subTest(card=cid):
                    href = url_for("thejo.opportunities", insight=cid) + "#simulator"
                    m = re.search(
                        rf'href="{re.escape(href)}"\s+data-sim-pick\s+data-insight-id="{re.escape(cid)}"'
                        rf'\s+data-device="{re.escape(device)}"\s+data-plan="{re.escape(plan)}"'
                        rf'\s+data-current="{current}"', html)
                    self.assertIsNotNone(m, "카드 버튼에 자기 데이터가 없음")

    def test_dashboard_cards_link_with_their_id(self):
        html = self.client.get("/thejo/").get_data(as_text=True)
        with app.test_request_context():
            for cid, *_ in CARDS:
                self.assertIn(url_for("thejo.opportunities", insight=cid) + "#simulator", html)

    def test_no_selection_uses_first_card_not_demo(self):
        html = self.page()
        self.assertEqual(_input_value(html), 7)
        self.assertNotIn("기본 인센티브 정책 기준", _sim_section(html).split("상세 계산 정보")[0])

    def test_stale_id_falls_back_with_notice(self):
        html = self.page("OPP-없는-기회")
        self.assertEqual(_input_value(html), 7)
        self.assertIn("선택한 기회가 최신 데이터에 없어", html)


class CalculationTest(SimulatorBase):
    """4·5번 검증: 서버 계산 + 계산식."""

    def test_api_with_insight_id(self):
        for cid, device, plan, current, needed, amount, target, budget, short in CARDS:
            with self.subTest(card=cid):
                data = self.api(units=current, insight_id=cid).get_json()
                self.assertEqual(data["basis"], "insight")
                self.assertEqual(data["device_model_name"], device)
                self.assertEqual(data["plan_code"], plan)
                self.assertEqual(data["report_date"], "2026-10-06")
                self.assertEqual(data["units"], current)
                self.assertEqual(data["units_needed"], needed)
                self.assertEqual(data["target_units"], target)
                self.assertEqual(data["tier_gain"], amount)
                self.assertEqual(data["minimum_secured_profit"], FLOOR)
                self.assertEqual(data["benefit_budget"], budget)
                self.assertEqual(data["shortfall"], short)

    def test_formula_is_gain_minus_floor_never_negative(self):
        for cid, _, _, current, _, amount, *_ in CARDS:
            data = self.api(units=current, insight_id=cid).get_json()
            self.assertEqual(data["benefit_budget"], max(amount - FLOOR, 0))
            self.assertGreaterEqual(data["benefit_budget"], 0)

    def test_api_with_device_and_plan_only(self):
        data = self.api(units=7, device_model_name="갤럭시 S26", plan_code="PLAN-LITE").get_json()
        self.assertEqual(data["basis"], "insight")
        self.assertEqual(data["benefit_budget"], 730_000)

    def test_same_device_different_plan_is_not_mixed(self):
        """같은 갤럭시 S26 이라도 요금제가 다르면 다른 기회다."""
        lite = self.api(units=7, device_model_name="갤럭시 S26", plan_code="PLAN-LITE").get_json()
        prem = self.api(units=1, device_model_name="갤럭시 S26", plan_code="PLAN-PREMIUM").get_json()
        self.assertEqual(lite["tier_gain"], 1_430_000)
        self.assertEqual(prem["tier_gain"], 560_000)

    def test_mismatched_device_is_rejected(self):
        res = self.api(units=7, insight_id=CARDS[0][0], device_model_name="갤럭시 Z Fold8")
        self.assertEqual(res.status_code, 409)

    def test_unknown_insight_is_404(self):
        self.assertEqual(self.api(units=7, insight_id="OPP-없음").status_code, 404)

    def test_explanation_sentence(self):
        data = self.api(units=7, insight_id=CARDS[0][0]).get_json()
        self.assertEqual(
            data["explanation"],
            "목표 구간을 달성하면 1,430,000원의 수익이 증가합니다. "
            "이 중 최소 700,000원을 매장 수익으로 확보하고, 최대 730,000원을 고객 혜택으로 활용할 수 있습니다.",
        )

    def test_shortfall_warning_on_screen(self):
        ok = _sim_section(self.page(CARDS[0][0]))
        short = _sim_section(self.page(CARDS[2][0]))
        warn = "최소 확보 수익을 충족하지 못해 고객 혜택으로 활용할 수 있는 금액이 없습니다."
        self.assertRegex(ok, r"data-sim-warn\s+hidden")
        self.assertNotRegex(short, r"data-sim-warn\s+hidden")
        self.assertIn(warn, short)
        self.assertNotIn("-100,000원", short)   # 음수를 표시하지 않는다

    def test_sheet_has_no_per_unit_so_it_is_not_invented(self):
        data = self.api(units=7, insight_id=CARDS[0][0]).get_json()
        self.assertIsNone(data["per_unit"])
        self.assertIsNone(data["monthly_incentive"])
        sim = _sim_section(self.page(CARDS[0][0]))
        self.assertRegex(sim, r'data-sim-row="per_unit"\s+hidden')


class ManualEditTest(SimulatorBase):
    """6번 검증: 판매 건수를 직접 바꿔 계산하는 기존 기능."""

    def test_changed_units_keeps_device_and_flags_default_policy(self):
        data = self.api(units=8, insight_id=CARDS[0][0]).get_json()
        self.assertEqual(data["basis"], "default")
        self.assertEqual(data["units"], 8)
        self.assertEqual(data["device_model_name"], "갤럭시 S26")    # 단말·요금제 표시는 유지
        self.assertEqual(data["plan_code"], "PLAN-LITE")
        self.assertIn("기본 인센티브 정책", data["note"])
        self.assertEqual(data["benefit_budget"], max(data["tier_gain"] - FLOOR, 0))

    def test_changing_back_returns_to_sheet_values(self):
        self.api(units=8, insight_id=CARDS[0][0])
        data = self.api(units=7, insight_id=CARDS[0][0]).get_json()
        self.assertEqual(data["basis"], "insight")
        self.assertEqual(data["benefit_budget"], 730_000)

    def test_plain_simulate_still_works(self):
        data = self.api(units=9).get_json()
        self.assertEqual(data["basis"], "default")
        self.assertEqual(data["tier_gain"], 1_100_000)
        self.assertEqual(data["benefit_budget"], 400_000)
        for key in ("units", "per_unit", "monthly_incentive", "units_needed",
                    "next_tier_units", "next_per_unit", "tier_gain",
                    "minimum_secured_profit", "benefit_budget"):
            self.assertIn(key, data)   # 기존 응답 키 유지

    def test_bad_units_still_rejected(self):
        self.assertEqual(self.api(units="abc", insight_id=CARDS[0][0]).status_code, 400)
        self.assertEqual(self.api(units=-1).status_code, 400)


class DemoFallbackTest(SimulatorBase):
    """n8n 데이터가 없을 때는 기존 데모 시뮬레이터 그대로."""

    def test_demo_simulator_unchanged(self):
        with mock.patch.object(config, "N8N_INSIGHTS_WEBHOOK_URL", ""):
            html = self.page()
        sim = _sim_section(html)
        self.assertEqual(_input_value(html), 9)
        self.assertIn("기본 인센티브 정책", sim)
        self.assertIn("1,100,000원", sim)
        self.assertIn("400,000원", sim)
        # 데모 카드에는 카드 선택 버튼이 없다 (data-sim-pick-box 는 시뮬레이터 자체라 제외)
        self.assertIsNone(re.search(r"data-sim-pick(?!-)", html))

    def test_demo_explanation(self):
        with mock.patch.object(config, "N8N_INSIGHTS_WEBHOOK_URL", ""):
            data = self.api(units=9).get_json()
        self.assertIn("1,100,000원의 수익이 증가합니다", data["explanation"])
        self.assertIn("최대 400,000원", data["explanation"])


if __name__ == "__main__":
    unittest.main()
