// 빅또리출동! F-01: 이번 주 옥외 기회 스캔 → 카드 선택 → 캠페인 시작
// 브라우저는 Flask(/api/f01/*)만 부르고, n8n 호출은 Flask 가 대신한다.
(function () {
  const storeSelect = document.getElementById('opp-store');
  const scanBtn = document.getElementById('scan-btn');
  const scanLabel = scanBtn.querySelector('span');
  const meta = document.getElementById('opp-meta');
  const grid = document.getElementById('opp-grid');
  const notice = document.getElementById('opp-notice');
  const briefStore = document.querySelector('#brief-form [name="store_name"]');
  const DAY = { weekday: '평일', friday: '금요일', weekend: '주말', holiday: '공휴일' };
  const SOURCE = { kma: '기상청', tour: 'TourAPI', roster: '근무표', dummy: '더미 데이터', llm: 'LLM 문구', db: '카드 저장' };
  // Flask 가 JSON 키를 알파벳순으로 정렬하므로 지표 순서는 여기서 고정한다
  const ORDER = ['footfall', 'event', 'weather', 'promo', 'staff'];
  let cards = [];

  const el = (tag, cls, text) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const fmtTime = (iso) => new Date(iso).toLocaleString('ko-KR', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' });

  async function post(url, body) {
    const response = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || '요청을 처리하지 못했어요.');
    return data;
  }

  function setNotice(message, isError) {
    notice.textContent = message || '';
    notice.classList.toggle('is-error', !!isError);
  }

  function selectable(card) {
    return card.teams !== 0 && card.card_id !== null && card.card_id !== undefined && !card.selected;
  }

  function renderCard(card, index) {
    const box = el('article', 'opp-card');
    box.id = `opp-${index}`;

    const top = el('div', 'opp-top');
    top.append(el('span', 'opp-date', `${card.rank}순위 · ${card.target_date} (${DAY[card.day_type] || ''})`));
    const score = el('span', 'opp-score', String(card.score));
    score.append(el('span', `opp-status is-${card.score_status}`, card.score_status));
    top.append(score);
    box.append(top, el('h3', null, card.title), el('p', null, card.summary));

    if (card.top_site) {
      const site = el('p');
      site.append('추천 장소 ', el('strong', null, card.top_site.site_name), ` · 매장까지 ${card.top_site.distance_to_store_m}m`);
      box.append(site);
    }

    const bars = el('div', 'opp-bars');
    ORDER.filter((k) => card.indicators && card.indicators[k]).map((k) => card.indicators[k]).forEach((v) => {
      const row = el('div', 'opp-bar');
      row.title = v.note || '';
      const track = el('i'); const fill = el('b'); fill.style.width = `${v.score ?? 0}%`; track.append(fill);
      row.append(el('span', null, v.label), track, el('span', null, v.score ?? '–'));
      bars.append(row);
    });
    box.append(bars);

    if (card.tags && card.tags.length) {
      const tags = el('div', 'opp-tags');
      card.tags.forEach((t) => tags.append(el('span', t.startsWith('출동 불가') ? 'opp-tag is-block' : 'opp-tag', t)));
      box.append(tags);
    }
    if (card.risk) {
      const risk = el('p'); risk.append(el('strong', null, '주의 '), card.risk); box.append(risk);
    }

    const btn = el('button', 'cc-btn', card.teams === 0 ? '출동 인원 부족' : '이 카드로 캠페인 시작');
    btn.type = 'button';
    btn.disabled = !selectable(card);
    btn.addEventListener('click', () => selectCard(index));
    box.append(btn);
    return box;
  }

  function refreshButtons() {
    grid.querySelectorAll('.opp-card').forEach((box, i) => {
      const btn = box.querySelector('.cc-btn');
      btn.disabled = !selectable(cards[i]);
      if (cards[i].selected) { btn.textContent = '선택됨'; box.classList.add('is-selected'); }
    });
  }

  async function scan() {
    scanBtn.disabled = true;
    scanLabel.textContent = '스캔 중…';
    setNotice('');
    meta.textContent = '기상 · 행사 · 근무표를 모아 점수를 내고 있습니다…';
    try {
      const data = await post('/api/f01/scan', { store_id: storeSelect.value });
      cards = data.cards || [];
      const off = Object.entries(data.sources || {}).filter(([, ok]) => !ok).map(([k]) => SOURCE[k] || k);
      meta.textContent = `${data.store_name} · ${fmtTime(data.scannedAt)} 스캔`;
      if (data.source === 'demo') meta.append(' · ', el('span', 'is-warn', '데모 데이터'));
      if (off.length) meta.append(' · ', el('span', 'is-warn', `${off.join(', ')} 연결 실패`));
      (data.dataTags || []).forEach((t) => { meta.append(document.createElement('br'), t); });
      grid.replaceChildren(...cards.map(renderCard));
      if (!cards.length) grid.replaceChildren(el('div', 'opp-empty', '제안할 기회가 없습니다. 다른 매장을 고르거나 잠시 뒤 다시 스캔하세요.'));
    } catch (err) {
      meta.textContent = '';
      grid.replaceChildren(el('div', 'opp-error', `기회 스캔에 실패했습니다. ${err.message}`));
      window.ccToast(err.message);
    } finally {
      scanBtn.disabled = false;
      scanLabel.textContent = '기회 스캔';
    }
  }

  async function selectCard(index) {
    const card = cards[index];
    grid.querySelectorAll('.opp-card .cc-btn').forEach((b) => { b.disabled = true; });
    setNotice('');
    try {
      const data = await post('/api/f01/select', { card_id: card.card_id, target_date: card.target_date, store_id: storeSelect.value });
      const c = data.campaign;
      card.selected = true;
      const storeName = storeSelect.selectedOptions[0].dataset.name;
      if (briefStore) briefStore.value = storeName;
      setNotice(`${c.target_date} 캠페인을 시작했습니다. 캠페인 번호 ${c.campaign_id} · 기획 마감 ${fmtTime(c.plan_due_at)} (3시간). 아래 캠페인 발의에서 조건을 입력하세요.`);
      if (data.source === 'demo') window.ccToast('데모 모드라 캠페인이 저장되지 않았어요.');
    } catch (err) {
      setNotice(err.message, true);
    } finally {
      refreshButtons();
    }
  }

  scanBtn.addEventListener('click', scan);
})();
