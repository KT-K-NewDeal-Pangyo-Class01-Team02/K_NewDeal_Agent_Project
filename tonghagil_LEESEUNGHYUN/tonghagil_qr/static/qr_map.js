// 통하길 QR 지도 화면: 카카오맵 위에 구역(통신 상태 색) · KT 부스 · 스탬프 QR 위치 · 내 위치를 그린다.
// 카카오맵이 못 뜨면(키 오류, 도메인 미등록, 카카오맵 활성화 OFF, 통신 불량) 그림 약도(#svg-map)로 되돌린다.
(function () {
  const el = document.getElementById('kmap');
  const dataEl = document.getElementById('map-data');
  if (!el || !dataEl) return;

  const data = JSON.parse(dataEl.textContent);
  const msg = document.getElementById('kmap-msg');
  const COLORS = { good: '#1d9a5b', busy: '#e09612', jam: '#e3313f' };
  const LOAD_TIMEOUT_MS = 8000;

  let map = null;
  let failed = false;
  let infoOverlay = null;
  let meOverlay = null;
  const polygons = {}; // 구역 id → kakao.maps.Polygon
  const zoneLabels = {}; // 구역 id → 라벨 요소

  // ---------------- 카카오맵 불러오기 ----------------
  const timer = setTimeout(fallback, LOAD_TIMEOUT_MS);
  const script = document.createElement('script');
  script.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${encodeURIComponent(el.dataset.key)}&autoload=false`;
  script.onerror = fallback;
  script.onload = () => {
    if (!window.kakao || !window.kakao.maps) {
      fallback();
      return;
    }
    window.kakao.maps.load(() => {
      if (failed) return;
      clearTimeout(timer);
      try {
        init();
      } catch (err) {
        console.error('[통하길 QR] 카카오맵 초기화 실패', err);
        map = null;
        fallback();
      }
    });
  };
  document.head.append(script);

  function fallback() {
    if (failed || map) return;
    failed = true;
    clearTimeout(timer);
    console.warn('[통하길 QR] 카카오맵을 불러오지 못해 약도로 바꿉니다. 키, 카카오 콘솔의 사이트 도메인, 카카오맵 활성화 설정을 확인하세요.');
    document.getElementById('kmap-card').hidden = true;
    const svg = document.getElementById('svg-map');
    if (svg) svg.hidden = false;
    const note = document.getElementById('svg-map-note');
    if (note) note.hidden = false;
  }

  // ---------------- 그리기 ----------------
  function init() {
    const maps = window.kakao.maps;
    el.replaceChildren();
    map = new maps.Map(el, { center: latLng(data.center), level: data.level });
    map.addControl(new maps.ZoomControl(), maps.ControlPosition.RIGHT);
    map.setMaxLevel(8);

    data.zones.forEach(drawZone);
    data.stamps.forEach(drawStamp);
    drawBooth();

    maps.event.addListener(map, 'click', closeInfo);
    fitAll();
    el.classList.add('is-ready');
    bindControls();
    document.addEventListener('qr:network', (event) => recolor(event.detail.zones));
  }

  function drawZone(zone) {
    const maps = window.kakao.maps;
    const path = zone.geo.map(latLng);
    const polygon = new maps.Polygon({
      map,
      path,
      strokeWeight: 2,
      strokeColor: COLORS[zone.level],
      strokeOpacity: 0.9,
      fillColor: COLORS[zone.level],
      fillOpacity: 0.22,
    });
    maps.event.addListener(polygon, 'click', () => showZone(zone.id));
    polygons[zone.id] = polygon;

    const label = document.createElement('div');
    label.className = 'km-zone';
    label.dataset.level = zone.level;
    const name = document.createElement('b');
    name.textContent = zone.name;
    const status = document.createElement('span');
    status.textContent = zone.label;
    label.append(name, status);
    new maps.CustomOverlay({ map, position: centerOf(zone.geo), content: label, yAnchor: 0.5, zIndex: 1 });
    zoneLabels[zone.id] = label;
  }

  function drawStamp(stamp) {
    const btn = markerButton(`km-stamp${stamp.done ? ' is-done' : ''}`, stamp.done ? '✓' : String(stamp.no),
      `스탬프 ${stamp.no}. ${stamp.name} QR 위치`);
    btn.addEventListener('click', () => showStamp(stamp.id));
    new window.kakao.maps.CustomOverlay({ map, position: latLng(stamp.geo), content: btn, yAnchor: 0.5, zIndex: 5, clickable: true });
  }

  function drawBooth() {
    const btn = markerButton('km-booth', 'KT', `${data.booth.name} 위치`);
    btn.addEventListener('click', showBooth);
    new window.kakao.maps.CustomOverlay({ map, position: latLng(data.booth.geo), content: btn, yAnchor: 0.5, zIndex: 6, clickable: true });
  }

  function markerButton(className, text, label) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = className;
    btn.textContent = text;
    btn.setAttribute('aria-label', label);
    return btn;
  }

  function recolor(zones) {
    if (!map) return;
    zones.forEach((zone) => {
      const polygon = polygons[zone.id];
      if (polygon) polygon.setOptions({ strokeColor: COLORS[zone.level], fillColor: COLORS[zone.level] });
      const label = zoneLabels[zone.id];
      if (label) {
        label.dataset.level = zone.level;
        label.querySelector('span').textContent = zone.label;
      }
    });
  }

  // ---------------- 안내 팝업 ----------------
  function showStamp(id) {
    const stamp = data.stamps.find((s) => s.id === id);
    if (!map || !stamp) return;
    openInfo(stamp.geo, `스탬프 ${stamp.no}. ${stamp.name}`, [
      `QR이 붙은 곳: ${stamp.hint}`,
      stamp.zone,
    ], stamp.done ? { text: '완료', cls: 'is-done' } : { text: '미완료', cls: '' });
    say(`${stamp.no}번 스탬프 QR 위치예요.`);
  }

  function showBooth() {
    if (!map) return;
    const b = data.booth;
    openInfo(b.geo, b.name, [
      b.location,
      `운영 ${b.hours}`,
      `지금 대기 ${textOf('[data-net="queue"]')}명 · 약 ${textOf('[data-net="wait"]')}분`,
    ], { text: 'KT', cls: 'is-kt' });
    say('KT 부스 위치예요. 스탬프를 다 모으면 여기서 선물을 받아요.');
  }

  function showZone(id) {
    const zone = data.zones.find((z) => z.id === id);
    const row = document.querySelector(`.q-zone-row[data-zone="${id}"]`);
    if (!map || !zone) return;
    const field = (name) => (row ? textOf(`[data-field="${name}"]`, row) : '');
    openInfo(centerOf(zone.geo, true), zone.name, [
      `통신 ${field('label')} · ${field('users')}명 접속`,
      `예상 속도 약 ${field('speed')}Mbps (모의)`,
    ], null);
  }

  function openInfo(geo, title, lines, badge) {
    closeInfo();
    const card = document.createElement('div');
    card.className = 'km-info';
    const head = document.createElement('div');
    head.className = 'km-info-head';
    const strong = document.createElement('strong');
    strong.textContent = title;
    head.append(strong);
    if (badge) {
      const tag = document.createElement('em');
      tag.className = `km-info-badge ${badge.cls}`;
      tag.textContent = badge.text;
      head.append(tag);
    }
    const close = document.createElement('button');
    close.type = 'button';
    close.className = 'km-info-close';
    close.setAttribute('aria-label', '닫기');
    close.textContent = '×';
    close.addEventListener('click', closeInfo);
    head.append(close);
    card.append(head);
    lines.filter(Boolean).forEach((line) => {
      const p = document.createElement('p');
      p.textContent = line;
      card.append(p);
    });

    const position = Array.isArray(geo) ? latLng(geo) : geo;
    infoOverlay = new window.kakao.maps.CustomOverlay({ map, position, content: card, yAnchor: 1.25, zIndex: 20, clickable: true });
    map.panTo(position);
  }

  function closeInfo() {
    if (infoOverlay) infoOverlay.setMap(null);
    infoOverlay = null;
  }

  // ---------------- 버튼 · 목록 ----------------
  function bindControls() {
    document.querySelectorAll('[data-map-action]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const action = btn.dataset.mapAction;
        if (action === 'fit') {
          closeInfo();
          fitAll();
          say('행사장 전체를 보여 드려요.');
        } else if (action === 'booth') {
          showBooth();
        } else if (action === 'me') {
          locateMe();
        }
      });
    });
    document.querySelectorAll('[data-focus-stamp]').forEach((btn) => {
      btn.addEventListener('click', () => {
        scrollToMap();
        showStamp(btn.dataset.focusStamp);
      });
    });
    document.querySelectorAll('[data-focus="booth"]').forEach((btn) => {
      btn.addEventListener('click', () => {
        scrollToMap();
        showBooth();
      });
    });
    document.querySelectorAll('.q-zone-row[data-zone]').forEach((row) => {
      row.addEventListener('click', () => {
        scrollToMap();
        showZone(row.dataset.zone);
      });
    });
  }

  function fitAll() {
    const bounds = new window.kakao.maps.LatLngBounds();
    data.zones.forEach((zone) => zone.geo.forEach((p) => bounds.extend(latLng(p))));
    data.stamps.forEach((s) => bounds.extend(latLng(s.geo)));
    bounds.extend(latLng(data.booth.geo));
    map.setBounds(bounds, 16, 16, 16, 16);
  }

  function scrollToMap() {
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  // ---------------- 내 위치 ----------------
  function locateMe() {
    if (!window.isSecureContext || !navigator.geolocation) {
      say('내 위치는 https 주소(또는 이 컴퓨터의 localhost)에서만 확인할 수 있어요.');
      return;
    }
    say('내 위치를 찾는 중…');
    navigator.geolocation.getCurrentPosition((pos) => {
      const me = [pos.coords.latitude, pos.coords.longitude];
      showMe(me);
      const far = distance(me, data.center);
      if (far > data.near_km * 1000) {
        say(`행사장에서 약 ${(far / 1000).toFixed(1)}km 떨어져 있어요. 행사장 근처에서 다시 눌러 보세요.`);
        return;
      }
      closeInfo();
      map.panTo(latLng(me));
      const next = nearestStamp(me);
      say(next
        ? `가장 가까운 남은 스탬프: ${next.stamp.no}. ${next.stamp.name} (약 ${Math.round(next.meters)}m)`
        : '스탬프를 모두 모았어요! KT 부스로 가서 선물을 받으세요.');
    }, (err) => {
      say(err.code === 1
        ? '위치 권한이 꺼져 있어요. 브라우저 설정에서 이 사이트의 위치 권한을 허용해 주세요.'
        : '위치를 찾지 못했어요. 잠시 후 다시 눌러 주세요.');
    }, { enableHighAccuracy: true, timeout: 10000, maximumAge: 30000 });
  }

  function showMe(me) {
    if (!meOverlay) {
      const dot = document.createElement('div');
      dot.className = 'km-me';
      dot.setAttribute('aria-label', '내 위치');
      meOverlay = new window.kakao.maps.CustomOverlay({ map, position: latLng(me), content: dot, yAnchor: 0.5, zIndex: 8 });
    } else {
      meOverlay.setPosition(latLng(me));
    }
  }

  function nearestStamp(me) {
    return data.stamps
      .filter((s) => !s.done)
      .map((stamp) => ({ stamp, meters: distance(me, stamp.geo) }))
      .sort((a, b) => a.meters - b.meters)[0];
  }

  // ---------------- 도우미 ----------------
  function latLng(p) {
    return new window.kakao.maps.LatLng(p[0], p[1]);
  }

  function centerOf(points, asLatLng = true) {
    const lat = points.reduce((sum, p) => sum + p[0], 0) / points.length;
    const lng = points.reduce((sum, p) => sum + p[1], 0) / points.length;
    return asLatLng ? latLng([lat, lng]) : [lat, lng];
  }

  // 두 위경도 사이 거리(m)
  function distance(a, b) {
    const rad = (d) => (d * Math.PI) / 180;
    const dLat = rad(b[0] - a[0]);
    const dLng = rad(b[1] - a[1]);
    const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a[0])) * Math.cos(rad(b[0])) * Math.sin(dLng / 2) ** 2;
    return 2 * 6371000 * Math.asin(Math.sqrt(h));
  }

  function textOf(selector, root = document) {
    const node = root.querySelector(selector);
    return node ? node.textContent.trim() : '';
  }

  function say(text) {
    if (msg) msg.textContent = text;
  }
})();
