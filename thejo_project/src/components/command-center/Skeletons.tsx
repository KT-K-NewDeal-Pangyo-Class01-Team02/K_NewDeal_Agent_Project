/** 자동 분석이 끝날 때까지 보여주는 자리표시 화면. */
export function DashboardSkeleton() {
  return (
    <div aria-busy="true" aria-live="polite">
      <p className="visually-hidden">판매일보와 정산 데이터를 분석하는 중입니다.</p>

      <div className="summary-grid">
        {[0, 1, 2, 3].map((index) => (
          <div key={index} className="card skeleton-card">
            <div className="skeleton" style={{ width: '45%', height: 14 }} />
            <div className="skeleton" style={{ width: '65%', height: 30 }} />
            <div className="skeleton" style={{ width: '55%', height: 12, marginTop: 'auto' }} />
          </div>
        ))}
      </div>

      <div className="content-grid">
        <div className="card skeleton-panel">
          <div className="skeleton" style={{ width: '40%', height: 18 }} />
          {[0, 1, 2].map((index) => (
            <div key={index} className="skeleton" style={{ width: '100%', height: 132 }} />
          ))}
        </div>
        <div className="card skeleton-panel">
          <div className="skeleton" style={{ width: '35%', height: 18 }} />
          <div className="skeleton" style={{ width: '100%', height: 110 }} />
          <div className="skeleton" style={{ width: '100%', height: 220 }} />
        </div>
      </div>

      <div className="card skeleton-panel">
        <div className="skeleton" style={{ width: '25%', height: 18 }} />
        <div className="skeleton" style={{ width: '100%', height: 240 }} />
      </div>
    </div>
  );
}
