import { runAnalysis } from '../src/services/analysis';
import { calculateVolumeIncentive } from '../src/services/incentiveCalculator';
import { demoPolicySet } from '../src/data/policies';

/**
 * 계산 로직이 판매정책 명세와 일치하는지 확인한다.
 * UI 없이 순수 계산 함수만 실행하므로 `npm run verify`로 빠르게 돌릴 수 있다.
 */

const r = runAnalysis();
const o = r.opportunity;

const checks: [string, unknown, unknown][] = [
  ['이번 달 판매', r.salesCount, 9],
  ['전월 대비', r.salesCountDelta, 2],
  ['예상 순마진', r.expectedNetMargin, 3_005_000],
  ['현재 인센티브', o.currentVolumeIncentive, 900_000],
  ['목표 달성 후 인센티브', o.projectedVolumeIncentive, 2_000_000],
  ['추가 예상 인센티브', o.additionalIncentive, 1_100_000],
  ['최소 확보 수익', o.minimumSecuredProfit, 700_000],
  ['활용 가능 혜택', o.availableCustomerBenefit, 400_000],
  ['남은 건수', o.remainingCount, 1],
  ['목표 건수', o.targetCount, 10],
  ['현재 단가', o.currentUnitIncentive, 100_000],
  ['다음 단가', o.nextUnitIncentive, 200_000],
  ['Warning 개수', r.warnings.length, 3],
  [
    '1순위 환수/긴급',
    `${r.warnings[0].category}/${r.warnings[0].severity}/${r.warnings[0].saleId}`,
    'clawback/critical/TX-202609-018',
  ],
  ['1순위 손실', r.warnings[0].estimatedLoss, 300_000],
  [
    '2순위 정산/주의',
    `${r.warnings[1].category}/${r.warnings[1].severity}/${r.warnings[1].saleId}`,
    'settlement-gap/warning/TX-202609-011',
  ],
  ['2순위 손실', r.warnings[1].estimatedLoss, 200_000],
  [
    '3순위 마진/확인',
    `${r.warnings[2].category}/${r.warnings[2].severity}/${r.warnings[2].saleId}`,
    'low-margin/info/TX-202609-022',
  ],
  ['3순위 손실', r.warnings[2].estimatedLoss, 50_000],
  ['손실 위험 합계', r.warnings.reduce((s, w) => s + w.estimatedLoss, 0), 550_000],
  ['확인 필요(긴급+주의)', r.warnings.filter((w) => w.severity !== 'info').length, 2],
  ['정산행 수', r.settlements.length, 9],
  ['TX-011 차액', r.settlements.find((s) => s.saleId === 'TX-202609-011')?.difference, -200_000],
  ['TX-011 상태', r.settlements.find((s) => s.saleId === 'TX-202609-011')?.status, 'underpaid'],
  [
    'TX-018 상태',
    r.settlements.find((s) => s.saleId === 'TX-202609-018')?.status,
    'clawback-review',
  ],
  ['일치 행 수', r.settlements.filter((s) => s.status === 'matched').length, 7],
  ['검증 이슈 없음', r.validationIssues.length, 0],
];

let failed = 0;
for (const [name, actual, expected] of checks) {
  const ok = actual === expected;
  if (!ok) failed += 1;
  const suffix = ok ? '' : ` (기대값 ${String(expected)})`;
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}: ${String(actual)}${suffix}`);
}

// rewardType을 바꿔도 계산기가 동작하는지 확인한다.
const tiers = demoPolicySet.tierIncentive;
const incremental = calculateVolumeIncentive({ ...tiers, rewardType: 'incremental' }, 10);
const lumpSum = calculateVolumeIncentive(
  {
    ...tiers,
    rewardType: 'lump-sum',
    tiers: tiers.tiers.map((t) => (t.minCount === 10 ? { ...t, lumpSumBonus: 500_000 } : t)),
  },
  10,
);

console.log('');
console.log(`${incremental === 1_100_000 ? 'PASS' : 'FAIL'}  incremental 10건: ${incremental}`);
console.log(`${lumpSum === 1_500_000 ? 'PASS' : 'FAIL'}  lump-sum 10건: ${lumpSum}`);
if (incremental !== 1_100_000) failed += 1;
if (lumpSum !== 1_500_000) failed += 1;

console.log('');
console.log(failed === 0 ? 'ALL PASS' : `${failed} FAILED`);
if (failed > 0) process.exitCode = 1;
