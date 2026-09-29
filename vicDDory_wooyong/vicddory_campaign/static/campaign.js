// 빅또리: 캠페인 파라미터를 Flask 로 보내고, 돌아온 기획안을 오른쪽 패널에 그린다.
(function () {
  const form = document.getElementById('brief-form');
  const submitBtn = document.getElementById('submit-btn');
  const submitLabel = submitBtn.querySelector('span');
  const errorBox = document.getElementById('form-error');
  const constraints = document.getElementById('constraints');
  const counter = document.getElementById('counter');
  const planBox = document.getElementById('plan-box');
  const planEmpty = document.getElementById('plan-empty');
  const planText = document.getElementById('plan-text');
  const copyBtn = document.getElementById('copy-btn');
  const copyLabel = copyBtn.querySelector('span');

  function updateCounter() {
    counter.textContent = `${constraints.value.length}/${constraints.maxLength}`;
  }
  constraints.addEventListener('input', updateCounter);
  updateCounter();

  function showPlan(text) {
    planText.textContent = text;
    planText.hidden = false;
    planEmpty.hidden = true;
    copyBtn.hidden = false;
  }

  function showWaiting(message) {
    planText.hidden = true;
    planEmpty.hidden = false;
    planEmpty.querySelector('p').innerHTML = message;
    copyBtn.hidden = true;
  }

  function setBusy(busy) {
    submitBtn.disabled = busy;
    planBox.classList.toggle('is-loading', busy);
    submitLabel.textContent = busy ? '에이전트 연산 중…' : 'BTL 기획서 생성';
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    errorBox.textContent = '';
    setBusy(true);
    showWaiting('n8n 에이전트가 입지 분석과 카피, 콜시트를 편성하고 있습니다…');

    const data = Object.fromEntries(new FormData(form).entries());

    try {
      const response = await fetch('/api/plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          store_name: data.store_name,
          target_group: data.target_group,
          constraints: data.constraints,
        }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || '기획안을 만들지 못했어요.');

      showPlan(body.plan);
      if (body.source === 'demo') {
        window.ccToast('데모 모드예요. .env 에 N8N_WEBHOOK_URL 을 넣으면 실제 기획안이 생성됩니다.');
      }
    } catch (err) {
      errorBox.textContent = err.message;
      showWaiting('왼쪽에 현장 조건을 입력하고 <strong>BTL 기획서 생성</strong>을 눌러 주세요.');
      window.ccToast(err.message);
    } finally {
      setBusy(false);
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
})();
