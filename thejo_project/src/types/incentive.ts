/**
 * '더 줘' Agent 도메인 타입.
 *
 * 금액 계산에 필요한 모든 값은 이 타입들을 통해 명시적으로 전달한다.
 * LLM은 계산에 관여하지 않고, 계산 결과를 설명하는 문장만 담당한다.
 */

/** 구간형 인센티브 지급 방식. */
export type TierRewardType = 'incremental' | 'retroactive' | 'lump-sum';

/** 구간 하나. maxCount가 null이면 상한 없음. */
export interface IncentiveTier {
  id: string;
  label: string;
  minCount: number;
  maxCount: number | null;
  perUnitIncentive: number;
  /** rewardType이 'lump-sum'일 때 구간 달성 시 지급되는 일괄 보너스. */
  lumpSumBonus?: number;
}

export interface TierIncentivePolicy {
  id: string;
  name: string;
  rewardType: TierRewardType;
  tiers: IncentiveTier[];
  /** 판매점이 반드시 확보해야 하는 최소 수익. 추가 고객 혜택 여력 계산에 사용. */
  minimumSecuredProfit: number;
}

/** 요금제 유지조건과 환수 정책. */
export interface RetentionPolicy {
  id: string;
  name: string;
  requiredRetentionDays: number;
  clawbackAmount: number;
  description: string;
}

/** 거래 한 건이 확보해야 하는 최소 마진. */
export interface MarginPolicy {
  id: string;
  minimumMarginPerDeal: number;
  description: string;
}

export interface PolicySet {
  effectiveMonth: string;
  tierIncentive: TierIncentivePolicy;
  retention: RetentionPolicy;
  margin: MarginPolicy;
}

/** 판매일보 한 줄. 사장님이 따로 입력하지 않고 기존 데이터를 그대로 읽어온다. */
export interface SaleRecord {
  id: string;
  soldAt: string;
  maskedCustomer: string;
  device: string;
  planName: string;
  /** 거래별 예상 개통 인센티브. */
  baseIncentive: number;
  /** 고객에게 지급한 혜택. */
  customerBenefit: number;
  /** 매장이 부담한 비용. */
  storeCost: number;
  /** 개통 후 요금제 변경까지 걸린 일수. 변경 이력이 없으면 null. */
  planChangedAfterDays: number | null;
}

/** 통신사에서 실제로 정산된 금액. */
export interface SettlementRecord {
  saleId: string;
  settledAt: string;
  actualPayout: number;
  adjustmentNote: string | null;
}

export interface MonthlySalesSummary {
  month: string;
  salesCount: number;
}

export type WarningSeverity = 'critical' | 'warning' | 'info';
export type WarningCategory = 'clawback' | 'settlement-gap' | 'low-margin';

/** 계산 근거 한 줄. 모달에서 그대로 노출된다. */
export interface CalculationLine {
  label: string;
  expression: string;
}

export interface RiskWarning {
  id: string;
  saleId: string;
  maskedCustomer: string;
  category: WarningCategory;
  severity: WarningSeverity;
  title: string;
  reason: string;
  estimatedLoss: number;
  recommendedAction: string;
  calculation: CalculationLine[];
}

/** 거래 한 건의 마진 계산 결과. */
export interface DealCalculation {
  saleId: string;
  soldAt: string;
  maskedCustomer: string;
  device: string;
  planName: string;
  baseIncentive: number;
  volumeIncentive: number;
  customerBenefit: number;
  storeCost: number;
  expectedClawback: number;
  /** 환수 반영 전 마진. 최소 마진 기준 판정에 사용. */
  contractMargin: number;
  /** 환수까지 반영한 최종 마진. */
  netMargin: number;
}

export interface ProfitOpportunity {
  rewardType: TierRewardType;
  isRetroactive: boolean;
  currentCount: number;
  targetCount: number;
  remainingCount: number;
  currentUnitIncentive: number;
  nextUnitIncentive: number;
  currentVolumeIncentive: number;
  projectedVolumeIncentive: number;
  additionalIncentive: number;
  minimumSecuredProfit: number;
  availableCustomerBenefit: number;
  calculation: CalculationLine[];
}

export type SettlementStatus = 'matched' | 'underpaid' | 'clawback-review' | 'acknowledged';

export interface SettlementComparisonRow {
  saleId: string;
  soldAt: string;
  expectedIncentive: number;
  actualPayout: number;
  difference: number;
  status: SettlementStatus;
  /** 이 거래에 연결된 Warning의 id. 행을 눌렀을 때 상세를 열기 위해 사용. */
  warningId: string | null;
}

export interface AnalysisResult {
  analyzedAt: string;
  monthLabel: string;
  salesCount: number;
  previousSalesCount: number;
  salesCountDelta: number;
  /** 인센티브 - 고객 혜택 - 매장 비용 - 예상 환수. */
  expectedNetMargin: number;
  warnings: RiskWarning[];
  opportunity: ProfitOpportunity;
  settlements: SettlementComparisonRow[];
  deals: DealCalculation[];
  validationIssues: string[];
}
