import { useState } from 'react';
import { Calculator, Check, CircleCheck, Sparkles, TrendingUp } from 'lucide-react';
import type { ProfitOpportunity as ProfitOpportunityData } from '../../types/incentive';
import { formatCount, formatWon } from '../../utils/format';
import { CalculationList } from './CalculationList';

interface ProfitOpportunityPanelProps {
  opportunity: ProfitOpportunityData;
  isAcknowledged: boolean;
  onAcknowledge: () => void;
  onReopen: () => void;
}

/** 놓치기 쉬운 누적 수익 기회. 가장 큰 숫자를 가장 크게 보여준다. */
export function ProfitOpportunityPanel({
  opportunity,
  isAcknowledged,
  onAcknowledge,
  onReopen,
}: ProfitOpportunityPanelProps) {
  const [showCalculation, setShowCalculation] = useState(false);

  const {
    currentCount,
    targetCount,
    remainingCount,
    currentUnitIncentive,
    nextUnitIncentive,
    currentVolumeIncentive,
    projectedVolumeIncentive,
    additionalIncentive,
    minimumSecuredProfit,
    availableCustomerBenefit,
    isRetroactive,
  } = opportunity;

  const progressPercent =
    targetCount > 0 ? Math.min(100, Math.round((currentCount / targetCount) * 100)) : 100;

  return (
    <section className="card">
      <div className="card-head">
        <div>
          <h2 className="card-title">놓치기 쉬운 수익 기회</h2>
          <p className="card-subtitle">이번 달 판매량과 구간 인센티브를 함께 계산했습니다.</p>
        </div>
        {isAcknowledged ? (
          <span className="badge badge-neutral">
            <CircleCheck size={13} aria-hidden="true" />
            확인 완료
          </span>
        ) : (
          <span className="badge badge-info">
            <TrendingUp size={13} aria-hidden="true" />
            기회 있음
          </span>
        )}
      </div>

      <div className="opportunity-body">
        <div className="progress-block">
          <div className="progress-head">
            <p className="progress-count">
              {currentCount}
              <span> / {targetCount}건</span>
            </p>
            <p className="progress-remaining">다음 구간까지 {formatCount(remainingCount)}</p>
          </div>

          <div
            className="progress-bar"
            role="progressbar"
            aria-valuenow={currentCount}
            aria-valuemin={0}
            aria-valuemax={targetCount}
            aria-label={`월간 판매 진행률 ${currentCount} / ${targetCount}건`}
          >
            <div className="progress-bar-fill" style={{ width: `${progressPercent}%` }} />
          </div>

          <div className="progress-tiers">
            <span>
              현재 구간 <strong>건당 {formatWon(currentUnitIncentive)}</strong>
            </span>
            <span>
              다음 구간 <strong>건당 {formatWon(nextUnitIncentive)}</strong>
            </span>
          </div>
        </div>

        <div className="highlight-card">
          <p className="highlight-top">
            <Sparkles size={15} aria-hidden="true" />
            가장 큰 수익 기회
          </p>

          <h3 className="highlight-headline">
            다음 인센티브 구간까지 {formatCount(remainingCount)} 남았습니다.
          </h3>

          <p className="highlight-amount">
            <span className="highlight-amount-value">+{formatWon(additionalIncentive)}</span>
            <span className="highlight-amount-label">목표 달성 시 추가 예상 인센티브</span>
          </p>

          <p className="highlight-text">
            {formatCount(remainingCount)}을 추가 판매하면 당월 예상 인센티브가{' '}
            {formatWon(currentVolumeIncentive)}에서 {formatWon(projectedVolumeIncentive)}으로
            증가합니다.
            {isRetroactive && ' 상위 구간 단가는 당월 전체 거래에 소급 적용됩니다.'}
          </p>
          <p className="highlight-text">
            최소 수익 {formatWon(minimumSecuredProfit)}을 확보하면서 최대{' '}
            {formatWon(availableCustomerBenefit)}을 추가 고객 혜택으로 활용할 수 있습니다.
          </p>

          <div className="highlight-buttons">
            <button
              type="button"
              className="btn"
              aria-expanded={showCalculation}
              onClick={() => setShowCalculation((open) => !open)}
            >
              <Calculator size={16} aria-hidden="true" />
              계산 근거 보기
            </button>
            {isAcknowledged ? (
              <button type="button" className="btn" onClick={onReopen}>
                확인 취소
              </button>
            ) : (
              <button type="button" className="btn btn-opportunity" onClick={onAcknowledge}>
                <Check size={16} aria-hidden="true" />
                기회 확인 완료
              </button>
            )}
          </div>

          {showCalculation && (
            <div className="calc-panel">
              <p className="calc-panel-title">계산 근거</p>
              <CalculationList lines={opportunity.calculation} />
            </div>
          )}
        </div>

        <div className="opportunity-facts">
          <div className="fact">
            <p className="fact-label">목표 달성 시 추가 인센티브</p>
            <p className="fact-value is-opportunity">+{formatWon(additionalIncentive)}</p>
          </div>
          <div className="fact">
            <p className="fact-label">최소 확보 수익</p>
            <p className="fact-value">{formatWon(minimumSecuredProfit)}</p>
          </div>
          <div className="fact">
            <p className="fact-label">추가 활용 가능 고객 혜택</p>
            <p className="fact-value">최대 {formatWon(availableCustomerBenefit)}</p>
          </div>
        </div>
      </div>
    </section>
  );
}
