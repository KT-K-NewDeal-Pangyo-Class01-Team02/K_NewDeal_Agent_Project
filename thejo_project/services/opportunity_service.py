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
    """혜택 시뮬레이션: 판매량을 바꿔 보면 금액이 어떻게 달라지는지."""
    floor = MINIMUM_SECURED_PROFIT if minimum_secured_profit is None else minimum_secured_profit
    tier = next_tier(units)
    return {
        "units": units,
        "per_unit": per_unit_incentive(units),
        "monthly_incentive": calculate_monthly_incentive(units),
        "units_needed": units_to_next_tier(units),
        "next_tier_units": tier["min_units"] if tier else None,
        "next_per_unit": tier["per_unit"] if tier else None,
        "tier_gain": calculate_next_tier_gain(units),
        "minimum_secured_profit": floor,
        "benefit_budget": calculate_available_benefit_budget(units, floor),
    }


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
