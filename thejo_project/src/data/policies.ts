import type { PolicySet } from '../types/incentive';

/**
 * 데모용 판매정책.
 *
 * 구간형 인센티브는 'retroactive'(소급 적용) 방식이다.
 * 10건을 달성하면 당월 전체 거래에 상위 구간 단가가 소급 적용된다.
 *
 * 정책 타입은 'incremental'(구간 이후 거래부터 상승) 및
 * 'lump-sum'(목표 달성 시 일괄 보너스)도 계산기가 지원하므로,
 * 이 파일의 rewardType만 바꾸면 다른 정책으로 전환할 수 있다.
 */
export const demoPolicySet: PolicySet = {
  effectiveMonth: '2026-09',
  tierIncentive: {
    id: 'POL-TIER-2609',
    name: '2026년 9월 월간 판매량 구간 인센티브',
    rewardType: 'retroactive',
    tiers: [
      { id: 'tier-1', label: '1~9건', minCount: 1, maxCount: 9, perUnitIncentive: 100_000 },
      { id: 'tier-2', label: '10~19건', minCount: 10, maxCount: 19, perUnitIncentive: 200_000 },
    ],
    minimumSecuredProfit: 700_000,
  },
  retention: {
    id: 'POL-RET-2609',
    name: '요금제 유지조건',
    requiredRetentionDays: 180,
    clawbackAmount: 300_000,
    description: '개통일 기준 180일 이상 요금제를 유지해야 하며, 미달 시 건당 300,000원이 환수됩니다.',
  },
  margin: {
    id: 'POL-MGN-2609',
    minimumMarginPerDeal: 150_000,
    description: '고객 혜택과 매장 부담 비용을 차감한 뒤 거래 한 건당 최소 150,000원의 마진을 확보해야 합니다.',
  },
};
