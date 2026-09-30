// 통하길 QR 방문객 화면: 통신 상태 갱신(홈·지도) · 쿠폰 지급 확인(스탬프) · 안내 챗봇
(function () {
  // 기준 주소(예: /qr/). 허브·ngrok 어디서 열어도 같은 서버의 API 를 부르도록 여기서만 주소를 만든다.
  const base = document.body.dataset.base;
  const api = (path) => base + path;

  // ---------------- 통신 상태 (모의) ----------------
  // data-net="best|queue|wait|updated" 글자, data-zone 요소의 data-level 과 data-field 를 바꾼다.
  if (document.querySelector('[data-net]')) {
    setInterval(refreshNetwork, 30000);
  }

  async function refreshNetwork() {
    try {
      const res = await fetch(api('api/network'));
      if (!res.ok) return;
      const net = await res.json();
      setText('best', net.best.name);
      setText('queue', net.booth.queue);
      setText('wait', net.booth.wait_min);
      setText('updated', net.updated_at);
      // 카카오맵(qr_map.js)도 같은 값으로 구역 색을 바꾸게 알린다
      document.dispatchEvent(new CustomEvent('qr:network', { detail: net }));
      net.zones.forEach((zone) => {
        document.querySelectorAll(`[data-zone="${zone.id}"]`).forEach((el) => {
          el.dataset.level = zone.level;
          el.querySelectorAll('[data-field="label"]').forEach((f) => { f.textContent = zone.label; });
          el.querySelectorAll('[data-field="users"]').forEach((f) => { f.textContent = zone.users; });
          el.querySelectorAll('[data-field="speed"]').forEach((f) => { f.textContent = zone.speed_mbps; });
        });
      });
    } catch {
      // 잠깐 끊겨도 다음 주기에 다시 시도한다
    }
  }

  function setText(name, value) {
    document.querySelectorAll(`[data-net="${name}"]`).forEach((el) => { el.textContent = value; });
  }

  // ---------------- 쿠폰 지급 확인 ----------------
  // 부스에서 지급 처리하면 방문객 화면이 스스로 '지급 완료'로 바뀌게 5초마다 확인한다.
  if (document.querySelector('[data-coupon-pending]')) {
    const timer = setInterval(async () => {
      try {
        const res = await fetch(api('api/me'));
        const me = await res.json();
        if (me.coupon && me.coupon.redeemed) {
          clearInterval(timer);
          window.location.reload();
        }
      } catch {
        // 다음 주기에 다시 확인
      }
    }, 5000);
  }

  // ---------------- 안내 챗봇 ----------------
  const chatForm = document.getElementById('chat-form');
  if (!chatForm) return;

  const log = document.getElementById('chat-log');
  const input = document.getElementById('chat-input');
  const send = document.getElementById('chat-send');

  log.addEventListener('click', (event) => {
    const chip = event.target.closest('[data-ask]');
    if (!chip) return;
    input.value = chip.dataset.ask;
    chatForm.requestSubmit();
  });

  input.addEventListener('input', autoGrow);
  input.addEventListener('keydown', (event) => {
    // 한글 입력 조합 중 Enter 는 무시 (글자가 두 번 전송되는 문제 방지)
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      chatForm.requestSubmit();
    }
  });

  chatForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const message = input.value.trim();
    if (!message || send.disabled) return;

    addMessage('user', message);
    input.value = '';
    autoGrow();
    const pending = addMessage('bot', '');
    pending.querySelector('p').innerHTML = '<span class="q-typing"><i></i><i></i><i></i></span>';
    send.disabled = true;

    try {
      const res = await fetch(api('api/chat'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body.error || '답변을 받지 못했어요. 다시 시도해 주세요.');
      pending.querySelector('p').textContent = body.reply;
    } catch (err) {
      pending.classList.add('is-error');
      pending.querySelector('p').textContent = err.message;
    } finally {
      send.disabled = false;
      scrollToEnd();
    }
  });

  function addMessage(role, text) {
    const msg = document.createElement('div');
    msg.className = `q-msg q-msg-${role}`;
    const p = document.createElement('p');
    p.textContent = text;
    msg.append(p);
    log.append(msg);
    scrollToEnd();
    return msg;
  }

  function autoGrow() {
    input.style.height = 'auto';
    input.style.height = `${Math.min(input.scrollHeight, 120)}px`;
  }

  function scrollToEnd() {
    window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
  }
})();
