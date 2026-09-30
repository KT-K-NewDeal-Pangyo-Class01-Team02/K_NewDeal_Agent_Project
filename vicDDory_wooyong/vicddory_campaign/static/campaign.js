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

  function showPlan(text) { planText.textContent = text; planText.hidden = false; planEmpty.hidden = true; copyBtn.hidden = false; }
  function showWaiting(message) {
    planText.hidden = true; planEmpty.hidden = false; copyBtn.hidden = true;
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

  copyBtn.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(planText.textContent);
      copyLabel.textContent = '복사됨';
      setTimeout(() => { copyLabel.textContent = '복사'; }, 1600);
    } catch (err) {
      window.ccToast('복사하지 못했어요. 텍스트를 직접 선택해 주세요.');
    }
  });

  loadOptions();
})();
