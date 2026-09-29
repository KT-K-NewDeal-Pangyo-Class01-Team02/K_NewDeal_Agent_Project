import { CircleCheck } from 'lucide-react';
import type { DealCalculation, SettlementComparisonRow } from '../../types/incentive';
import { formatDate, formatSignedWon, formatWon } from '../../utils/format';
import { CalculationList } from './CalculationList';
import { Modal } from './Modal';

interface DealDetailProps {
  deal: DealCalculation;
  row: SettlementComparisonRow | undefined;
  onClose: () => void;
}

/** Warning이 없는 거래를 눌렀을 때 보여주는 상세 패널. */
export function DealDetail({ deal, row, onClose }: DealDetailProps) {
  return (
    <Modal
      title="이 거래는 이상이 없습니다"
      onClose={onClose}
      eyebrow={
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          <span className="badge badge-success">
            <CircleCheck size={13} aria-hidden="true" />
            확인 필요 없음
          </span>
          <span className="badge badge-neutral">{deal.saleId}</span>
        </div>
      }
      footer={
        <button type="button" className="btn" onClick={onClose}>
          닫기
        </button>
      }
    >
      <p className="modal-note">
        예상 인센티브와 실제 정산액이 일치하고, 환수 위험이나 최소 마진 미달도 없습니다.
      </p>

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

      <div>
        <p className="modal-section-title">마진 계산</p>
        <CalculationList
          lines={[
            { label: '예상 개통 인센티브', expression: formatWon(deal.baseIncentive) },
            { label: '구간 인센티브(건당)', expression: `+ ${formatWon(deal.volumeIncentive)}` },
            { label: '고객 혜택', expression: `- ${formatWon(deal.customerBenefit)}` },
            { label: '매장 부담 비용', expression: `- ${formatWon(deal.storeCost)}` },
            { label: '예상 환수 금액', expression: `- ${formatWon(deal.expectedClawback)}` },
            { label: '예상 마진', expression: formatWon(deal.netMargin) },
          ]}
        />
      </div>

      {row && (
        <div>
          <p className="modal-section-title">정산 비교</p>
          <CalculationList
            lines={[
              { label: '예상 인센티브', expression: formatWon(row.expectedIncentive) },
              { label: '실제 정산액', expression: formatWon(row.actualPayout) },
              { label: '차액', expression: formatSignedWon(row.difference) },
            ]}
          />
        </div>
      )}
    </Modal>
  );
}
