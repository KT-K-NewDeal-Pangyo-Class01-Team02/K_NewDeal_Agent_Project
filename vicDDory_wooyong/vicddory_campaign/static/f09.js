// 빅또리출동! F-09 성과 환류: 지난 캠페인 POS 퍼널 → 차기 기준선 제안 (Flask /api/f09/report → n8n F09_report)
(function () {
  const $ = (id) => document.getElementById(id);
  const storeSel = $('f09-store'), btn = $('f09-btn'), meta = $('f09-meta');
  const pct = (x) => `${((x || 0) * 100).toFixed(1)}%`;
  const num = (n) => Number(n || 0).toLocaleString('ko-KR');
  const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text !== undefined) n.textContent = text; return n; };

  function bars(box, rows, bestKey, label) {
    const max = Math.max(0.01, ...rows.map((r) => r.visit_rate));
    box.replaceChildren(...rows.map((r) => {
      const row = el('div', `hour-bar${r.key === bestKey ? ' is-best' : ''}`);
      const track = el('i'); const fill = el('b'); fill.style.width = `${(r.visit_rate / max) * 100}%`; track.append(fill);
      row.append(el('span', null, label(r)), track, el('span', null, `${pct(r.visit_rate)} · ${num(r.visits)}/${num(r.booth)}명`));
      return row;
    }));
    if (!rows.length) box.replaceChildren(el('p', 'f09-mix', '집계할 데이터가 없습니다.'));
  }

  async function load() {
    btn.disabled = true;
    meta.textContent = 'POS 퍼널을 집계하고 있습니다…';
    try {
      const res = await fetch('/api/f09/report', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ store_id: storeSel.value }) });
      const d = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(d.error || '성과 리포트를 불러오지 못했어요.');
      const t = d.totals || {}, b = d.baseline || {};
      $('f09-booth').textContent = `${num(t.booth)}명`;
      $('f09-booth-sub').textContent = `지난 캠페인 ${(d.campaigns || []).length || '-'}건 합계`;
      $('f09-visit').textContent = pct(t.visit_rate);
      $('f09-visit-sub').textContent = `${num(t.visits)}명 내방`;
      $('f09-acts').textContent = `${num(t.acts)}건`;
      $('f09-acts-sub').textContent = `내방 대비 ${pct(t.act_rate)}`;
      $('f09-base').textContent = `내방 ${pct(b.visit_rate)}`;
      $('f09-base-sub').textContent = `개통 ${pct(b.act_rate)} 이상을 목표로`;
      bars($('f09-hours'), d.by_hour || [], b.best_slot, (r) => r.key.replace('-', '~'));
      bars($('f09-types'), d.by_type || [], b.best_type, (r) => r.key);
      $('f09-mix').textContent = Object.entries(d.mix || {}).map(([k, v]) => `${k} ${v}건`).join(' · ') || '–';
      $('f09-insight').textContent = d.insight || '';
      meta.textContent = [d.period ? `${d.period.from} ~ ${d.period.to} 캠페인` : '', ...(d.dataTags || []), d.source === 'demo' ? '데모 데이터' : (d.llm ? 'LLM 제안' : '계산 기반 제안')].filter(Boolean).join(' · ');
    } catch (err) {
      meta.textContent = `불러오지 못했습니다. ${err.message}`;
    } finally { btn.disabled = false; }
  }

  btn.addEventListener('click', load);
  storeSel.addEventListener('change', load);
  load();
})();
