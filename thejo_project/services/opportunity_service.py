"""놓치고 있는 수익 기회 + 대시보드 요약.

금액은 전부 incentive_service 가 계산한다. 화면에는 하드코딩된 숫자가 없다.
"""
from thejo_project.config import MINIMUM_SECURED_PROFIT
from thejo_project.data import demo_data
from thejo_project.services import warning_service
from thejo_project.services.incentive_service import (
    calculate_available_benefit_budget,
    calculate_monthly_incentive,
    calculate_next_tier_gain,
    next_tier,
    per_unit_incentive,
    units_to_next_tier,
)


def get_profit_opportunities(units=None):
    """지금 활용할 수 있는 추가 수익 기회 목록."""
    if units is None:
        units = demo_data.get_sales_snapshot()["units_sold"]

    opportunities = []
    for raw in demo_data.get_opportunities():
        if raw["kind"] != "tier_upgrade":
            continue
        tier = next_tier(units)
        if not tier:
            continue
        opportunities.append(
            {
                **raw,
                "current_units": units,
                "next_tier_units": tier["min_units"],
                "units_needed": units_to_next_tier(units),
                "current_per_unit": per_unit_incentive(units),
                "next_per_unit": tier["per_unit"],
                "tier_gain": calculate_next_tier_gain(units),
                "minimum_secured_profit": MINIMUM_SECURED_PROFIT,
                "benefit_budget": calculate_available_benefit_budget(units),
            }
        )
    return opportunities


def simulate_benefit(units, minimum_secured_profit=None):
    """혜택 시뮬레이션 (기본 인센티브 정책 기준): 판매량을 바꿔 보면 금액이 어떻게 달라지는지."""
    return _finish(_default_simulation(units, minimum_secured_profit))


def simulate_insight(row, report_date=None):
    """혜택 시뮬레이션 (Google Sheets 인사이트 기준).

    시트에는 단말·요금제별 정책 표가 없고, n8n 이 그 정책으로 계산한 `amount`(구간 달성 증가액)만 있다.
    그래서 카드의 현재 판매량 그대로일 때만 이 값을 쓴다. 건당·총 인센티브는 시트에 없으므로 만들지 않는다(None).
    """
    current = row["current_sales"]
    needed = row["additional_sales_needed"]
    target = current + needed if needed > 0 else None
    gain = row["amount"]
    floor = MINIMUM_SECURED_PROFIT
    return _finish({
        "basis": "insight",
        "report_date": report_date,
        "insight_id": row["insight_id"],
        "device_model_name": row["device_model_name"],
        "plan_code": row["plan_code"],
        "reason": row["reason"] or None,
        "note": None,
        "units": current,
        "units_needed": needed,
        "target_units": target,
        "next_tier_units": target,
        "tier_gain": gain,
        "minimum_secured_profit": floor,
        "benefit_budget": max(0, gain - floor),
        "per_unit": None,
        "next_per_unit": None,
        "monthly_incentive": None,
    })


def simulate(units, row=None, report_date=None):
    """시뮬레이션 API 의 진입점.

    - 기회(row)를 고르지 않았으면 기본 정책으로 계산한다.
    - 골랐고 판매량이 카드 그대로면 시트 값(단말·요금제 정책 결과)으로 계산한다.
    - 골랐는데 판매량을 바꿨으면, 그 판매량에 대한 단말·요금제 정책 정보가 시트에 없으므로
      기본 정책으로 계산하고 그 사실을 note 로 알린다. 단말·요금제 표시는 유지한다.
    """
    if row is None:
        return simulate_benefit(units)
    if units == row["current_sales"]:
        return simulate_insight(row, report_date)

    sim = _default_simulation(units)
    sim.update({
        "report_date": report_date,
        "insight_id": row["insight_id"],
        "device_model_name": row["device_model_name"],
        "plan_code": row["plan_code"],
        "note": (
            f"입력한 {units}건은 시트의 현재 판매량({row['current_sales']}건)과 달라 "
            "단말·요금제별 정책 정보가 없습니다. 기본 인센티브 정책으로 계산했습니다."
        ),
    })
    return _finish(sim)


def _default_simulation(units, minimum_secured_profit=None):
    floor = MINIMUM_SECURED_PROFIT if minimum_secured_profit is None else minimum_secured_profit
    tier = next_tier(units)
    return {
        "basis": "default",
        "report_date": None,
        "insight_id": None,
        "device_model_name": None,
        "plan_code": None,
        "reason": None,
        "note": None,
        "units": units,
        "per_unit": per_unit_incentive(units),
        "monthly_incentive": calculate_monthly_incentive(units),
        "units_needed": units_to_next_tier(units),
        "target_units": tier["min_units"] if tier else None,
        "next_tier_units": tier["min_units"] if tier else None,
        "next_per_unit": tier["per_unit"] if tier else None,
        "tier_gain": calculate_next_tier_gain(units),
        "minimum_secured_profit": floor,
        "benefit_budget": calculate_available_benefit_budget(units, floor),
    }


def _finish(sim):
    """화면 문구·경고 여부를 붙인다. 금액은 이미 계산된 값을 그대로 쓴다(새로 계산하지 않는다)."""
    gain = sim["tier_gain"]
    floor = sim["minimum_secured_profit"]
    budget = sim["benefit_budget"]
    has_next = bool(sim.get("target_units")) and sim.get("units_needed", 0) > 0

    sim["has_next_tier"] = has_next
    # 증가액이 최소 확보 수익보다 작으면 고객 혜택으로 쓸 돈이 없다 (음수는 표시하지 않는다)
    sim["shortfall"] = has_next and gain < floor
    sim["units_needed_text"] = f"{sim['units_needed']}건" if has_next else "최상위 구간"

    parts = [p for p in (sim.get("device_model_name"), sim.get("plan_code")) if p]
    sim["title"] = " · ".join(parts) if parts else "기본 인센티브 정책"
    if sim["basis"] == "insight":
        date = sim.get("report_date")
        sim["basis_label"] = f"Google Sheets 인사이트 기준 · {date}" if date else "Google Sheets 인사이트 기준"
    else:
        sim["basis_label"] = "기본 인센티브 정책 기준"

    if not has_next:
        sim["explanation"] = "이미 최상위 구간이라 추가로 올릴 구간이 없습니다."
    elif sim["shortfall"]:
        sim["explanation"] = (
            f"목표 구간을 달성하면 {gain:,}원의 수익이 증가하지만, "
            f"최소 확보 수익 {floor:,}원에 미치지 못합니다."
        )
    else:
        sim["explanation"] = (
            f"목표 구간을 달성하면 {gain:,}원의 수익이 증가합니다. "
            f"이 중 최소 {floor:,}원을 매장 수익으로 확보하고, "
            f"최대 {budget:,}원을 고객 혜택으로 활용할 수 있습니다."
        )
    return sim


def get_dashboard_summary():
    """대시보드 상단 요약 카드 6개의 값."""
    units = demo_data.get_sales_snapshot()["units_sold"]
    monthly_incentive = calculate_monthly_incentive(units)
    clawback = warning_service.total_expected_loss(kind="clawback")
    risk_exposure = warning_service.total_expected_loss()

    return {
        "units_sold": units,
        "monthly_incentive": monthly_incentive,
        "expected_clawback": clawback,
        # 예상 마진 = 예상 인센티브 - 아직 조치하지 않은 위험 노출액 전체
        "estimated_margin": monthly_incentive - risk_exposure,
        "risk_exposure": risk_exposure,
        "units_to_next_tier": units_to_next_tier(units),
        "benefit_budget": calculate_available_benefit_budget(units),
        "tier_gain": calculate_next_tier_gain(units),
        "minimum_secured_profit": MINIMUM_SECURED_PROFIT,
    }
