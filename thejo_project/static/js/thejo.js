// 더 줘 화면 동작: 조치 완료, 고객 안내 문자 모달, 혜택 시뮬레이션.
// 금액과 문자 본문은 서버(Python)가 만든다. 여기서는 표기만 바꾼다.
// n8n Webhook 주소는 이 파일에 오지 않는다. 서버에서만 읽는다.
(function () {
  const toast = window.ccToast || function () {};
  const won = (value) => `${Number(value).toLocaleString('ko-KR')}원`;

  // ── '조치 완료' 버튼 ────────────────────────────────────────────────────
  document.querySelectorAll('form[data-ack]').forEach((form) => {
    form.addEventListener('submit', (event) => {
      event.preventDefault();
      const button = form.querySelector('button');
      button.disabled = true;

      fetch(form.action, { method: 'POST', headers: { Accept: 'application/json' } })
        .then((res) => (res.ok ? res.json() : Promise.reject(res)))
        .then(() => {
          form.closest('.tj-warning').classList.add('is-done');
          button.textContent = '조치함';
          toast('조치 완료로 표시했어요.');
        })
        .catch(() => {
          button.disabled = false;
          toast('처리하지 못했어요. 새로고침 후 다시 시도해 주세요.');
        });
    });
  });

  // ── 고객 안내 문자 모달 ─────────────────────────────────────────────────
  const dialog = document.getElementById('sms-dialog');
  if (dialog) initSmsDialog(dialog);

  function initSmsDialog(dialog) {
    const form = dialog.querySelector('#sms-form');
    const textarea = dialog.querySelector('[data-sms-text]');
    const sendButton = dialog.querySelector('[data-sms-send]');
    const errorBox = dialog.querySelector('[data-sms-error]');
    const kindBox = dialog.querySelector('[data-sms-kind]');
    const bytesBox = dialog.querySelector('[data-sms-bytes]');
    const charsBox = dialog.querySelector('[data-sms-chars]');
    const chips = Array.from(dialog.querySelectorAll('[data-template-id]'));
    const byteLimit = Number(dialog.querySelector('[data-sms-text]').dataset.limit || 90);

    let current = null; // { transaction, templates, card }

    // 한글은 2바이트. 서버(sms_service.message_bytes)와 같은 규칙이어야 한다.
    const byteLength = (text) =>
      Array.from(text || '').reduce((sum, ch) => sum + (ch.codePointAt(0) < 128 ? 1 : 2), 0);

    function refreshCounter() {
      const text = textarea.value;
      const bytes = byteLength(text);
      bytesBox.textContent = bytes;
      charsBox.textContent = Array.from(text).length;

      const isLms = bytes > byteLimit;
      kindBox.textContent = isLms ? 'LMS' : 'SMS';
      kindBox.classList.toggle('is-lms', isLms);

      // 내용이 있고 전화번호가 있어야 전송 가능
      const hasPhone = Boolean(current && current.transaction.customer_phone);
      sendButton.disabled = !text.trim() || !hasPhone;
    }

    function fill(tx) {
      dialog.querySelectorAll('[data-tx]').forEach((cell) => {
        const key = cell.dataset.tx;
        const value = tx[key];
        if (key === 'expected_clawback' || key === 'benefit_amount') cell.textContent = won(value);
        else if (key === 'required_maintenance_days' || key === 'remaining_days' || key === 'maintained_days')
          cell.textContent = `${value}일`;
        else cell.textContent = value || '—';
      });
    }

    function open(card) {
      const transactionId = card.dataset.transactionId;
      errorBox.textContent = '';
      textarea.value = '';
      chips.forEach((chip) => chip.classList.remove('is-active'));
      sendButton.disabled = true;

      fetch(`${dialog.dataset.txUrl}${encodeURIComponent(transactionId)}`, {
        headers: { Accept: 'application/json' },
      })
        .then((res) => (res.ok ? res.json() : Promise.reject(res)))
        .then((data) => {
          current = { transaction: data.transaction, templates: data.templates, card };
          fill(data.transaction);

          if (!data.transaction.customer_phone) {
            errorBox.textContent = '이 고객은 전화번호가 없어 문자를 보낼 수 없습니다.';
          }
          refreshCounter();
          if (!dialog.open) dialog.showModal();
        })
        .catch(() => toast('거래 정보를 불러오지 못했어요.'));
    }

    function close() {
      textarea.value = '';
      errorBox.textContent = '';
      chips.forEach((chip) => chip.classList.remove('is-active'));
      current = null;
      dialog.close();
    }

    // 카드의 '거래 확인' 버튼
    document.querySelectorAll('[data-open-sms]').forEach((button) => {
      button.addEventListener('click', () => open(button.closest('.tj-warning')));
    });

    // 템플릿 칩 → 치환된 본문을 textarea 에 넣는다 (서버가 이미 치환해 보냈다)
    chips.forEach((chip) => {
      chip.addEventListener('click', () => {
        if (!current) return;
        const template = current.templates.find((t) => t.id === chip.dataset.templateId);
        if (!template) return;
        textarea.value = template.body;
        chips.forEach((c) => c.classList.toggle('is-active', c === chip));
        refreshCounter();
        textarea.focus();
      });
    });

    textarea.addEventListener('input', () => {
      // 직접 고치면 템플릿 선택 표시를 풀되, template_id 는 유지한다
      refreshCounter();
    });

    dialog.querySelectorAll('[data-sms-close]').forEach((button) => {
      button.addEventListener('click', close);
    });
    // ESC 로 닫을 때도 입력을 비운다
    dialog.addEventListener('cancel', (event) => {
      event.preventDefault();
      close();
    });

    form.addEventListener('submit', (event) => {
      event.preventDefault();
      if (!current || sendButton.disabled) return;

      const tx = current.transaction;
      if (!window.confirm(`${tx.customer_name} 고객님에게 안내 문자를 전송하시겠습니까?`)) return;

      const activeChip = chips.find((c) => c.classList.contains('is-active'));
      errorBox.textContent = '';
      sendButton.disabled = true;

      fetch(dialog.dataset.sendUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({
          transaction_id: tx.transaction_id,
          template_id: activeChip ? activeChip.dataset.templateId : null,
          message: textarea.value,
        }),
      })
        .then((res) => res.json().then((body) => (res.ok && body.success ? body : Promise.reject(body))))
        .then((body) => {
          markSent(current.card, body.sent_at);
          close();
          toast('문자 발송 요청이 완료되었습니다');
        })
        .catch((body) => {
          // 실패하면 모달을 닫지 않는다. 고치고 다시 보낼 수 있게 둔다.
          sendButton.disabled = false;
          errorBox.textContent = (body && body.error) || '문자를 보내지 못했어요. 잠시 후 다시 시도해 주세요.';
        });
    });

    function markSent(card, sentAt) {
      if (!card) return;
      const badge = card.querySelector('[data-sms-badge]');
      if (!badge) return;
      badge.hidden = false;
      const time = badge.querySelector('[data-sms-time]');
      if (time && sentAt) time.textContent = sentAt.slice(0, 16).replace('T', ' ');
    }
  }

  // ── 혜택 시뮬레이션 ────────────────────────────────────────────────────
  // 첫 화면은 서버가 채운다. 여기서는 (1) 카드 선택 (2) 계산하기 때 서버에 다시 물어 같은 칸을 갈아 끼운다.
  // 금액은 서버 응답을 그대로 쓰고, 표기(쉼표·원)만 바꾼다.
  const sim = document.getElementById('simulator');
  if (!sim) return;

  const simForm = sim.querySelector('[data-sim-form]');
  const input = sim.querySelector('[data-sim-input]');
  const errorBox = sim.querySelector('[data-sim-error]');
  const pickBox = sim.querySelector('[data-sim-pick-box]');
  const warnBox = sim.querySelector('[data-sim-warn]');
  const resultBox = sim.querySelector('[data-sim-result]');
  const missingBox = sim.querySelector('[data-sim-missing]');

  const MONEY = new Set([
    'tier_gain', 'minimum_secured_profit', 'benefit_budget',
    'per_unit', 'next_per_unit', 'monthly_incentive',
  ]);
  const isEmpty = (v) => v === null || v === undefined || v === '';

  function render(data) {
    sim.querySelectorAll('[data-sim]').forEach((el) => {
      const value = data[el.dataset.sim];
      if (isEmpty(value)) el.textContent = '—';
      else el.textContent = MONEY.has(el.dataset.sim) ? won(value) : String(value);
    });
    // 시트에 없는 값(건당·총 인센티브 등)은 칸째 숨긴다
    sim.querySelectorAll('[data-sim-row]').forEach((row) => {
      row.hidden = isEmpty(data[row.dataset.simRow]);
    });
    sim.querySelector('[data-sim-note]').hidden = isEmpty(data.note);
    warnBox.hidden = !data.shortfall;
    resultBox.classList.toggle('is-zero', !data.benefit_budget);
    if (missingBox) missingBox.hidden = data.basis !== 'insight';
  }

  function calculate() {
    errorBox.textContent = '';
    const params = new URLSearchParams({ units: input.value });
    // 선택한 기회를 같이 보낸다. 서버가 최신 인사이트에서 다시 찾아 계산한다.
    if (pickBox.dataset.insightId) params.set('insight_id', pickBox.dataset.insightId);
    if (pickBox.dataset.device) params.set('device_model_name', pickBox.dataset.device);
    if (pickBox.dataset.plan) params.set('plan_code', pickBox.dataset.plan);

    return fetch(`${sim.dataset.simUrl}?${params}`, { headers: { Accept: 'application/json' } })
      .then((res) => res.json().then((body) => (res.ok ? body : Promise.reject(body))))
      .then(render)
      .catch((body) => {
        errorBox.textContent = (body && body.error) || '계산하지 못했어요. 잠시 후 다시 시도해 주세요.';
      });
  }

  // 판매 건수를 직접 바꿔 계산하기 (기존 기능)
  simForm.addEventListener('submit', (event) => {
    event.preventDefault();
    calculate();
  });

  // 수익 기회 카드의 '혜택 시뮬레이션' → 그 카드로 바로 교체
  document.querySelectorAll('[data-sim-pick]').forEach((button) => {
    button.addEventListener('click', (event) => {
      event.preventDefault();
      const id = button.dataset.insightId;

      pickBox.dataset.insightId = id;
      pickBox.dataset.device = button.dataset.device || '';
      pickBox.dataset.plan = button.dataset.plan || '';
      input.value = button.dataset.current;
      document.querySelectorAll('[data-insight-card]').forEach((card) => {
        card.classList.toggle('is-selected', card.dataset.insightCard === id);
      });

      // 새로고침해도 같은 카드가 선택되도록 주소에 남긴다
      try {
        const url = new URL(window.location.href);
        url.searchParams.set('insight', id);
        url.hash = 'simulator';
        window.history.replaceState(null, '', url);
      } catch (_) { /* 주소 갱신 실패는 무시 */ }

      sim.scrollIntoView({ behavior: 'smooth', block: 'start' });
      calculate();
    });
  });
})();
