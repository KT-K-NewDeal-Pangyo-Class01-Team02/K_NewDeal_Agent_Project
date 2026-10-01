// 빅또리출동! 지사 승인 화면 (F-06): 승인 대기 목록 → 기획안 검토 → 승인 / 반려(사유 필수)
(function () {
  const list = document.getElementById('hq-list');
  const meta = document.getElementById('hq-meta');
  const refreshBtn = document.getElementById('hq-refresh');
  const { toHtml } = window.vicPlan;
  const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text !== undefined) n.textContent = text; return n; };
  const when = (iso) => (iso ? new Date(iso).toLocaleString('ko-KR', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '-');
  const won = (n) => (n ? `${Number(n).toLocaleString('ko-KR')}원` : '-');

  async function post(url, body) {
    const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || '요청을 처리하지 못했어요.');
    return data;
  }

  function card(item) {
    const box = el('article', 'hq-card');
    const head = el('div', 'hq-head');
    const title = el('div');
    title.append(el('h3', null, [item.store_name || item.store_id, item.target_date].filter(Boolean).join(' · ')),
      el('p', 'hq-sub', [item.site_name, item.operating_hours && item.operating_hours.replace('-', '~'), item.staff, item.budget && `예산 ${won(item.budget)}`].filter(Boolean).join(' · ')));
    const badges = el('div', 'hq-badges');
    badges.append(el('span', 'approval-badge is-requested', '승인 대기'));
    if (item.revision_round) badges.append(el('span', 'approval-badge is-rejected', `수정 ${item.revision_round}회차`));
    if (item.review_status === 'auto_revised') badges.append(el('span', 'approval-badge', '카피 자동 수정 있음'));
    head.append(title, badges);

    const info = el('p', 'hq-sub', `캠페인 ${item.campaign_id} · ${item.requested_by || '점장'} 요청 ${when(item.requested_at)}`);
    const prev = (item.history || []).filter((h) => h.action === 'rejected').slice(-1)[0];
    const details = el('details', 'hq-plan');
    details.append(el('summary', null, '기획안 전체 보기'));
    const doc = el('article', 'plan-doc');
    doc.innerHTML = toHtml(item.plan_markdown || '(첨부된 기획안이 없습니다)');  // toHtml 은 모든 글자를 이스케이프한다
    details.append(doc);

    const comment = el('textarea', 'cc-textarea');
    comment.rows = 2; comment.maxLength = 300;
    comment.placeholder = '코멘트 (반려할 때는 무엇을 고쳐야 하는지 5자 이상)';
    const actions = el('div', 'approval-actions');
    const approve = el('button', 'cc-btn cc-btn-primary', '승인');
    const reject = el('button', 'cc-btn', '반려');
    [approve, reject].forEach((b) => { b.type = 'button'; });
    const msg = el('p', 'form-error');
    async function decide(decision) {
      approve.disabled = true; reject.disabled = true; msg.textContent = '';
      try {
        const r = await post('/api/f06/decide', { campaign_id: item.campaign_id, decision, comment: comment.value });
        window.ccToast(r.message || '처리했습니다.');
        load();
      } catch (err) {
        msg.textContent = err.message;
        approve.disabled = false; reject.disabled = false;
      }
    }
    approve.addEventListener('click', () => decide('approve'));
    reject.addEventListener('click', () => decide('reject'));
    actions.append(approve, reject);

    box.append(head, info);
    if (prev) box.append(el('p', 'hq-prev', `이전 반려 사유 (${prev.round + 1}회차 요청 때): ${prev.comment}`));
    box.append(details, comment, actions, msg);
    return box;
  }

  async function load() {
    refreshBtn.disabled = true;
    try {
      const data = await post('/api/f06/list');
      const items = data.items || [];
      meta.textContent = `${items.length}건 대기 · ${when(new Date().toISOString())} 기준${data.source === 'demo' ? ' · 데모 데이터' : ''}`;
      list.replaceChildren(...(items.length ? items.map(card) : [el('div', 'opp-empty', '승인 대기 중인 캠페인이 없습니다. 점장이 기획안에서 "지사 승인 요청"을 누르면 여기에 나타납니다.')]));
    } catch (err) {
      meta.textContent = '';
      list.replaceChildren(el('div', 'opp-error', `목록을 불러오지 못했습니다. ${err.message}`));
    } finally { refreshBtn.disabled = false; }
  }

  refreshBtn.addEventListener('click', load);
  setInterval(load, 20000);  // 새 요청이 들어오면 20초 안에 보인다
  load();
})();
