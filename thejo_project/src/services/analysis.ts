import type {
  AnalysisResult,
  PolicySet,
  RiskWarning,
  SaleRecord,
  SettlementComparisonRow,
  SettlementRecord,
  SettlementStatus,
} from '../types/incentive';
import { demoPolicySet } from '../data/policies';
import { currentMonthLabel, currentMonthSales, monthlySalesHistory } from '../data/sales';
import { currentMonthSettlements } from '../data/settlements';
import {
  calculateDealMargins,
  calculateMonthlyNetMargin,
  calculateSettlementDifference,
  indexSettlements,
} from './incentiveCalculator';
import { detectWarnings } from './warningDetector';
import { detectProfitOpportunity } from './opportunityDetector';

/**
 * 자동 분석 파이프라인.
 *
 *   판매정책과 환수 조건 불러오기
 *   → 기존 판매일보 데이터 불러오기
 *   → 실제 정산 데이터 불러오기
 *   → 필수 데이터 검증
 *   → 거래별 예상 인센티브와 마진 계산
 *   → 월간 판매량과 마진 누적
 *   → 예상 정산액과 실제 정산액 비교
 *   → 환수·정산 불일치·최소 마진 미달 탐지
 *   → 다음 인센티브 구간과 추가 수익 계산
 *   → Warning과 수익 기회를 우선순위별로 표시
 */

/** 계산 전에 데이터가 쓸 만한 상태인지 확인한다. */
export function validateInputs(
  policies: PolicySet,
  sales: SaleRecord[],
  settlements: SettlementRecord[],
): string[] {
  const issues: string[] = [];

  if (policies.tierIncentive.tiers.length === 0) {
    issues.push('구간형 인센티브 정책에 구간이 정의되어 있지 않습니다.');
  }
  if (sales.length === 0) {
    issues.push('이번 달 판매일보 데이터가 없습니다.');
  }

  const settledIds = new Set(settlements.map((record) => record.saleId));
  const missing = sales.filter((sale) => !settledIds.has(sale.id));
  if (missing.length > 0) {
    issues.push(`정산 내역이 아직 없는 거래 ${missing.length}건이 있습니다.`);
  }

  const invalid = sales.filter(
    (sale) => sale.baseIncentive <= 0 || sale.customerBenefit < 0 || sale.storeCost < 0,
  );
  if (invalid.length > 0) {
    issues.push(`금액이 올바르지 않은 거래 ${invalid.length}건이 있습니다.`);
  }

  return issues;
}

function resolveStatus(difference: number, hasClawbackRisk: boolean): SettlementStatus {
  if (difference < 0) return 'underpaid';
  if (hasClawbackRisk) return 'clawback-review';
  return 'matched';
}

/** 예상 인센티브와 실제 정산액을 거래별로 비교한다. */
export function buildSettlementComparison(
  sales: SaleRecord[],
  settlements: SettlementRecord[],
  warnings: RiskWarning[],
): SettlementComparisonRow[] {
  const settlementBySaleId = indexSettlements(settlements);
  const warningBySaleId = new Map(warnings.map((warning) => [warning.saleId, warning]));

  return sales.map((sale) => {
    const settlement = settlementBySaleId.get(sale.id);
    const actualPayout = settlement?.actualPayout ?? 0;
    const difference = calculateSettlementDifference(sale.baseIncentive, actualPayout);
    const warning = warningBySaleId.get(sale.id) ?? null;

    return {
      saleId: sale.id,
      soldAt: sale.soldAt,
      expectedIncentive: sale.baseIncentive,
      actualPayout,
      difference,
      status: resolveStatus(difference, warning?.category === 'clawback'),
      warningId: warning?.id ?? null,
    };
  });
}

export interface AnalysisInput {
  policies?: PolicySet;
  sales?: SaleRecord[];
  settlements?: SettlementRecord[];
  monthLabel?: string;
}

/** 동기 계산만 수행한다. 테스트에서 그대로 호출할 수 있다. */
export function runAnalysis(input: AnalysisInput = {}): AnalysisResult {
  const policies = input.policies ?? demoPolicySet;
  const sales = input.sales ?? currentMonthSales;
  const settlements = input.settlements ?? currentMonthSettlements;
  const monthLabel = input.monthLabel ?? currentMonthLabel;

  const validationIssues = validateInputs(policies, sales, settlements);

  const deals = calculateDealMargins(sales, policies);
  const salesCount = sales.length;
  const expectedNetMargin = calculateMonthlyNetMargin(deals);

  const warnings = detectWarnings(sales, settlements, deals, policies);
  const opportunity = detectProfitOpportunity(policies.tierIncentive, salesCount);
  const settlementRows = buildSettlementComparison(sales, settlements, warnings);

  const previousSalesCount =
    monthlySalesHistory[monthlySalesHistory.length - 1]?.salesCount ?? 0;

  return {
    analyzedAt: new Date().toISOString(),
    monthLabel,
    salesCount,
    previousSalesCount,
    salesCountDelta: salesCount - previousSalesCount,
    expectedNetMargin,
    warnings,
    opportunity,
    settlements: settlementRows,
    deals,
    validationIssues,
  };
}

/**
 * 화면에서 호출하는 비동기 래퍼.
 * 실제 데이터 조회를 대신해 짧은 지연을 두고 loading 상태를 노출한다.
 */
export function runAnalysisAsync(
  input: AnalysisInput = {},
  delayMs = 700,
): Promise<AnalysisResult> {
  return new Promise((resolve) => {
    window.setTimeout(() => resolve(runAnalysis(input)), delayMs);
  });
}
