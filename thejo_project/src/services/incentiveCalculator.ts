import type {
  DealCalculation,
  IncentiveTier,
  PolicySet,
  SaleRecord,
  SettlementRecord,
  TierIncentivePolicy,
} from '../types/incentive';

/**
 * 금액 계산 전담 모듈.
 * UI와 완전히 분리된 순수 함수로만 구성하며, 외부 상태를 읽거나 바꾸지 않는다.
 */

/** 판매량이 속한 구간을 찾는다. 구간이 없으면 null. */
export function findTierForCount(
  tiers: IncentiveTier[],
  count: number,
): IncentiveTier | null {
  if (count <= 0) return null;
  return (
    tiers.find((tier) => {
      const upper = tier.maxCount ?? Number.POSITIVE_INFINITY;
      return count >= tier.minCount && count <= upper;
    }) ?? null
  );
}

/** 현재 판매량 기준으로 다음 구간을 찾는다. 최상위 구간이면 null. */
export function findNextTier(
  tiers: IncentiveTier[],
  count: number,
): IncentiveTier | null {
  const upcoming = tiers
    .filter((tier) => tier.minCount > count)
    .sort((a, b) => a.minCount - b.minCount);
  return upcoming[0] ?? null;
}

/**
 * 월간 판매량에 대한 구간형 인센티브 총액.
 *
 * - retroactive:  달성 구간 단가를 당월 전체 거래에 소급 적용
 * - incremental:  구간별로 해당 구간에 속한 건수에만 그 구간 단가를 적용
 * - lump-sum:     기본 단가로 전 건수를 계산한 뒤 달성 구간의 보너스를 더함
 */
export function calculateVolumeIncentive(
  policy: TierIncentivePolicy,
  count: number,
): number {
  if (count <= 0) return 0;

  if (policy.rewardType === 'retroactive') {
    const tier = findTierForCount(policy.tiers, count);
    return count * (tier?.perUnitIncentive ?? 0);
  }

  if (policy.rewardType === 'incremental') {
    return policy.tiers.reduce((total, tier) => {
      const upper = tier.maxCount ?? Number.POSITIVE_INFINITY;
      const unitsInTier = Math.max(0, Math.min(count, upper) - tier.minCount + 1);
      return total + unitsInTier * tier.perUnitIncentive;
    }, 0);
  }

  // lump-sum
  const baseTier = policy.tiers[0];
  const bonus = policy.tiers
    .filter((tier) => count >= tier.minCount)
    .reduce((sum, tier) => sum + (tier.lumpSumBonus ?? 0), 0);
  return count * (baseTier?.perUnitIncentive ?? 0) + bonus;
}

/** 현재 판매량에서 거래 한 건에 배분되는 구간 인센티브 단가. */
export function currentUnitIncentive(
  policy: TierIncentivePolicy,
  count: number,
): number {
  const tier = findTierForCount(policy.tiers, count);
  return tier?.perUnitIncentive ?? 0;
}

/** 요금제 유지조건 위반 시 예상되는 환수 금액. */
export function calculateExpectedClawback(
  sale: SaleRecord,
  policies: PolicySet,
): number {
  const { planChangedAfterDays } = sale;
  if (planChangedAfterDays === null) return 0;
  if (planChangedAfterDays >= policies.retention.requiredRetentionDays) return 0;
  return policies.retention.clawbackAmount;
}

/**
 * 거래 한 건의 마진.
 *
 *   예상 마진 = 예상 인센티브 - 고객 혜택 - 매장 부담 비용 - 예상 환수 금액
 *
 * contractMargin은 환수 반영 전 값으로, 최소 마진 기준 판정에 사용한다.
 */
export function calculateDealMargin(
  sale: SaleRecord,
  policies: PolicySet,
  unitVolumeIncentive: number,
): DealCalculation {
  const expectedClawback = calculateExpectedClawback(sale, policies);
  const contractMargin =
    sale.baseIncentive + unitVolumeIncentive - sale.customerBenefit - sale.storeCost;

  return {
    saleId: sale.id,
    soldAt: sale.soldAt,
    maskedCustomer: sale.maskedCustomer,
    device: sale.device,
    planName: sale.planName,
    baseIncentive: sale.baseIncentive,
    volumeIncentive: unitVolumeIncentive,
    customerBenefit: sale.customerBenefit,
    storeCost: sale.storeCost,
    expectedClawback,
    contractMargin,
    netMargin: contractMargin - expectedClawback,
  };
}

/** 월 전체 거래의 마진 계산 결과. */
export function calculateDealMargins(
  sales: SaleRecord[],
  policies: PolicySet,
): DealCalculation[] {
  const unit = currentUnitIncentive(policies.tierIncentive, sales.length);
  return sales.map((sale) => calculateDealMargin(sale, policies, unit));
}

/** 월간 예상 순마진 합계. */
export function calculateMonthlyNetMargin(deals: DealCalculation[]): number {
  return deals.reduce((sum, deal) => sum + deal.netMargin, 0);
}

/**
 * 정산 차액 = 실제 정산액 - 예상 인센티브.
 * 음수이면 받아야 할 금액보다 적게 지급된 것이다.
 */
export function calculateSettlementDifference(
  expectedIncentive: number,
  actualPayout: number,
): number {
  return actualPayout - expectedIncentive;
}

/** saleId로 정산 내역을 빠르게 찾기 위한 인덱스. */
export function indexSettlements(
  settlements: SettlementRecord[],
): Map<string, SettlementRecord> {
  return new Map(settlements.map((record) => [record.saleId, record]));
}
