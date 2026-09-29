"""인센티브 구간 계산.

순수 함수만 둔다. 같은 입력이면 항상 같은 결과가 나오고, 외부 호출(LLM·네트워크·시계)을 하지 않는다.
"""
from thejo_project.config import INCENTIVE_TIERS, MINIMUM_SECURED_PROFIT


def _sorted_tiers(tiers=None):
    return sorted(tiers if tiers is not None else INCENTIVE_TIERS, key=lambda t: t["min_units"])


def tier_for(units, tiers=None):
    """판매량 units 가 속한 구간을 돌려준다. 어느 구간에도 없으면 None."""
    for tier in _sorted_tiers(tiers):
        upper = tier["max_units"]
        if units >= tier["min_units"] and (upper is None or units <= upper):
            return tier
    return None


def per_unit_incentive(units, tiers=None):
    """현재 판매량 기준 건당 인센티브(원)."""
    tier = tier_for(units, tiers)
    return tier["per_unit"] if tier else 0


def calculate_monthly_incentive(units, tiers=None):
    """이번 달 예상 총인센티브(원).

    구간 단가는 소급 적용된다. 10건이면 10건 전부에 20만 원이 붙어 200만 원이 된다.
    """
    if units <= 0:
        return 0
    return units * per_unit_incentive(units, tiers)


def next_tier(units, tiers=None):
    """다음 상위 구간. 이미 최상위면 None."""
    for tier in _sorted_tiers(tiers):
        if tier["min_units"] > units:
            return tier
    return None


def units_to_next_tier(units, tiers=None):
    """다음 구간까지 남은 판매 건수. 다음 구간이 없으면 0."""
    tier = next_tier(units, tiers)
    return tier["min_units"] - units if tier else 0


def calculate_next_tier_gain(units, tiers=None):
    """다음 구간을 달성했을 때 **늘어나는 총인센티브**(원).

    9건(90만) → 10건(200만) 이면 110만 원.
    """
    tier = next_tier(units, tiers)
    if not tier:
        return 0
    return calculate_monthly_incentive(tier["min_units"], tiers) - calculate_monthly_incentive(units, tiers)


def calculate_available_benefit_budget(units, minimum_secured_profit=None, tiers=None):
    """고객 혜택으로 쓸 수 있는 금액(원) = 구간 달성 증가분 - 최소 확보 수익. 음수면 0."""
    floor = MINIMUM_SECURED_PROFIT if minimum_secured_profit is None else minimum_secured_profit
    return max(0, calculate_next_tier_gain(units, tiers) - floor)
