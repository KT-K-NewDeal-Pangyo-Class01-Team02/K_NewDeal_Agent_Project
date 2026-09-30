// 빅또리출동! 캠페인 발의 (F-02 제약 검증 → 통과 시 기획안 생성)
// 브라우저는 Flask(/api/f02/*, /api/plan)만 부르고, n8n 호출은 Flask 가 대신한다.
(function () {
  const form = document.getElementById('brief-form');
  const submitBtn = document.getElementById('submit-btn');
  const submitLabel = submitBtn.querySelector('span');
  const errorBox = document.getElementById('form-error');
  const constraints = document.getElementById('constraints');
  const counter = document.getElementById('counter');
  const storeSel = document.getElementById('f-store');
  const dateInput = document.getElementById('f-date');
  const hoursSel = document.getElementById('f-hours');
  const siteSel = document.getElementById('f-site');
  const staffSels = [...form.querySelectorAll('.staff-select')];
  const staffHint = document.getElementById('f-staff-hint');
  const rewardSel = document.getElementById('f-reward');
  const rewardHint = document.getElementById('f-reward-hint');
  const campaignInput = document.getElementById('f-campaign-id');
  const linked = document.getElementById('f-linked');
  const checksBox = document.getElementById('checks');
  const planBox = document.getElementById('plan-box');
  const planEmpty = document.getElementById('plan-empty');
  const planText = document.getElementById('plan-text');
  const copyBtn = document.getElementById('copy-btn');
  const copyLabel = copyBtn.querySelector('span');
  const pdfBtn = document.getElementById('pdf-btn');
  let lastSiteName = '';
  let staff = [];
  let optionsSeq = 0;

  const el = (tag, cls, text) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const option = (value, label) => { const o = el('option', null, label); o.value = value; return o; };

  async function post(url, body) {
    const response = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || '요청을 처리하지 못했어요.');
    return data;
  }

  function updateCounter() { counter.textContent = `${constraints.value.length}/${constraints.maxLength}`; }
  constraints.addEventListener('input', updateCounter);
  updateCounter();

  // ---------- 근무자 · 장소 · 사은품 불러오기 ----------
  function covers(s) { const [a, b] = hoursSel.value.split('-'); return s.start_time <= a && s.end_time >= b; }

  function renderStaff() {
    const keep = staffSels.map((s) => s.value);
    staffSels.forEach((sel, i) => {
      sel.replaceChildren(option('', staff.length ? `출동 인력 ${i + 1} 선택` : '그날 근무자가 없습니다'));
      staff.forEach((s) => {
        const o = option(s.employee_id, `${s.employee_name} · ${s.employment_type} ${s.start_time}~${s.end_time}${covers(s) ? '' : ' (시간대 밖)'}`);
        sel.append(o);
      });
      if (staff.some((s) => s.employee_id === keep[i])) sel.value = keep[i];
    });
    const avail = staff.filter(covers);
    const reg = avail.filter((s) => s.employment_type === '정규직').length;
    staffHint.textContent = staff.length ? `이 시간대 근무 ${avail.length}명 (정규직 ${reg}명) · 출동 2명을 빼고 매장에 2명 이상, 정규직 1명 이상 남아야 합니다.` : '';
    staffHint.classList.toggle('is-warn', avail.length < 4 || reg < 2);
  }

  async function loadOptions() {
    const seq = ++optionsSeq;
    if (!dateInput.value) return;
    staffSels.forEach((s) => s.replaceChildren(option('', '근무표 불러오는 중…')));
    try {
      const data = await post('/api/f02/options', { store_id: storeSel.value, target_date: dateInput.value });
      if (seq !== optionsSeq) return;  // 더 최근 요청이 있으면 버린다
      staff = data.staff || [];
      renderStaff();
      if (!data.roster_found) { staffHint.textContent = `${dateInput.value} 근무표가 없습니다.`; staffHint.classList.add('is-warn'); }

      const siteKeep = siteSel.value;
      siteSel.replaceChildren(option('', '운영 장소 선택'));
      (data.sites || []).forEach((s) => siteSel.append(option(s.site_id, `${s.site_name} · 매장까지 ${s.distance_to_store_m}m`)));
      if ([...siteSel.options].some((o) => o.value === siteKeep)) siteSel.value = siteKeep;

      const rewardKeep = rewardSel.value;
      rewardSel.replaceChildren(option('', '없음'));
      (data.rewards || []).forEach((r) => { const o = option(r.item_name, `${r.item_name} (재고 ${r.quantity})`); o.dataset.qty = r.quantity; rewardSel.append(o); });
      if ([...rewardSel.options].some((o) => o.value === rewardKeep)) rewardSel.value = rewardKeep;
      updateRewardHint();
    } catch (err) {
      if (seq !== optionsSeq) return;
      staff = [];
      renderStaff();
      staffHint.textContent = err.message;
      staffHint.classList.add('is-warn');
    }
  }

  function updateRewardHint() {
    const o = rewardSel.selectedOptions[0];
    rewardHint.textContent = o && o.dataset.qty ? `매장 재고 ${o.dataset.qty}개` : '';
  }

  storeSel.addEventListener('change', loadOptions);
  dateInput.addEventListener('change', loadOptions);
  hoursSel.addEventListener('change', renderStaff);
  rewardSel.addEventListener('change', updateRewardHint);

  // F-01 에서 카드를 고르면 매장 · 날짜 · 캠페인 번호를 받아 온다
  document.addEventListener('vicddory:campaign-selected', (event) => {
    const d = event.detail;
    storeSel.value = d.store_id;
    if (d.target_date) dateInput.value = d.target_date;
    campaignInput.value = typeof d.campaign_id === 'number' ? d.campaign_id : '';
    linked.textContent = `F-01 카드 "${d.title}" · 캠페인 ${d.campaign_id} 에 이어서 발의합니다.`;
    linked.hidden = false;
    loadOptions();
  });

  // ---------- 제출: F-02 검증 → 기획안 ----------
  function renderChecks(result) {
    checksBox.replaceChildren(el('li', 'checks-head', result.isValid ? 'F-02 제약 검증 통과' : 'F-02 제약 검증 실패: 아래 항목을 고쳐 주세요'));
    (result.checks || []).forEach((c) => {
      const li = el('li', `is-${c.level}`);
      li.append(el('b', null, c.code), el('span', null, `${c.label} · ${c.message}`));
      checksBox.append(li);
    });
    checksBox.hidden = false;
  }

  // ---------- 기획안: 마크다운 → 문서 ----------
  const esc = (t) => t.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const inline = (t) => esc(t).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/`([^`]+)`/g, '<code>$1</code>');
  const cells = (line) => line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((c) => c.trim());

  function markdownToHtml(md) {
    const lines = md.replace(/\r/g, '').split('\n');
    const out = [];
    const stack = [];  // 열린 목록 [{ kind, indent }] — 들여쓰기로 하위 목록을 만든다
    const closeOne = () => { const top = stack.pop(); out.push(`</li></${top.kind}>`); };
    const closeAll = () => { while (stack.length) closeOne(); };
    for (let i = 0; i < lines.length; i += 1) {
      const line = lines[i];
      const t = line.trim();
      if (!t) continue;  // 빈 줄은 목록을 끊지 않는다 (번호가 1부터 다시 시작하지 않게)
      if (/^\|.*\|$/.test(t) && lines[i + 1] && /^\|?\s*:?-{2,}/.test(lines[i + 1].trim())) {
        closeAll();
        const head = cells(t);
        const rows = [];
        i += 2;
        while (i < lines.length && /^\|.*\|$/.test(lines[i].trim())) { rows.push(cells(lines[i])); i += 1; }
        i -= 1;
        out.push('<div class="plan-table-wrap"><table><thead><tr>' + head.map((c) => `<th>${inline(c)}</th>`).join('') +
          '</tr></thead><tbody>' + rows.map((r) => '<tr>' + r.map((c) => `<td>${inline(c)}</td>`).join('') + '</tr>').join('') + '</tbody></table></div>');
        continue;
      }
      const h = t.match(/^(#{1,6})\s+(.*)$/);
      if (h) { closeAll(); const lv = Math.min(4, Math.max(2, h[1].length - 1)); out.push(`<h${lv}>${inline(h[2])}</h${lv}>`); continue; }
      const m = line.match(/^(\s*)(?:([-*])|(\d+)[.)])\s+(.*)$/);
      if (m) {
        const indent = m[1].replace(/\t/g, '  ').length;
        const kind = m[2] ? 'ul' : 'ol';
        while (stack.length && stack[stack.length - 1].indent > indent) closeOne();
        const top = stack[stack.length - 1];
        if (top && top.indent === indent) {
          if (top.kind !== kind) { closeOne(); out.push(`<${kind}>`); stack.push({ kind, indent }); } else out.push('</li>');
        } else { out.push(`<${kind}>`); stack.push({ kind, indent }); }
        out.push(`<li>${inline(m[4])}`);
        continue;
      }
      if (/^-{3,}$/.test(t)) { closeAll(); continue; }
      if (stack.length && /^\s{2,}/.test(line)) { out.push(`<br>${inline(t)}`); continue; }  // 목록 항목의 이어지는 줄
      closeAll();
      out.push(`<p>${inline(t)}</p>`);
    }
    closeAll();
    return out.join('');
  }

  // 입지 섹션 아래에 캠페인 이미지 자리를 둔다 (지금은 시안 자리, 이후 생성 이미지로 교체)
  function siteVisual(siteName) {
    const fig = el('figure', 'site-visual');
    const name = esc(siteName || '추천 입지');
    fig.innerHTML = `
      <svg viewBox="0 0 640 220" role="img" aria-label="${name} 캠페인 이미지 자리">
        <rect width="640" height="220" fill="#fff4e8"/>
        <rect x="0" y="150" width="640" height="70" fill="#f3dcc0"/>
        <circle cx="560" cy="52" r="26" fill="#ffd28a"/>
        <rect x="236" y="70" width="168" height="84" rx="8" fill="#fff" stroke="#d46b12" stroke-width="3"/>
        <path d="M226 74 L320 36 L414 74 Z" fill="#d46b12"/>
        <text x="320" y="106" text-anchor="middle" font-size="18" font-weight="800" fill="#d46b12">빅또리출동!</text>
        <text x="320" y="132" text-anchor="middle" font-size="13" fill="#8a4a0c">${name}</text>
        <circle cx="178" cy="150" r="10" fill="#8a4a0c"/><rect x="170" y="160" width="16" height="30" rx="6" fill="#8a4a0c"/>
        <circle cx="462" cy="150" r="10" fill="#8a4a0c"/><rect x="454" y="160" width="16" height="30" rx="6" fill="#8a4a0c"/>
        <text x="320" y="204" text-anchor="middle" font-size="12" fill="#8a4a0c">캠페인 이미지 자리 · 현장 부스 시안이 여기에 들어갑니다</text>
      </svg>
      <figcaption><span>${name} 현장 부스 · 홍보 포스터 이미지 (예정)</span>
        <a href="${esc(planBox.dataset.tonghagil || 'http://localhost:5004')}" target="_blank" rel="noopener">통하길 스튜디오에서 포스터 만들기 ↗</a></figcaption>`;
    return fig;
  }

  function showPlan(text) {
    planText.innerHTML = markdownToHtml(text || '');
    const siteHead = [...planText.querySelectorAll('h2, h3, h4')].find((h) => h.textContent.includes('입지'));
    if (siteHead) {
      // 입지 섹션의 첫 목록·문단 다음에 이미지를 둔다
      let anchor = siteHead;
      while (anchor.nextElementSibling && !/^H[2-4]$/.test(anchor.nextElementSibling.tagName) && anchor === siteHead) anchor = anchor.nextElementSibling;
      anchor.after(siteVisual(lastSiteName));
    }
    planText.hidden = false; planEmpty.hidden = true; copyBtn.hidden = false; pdfBtn.hidden = false;
  }
  function showWaiting(message) {
    planText.hidden = true; planEmpty.hidden = false; copyBtn.hidden = true; pdfBtn.hidden = true;
    planEmpty.querySelector('p').textContent = message;
  }
  function setBusy(label) {
    submitBtn.disabled = !!label;
    planBox.classList.toggle('is-loading', label === '기획서 생성 중…');
    submitLabel.textContent = label || '캠페인 발의 제출';
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    errorBox.textContent = '';
    const data = Object.fromEntries(new FormData(form).entries());
    const params = {
      store_id: data.store_id, target_date: data.target_date, operating_hours: data.operating_hours,
      target_group: data.target_group, site_id: data.site_id,
      staff_ids: [data.staff_1, data.staff_2].filter(Boolean),
      budget: data.budget === '' ? null : Number(data.budget),
      reward_item: data.reward_item, reward_qty: data.reward_qty === '' ? 0 : Number(data.reward_qty),
      constraints: data.constraints, campaign_id: data.campaign_id ? Number(data.campaign_id) : null,
    };

    setBusy('제약 검증 중…');
    let result;
    try {
      result = await post('/api/f02/validate', params);
      renderChecks(result);
    } catch (err) {
      errorBox.textContent = err.message;
      window.ccToast(err.message);
      setBusy(null);
      return;
    }
    if (!result.isValid) {
      showWaiting('제약 검증을 통과하면 입지 분석과 카피, 콜시트를 편성합니다.');
      setBusy(null);
      return;
    }

    lastSiteName = (result.f02 && result.f02.site_name) || (siteSel.selectedOptions[0] && siteSel.value ? siteSel.selectedOptions[0].textContent.split(' · ')[0] : '');
    setBusy('기획서 생성 중…');
    showWaiting('n8n 에이전트가 입지 분석과 카피, 콜시트를 편성하고 있습니다…');
    try {
      const body = await post('/api/plan', {
        store_name: storeSel.selectedOptions[0].textContent, target_group: data.target_group,
        constraints: data.constraints, f02: result.f02, campaign_id: params.campaign_id,
      });
      showPlan(body.plan);
      if (body.source === 'demo' || result.source === 'demo') window.ccToast('데모 모드예요. .env 에 n8n 주소를 넣으면 실제로 검증·생성합니다.');
    } catch (err) {
      errorBox.textContent = err.message;
      showWaiting('기획안을 만들지 못했습니다. 다시 제출해 주세요.');
      window.ccToast(err.message);
    } finally {
      setBusy(null);
    }
  });

  // 서식 복사: 워드 · 한글 · 구글 문서에 붙이면 표와 굵은 글씨가 그대로 살아 있다
  const DOC_CSS = 'body{font-family:"Malgun Gothic","Apple SD Gothic Neo",sans-serif;font-size:11pt;line-height:1.7;color:#111}' +
    'h2{font-size:17pt}h3{font-size:14pt;border-bottom:1px solid #ccc;padding-bottom:4px}h4{font-size:12pt}' +
    'table{border-collapse:collapse;width:100%;margin:8px 0}th,td{border:1px solid #bbb;padding:6px 8px;text-align:left;vertical-align:top}th{background:#f2f2f2}' +
    'figure{margin:10px 0;border:1px solid #ddd}figure svg{width:100%;height:auto}figcaption{font-size:9pt;padding:6px 10px;color:#555}figcaption a{display:none}';
  const docHtml = () => `<h2>${esc(storeSel.selectedOptions[0].textContent)} 옥외 BTL 기획 확정안</h2>${planText.innerHTML}`;

  copyBtn.addEventListener('click', async () => {
    const html = `<style>${DOC_CSS}</style>${docHtml()}`;
    try {
      if (window.ClipboardItem) {
        await navigator.clipboard.write([new ClipboardItem({
          'text/html': new Blob([html], { type: 'text/html' }),
          'text/plain': new Blob([planText.innerText], { type: 'text/plain' }),
        })]);
      } else {
        await navigator.clipboard.writeText(planText.innerText);
      }
      copyLabel.textContent = '복사됨';
      setTimeout(() => { copyLabel.textContent = '서식 복사'; }, 1600);
    } catch (err) {
      window.ccToast('복사하지 못했어요. 문서를 직접 선택해 주세요.');
    }
  });

  // PDF 저장: 기획안만 담은 인쇄 창을 열어 'PDF로 저장'을 고르게 한다
  pdfBtn.addEventListener('click', () => {
    const w = window.open('', '_blank');
    if (!w) { window.ccToast('팝업이 막혔어요. 이 사이트의 팝업을 허용해 주세요.'); return; }
    w.document.write(`<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>빅또리출동! 기획 확정안</title>
      <style>@page{size:A4;margin:16mm}${DOC_CSS}</style></head><body>${docHtml()}</body></html>`);
    w.document.close();
    w.focus();
    setTimeout(() => w.print(), 300);
  });

  loadOptions();
})();
