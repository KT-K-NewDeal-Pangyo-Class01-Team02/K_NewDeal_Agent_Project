// 통하길 스튜디오: 채팅으로 포스터 요청 → /api/posters (n8n) → 갤러리에 추가
(function () {
  const $ = (id) => document.getElementById(id);

  const log = $('chat-log');
  const form = $('composer-form');
  const textarea = $('message');
  const counter = $('counter');
  const submitBtn = $('submit-btn');

  const grid = $('gallery-grid');
  const empty = $('gallery-empty');
  const cardTpl = $('poster-card-tpl');
  const filterAll = $('filter-all');
  const filterEvent = $('filter-event');
  const sortSelect = $('sort');

  const preview = $('preview-dialog');

  const maxLen = textarea.maxLength;
  const sessionId = getSessionId();
  let posters = [];
  let newPosterId = null;

  // ---------------- 갤러리 ----------------

  async function loadPosters() {
    try {
      const res = await fetch('/api/posters');
      if (!res.ok) throw new Error();
      posters = await res.json();
      renderGallery();
    } catch {
      empty.textContent = '포스터 목록을 불러오지 못했어요. 새로고침해 주세요.';
      empty.hidden = false;
    }
  }

  function renderGallery() {
    const type = filterEvent.value;
    const oldestFirst = sortSelect.value === 'oldest';
    const list = posters
      .filter((p) => !type || p.event_type === type)
      .sort((a, b) => (oldestFirst ? 1 : -1) * (a.created_at || '').localeCompare(b.created_at || ''));

    filterAll.classList.toggle('is-active', !type);
    filterEvent.classList.toggle('is-active', Boolean(type));
    grid.replaceChildren(...list.map(buildCard));
    empty.hidden = list.length > 0;
  }

  function buildCard(poster) {
    const card = cardTpl.content.firstElementChild.cloneNode(true);
    card.dataset.id = poster.id;
    if (poster.id === newPosterId) card.classList.add('is-new');

    const img = card.querySelector('img');
    img.addEventListener('error', () => card.classList.add('is-broken'), { once: true });
    img.src = poster.image_url;
    img.alt = `${poster.title} 포스터`;

    card.querySelector('.poster-title').textContent = poster.title;
    card.querySelector('.poster-sub').textContent = [poster.event_type, formatDate(poster.created_at)].filter(Boolean).join(' · ');
    setLink(card.querySelector('[data-link="download"]'), downloadUrl(poster), poster);
    setLink(card.querySelector('[data-link="share"]'), shareUrl(poster));
    return card;
  }

  grid.addEventListener('click', (event) => {
    if (event.target.closest('[data-link]')) {
      closeMenus();
      return;
    }
    const target = event.target.closest('[data-action]');
    if (!target) return;
    const card = target.closest('.poster');
    const poster = posters.find((p) => p.id === card.dataset.id);

    if (target.dataset.action === 'menu') {
      const menu = card.querySelector('.menu');
      const willOpen = menu.hidden;
      closeMenus();
      menu.hidden = !willOpen;
      target.setAttribute('aria-expanded', String(willOpen));
    } else if (target.dataset.action === 'preview') {
      closeMenus();
      openPreview(poster);
    }
  });

  function closeMenus() {
    grid.querySelectorAll('.menu').forEach((menu) => { menu.hidden = true; });
    grid.querySelectorAll('[data-action="menu"]').forEach((btn) => btn.setAttribute('aria-expanded', 'false'));
  }
  document.addEventListener('click', (event) => {
    if (!event.target.closest('.poster-menu')) closeMenus();
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') closeMenus();
  });

  filterAll.addEventListener('click', () => {
    filterEvent.value = '';
    renderGallery();
  });
  filterEvent.addEventListener('change', renderGallery);
  sortSelect.addEventListener('change', renderGallery);

  // ---------------- 미리보기 ----------------

  function openPreview(poster) {
    $('preview-title').textContent = poster.title;
    $('preview-img').src = poster.image_url;
    $('preview-img').alt = `${poster.title} 포스터`;
    $('preview-prompt').textContent = poster.prompt ? `요청 내용: ${poster.prompt}` : '';
    setLink($('preview-download'), downloadUrl(poster), poster);
    setLink($('preview-share'), shareUrl(poster));
    preview.showModal();
  }
  preview.querySelector('[data-close]').addEventListener('click', () => preview.close());
  preview.addEventListener('click', (event) => {
    if (event.target === preview) preview.close();
  });

  // ---------------- 채팅 ----------------

  log.addEventListener('click', (event) => {
    const example = event.target.closest('[data-example]');
    if (example) {
      textarea.value = example.dataset.example;
      updateCounter();
      textarea.focus();
      return;
    }
    const result = event.target.closest('[data-poster-id]');
    if (result) {
      const poster = posters.find((p) => p.id === result.dataset.posterId);
      if (poster) openPreview(poster);
    }
  });

  textarea.addEventListener('input', updateCounter);
  textarea.addEventListener('keydown', (event) => {
    // 한글 입력 조합 중 Enter 는 무시 (글자가 두 번 전송되는 문제 방지)
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      form.requestSubmit();
    }
  });

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (submitBtn.disabled) return;
    const message = textarea.value.trim();
    if (!message) {
      textarea.focus();
      return;
    }

    const data = new FormData(form);
    const styleInput = form.querySelector('input[name="style"]:checked');
    const styleLabel = styleInput.closest('label').querySelector('.style-label').textContent;

    const userMsg = addMessage('user', message);
    const tag = document.createElement('span');
    tag.className = 'msg-tag';
    tag.textContent = `${styleLabel} · ${data.get('event_type')}`;
    userMsg.append(tag);

    textarea.value = '';
    updateCounter();

    const pending = addMessage('bot', '포스터를 그리는 중이에요. 보통 30초~1분 정도 걸려요.');
    const typing = document.createElement('span');
    typing.className = 'typing';
    typing.innerHTML = '<i></i><i></i><i></i>';
    pending.prepend(typing);
    setBusy(true);

    try {
      const res = await fetch('/api/posters', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message,
          style: data.get('style'),
          event_type: data.get('event_type'),
          session_id: sessionId,
        }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body.error || '포스터를 만들지 못했어요. 다시 시도해 주세요.');

      posters.push(body);
      newPosterId = body.id;
      filterEvent.value = '';
      sortSelect.value = 'latest';
      renderGallery();

      pending.replaceChildren(paragraph('포스터 시안이 완성됐어요! 갤러리에도 추가했어요.'), resultThumb(body));
    } catch (err) {
      pending.classList.add('is-error');
      pending.replaceChildren(paragraph(err.message));
    } finally {
      setBusy(false);
      scrollLog();
    }
  });

  function addMessage(role, text) {
    const msg = document.createElement('div');
    msg.className = `msg msg-${role}`;
    msg.append(paragraph(text));
    log.append(msg);
    scrollLog();
    return msg;
  }

  function paragraph(text) {
    const p = document.createElement('p');
    p.textContent = text;
    return p;
  }

  function resultThumb(poster) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'msg-result';
    btn.dataset.posterId = poster.id;
    btn.setAttribute('aria-label', `${poster.title} 크게 보기`);
    const img = document.createElement('img');
    img.src = poster.image_url;
    img.alt = '';
    img.referrerPolicy = 'no-referrer';
    img.addEventListener('load', scrollLog, { once: true });
    btn.append(img);
    return btn;
  }

  function setBusy(busy) {
    submitBtn.disabled = busy;
    submitBtn.querySelector('span').textContent = busy ? '생성 중…' : '포스터 생성';
  }

  function updateCounter() {
    counter.textContent = `${textarea.value.length}/${maxLen}`;
  }

  function scrollLog() {
    log.scrollTop = log.scrollHeight;
  }

  // ---------------- 도우미 ----------------

  function downloadUrl(poster) {
    return poster.download_url || poster.image_url;
  }

  function shareUrl(poster) {
    return poster.share_url || poster.image_url;
  }

  function setLink(anchor, url, poster) {
    anchor.href = url;
    // 같은 서버의 파일(데모/샘플 SVG)은 바로 저장되게 한다. 드라이브 링크는 드라이브가 다운로드를 처리한다.
    if (poster && url.startsWith('/')) anchor.download = `${poster.title}.svg`;
    else anchor.removeAttribute('download');
  }

  function formatDate(iso) {
    return iso ? iso.slice(0, 10).replaceAll('-', '.') : '';
  }

  function getSessionId() {
    const make = () => (window.crypto && crypto.randomUUID ? crypto.randomUUID() : `s-${Date.now()}-${Math.random().toString(16).slice(2)}`);
    try {
      let id = sessionStorage.getItem('tonghagil-session');
      if (!id) {
        id = make();
        sessionStorage.setItem('tonghagil-session', id);
      }
      return id;
    } catch {
      return make();
    }
  }

  loadPosters();
})();
