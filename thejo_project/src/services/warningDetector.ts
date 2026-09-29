import type {
  DealCalculation,
  PolicySet,
  RiskWarning,
  SaleRecord,
  SettlementRecord,
  WarningSeverity,
} from '../types/incentive';
import { calculateSettlementDifference, indexSettlements } from './incentiveCalculator';
import { formatWon } from '../utils/format';

/**
 * 손실 위험 탐지.
 *
 * 환수 위험 / 정산 금액 불일치 / 최소 마진 미달 세 가지를 찾아
 * 사장님이 바로 읽을 수 있는 문장으로 만들어 반환한다.
 */

const severityWeight: Record<WarningSeverity, number> = {
  critical: 0,
  warning: 1,
  info: 2,
};

/** 정산 차액이 이 금액을 넘어서면 확인이 필요하다고 본다. */
const SETTLEMENT_GAP_THRESHOLD = 10_000;

/** 요금제 유지조건 미충족으로 인한 환수 위험. */
function detectClawbackRisks(
  sales: SaleRecord[],
  deals: DealCalculation[],
  policies: PolicySet,
): RiskWarning[] {
  const dealById = new Map(deals.map((deal) => [deal.saleId, deal]));
  const { requiredRetentionDays } = policies.retention;

  return sales
    .filter(
      (sale) =>
        sale.planChangedAfterDays !== null &&
        sale.planChangedAfterDays < requiredRetentionDays,
    )
    .map((sale) => {
      const deal = dealById.get(sale.id);
      const clawback = deal?.expectedClawback ?? policies.retention.clawbackAmount;
      const keptDays = sale.planChangedAfterDays ?? 0;

      return {
        id: `WARN-CLAWBACK-${sale.id}`,
        saleId: sale.id,
        maskedCustomer: sale.maskedCustomer,
        category: 'clawback',
        severity: 'critical',
        title: '요금제 유지조건을 확인하세요',
        reason: `개통 후 ${keptDays}일 만에 요금제가 변경되었습니다. 정책상 ${requiredRetentionDays}일 유지가 필요합니다.`,
        estimatedLoss: clawback,
        recommendedAction: '요금제 변경 이력과 실제 환수 반영 여부를 확인하세요.',
        calculation: [
          { label: '정책 유지 기간', expression: `${requiredRetentionDays}일` },
          { label: '실제 유지 기간', expression: `${keptDays}일` },
          {
            label: '미달 기간',
            expression: `${requiredRetentionDays}일 - ${keptDays}일 = ${requiredRetentionDays - keptDays}일`,
          },
          { label: '예상 환수액', expression: formatWon(clawback) },
          {
            label: '환수 반영 후 마진',
            expression: `${formatWon(deal?.contractMargin ?? 0)} - ${formatWon(clawback)} = ${formatWon(deal?.netMargin ?? 0)}`,
          },
        ],
      } satisfies RiskWarning;
    });
}

/** 예상 인센티브보다 적게 정산된 거래. */
function detectSettlementGaps(
  sales: SaleRecord[],
  settlements: SettlementRecord[],
): RiskWarning[] {
  const settlementBySaleId = indexSettlements(settlements);

  return sales.flatMap((sale) => {
    const settlement = settlementBySaleId.get(sale.id);
    if (!settlement) return [];

    const difference = calculateSettlementDifference(
      sale.baseIncentive,
      settlement.actualPayout,
    );
    if (difference >= -SETTLEMENT_GAP_THRESHOLD) return [];

    const shortfall = Math.abs(difference);

    return [
      {
        id: `WARN-SETTLEMENT-${sale.id}`,
        saleId: sale.id,
        maskedCustomer: sale.maskedCustomer,
        category: 'settlement-gap',
        severity: 'warning',
        title: `예상보다 ${formatWon(shortfall)} 적게 정산되었습니다`,
        reason: `예상 지급액은 ${formatWon(sale.baseIncentive)}인데 실제 지급액은 ${formatWon(settlement.actualPayout)}입니다.`,
        estimatedLoss: shortfall,
        recommendedAction: '정산서의 조정 사유와 거래 조건을 확인하세요.',
        calculation: [
          { label: '예상 지급액', expression: formatWon(sale.baseIncentive) },
          { label: '실제 지급액', expression: formatWon(settlement.actualPayout) },
          {
            label: '차액',
            expression: `${formatWon(settlement.actualPayout)} - ${formatWon(sale.baseIncentive)} = -${formatWon(shortfall)}`,
          },
          {
            label: '정산서 조정 사유',
            expression: settlement.adjustmentNote ?? '기재 없음',
          },
        ],
      } satisfies RiskWarning,
    ];
  });
}

/** 고객 혜택을 차감하고 나면 최소 마진에 못 미치는 거래. */
function detectLowMargins(
  deals: DealCalculation[],
  policies: PolicySet,
): RiskWarning[] {
  const threshold = policies.margin.minimumMarginPerDeal;

  return deals
    .filter((deal) => deal.contractMargin < threshold)
    .map((deal) => {
      const shortfall = threshold - deal.contractMargin;

      return {
        id: `WARN-MARGIN-${deal.saleId}`,
        saleId: deal.saleId,
        maskedCustomer: deal.maskedCustomer,
        category: 'low-margin',
        severity: 'info',
        title: '고객 혜택 차감 후 최소 마진에 미달합니다',
        reason: `최소 마진 기준 ${formatWon(threshold)}보다 ${formatWon(shortfall)} 부족합니다.`,
        estimatedLoss: shortfall,
        recommendedAction: '최종 지급 혜택과 매장 부담 비용을 확인하세요.',
        calculation: [
          { label: '예상 개통 인센티브', expression: formatWon(deal.baseIncentive) },
          { label: '구간 인센티브(건당)', expression: `+ ${formatWon(deal.volumeIncentive)}` },
          { label: '고객 혜택', expression: `- ${formatWon(deal.customerBenefit)}` },
          { label: '매장 부담 비용', expression: `- ${formatWon(deal.storeCost)}` },
          { label: '실제 마진', expression: formatWon(deal.contractMargin) },
          { label: '최소 마진 기준', expression: formatWon(threshold) },
          {
            label: '부족 금액',
            expression: `${formatWon(threshold)} - ${formatWon(deal.contractMargin)} = ${formatWon(shortfall)}`,
          },
        ],
      } satisfies RiskWarning;
    });
}

/**
 * 세 가지 위험을 모두 탐지한 뒤 위험도 순서로 정렬한다.
 * 위험도가 같으면 예상 손실 금액이 큰 거래를 앞에 둔다.
 */
export function detectWarnings(
  sales: SaleRecord[],
  settlements: SettlementRecord[],
  deals: DealCalculation[],
  policies: PolicySet,
): RiskWarning[] {
  return [
    ...detectClawbackRisks(sales, deals, policies),
    ...detectSettlementGaps(sales, settlements),
    ...detectLowMargins(deals, policies),
  ].sort((a, b) => {
    const bySeverity = severityWeight[a.severity] - severityWeight[b.severity];
    return bySeverity !== 0 ? bySeverity : b.estimatedLoss - a.estimatedLoss;
  });
}
