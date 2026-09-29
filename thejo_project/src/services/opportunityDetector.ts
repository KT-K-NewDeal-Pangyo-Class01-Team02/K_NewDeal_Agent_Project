import type { ProfitOpportunity, TierIncentivePolicy } from '../types/incentive';
import {
  calculateVolumeIncentive,
  currentUnitIncentive,
  findNextTier,
} from './incentiveCalculator';
import { formatWon } from '../utils/format';

/**
 * 놓치기 쉬운 누적 수익 기회 탐지.
 *
 * 판매점이 스스로 계산하기 어려운 "몇 건만 더 팔면 얼마가 늘어나는가"를
 * 정책 데이터만으로 계산한다.
 */
export function detectProfitOpportunity(
  policy: TierIncentivePolicy,
  salesCount: number,
): ProfitOpportunity {
  const nextTier = findNextTier(policy.tiers, salesCount);
  const targetCount = nextTier?.minCount ?? salesCount;
  const remainingCount = Math.max(0, targetCount - salesCount);

  const currentUnit = currentUnitIncentive(policy, salesCount);
  const nextUnit = nextTier?.perUnitIncentive ?? currentUnit;

  const currentVolumeIncentive = calculateVolumeIncentive(policy, salesCount);
  const projectedVolumeIncentive = calculateVolumeIncentive(policy, targetCount);
  const additionalIncentive = projectedVolumeIncentive - currentVolumeIncentive;

  const { minimumSecuredProfit } = policy;
  const availableCustomerBenefit = Math.max(0, additionalIncentive - minimumSecuredProfit);

  const isRetroactive = policy.rewardType === 'retroactive';

  return {
    rewardType: policy.rewardType,
    isRetroactive,
    currentCount: salesCount,
    targetCount,
    remainingCount,
    currentUnitIncentive: currentUnit,
    nextUnitIncentive: nextUnit,
    currentVolumeIncentive,
    projectedVolumeIncentive,
    additionalIncentive,
    minimumSecuredProfit,
    availableCustomerBenefit,
    calculation: [
      {
        label: '현재 인센티브',
        expression: `${salesCount}건 × ${formatWon(currentUnit)} = ${formatWon(currentVolumeIncentive)}`,
      },
      {
        label: '목표 달성 후 인센티브',
        expression: `${targetCount}건 × ${formatWon(nextUnit)} = ${formatWon(projectedVolumeIncentive)}`,
      },
      {
        label: '추가 예상 인센티브',
        expression: `${formatWon(projectedVolumeIncentive)} - ${formatWon(currentVolumeIncentive)} = ${formatWon(additionalIncentive)}`,
      },
      {
        label: '활용 가능 혜택',
        expression: `${formatWon(additionalIncentive)} - 최소 확보 수익 ${formatWon(minimumSecuredProfit)} = ${formatWon(availableCustomerBenefit)}`,
      },
    ],
  };
}
