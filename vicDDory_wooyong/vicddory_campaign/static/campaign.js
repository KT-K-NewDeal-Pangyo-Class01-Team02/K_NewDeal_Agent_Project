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
  const approval = document.getElementById('approval');
  const approvalBadge = document.getElementById('approval-badge');
  const approvalText = document.getElementById('approval-text');
  const approvalBtn = document.getElementById('approval-btn');
  const reviseBtn = document.getElementById('revise-btn');
  let lastPlanMd = '';
  let planCampaignId = null;
  let pollTimer = null;
  let planShownAt = 0;  // 지금 보이는 기획안이 만들어진 시각 (반려 이후에 새로 만든 건지 판단)
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

  // 마크다운 → 문서 변환은 plan_render.js (지사 승인 화면과 같이 쓴다)
  const { esc, toHtml: markdownToHtml } = window.vicPlan;

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
    approval.hidden = true; stopPolling();
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
        store_id: storeSel.value, store_name: storeSel.selectedOptions[0].textContent, target_group: data.target_group,
        constraints: data.constraints, f02: result.f02, campaign_id: params.campaign_id,
      });
      lastPlanMd = body.plan || '';
      planCampaignId = params.campaign_id;
      showPlan(body.plan);
      planShownAt = Date.now();
      showApproval();
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

  // ---------- F-06 승인 요청 · 상태 반영 ----------
  const BADGE = { not_requested: '승인 요청 전', requested: '지사 승인 대기', approved: '승인됨', rejected: '반려' };
  const hhmm = (iso) => (iso ? new Date(iso).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' }) : '');
  function stopPolling() { if (pollTimer) { clearInterval(pollTimer); pollTimer = null; } }

  function renderApproval(c) {
    const st = (c && c.approval_status) || 'not_requested';
    approvalBadge.textContent = BADGE[st] || st;
    approvalBadge.className = `approval-badge is-${st}`;
    const last = c && c.last_decision;
    const round = (c && c.revision_round) || 0;
    // 반려 뒤에는 발의를 고쳐 새 기획안이 나온 경우에만 재요청할 수 있다
    const revisedAfterReject = st === 'rejected' && last && new Date(last.at).getTime() < planShownAt;
    approvalBtn.hidden = st === 'requested' || st === 'approved' || (st === 'rejected' && !revisedAfterReject);
    reviseBtn.hidden = st !== 'rejected' || revisedAfterReject;
    approvalBtn.textContent = st === 'rejected' ? '수정본으로 다시 승인 요청' : '지사 승인 요청';
    if (st === 'requested') approvalText.textContent = `${hhmm(c.requested_at)}에 요청했습니다. 지사가 승인하거나 반려하면 여기에 바로 표시됩니다.${round ? ` (수정 ${round}회차)` : ''}`;
    else if (st === 'approved') approvalText.textContent = `${last ? `${last.by} · ${hhmm(last.at)}` : ''} 승인되었습니다. 콜시트대로 출동을 준비하세요.${last && last.comment ? ` 코멘트: ${last.comment}` : ''}`;
    else if (st === 'rejected') approvalText.textContent = revisedAfterReject
      ? `수정 ${round}회차 기획안이 준비됐습니다. 지난 반려 사유: ${(last && last.comment) || '-'}`
      : `수정 ${round}회차 · 반려 사유: ${(last && last.comment) || '-'} → 캠페인 발의를 고쳐 다시 제출하면 새 기획안으로 재요청할 수 있습니다.`;
    else approvalText.textContent = '기획안을 확인했으면 지사에 승인을 요청하세요.';
    if (st === 'requested') startPolling(); else stopPolling();
  }

  async function refreshApproval() {
    try {
      const data = await post('/api/f06/status', { campaign_id: planCampaignId });
      renderApproval(data.campaign);
    } catch (err) { /* 잠깐의 네트워크 오류는 다음 확인 때 다시 시도한다 */ }
  }
  function startPolling() { if (!pollTimer) pollTimer = setInterval(refreshApproval, 8000); }

  function showApproval() {
    approval.hidden = false;
    if (!planCampaignId) {
      approvalBadge.textContent = '요청 불가';
      approvalBadge.className = 'approval-badge';
      approvalText.textContent = '승인 요청은 위 "이번 주 옥외 기회"에서 카드를 골라 시작한 캠페인만 할 수 있습니다.';
      approvalBtn.hidden = true; reviseBtn.hidden = true;
      return;
    }
    refreshApproval();  // 재제출이면 이전 반려 기록이 함께 보인다
  }

  approvalBtn.addEventListener('click', async () => {
    approvalBtn.disabled = true;
    try {
      const data = await post('/api/f06/submit', { campaign_id: planCampaignId, plan_markdown: lastPlanMd });
      renderApproval(data.campaign);
      window.ccToast(data.source === 'demo' ? '데모 모드: 지사 승인 화면에서 승인·반려를 눌러 보세요.' : '지사에 승인을 요청했습니다.');
    } catch (err) {
      window.ccToast(err.message);
      refreshApproval();
    } finally { approvalBtn.disabled = false; }
  });

  reviseBtn.addEventListener('click', () => {
    form.scrollIntoView({ behavior: 'smooth', block: 'start' });
    siteSel.focus();
  });

  loadOptions();
})();
