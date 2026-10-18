// 통하길 QR 담당자 화면: 최근 지급 목록 갱신 · 관리자 에이전트 채팅
(function () {
  // ---------------- 사은품 증정 목록 ----------------
  // 방문객이 뽑기를 마치면 코드와 사은품이 바로 보이게 5초마다 다시 읽는다. 찾기 칸은 목록을 걸러 보여 준다.
  const list = document.getElementById('coupon-list');
  const search = document.getElementById('coupon-search');
  const empty = document.getElementById('coupon-empty');
  const noMatch = document.getElementById('coupon-nomatch');
  let word = '';  // 지금 적용된 찾기 글자. 목록이 5초마다 새로 그려져도 이 글자로 다시 거른다
  if (list) {
    document.getElementById('coupon-search-form').addEventListener('submit', (event) => {
      event.preventDefault();
      word = cleanCode(search.value);
      search.value = word;
      applyFilter();
    });
    // 칸을 비우면(지우기 ✕ 포함) 바로 전체 목록으로 돌아간다
    search.addEventListener('input', () => {
      if (!search.value.trim()) {
        word = '';
        applyFilter();
      }
    });
    applyFilter();
    setInterval(async () => {
      try {
        const res = await fetch(list.dataset.api);
        if (!res.ok) return;
        const rows = (await res.json()).coupons;
        list.replaceChildren(...rows.map(couponRow));
        applyFilter();
      } catch (_e) {
        // 잠깐 끊겨도 다음 주기에 다시 시도한다
      }
    }, 5000);
  }

  function couponRow(row) {
    const li = document.createElement('li');
    li.className = `is-${row.state}`;
    li.dataset.code = row.code;
    li.dataset.gift = row.gift || '';
    const code = document.createElement('code');
    code.textContent = row.code;
    const gift = document.createElement(row.gift ? 'strong' : 'em');
    gift.className = row.gift ? 's-gift' : 's-gift is-wait';
    gift.textContent = row.gift || '아직 안 뽑음';
    li.append(code, gift);
    if (row.state === 'ready') {
      // 증정은 화면을 새로 여는 일반 전송이다 (결과 안내가 위에 뜬다)
      const form = document.createElement('form');
      form.method = 'post';
      form.action = list.dataset.redeem;
      const hidden = document.createElement('input');
      hidden.type = 'hidden';
      hidden.name = 'code';
      hidden.value = row.code;
      const button = document.createElement('button');
      button.type = 'submit';
      button.className = 'cc-btn cc-btn-primary s-give';
      button.textContent = '증정';
      form.append(hidden, button);
      li.append(form);
    } else {
      const note = document.createElement('span');
      note.textContent = `${row.state === 'done' ? '증정 완료' : '발급'} ${row.time}`;
      li.append(note);
    }
    return li;
  }

  // 쿠폰 코드는 대문자와 숫자뿐이다. 소문자·빈칸·하이픈을 섞어 쳐도 찾아지게 맞춘다
  function cleanCode(text) {
    return text.toUpperCase().replace(/[^A-Z0-9]/g, '');
  }

  // 찾는 글자로 **시작하는** 코드만 보여 준다. 예) "AB" → ABCDEF, ABFE 는 보이고 CCE 는 숨긴다
  function applyFilter() {
    let shown = 0;
    list.querySelectorAll('li').forEach((li) => {
      const hit = !word || li.dataset.code.startsWith(word);
      li.hidden = !hit;
      if (hit) shown += 1;
    });
    const total = list.children.length;
    empty.hidden = total > 0;
    noMatch.hidden = !(total > 0 && shown === 0);
  }

  // ---------------- 사은품 뽑기 테스트 ----------------
  const testBtn = document.getElementById('gift-test-btn');
  if (testBtn) {
    const box = document.getElementById('gift-test');
    const out = document.getElementById('gift-test-result');
    testBtn.addEventListener('click', async () => {
      testBtn.disabled = true;
      out.classList.remove('is-error');
      out.textContent = '뽑는 중…';
      try {
        const res = await fetch(box.dataset.api, { method: 'POST' });
        const body = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(body.error || `실패했어요 (HTTP ${res.status}).`);
        const left = body.remaining === null || body.remaining === undefined ? '' : ` · 이 품목 남은 수량 ${body.remaining}개`;
        const where = body.source === 'n8n' ? '구글 시트' : '앱 내부 목록';
        out.textContent = `${body.gift}${left} (${where})`;
      } catch (err) {
        out.classList.add('is-error');
        out.textContent = err.message;
      } finally {
        testBtn.disabled = false;
      }
    });
  }

  // ---------------- 순찰 알림 (오른쪽 아래 메신저 창) ----------------
  // n8n 순찰 에이전트가 넣은 알림을 15초마다 다시 읽는다. 창이 닫혀 있으면 안 읽은 알림 수를 버튼 위 숫자로 보여 준다.
  // 어디까지 읽었는지는 이 브라우저에만 기억한다(담당자마다 따로).
  // PIN 으로 들어올 때마다(?welcome=1) 맨 위 인사 메시지를 '안 읽음 1'로 만든다 → 로그인하자마자 창을 열어 보게.
  const patrol = document.getElementById('patrol');
  if (patrol) {
    const panel = document.getElementById('patrol-panel');
    const fab = document.getElementById('patrol-fab');
    const log = document.getElementById('patrol-log');
    const hello = document.getElementById('patrol-hello');
    const count = document.getElementById('patrol-count');
    const status = document.getElementById('patrol-status');
    const SEEN_KEY = 'tq_patrol_seen';
    const HELLO_KEY = 'tq_patrol_hello';   // 인사 메시지: 'unread' | 'read'
    const HELLO_AT_KEY = 'tq_patrol_hello_at';
    let seen = Number(readStore(SEEN_KEY)) || 0;
    let latest = 0;    // 지금 받은 알림 중 가장 큰 id
    let shown = null;  // 마지막으로 그린 목록 (바뀌었을 때만 다시 그린다)
    let unread = 0;
    let alertsUnread = 0;

    if (patrol.dataset.welcome) {
      const now = new Date();
      writeStore(HELLO_KEY, 'unread');
      writeStore(HELLO_AT_KEY, `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`);
      // 새로고침할 때마다 다시 '안 읽음'이 되지 않게 주소에서 welcome=1 을 뗀다
      const url = new URL(window.location.href);
      url.searchParams.delete('welcome');
      window.history.replaceState(null, '', url.pathname + url.search + url.hash);
    }
    let helloUnread = patrol.dataset.welcome ? true : readStore(HELLO_KEY) === 'unread';
    document.getElementById('patrol-hello-time').textContent = readStore(HELLO_AT_KEY) || '';
    setCount(helloUnread ? 1 : 0);

    const open = (yes) => {
      panel.hidden = !yes;
      fab.setAttribute('aria-expanded', String(yes));
      fab.setAttribute('aria-label', yes ? '에이전트 알림 닫기' : '에이전트 알림 열기');
      if (yes) {
        markRead();
        log.scrollTop = log.scrollHeight;
      }
    };
    fab.addEventListener('click', () => open(panel.hidden));
    document.getElementById('patrol-close').addEventListener('click', () => open(false));
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && !panel.hidden) open(false);
    });

    const load = async () => {
      try {
        const res = await fetch(patrol.dataset.api);
        if (!res.ok) return;
        const body = await res.json();
        status.textContent = body.last_patrol ? `마지막 순찰 ${body.last_patrol}` : '아직 순찰 기록 없음';
        // 서버는 최근 것부터 준다 → 뒤집어서 오래된 것이 위, 가장 최근 메시지가 맨 아래 (카카오톡 순서)
        const items = body.alerts.slice().reverse();
        latest = items.length ? items[items.length - 1].id : 0;
        if (latest < seen) seen = 0;  // DB 를 새로 만들어 번호가 처음부터 다시 시작한 경우
        const key = items.map((a) => a.id).join(',');
        if (key !== shown) {
          shown = key;
          log.replaceChildren(hello, ...items.map(message));
          log.scrollTop = log.scrollHeight;
        }
        if (!panel.hidden) {
          markRead();
        } else {
          alertsUnread = items.filter((a) => a.id > seen).length;
          setCount(alertsUnread + (helloUnread ? 1 : 0));
        }
      } catch (_e) {
        // 잠깐 끊겨도 다음 주기에 다시 시도한다
      }
    };
    load();
    setInterval(load, 15000);

    function message(a) {
      const row = document.createElement('div');
      row.className = `s-patrol-msg is-${a.level}`;
      const bubble = document.createElement('p');
      bubble.className = 's-patrol-bubble';
      const title = document.createElement('strong');
      title.textContent = a.title;
      const text = document.createElement('span');
      text.textContent = a.message;
      bubble.append(title, text);
      const time = document.createElement('time');
      time.textContent = a.time;
      row.append(bubble, time);
      return row;
    }

    function setCount(n) {
      count.hidden = n === 0;
      count.textContent = n > 99 ? '99+' : String(n);
      if (n > unread) {
        // 새 알림이 오면 숫자가 톡 튀어나온다
        count.classList.remove('is-new');
        void count.offsetWidth;
        count.classList.add('is-new');
      }
      unread = n;
    }

    function markRead() {
      seen = Math.max(seen, latest);
      writeStore(SEEN_KEY, String(seen));
      if (helloUnread) {
        helloUnread = false;
        writeStore(HELLO_KEY, 'read');
      }
      alertsUnread = 0;
      setCount(0);
    }

    // 저장이 막힌 브라우저(사생활 보호 모드 등)에서도 이번 화면에서는 동작한다
    function readStore(name) {
      try { return localStorage.getItem(name); } catch (_e) { return null; }
    }
    function writeStore(name, value) {
      try { localStorage.setItem(name, value); } catch (_e) { /* 무시 */ }
    }
  }

  // ---------------- 비밀 값 복사 (설정) ----------------
  document.querySelectorAll('[data-copy]').forEach((button) => {
    button.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(button.dataset.copy);
        button.textContent = '복사됨';
      } catch (_e) {
        button.textContent = '복사 안 됨 · 보기를 눌러 직접 복사';
      }
      setTimeout(() => { button.textContent = '복사'; }, 2000);
    });
  });

  // ---------------- 관리자 에이전트 ----------------
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
