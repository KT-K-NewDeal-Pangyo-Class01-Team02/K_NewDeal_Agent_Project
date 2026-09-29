import { Check, Lightbulb } from 'lucide-react';
import type { DealCalculation, RiskWarning } from '../../types/incentive';
import { formatDate, formatWon } from '../../utils/format';
import { CalculationList } from './CalculationList';
import { Modal } from './Modal';
import { categoryMeta, severityMeta } from './warningMeta';

interface WarningDetailProps {
  warning: RiskWarning;
  deal: DealCalculation | undefined;
  isResolved: boolean;
  onResolve: (warningId: string) => void;
  onReopen: (warningId: string) => void;
  onClose: () => void;
}

/** Warning 카드와 정산표 행이 공유하는 상세 패널. */
export function WarningDetail({
  warning,
  deal,
  isResolved,
  onResolve,
  onReopen,
  onClose,
}: WarningDetailProps) {
  const severity = severityMeta[warning.severity];
  const category = categoryMeta[warning.category];

  return (
    <Modal
      title={warning.title}
      onClose={onClose}
      eyebrow={
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          <span className={isResolved ? 'badge badge-neutral' : severity.badgeClass}>
            {isResolved ? '조치 완료' : severity.label}
          </span>
          <span className="badge badge-neutral">{category.label}</span>
          <span className="badge badge-neutral">{warning.saleId}</span>
        </div>
      }
      footer={
        <>
          <button type="button" className="btn" onClick={onClose}>
            닫기
          </button>
          {isResolved ? (
            <button type="button" className="btn" onClick={() => onReopen(warning.id)}>
              완료 취소
            </button>
          ) : (
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => {
                onResolve(warning.id);
                onClose();
              }}
            >
              <Check size={16} aria-hidden="true" />
              조치 완료
            </button>
          )}
        </>
      }
    >
      <p className="modal-note">{warning.reason}</p>

      {deal && (
        <div>
          <p className="modal-section-title">거래 정보</p>
          <div className="detail-meta">
            <div className="detail-meta-item">
              <p className="detail-meta-label">판매일</p>
              <p className="detail-meta-value">{formatDate(deal.soldAt)}</p>
            </div>
            <div className="detail-meta-item">
              <p className="detail-meta-label">고객</p>
              <p className="detail-meta-value">{deal.maskedCustomer}</p>
            </div>
            <div className="detail-meta-item">
              <p className="detail-meta-label">단말</p>
              <p className="detail-meta-value">{deal.device}</p>
            </div>
            <div className="detail-meta-item">
              <p className="detail-meta-label">요금제</p>
              <p className="detail-meta-value">{deal.planName}</p>
            </div>
          </div>
        </div>
      )}

      <div>
        <p className="modal-section-title">계산 근거</p>
        <CalculationList lines={warning.calculation} />
      </div>

      <div>
        <p className="modal-section-title">
          {warning.category === 'clawback' ? '예상 환수액' : '예상 손실 금액'}
        </p>
        <div className="warning-loss">
          <span className="warning-loss-label">이 거래에서 줄어드는 금액</span>
          <span className="warning-loss-value">{formatWon(warning.estimatedLoss)}</span>
        </div>
      </div>

      <div className="modal-callout">
        <Lightbulb size={18} aria-hidden="true" style={{ flex: '0 0 auto', marginTop: 2 }} />
        <span>
          <strong>이렇게 하세요. </strong>
          {warning.recommendedAction}
        </span>
      </div>
    </Modal>
  );
}
