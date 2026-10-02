// 통하길 QR 담당자 화면: 관리자 에이전트 채팅
(function () {
  const panel = document.getElementById('agent');
  if (!panel) return;

  const form = document.getElementById('agent-form');
  const log = document.getElementById('agent-log');
  const input = document.getElementById('agent-input');
  const send = document.getElementById('agent-send');
  const session = sessionId();

  document.getElementById('agent-suggest').addEventListener('click', (event) => {
    const chip = event.target.closest('[data-ask]');
    if (!chip) return;
    input.value = chip.dataset.ask;
    form.requestSubmit();
  });

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const message = input.value.trim();
    if (!message || send.disabled) return;

    addMessage('user', message);
    input.value = '';
    const pending = addMessage('bot', '');
    pending.querySelector('p').innerHTML = '<span class="s-typing"><i></i><i></i><i></i></span>';
    send.disabled = true;

    try {
      // 주소는 서버가 url_for 로 만들어 준 것을 쓴다 (허브·ngrok 어디서 열어도 같은 서버로 간다)
      const res = await fetch(panel.dataset.api, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, session }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body.error || '답변을 받지 못했어요. 다시 시도해 주세요.');
      pending.querySelector('p').textContent = body.reply;
    } catch (err) {
      pending.classList.add('is-error');
      pending.querySelector('p').textContent = err.message;
    } finally {
      send.disabled = false;
      log.scrollTop = log.scrollHeight;
      input.focus();
    }
  });

  function addMessage(role, text) {
    const msg = document.createElement('div');
    msg.className = `s-msg s-msg-${role}`;
    const p = document.createElement('p');
    p.textContent = text;
    msg.append(p);
    log.append(msg);
    log.scrollTop = log.scrollHeight;
    return msg;
  }

  // 대화 기억(n8n Memory)을 브라우저 탭마다 나눈다. 탭을 닫으면 새 대화로 시작한다.
  function sessionId() {
    const key = 'tq_staff_chat';
    try {
      let id = sessionStorage.getItem(key);
      if (!id) {
        id = window.crypto && crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2, 14)}`;
        sessionStorage.setItem(key, id);
      }
      return id;
    } catch (_e) {
      return '';
    }
  }
})();
