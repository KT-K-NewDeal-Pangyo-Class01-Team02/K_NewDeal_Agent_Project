import { TriangleAlert } from 'lucide-react';
import type { SettlementComparisonRow, SettlementStatus } from '../../types/incentive';
import { formatDate, formatSignedWon, formatWon } from '../../utils/format';

interface SettlementTableProps {
  rows: SettlementComparisonRow[];
  resolvedWarningIds: ReadonlySet<string>;
  onSelectRow: (warningId: string | null, saleId: string) => void;
}

const statusMeta: Record<SettlementStatus, { label: string; className: string }> = {
  matched: { label: '일치', className: 'badge badge-success' },
  underpaid: { label: '부족 지급', className: 'badge badge-danger' },
  'clawback-review': { label: '환수 검토', className: 'badge badge-caution' },
  acknowledged: { label: '확인 완료', className: 'badge badge-info' },
};

/** 예상 인센티브와 실제 정산액을 나란히 비교한다. */
export function SettlementTable({ rows, resolvedWarningIds, onSelectRow }: SettlementTableProps) {
  return (
    <section className="card">
      <div className="card-head">
        <div>
          <h2 className="card-title">최근 정산 비교</h2>
          <p className="card-subtitle">
            예상 인센티브와 실제 정산액의 차이를 거래별로 확인하세요. 행을 누르면 상세가 열립니다.
          </p>
        </div>
      </div>

      <div className="table-scroll">
        <table className="settlement-table">
          <caption className="visually-hidden">거래별 예상 인센티브와 실제 정산액 비교표</caption>
          <thead>
            <tr>
              <th scope="col">거래 ID</th>
              <th scope="col">판매일</th>
              <th scope="col" className="num">
                예상 인센티브
              </th>
              <th scope="col" className="num">
                실제 정산액
              </th>
              <th scope="col" className="num">
                차액
              </th>
              <th scope="col">상태</th>
              <th scope="col">조치</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const isResolved = row.warningId !== null && resolvedWarningIds.has(row.warningId);
              const status = statusMeta[isResolved ? 'acknowledged' : row.status];
              const hasOpenWarning = row.warningId !== null && !isResolved;

              return (
                <tr
                  key={row.saleId}
                  tabIndex={0}
                  onClick={() => onSelectRow(row.warningId, row.saleId)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      onSelectRow(row.warningId, row.saleId);
                    }
                  }}
                >
                  <td>
                    <span className="settlement-tx">
                      {hasOpenWarning && (
                        <span className="row-flag" aria-label="확인이 필요한 거래">
                          <TriangleAlert size={14} aria-hidden="true" />
                        </span>
                      )}
                      {row.saleId}
                    </span>
                  </td>
                  <td>{formatDate(row.soldAt)}</td>
                  <td className="num">{formatWon(row.expectedIncentive)}</td>
                  <td className="num">{formatWon(row.actualPayout)}</td>
                  <td className="num">
                    <span
                      className={`settlement-diff${
                        row.difference < 0 ? ' is-negative' : row.difference === 0 ? ' is-zero' : ''
                      }`}
                    >
                      {formatSignedWon(row.difference)}
                    </span>
                  </td>
                  <td>
                    <span className={status.className}>{status.label}</span>
                  </td>
                  <td>
                    <span style={{ color: 'var(--opportunity)', fontWeight: 600 }}>
                      {row.warningId ? '상세 보기' : '이상 없음'}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <p className="table-foot-note">
        차액은 <strong>실제 정산액 - 예상 인센티브</strong>로 계산합니다. 음수이면 받아야 할 금액보다
        적게 지급된 것입니다.
      </p>
    </section>
  );
}
