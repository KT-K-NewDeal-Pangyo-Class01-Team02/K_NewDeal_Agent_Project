// '새 에이전트 추가' 팝업: 입력값을 /api/agents 로 보내 agents.json 에 저장한 뒤 새로고침
(function () {
  const dialog = document.getElementById('agent-dialog');
  const form = document.getElementById('agent-form');
  const errorEl = document.getElementById('agent-form-error');
  const submitBtn = form.querySelector('[type="submit"]');

  document.getElementById('agent-add-open').addEventListener('click', () => {
    form.reset();
    errorEl.textContent = '';
    dialog.showModal();
  });
  dialog.querySelectorAll('[data-close]').forEach((btn) => btn.addEventListener('click', () => dialog.close()));
  dialog.addEventListener('click', (event) => {
    if (event.target === dialog) dialog.close();
  });

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    errorEl.textContent = '';
    submitBtn.disabled = true;
    try {
      const res = await fetch('/api/agents', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(Object.fromEntries(new FormData(form))),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body.error || '저장하지 못했어요. 다시 시도해 주세요.');
      location.reload();
    } catch (err) {
      errorEl.textContent = err.message;
      submitBtn.disabled = false;
    }
  });
})();
