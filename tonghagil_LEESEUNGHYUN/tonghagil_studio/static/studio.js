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
  const refreshBtn = $('refresh-btn');

  const preview = $('preview-dialog');

  const maxLen = textarea.maxLength;
  const sessionId = getSessionId();
  let posters = [];
  let newPosterId = null;

  // ---------------- 갤러리 ----------------

  async function loadPosters(refresh = false) {
    refreshBtn.classList.add('is-loading');
    refreshBtn.disabled = true;
    try {
      const res = await fetch(refresh ? '/api/posters?refresh=1' : '/api/posters');
      const body = await res.json().catch(() => null);
      if (!res.ok || !Array.isArray(body)) throw new Error((body && body.error) || '포스터 목록을 불러오지 못했어요. 새로고침해 주세요.');
      posters = body;
      renderGallery();
    } catch (err) {
      grid.replaceChildren();
      empty.textContent = err.message;
      empty.hidden = false;
    } finally {
      refreshBtn.classList.remove('is-loading');
      refreshBtn.disabled = false;
    }
  }

  refreshBtn.addEventListener('click', () => loadPosters(true));

  function renderGallery() {
    empty.textContent = '조건에 맞는 포스터가 없어요.';
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
    // 수정·삭제는 드라이브 포스터만 가능 (샘플·데모 포스터는 메뉴에서 뺀다)
    if (poster.source !== 'drive') card.querySelectorAll('[data-drive-only]').forEach((el) => el.remove());
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
    } else if (target.dataset.action === 'edit') {
      closeMenus();
      openEdit(poster);
    } else if (target.dataset.action === 'delete') {
      closeMenus();
      openDelete(poster);
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
  // ---------------- 정보 수정 · 삭제 (드라이브 포스터) ----------------

  const editDialog = $('edit-dialog');
  const editForm = $('edit-form');
  const editError = $('edit-error');
  const deleteDialog = $('delete-dialog');
  const deleteError = $('delete-error');
  const deleteConfirm = $('delete-confirm');
  let editing = null;

  function openEdit(poster) {
    editing = poster;
    editForm.elements.title.value = poster.title;
    editForm.elements.event_type.value = poster.event_type || '';
    editError.textContent = '';
    updateFilenamePreview();
    editDialog.showModal();
    editForm.elements.title.select();
  }

  function updateFilenamePreview() {
    const title = editForm.elements.title.value.replace(/[_/\\]+/g, ' ').trim() || '제목';
    const date = (editing.created_at || '').slice(0, 10).replaceAll('-', '');
    $('edit-filename').textContent = [editForm.elements.event_type.value, title, date].filter(Boolean).join('_') + '.png';
  }
  editForm.addEventListener('input', updateFilenamePreview);

  editForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const submit = editForm.querySelector('[type="submit"]');
    submit.disabled = true;
    editError.textContent = '';
    try {
      const updated = await requestJson(`/api/posters/${encodeURIComponent(editing.id)}`, 'PATCH', {
        title: editForm.elements.title.value.trim(),
        event_type: editForm.elements.event_type.value,
      });
      posters = posters.map((p) => (p.id === updated.id ? updated : p));
      renderGallery();
      editDialog.close();
      window.ccToast('포스터 정보를 수정했어요. 드라이브 파일 이름도 바뀌었어요.');
    } catch (err) {
      editError.textContent = err.message;
    } finally {
      submit.disabled = false;
    }
  });

  function openDelete(poster) {
    editing = poster;
    $('delete-name').textContent = `'${poster.title}'`;
    deleteError.textContent = '';
    deleteDialog.showModal();
  }

  deleteConfirm.addEventListener('click', async () => {
    deleteConfirm.disabled = true;
    deleteError.textContent = '';
    try {
      await requestJson(`/api/posters/${encodeURIComponent(editing.id)}`, 'DELETE');
      posters = posters.filter((p) => p.id !== editing.id);
      renderGallery();
      deleteDialog.close();
      window.ccToast("드라이브의 '_보관함' 폴더로 옮겼어요.");
    } catch (err) {
      deleteError.textContent = err.message;
    } finally {
      deleteConfirm.disabled = false;
    }
  });

  async function requestJson(url, method, payload) {
    const res = await fetch(url, {
      method,
      headers: payload ? { 'Content-Type': 'application/json' } : {},
      body: payload ? JSON.stringify(payload) : undefined,
    });
    const body = res.status === 204 ? null : await res.json().catch(() => ({}));
    if (!res.ok) throw new Error((body && body.error) || '요청을 처리하지 못했어요. 다시 시도해 주세요.');
    return body;
  }

  // 모든 팝업 공통: 닫기 버튼 · 바깥 클릭으로 닫기
  [preview, editDialog, deleteDialog].forEach((dialog) => {
    dialog.querySelectorAll('[data-close]').forEach((btn) => btn.addEventListener('click', () => dialog.close()));
    dialog.addEventListener('click', (event) => {
      if (event.target === dialog) dialog.close();
    });
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
    // 데모/샘플 SVG 는 바로 저장되게 한다. 드라이브 이미지는 서버(/drive-image/…?download=1)가 파일 이름을 붙여 준다.
    if (poster && url.startsWith('/placeholder')) anchor.download = `${poster.title}.svg`;
    else if (poster && url.startsWith('/')) anchor.download = '';
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
