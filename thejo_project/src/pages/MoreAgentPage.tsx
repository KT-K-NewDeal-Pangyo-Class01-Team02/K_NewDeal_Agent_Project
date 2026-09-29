import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Clock,
  Link2,
  RefreshCw,
  ShieldAlert,
  Target,
  TrendingUp,
  TriangleAlert,
  Wallet,
} from 'lucide-react';
import { AppShell } from '../components/command-center/AppShell';
import { DashboardSkeleton } from '../components/command-center/Skeletons';
import { DealDetail } from '../components/command-center/DealDetail';
import { ProfitOpportunityPanel } from '../components/command-center/ProfitOpportunity';
import { SettlementTable } from '../components/command-center/SettlementTable';
import { SummaryCard } from '../components/command-center/SummaryCard';
import { WarningDetail } from '../components/command-center/WarningDetail';
import { WarningList } from '../components/command-center/WarningList';
import { usePersistentSet } from '../hooks/usePersistentSet';
import { runAnalysisAsync } from '../services/analysis';
import type { AnalysisResult } from '../types/incentive';
import {
  formatAnalyzedAt,
  formatCount,
  formatSignedCount,
  formatWon,
} from '../utils/format';

const RESOLVED_WARNINGS_KEY = 'thejo.more-agent.resolved-warnings.v1';
const ACKNOWLEDGED_KEY = 'thejo.more-agent.acknowledged.v1';
const OPPORTUNITY_ID = 'monthly-tier';

type Selection =
  | { kind: 'warning'; id: string }
  | { kind: 'deal'; id: string }
  | null;

export function MoreAgentPage() {
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(true);
  const [selection, setSelection] = useState<Selection>(null);

  const resolvedWarnings = usePersistentSet(RESOLVED_WARNINGS_KEY);
  const acknowledged = usePersistentSet(ACKNOWLEDGED_KEY);

  /** 페이지 진입과 '자동 분석 다시 실행' 버튼이 공유하는 흐름. */
  const analyze = useCallback(() => {
    let cancelled = false;
    setIsAnalyzing(true);
    setSelection(null);

    void runAnalysisAsync().then((result) => {
      if (cancelled) return;
      setAnalysis(result);
      setIsAnalyzing(false);
    });

    return () => {
      cancelled = true;
    };
  }, []);

  // 진입하면 별도 입력 없이 바로 분석한다.
  useEffect(() => analyze(), [analyze]);

  const openLoss = useMemo(() => {
    if (!analysis) return { amount: 0, needsCheckCount: 0 };
    const open = analysis.warnings.filter((warning) => !resolvedWarnings.ids.has(warning.id));
    return {
      amount: open.reduce((sum, warning) => sum + warning.estimatedLoss, 0),
      needsCheckCount: open.filter((warning) => warning.severity !== 'info').length,
    };
  }, [analysis, resolvedWarnings.ids]);

  const selectedWarning =
    analysis && selection?.kind === 'warning'
      ? analysis.warnings.find((warning) => warning.id === selection.id) ?? null
      : null;

  const selectedDeal =
    analysis && selection?.kind === 'deal'
      ? analysis.deals.find((deal) => deal.saleId === selection.id) ?? null
      : null;

  const closeDetail = useCallback(() => setSelection(null), []);

  return (
    <AppShell breadcrumb={['Command Center', '더 줘']}>
      <div className="page-head">
        <div>
          <h1 className="page-title">더 줘</h1>
          <p className="page-description">
            놓칠 수 있는 손실은 막고, 월간 누적 수익 기회는 먼저 알려드립니다.
          </p>
          <div className="page-meta">
            <span className="badge badge-success">
              <Link2 size={13} aria-hidden="true" />
              판매일보 연동 완료
            </span>
            <span className="page-meta-time">
              <Clock size={14} aria-hidden="true" />
              마지막 분석{' '}
              {isAnalyzing || !analysis ? '분석 중…' : formatAnalyzedAt(analysis.analyzedAt)}
            </span>
            {analysis && analysis.validationIssues.length > 0 && (
              <span className="badge badge-caution">
                <TriangleAlert size={13} aria-hidden="true" />
                {analysis.validationIssues[0]}
              </span>
            )}
          </div>
        </div>

        <button type="button" className="btn btn-primary" onClick={analyze} disabled={isAnalyzing}>
          <RefreshCw size={16} aria-hidden="true" />
          {isAnalyzing ? '분석 중…' : '자동 분석 다시 실행'}
        </button>
      </div>

      {isAnalyzing || !analysis ? (
        <DashboardSkeleton />
      ) : (
        <>
          <div className="summary-grid">
            <SummaryCard
              label="이번 달 판매"
              Icon={TrendingUp}
              value={formatCount(analysis.salesCount)}
              hint={`전월 대비 ${formatSignedCount(analysis.salesCountDelta)}`}
              hintTone={analysis.salesCountDelta > 0 ? 'positive' : 'default'}
            />
            <SummaryCard
              label="예상 순마진"
              Icon={Wallet}
              value={formatWon(analysis.expectedNetMargin)}
              hint="인센티브 - 고객 혜택 - 매장 비용"
            />
            <SummaryCard
              label="손실 위험 금액"
              Icon={ShieldAlert}
              value={formatWon(openLoss.amount)}
              tone="danger"
              hint={
                openLoss.needsCheckCount > 0
                  ? `확인 필요 ${openLoss.needsCheckCount}건`
                  : '확인이 필요한 거래 없음'
              }
            />
            <SummaryCard
              label="다음 인센티브 구간"
              Icon={Target}
              value={formatCount(analysis.opportunity.remainingCount) + ' 남음'}
              tone="opportunity"
              hint={`${analysis.opportunity.targetCount}건 달성 시 구간 상승`}
            />
          </div>

          <div className="content-grid">
            <WarningList
              warnings={analysis.warnings}
              resolvedIds={resolvedWarnings.ids}
              onOpenDetail={(id) => setSelection({ kind: 'warning', id })}
              onResolve={resolvedWarnings.add}
              onReopen={resolvedWarnings.remove}
            />

            <ProfitOpportunityPanel
              opportunity={analysis.opportunity}
              isAcknowledged={acknowledged.ids.has(OPPORTUNITY_ID)}
              onAcknowledge={() => acknowledged.add(OPPORTUNITY_ID)}
              onReopen={() => acknowledged.remove(OPPORTUNITY_ID)}
            />
          </div>

          <SettlementTable
            rows={analysis.settlements}
            resolvedWarningIds={resolvedWarnings.ids}
            onSelectRow={(warningId, saleId) =>
              setSelection(
                warningId ? { kind: 'warning', id: warningId } : { kind: 'deal', id: saleId },
              )
            }
          />
        </>
      )}

      {analysis && selectedWarning && (
        <WarningDetail
          warning={selectedWarning}
          deal={analysis.deals.find((deal) => deal.saleId === selectedWarning.saleId)}
          isResolved={resolvedWarnings.ids.has(selectedWarning.id)}
          onResolve={resolvedWarnings.add}
          onReopen={resolvedWarnings.remove}
          onClose={closeDetail}
        />
      )}

      {analysis && selectedDeal && (
        <DealDetail
          deal={selectedDeal}
          row={analysis.settlements.find((row) => row.saleId === selectedDeal.saleId)}
          onClose={closeDetail}
        />
      )}
    </AppShell>
  );
}
