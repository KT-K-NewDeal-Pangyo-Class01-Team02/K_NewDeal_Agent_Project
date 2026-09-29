import { Check, CircleCheck, Lightbulb } from 'lucide-react';
import type { RiskWarning } from '../../types/incentive';
import { formatWon } from '../../utils/format';
import { categoryMeta, severityMeta } from './warningMeta';

interface WarningListProps {
  warnings: RiskWarning[];
  resolvedIds: ReadonlySet<string>;
  onOpenDetail: (warningId: string) => void;
  onResolve: (warningId: string) => void;
  onReopen: (warningId: string) => void;
}

/** 위험도 순서대로 정렬된 Warning 목록. 카드를 누르면 상세가 열린다. */
export function WarningList({
  warnings,
  resolvedIds,
  onOpenDetail,
  onResolve,
  onReopen,
}: WarningListProps) {
  const openCount = warnings.filter((warning) => !resolvedIds.has(warning.id)).length;

  return (
    <section className="card">
      <div className="card-head">
        <div>
          <h2 className="card-title">오늘의 Warning</h2>
          <p className="card-subtitle">위험이 큰 순서대로 보여드립니다.</p>
        </div>
        <span className={openCount > 0 ? 'badge badge-danger' : 'badge badge-success'}>
          {openCount > 0 ? `확인 필요 ${openCount}건` : '모두 확인'}
        </span>
      </div>

      {warnings.length === 0 ? (
        <p className="warning-empty">지금 확인해야 할 위험이 없습니다.</p>
      ) : (
        <div className="warning-list">
          {warnings.map((warning) => {
            const isResolved = resolvedIds.has(warning.id);
            const severity = severityMeta[warning.severity];
            const category = categoryMeta[warning.category];
            const { Icon } = category;

            return (
              <article
                key={warning.id}
                className={`warning-card ${severity.toneClass}${isResolved ? ' is-resolved' : ''}`}
              >
                <div className="warning-card-top">
                  <span
                    className={`warning-icon ${severity.toneClass}${isResolved ? ' is-resolved' : ''}`}
                    aria-hidden="true"
                  >
                    {isResolved ? <CircleCheck size={17} /> : <Icon size={17} />}
                  </span>
                  <span className={isResolved ? 'badge badge-neutral' : severity.badgeClass}>
                    {isResolved ? '조치 완료' : severity.label}
                  </span>
                  <span className="badge badge-neutral">{category.label}</span>
                  <span className="warning-tx">
                    {warning.saleId} · {warning.maskedCustomer}
                  </span>
                </div>

                <button
                  type="button"
                  className="warning-open"
                  onClick={() => onOpenDetail(warning.id)}
                >
                  <h3 className="warning-title">{warning.title}</h3>
                  <p className="warning-reason">{warning.reason}</p>
                </button>

                <div className="warning-loss">
                  <span className="warning-loss-label">
                    {warning.category === 'clawback' ? '예상 환수액' : '예상 손실 금액'}
                  </span>
                  <span className={`warning-loss-value${isResolved ? ' is-resolved' : ''}`}>
                    {formatWon(warning.estimatedLoss)}
                  </span>
                </div>

                <p className="warning-action">
                  <Lightbulb size={15} aria-hidden="true" style={{ flex: '0 0 auto', marginTop: 2 }} />
                  <span>{warning.recommendedAction}</span>
                </p>

                <div className="warning-buttons">
                  <button
                    type="button"
                    className="btn"
                    onClick={() => onOpenDetail(warning.id)}
                  >
                    거래 확인
                  </button>
                  {isResolved ? (
                    <button type="button" className="btn" onClick={() => onReopen(warning.id)}>
                      완료 취소
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="btn btn-primary"
                      onClick={() => onResolve(warning.id)}
                    >
                      <Check size={16} aria-hidden="true" />
                      조치 완료
                    </button>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
