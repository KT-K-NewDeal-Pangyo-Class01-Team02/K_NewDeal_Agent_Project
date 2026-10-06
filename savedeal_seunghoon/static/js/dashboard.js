// 예약 운영 대시보드. 우선순위·위험도·가능한 동작은 모두 서버(/api/reservations)가 계산해 주고,
// 이 파일은 받은 값을 그리고 버튼 요청을 보내기만 한다.
(function () {
  "use strict";

  var state = { filter: "all", selectedId: null };

  // 표시용 색 매핑 (판정이 아니라 서버가 준 상태값을 어떤 색 뱃지로 그릴지만 정한다)
  var STATUS_TONES = {
    ACTION_REQUIRED: "tone-warning",
    IN_PROGRESS: "tone-info",
    READY: "tone-success",
    COMPLETED: "tone-success",
    CANCELLED: "",
  };
  var STATUS_ICONS = {
    ACTION_REQUIRED: "circle-alert",
    IN_PROGRESS: "circle-dashed",
    READY: "clock",
    COMPLETED: "circle-check",
    CANCELLED: "ban",
  };
  var RISK_TONES = { high: "tone-danger", medium: "tone-warning", low: "tone-success" };
  var ACTION_STATUS_TONES = { APPROVED: "tone-info", SUCCEEDED: "tone-success", FAILED: "tone-danger" };
  var SVG_NS = "http://www.w3.org/2000/svg";

  // ── 흐르는 시간 ─────────────────────────────────────────────────
  // 남은 시간·대기 시간은 서버가 준 원래 시각(마감, 대기 시작)으로 1초마다 다시 계산한다.
  // 서버 시계를 기준으로 하기 위해 응답의 generated_at 과 이 컴퓨터 시계의 차이를 기억해 둔다.
  // 시간에 따라 바뀌는 점수·우선순위·건수는 서버가 계산하므로 1분마다 목록을 다시 받는다.
  var clock = { offset: 0 };

  function parseLocal(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?/.exec(iso || "");
    if (!m) return NaN;
    return new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +(m[6] || 0)).getTime();
  }

  function syncClock(serverIso) {
    var server = parseLocal(serverIso);
    if (!isNaN(server)) clock.offset = server - Date.now();
  }

  function nowMs() {
    return Date.now() + clock.offset;
  }

  // data-deadline: 남은 시간 / data-since: 지난 시간. data-overdue-class: 마감이 지나면 붙일 클래스
  function liveDeadline(node, deadlineIso, overdueClass, withIcon) {
    node.dataset.deadline = deadlineIso;
    if (overdueClass) node.dataset.overdueClass = overdueClass;
    if (withIcon) node.dataset.overdueIcon = "1";
    renderLive(node);
    return node;
  }

  function liveSince(node, sinceIso) {
    node.dataset.since = sinceIso;
    renderLive(node);
    return node;
  }

  function renderLive(node) {
    if (node.dataset.since) {
      var since = parseLocal(node.dataset.since);
      if (!isNaN(since)) renderTicker(node, timeParts(nowMs() - since), "", false);
      return;
    }
    var deadline = parseLocal(node.dataset.deadline);
    if (isNaN(deadline)) return;
    var left = deadline - nowMs();
    var overdue = left < 0;
    if (node.dataset.overdueClass) node.classList.toggle(node.dataset.overdueClass, overdue);
    var row = node.closest(".reservation-row");
    if (row) row.classList.toggle("is-overdue", overdue);
    renderTicker(node, timeParts(left), overdue ? "초과" : "남음", overdue && !!node.dataset.overdueIcon);
  }

  // ── 초 단위 숫자 애니메이션 ──────────────────────────────────────
  // 화면의 시간은 초까지 보여 주고, 바뀐 숫자 한 자리만 아래에서 위로 부드럽게 올라온다 (주행거리계처럼).
  // 앞 단위가 있으면 두 자리로 채워(05분 09초) 숫자가 바뀌어도 글자 폭이 흔들리지 않게 한다.
  var REDUCED_MOTION = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);

  function pad2(n) {
    return n < 10 ? "0" + n : String(n);
  }

  // 예: [{num: "3", unit: "시간"}, {num: "05", unit: "분"}, {num: "09", unit: "초"}]
  function timeParts(ms) {
    var total = Math.floor(Math.abs(ms) / 1000);
    var values = [
      [Math.floor(total / 86400), "일"],
      [Math.floor((total % 86400) / 3600), "시간"],
      [Math.floor((total % 3600) / 60), "분"],
      [total % 60, "초"],
    ];
    var parts = [];
    values.forEach(function (pair, index) {
      if (!parts.length && pair[0] === 0 && index < values.length - 1) return;
      parts.push({ num: parts.length ? pad2(pair[0]) : String(pair[0]), unit: pair[1] });
    });
    return parts;
  }

  function renderTicker(node, parts, suffix, withIcon) {
    // 자릿수·단위·아이콘이 그대로면 바뀐 숫자만 굴리고, 달라졌을 때만 새로 그린다
    var signature =
      parts.map(function (p) { return p.num.length + p.unit; }).join(" ") + "|" + suffix + "|" + (withIcon ? "icon" : "");
    var digits = parts.map(function (p) { return p.num; }).join("");
    if (node.dataset.tickerSig !== signature) {
      node.dataset.tickerSig = signature;
      node.textContent = "";
      if (withIcon) node.appendChild(icon("alarm-clock"));
      var ticker = el("span", "ticker");
      parts.forEach(function (part) {
        for (var i = 0; i < part.num.length; i++) {
          var slot = el("span", "tick-digit");
          slot.appendChild(el("span", "tick-face", part.num.charAt(i)));
          ticker.appendChild(slot);
        }
        ticker.appendChild(el("span", "tick-unit", part.unit));
      });
      if (suffix) ticker.appendChild(el("span", "tick-suffix", suffix));
      node.appendChild(ticker);
      return;
    }
    node.querySelectorAll(".tick-digit").forEach(function (slot, index) {
      if (slot.lastElementChild.textContent !== digits.charAt(index)) rollDigit(slot, digits.charAt(index));
    });
  }

  function rollDigit(slot, next) {
    if (REDUCED_MOTION) {
      slot.lastElementChild.textContent = next;
      return;
    }
    // 아직 사라지는 중인 숫자가 있으면 먼저 치운다 (탭을 오래 비웠다 돌아온 경우 등)
    while (slot.children.length > 1) slot.removeChild(slot.firstElementChild);
    var old = slot.firstElementChild;
    old.className = "tick-face is-leaving";
    var face = el("span", "tick-face is-entering", next);
    slot.appendChild(face);
    old.addEventListener("animationend", function () {
      if (old.parentNode) old.parentNode.removeChild(old);
    });
    face.addEventListener("animationend", function () {
      face.classList.remove("is-entering");
    });
  }

  function tickTimes() {
    document.querySelectorAll("[data-deadline], [data-since]").forEach(renderLive);
  }

  function $(selector, scope) {
    return (scope || document).querySelector(selector);
  }

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function icon(name, extraClass) {
    var svg = document.createElementNS(SVG_NS, "svg");
    svg.setAttribute("class", "icon" + (extraClass ? " " + extraClass : ""));
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("focusable", "false");
    var use = document.createElementNS(SVG_NS, "use");
    use.setAttribute("href", "#icon-" + name);
    svg.appendChild(use);
    return svg;
  }

  function withIcon(node, name, text) {
    node.appendChild(icon(name, "icon-sm"));
    node.appendChild(document.createTextNode(text));
    return node;
  }

  function badge(text, tone, iconName) {
    var node = el("span", "badge" + (tone ? " " + tone : ""));
    if (iconName) node.appendChild(icon(iconName));
    node.appendChild(document.createTextNode(text));
    return node;
  }

  // 단말 사진 (없거나 불러오지 못하면 기본 단말 아이콘)
  function deviceThumb(image, label, large) {
    var box = el("span", "device-thumb" + (large ? " is-large" : ""));
    var fallback = function () {
      box.innerHTML = "";
      box.appendChild(icon("smartphone", large ? "" : "icon-sm"));
    };
    if (!image) {
      fallback();
      return box;
    }
    var img = document.createElement("img");
    img.src = image.url;
    img.alt = large ? label : "";
    img.loading = "lazy";
    img.decoding = "async";
    img.addEventListener("error", fallback);
    box.title = image.is_representative ? label + " (대표 이미지 · 실제 색상과 다를 수 있음)" : label;
    box.appendChild(img);
    return box;
  }

  // 번호이동: [기존 통신사 로고] → [KT 로고]. 로고가 없으면 이름을 글자로 쓴다.
  function carrierMark(carrier) {
    if (!carrier) return el("span", "carrier-name", "미입력");
    if (!carrier.logo_url) return el("span", "carrier-name", carrier.label);
    var img = document.createElement("img");
    img.className = "carrier-logo carrier-" + carrier.code;
    img.src = carrier.logo_url;
    img.alt = carrier.label;
    img.addEventListener("error", function () {
      img.replaceWith(el("span", "carrier-name", carrier.label));
    });
    return img;
  }

  function carrierChange(change, large) {
    var box = el("span", "carrier-change" + (large ? " is-large" : ""));
    box.title = "번호이동 · " + change.label;
    box.appendChild(carrierMark(change.from));
    box.appendChild(el("span", "carrier-arrow", "→"));
    box.appendChild(carrierMark(change.to));
    return box;
  }

  function statusBadge(status, label) {
    return badge(label, STATUS_TONES[status], STATUS_ICONS[status]);
  }

  function riskBadge(level, label, score) {
    var node = el("span", "badge " + (RISK_TONES[level] || ""));
    node.appendChild(el("span", "badge-dot"));
    node.appendChild(document.createTextNode(label));
    node.title = "이탈위험 점수 " + score;
    return node;
  }

  // 로딩 · 빈 목록 · 오류를 같은 모양으로 그린다
  function stateBlock(kind, title, desc) {
    var icons = { loading: "loader-circle", empty: "inbox", error: "triangle-alert" };
    var block = el("div", "state-block" + (kind === "error" ? " is-error" : ""));
    block.appendChild(icon(icons[kind], "state-icon" + (kind === "loading" ? " is-spinning" : "")));
    block.appendChild(el("span", "state-title", title));
    if (desc) block.appendChild(el("span", "state-desc", desc));
    return block;
  }

  function tableState(kind, title, desc) {
    var tbody = $("#reservation-rows");
    tbody.innerHTML = "";
    var row = el("tr");
    var cell = el("td", "table-state");
    cell.colSpan = 7;
    cell.appendChild(stateBlock(kind, title, desc));
    row.appendChild(cell);
    tbody.appendChild(row);
  }

  function request(method, url) {
    return fetch(url, { method: method, headers: { "Content-Type": "application/json" } })
      .then(function (response) {
        return response.json();
      })
      .then(function (body) {
        if (!body.success) throw new Error((body.error && body.error.message) || "요청을 처리하지 못했습니다.");
        return body.data;
      });
  }

  // ── 목록 ────────────────────────────────────────────────────────

  function loadList() {
    return request("GET", "/api/reservations?filter=" + encodeURIComponent(state.filter))
      .then(renderList)
      .catch(function (err) {
        tableState("error", "예약 목록을 불러오지 못했습니다.", err.message);
      });
  }

  function renderList(data) {
    syncClock(data.generated_at);
    Object.keys(data.summary).forEach(function (key) {
      var target = document.getElementById("summary-" + key);
      if (target) target.textContent = data.summary[key];
    });
    var noteTones = data.summary_note_tones || {};
    Object.keys(data.summary_notes || {}).forEach(function (key) {
      var note = document.getElementById("summary-note-" + key);
      if (!note) return;
      note.textContent = data.summary_notes[key];
      note.className = "summary-note" + (noteTones[key] ? " tone-" + noteTones[key] : "");
    });
    data.filters.forEach(function (filter) {
      var count = document.querySelector('[data-count-for="' + filter.key + '"]');
      if (count) count.textContent = filter.count;
    });
    document.querySelectorAll(".filter-tab").forEach(function (tab) {
      tab.setAttribute("aria-selected", String(tab.dataset.filter === data.filter));
    });
    document.querySelectorAll(".summary-card").forEach(function (card) {
      card.classList.toggle("is-active", card.dataset.filter === data.filter);
    });

    var tbody = $("#reservation-rows");
    tbody.innerHTML = "";
    if (data.items.length === 0) {
      tableState("empty", "해당하는 예약이 없습니다.", "다른 필터를 선택해 보세요.");
      return;
    }

    var rank = 0;
    data.items.forEach(function (item) {
      tbody.appendChild(renderRow(item, item.is_open ? ++rank : null));
    });
  }

  function renderRow(item, rank) {
    var row = el(
      "tr",
      "reservation-row" +
        (item.is_open ? "" : " is-closed") +
        (item.is_overdue ? " is-overdue" : "") +
        (item.reservation_id === state.selectedId ? " is-selected" : "")
    );
    row.tabIndex = 0;
    row.dataset.id = item.reservation_id;
    if (item.reservation_id === state.selectedId) row.classList.add("is-selected");

    var priority = el("td", "col-num");
    var priorityCell = el("div", "priority-cell");
    if (rank !== null) {
      priorityCell.appendChild(el("span", "priority-rank" + (rank <= 3 ? " is-top" : ""), rank));
      var score = el("span", "priority-score", item.priority_score);
      score.appendChild(el("span", "priority-unit", "점"));
      priorityCell.appendChild(score);
    } else {
      priorityCell.appendChild(el("span", "cell-sub", "-"));
    }
    priority.appendChild(priorityCell);
    row.appendChild(priority);

    var customer = el("td");
    customer.appendChild(el("span", "cell-main cell-strong", item.customer_name));
    var customerSub = el("span", "cell-sub cell-sub-inline", item.reservation_id + " · ");
    if (item.carrier_change) {
      customerSub.appendChild(carrierChange(item.carrier_change, false));
    } else {
      customerSub.appendChild(document.createTextNode(item.line_type_label));
    }
    customer.appendChild(customerSub);
    row.appendChild(customer);

    var device = el("td", "cell-device");
    var deviceCell = el("div", "device-cell");
    deviceCell.appendChild(deviceThumb(item.device_image, item.device_label, false));
    var deviceText = el("div", "device-text");
    var deviceName = el("span", "cell-main", item.device_model);
    deviceName.title = item.device_label;
    deviceText.appendChild(deviceName);
    deviceText.appendChild(el("span", "cell-sub", item.device_option + " · " + item.store_name));
    deviceCell.appendChild(deviceText);
    device.appendChild(deviceCell);
    row.appendChild(device);

    var issues = el("td", "cell-issues");
    var chips = el("div", "chip-list");
    if (item.issues.length === 0) {
      chips.appendChild(el("span", "cell-sub", item.is_open ? "문제 없음" : "-"));
    }
    item.issues.forEach(function (issue) {
      chips.appendChild(el("span", "chip", issue.label));
    });
    issues.appendChild(chips);
    row.appendChild(issues);

    var risk = el("td");
    if (item.is_open) {
      risk.appendChild(riskBadge(item.risk_level, item.risk_label, item.churn_risk_score));
    } else {
      risk.appendChild(el("span", "cell-sub", "-"));
    }
    row.appendChild(risk);

    var deadline = el("td", "cell-deadline");
    if (item.is_open) {
      var deadlineLabel = el("span", "cell-main cell-strong");
      deadlineLabel.appendChild(document.createTextNode(item.deadline_label));
      deadline.appendChild(liveDeadline(deadlineLabel, item.activation_deadline, "deadline-overdue", true));
      deadline.appendChild(el("span", "cell-sub", item.deadline_display));
    } else {
      deadline.appendChild(el("span", "cell-sub", item.completed_at_display ? item.completed_at_display + " 완료" : "-"));
    }
    row.appendChild(deadline);

    var status = el("td");
    status.appendChild(statusBadge(item.status, item.status_label));
    row.appendChild(status);

    row.addEventListener("click", function () {
      selectReservation(item.reservation_id);
    });
    row.addEventListener("keydown", function (event) {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        selectReservation(item.reservation_id);
      }
    });
    return row;
  }

  // ── 상세 패널 ────────────────────────────────────────────────────

  function selectReservation(id) {
    state.selectedId = id;
    document.querySelectorAll(".reservation-row").forEach(function (row) {
      row.classList.toggle("is-selected", row.dataset.id === id);
    });
    var url = new URL(window.location.href);
    url.searchParams.set("reservation", id);
    window.history.replaceState(null, "", url);
    openPanel();
    $("#detail-body").innerHTML = "";
    $("#detail-body").appendChild(stateBlock("loading", "상세 정보를 불러오는 중입니다..."));
    return loadDetail();
  }

  function loadDetail(message) {
    if (!state.selectedId) return Promise.resolve();
    return request("GET", "/api/reservations/" + encodeURIComponent(state.selectedId))
      .then(function (detail) {
        renderDetail(detail, message);
      })
      .catch(function (err) {
        $("#detail-body").innerHTML = "";
        $("#detail-body").appendChild(stateBlock("error", "상세 정보를 불러오지 못했습니다.", err.message));
      });
  }

  function openPanel() {
    $("#detail-panel").hidden = false;
    $("#drawer-backdrop").hidden = false;
    $("#dashboard-layout").classList.add("has-detail");
  }

  function closePanel() {
    state.selectedId = null;
    $("#detail-panel").hidden = true;
    $("#drawer-backdrop").hidden = true;
    $("#dashboard-layout").classList.remove("has-detail");
    document.querySelectorAll(".reservation-row.is-selected").forEach(function (row) {
      row.classList.remove("is-selected");
    });
    var url = new URL(window.location.href);
    url.searchParams.delete("reservation");
    window.history.replaceState(null, "", url);
  }

  function section(title) {
    var wrap = el("section", "detail-section");
    wrap.appendChild(el("h3", null, title));
    return wrap;
  }

  function scoreTile(label, value, sub, className) {
    var tile = el("div", "score-tile");
    tile.appendChild(el("span", "score-tile-label", label));
    tile.appendChild(el("span", "score-tile-value" + (className ? " " + className : ""), value));
    if (sub) tile.appendChild(el("span", "score-tile-sub", sub));
    return tile;
  }

  function renderDetail(detail, message) {
    var eyebrow = $("#detail-id");
    eyebrow.innerHTML = "";
    eyebrow.appendChild(document.createTextNode(detail.reservation_id));
    eyebrow.appendChild(statusBadge(detail.status, detail.status_label));
    $("#detail-title").textContent = detail.customer_name + " 고객";
    syncClock(detail.generated_at);

    var body = $("#detail-body");
    body.innerHTML = "";

    if (message) {
      var messageIcon = message.kind === "is-error" ? "triangle-alert" : "circle-check";
      body.appendChild(withIcon(el("div", "panel-message " + message.kind), messageIcon, message.text));
    }

    var deviceSummary = el("div", "detail-device");
    deviceSummary.appendChild(deviceThumb(detail.device_image, detail.device_label, true));
    var deviceInfo = el("div");
    deviceInfo.appendChild(el("span", "detail-device-model", detail.device_model));
    deviceInfo.appendChild(el("span", "detail-device-option", detail.device_option + " · " + detail.store_name));
    if (detail.device_image && detail.device_image.is_representative) {
      deviceInfo.appendChild(el("span", "detail-device-note", "대표 이미지 · 실제 색상과 다를 수 있음"));
    }
    deviceSummary.appendChild(deviceInfo);
    body.appendChild(deviceSummary);

    var scores = el("div", "score-grid");
    if (detail.is_open) {
      var riskClass = detail.risk_level === "high" ? "tone-danger" : detail.risk_level === "medium" ? "tone-warning" : "tone-success";
      scores.appendChild(scoreTile("이탈위험 점수", detail.churn_risk_score, detail.risk_label, riskClass));
      scores.appendChild(scoreTile("우선순위", detail.priority_score + "점", null));
      var deadlineTile = scoreTile("처리 마감", detail.deadline_label, detail.deadline_display, null);
      deadlineTile.classList.add("is-countdown");
      liveDeadline($(".score-tile-value", deadlineTile), detail.activation_deadline, "tone-danger", false);
      scores.appendChild(deadlineTile);
    } else {
      scores.appendChild(scoreTile("진행상태", detail.status_label, detail.completed_at_display));
    }
    body.appendChild(scores);

    // 고객 및 예약정보
    var info = section("고객 및 예약정보");
    var dl = el("dl", "info-list");
    [
      ["고객", detail.customer_name + " (" + detail.customer_id + ")"],
      ["연락처", detail.customer_phone || "-"],
      ["가입유형", detail.line_type_label],
      ["단말", detail.device_label],
      ["매장", detail.store_name],
      ["희망 수령일", detail.desired_activation_date],
      ["예약 등록", detail.created_at_display],
      ["고객 대기", detail.waiting_label],
      ["재시도", detail.retry_count + "회"],
      ["진행상태", detail.status_label],
    ].forEach(function (pair) {
      dl.appendChild(el("dt", null, pair[0]));
      var value = el("dd", null, pair[1]);
      // 가입유형이 번호이동이면 통신사 변경을 로고로 함께 보여 준다
      if (pair[0] === "가입유형" && detail.carrier_change) {
        value.textContent = pair[1] + " ";
        value.appendChild(carrierChange(detail.carrier_change, true));
      }
      if (pair[0] === "고객 대기" && detail.waiting_since) liveSince(value, detail.waiting_since);
      dl.appendChild(value);
    });
    info.appendChild(dl);
    body.appendChild(info);

    // 고객 메모 (업로드 명단의 자유 메모) + AI·규칙 해석 결과
    if (detail.memo) {
      var memoSection = section("고객 메모");
      var memoBox = el("div", "memo-box");
      memoBox.appendChild(withIcon(el("p", "memo-text"), "sticky-note", detail.memo));
      var insight = detail.memo_insight;
      if (insight) {
        var facts = el("ul", "insight-list");
        if (insight.flexible_colors && insight.flexible_colors.length) {
          facts.appendChild(el("li", null, "대체 가능 색상: " + insight.flexible_colors.join(", ")));
        }
        if (insight.document_eta) facts.appendChild(el("li", null, "서류 제출 예정일: " + insight.document_eta));
        if (insight.contact_preference) facts.appendChild(el("li", null, "선호 연락: " + insight.contact_preference));
        if (!facts.childNodes.length) facts.appendChild(el("li", null, "해결책에 반영할 정보를 찾지 못했습니다."));
        memoBox.appendChild(facts);
        memoBox.appendChild(sourceTag(insight, "메모 해석"));
      }
      memoSection.appendChild(memoBox);
      body.appendChild(memoSection);
    }

    // AI 브리핑 (누를 때만 생성)
    if (detail.is_open) {
      var briefing = section("AI 브리핑");
      var briefingBody = el("div", "briefing-box");
      briefingBody.appendChild(el("p", "muted", "이 예약이 왜 급한지 3줄로 요약합니다."));
      var briefingButton = withIcon(el("button", "btn-secondary btn-small"), "sparkles", "브리핑 생성");
      briefingButton.type = "button";
      briefingButton.addEventListener("click", function () {
        briefingButton.disabled = true;
        briefingButton.lastChild.textContent = "생성 중...";
        request("POST", "/api/reservations/" + encodeURIComponent(detail.reservation_id) + "/briefing")
          .then(function (result) {
            briefingBody.innerHTML = "";
            briefingBody.appendChild(el("p", "briefing-text", result.text));
            briefingBody.appendChild(sourceTag(result, "직원 브리핑"));
            loadIntegrations();
          })
          .catch(function (err) {
            briefingBody.innerHTML = "";
            briefingBody.appendChild(stateBlock("error", "브리핑을 만들지 못했습니다.", err.message));
          });
      });
      briefingBody.appendChild(briefingButton);
      briefing.appendChild(briefingBody);
      body.appendChild(briefing);
    }

    // 문제 원인
    if (detail.is_open) {
      var issues = section("문제 원인");
      if (detail.issues.length === 0) {
        issues.appendChild(el("p", "muted", "남은 문제가 없습니다."));
      } else {
        var issueList = el("ul", "issue-cards");
        detail.issues.forEach(function (issue) {
          var li = el("li", "issue-card");
          li.appendChild(icon("circle-alert", "icon-sm"));
          var text = el("div");
          text.appendChild(el("strong", null, issue.label));
          text.appendChild(el("span", null, issue.summary));
          li.appendChild(text);
          issueList.appendChild(li);
        });
        issues.appendChild(issueList);
      }
      body.appendChild(issues);
    }

    // 해결책
    if (detail.is_open) {
      var actions = section("Agent 제안 해결책");
      if (detail.can_complete) {
        var ready = el("div", "ready-box");
        ready.appendChild(withIcon(el("p"), "circle-check", "모든 문제가 해결됐습니다. 개통을 진행한 뒤 완료 처리하세요."));
        var completeButton = el("button", "btn-success btn-small", "개통 완료 처리");
        completeButton.type = "button";
        completeButton.addEventListener("click", function () {
          runAction(completeButton, "/api/reservations/" + detail.reservation_id + "/complete", "개통 완료로 처리했습니다.");
        });
        ready.appendChild(completeButton);
        actions.appendChild(ready);
      } else if (detail.actions.length === 0) {
        actions.appendChild(el("p", "muted", "제안할 해결책이 없습니다."));
      }
      var actionList = el("ul", "action-cards");
      detail.actions.forEach(function (action) {
        actionList.appendChild(renderActionCard(detail.reservation_id, action));
      });
      actions.appendChild(actionList);
      body.appendChild(actions);
    }

    // 점수 근거
    if (detail.is_open) {
      var factors = section("점수 근거");
      var columns = el("div", "factor-columns");
      columns.appendChild(factorColumn("이탈위험", detail.churn_factors));
      columns.appendChild(factorColumn("우선순위", detail.priority_factors));
      factors.appendChild(columns);
      body.appendChild(factors);
    }

    // 알림 기록 (n8n → Gmail)
    if (detail.notifications && detail.notifications.length) {
      var notices = section("알림 기록");
      var noticeList = el("ul", "notice-list");
      detail.notifications.forEach(function (item) {
        noticeList.appendChild(renderNotification(item));
      });
      notices.appendChild(noticeList);
      body.appendChild(notices);
    }

    // 처리이력
    var history = section("처리이력");
    var timeline = el("ul", "timeline");
    detail.history.forEach(function (item) {
      var li = el("li");
      li.appendChild(el("span", "timeline-meta", item.created_at_display + " · " + item.event_label));
      li.appendChild(el("span", null, item.description));
      timeline.appendChild(li);
    });
    history.appendChild(timeline);
    body.appendChild(history);
  }

  // AI 결과의 출처 표시: 실제 AI 호출이면 모델·응답 시간, 아니면 규칙 기반
  function sourceTag(result, label) {
    var tag = el("span", "source-tag" + (result.source === "ai" ? " is-ai" : ""));
    tag.appendChild(icon(result.source === "ai" ? "sparkles" : "info", "icon-sm"));
    var text =
      result.source === "ai"
        ? label + " · AI 생성 · " + result.model + " · " + (result.latency_ms / 1000).toFixed(1) + "초"
        : label + " · 규칙 기반" + (result.ai_error ? " (AI 실패: " + result.ai_error + ")" : " (AI 꺼짐)");
    tag.appendChild(document.createTextNode(text));
    return tag;
  }

  var NOTICE_TONES = { SENT: "tone-success", FAILED: "tone-danger", DEMO: "" };

  function renderNotification(item) {
    var li = el("li", "notice-item");
    var top = el("div", "notice-top");
    top.appendChild(withIcon(el("span", "notice-kind"), "mail", item.kind_label));
    top.appendChild(badge(item.status_label, NOTICE_TONES[item.status]));
    li.appendChild(top);
    var details = el("details", "notice-body");
    details.appendChild(el("summary", null, item.subject));
    details.appendChild(el("pre", "notice-text", item.body));
    li.appendChild(details);
    if (item.last_error) li.appendChild(el("p", "notice-error", item.last_error));
    if (item.can_retry) {
      var retry = el("button", "btn-secondary btn-small", "다시 보내기");
      retry.type = "button";
      retry.addEventListener("click", function () {
        retry.disabled = true;
        request("POST", "/api/notifications/" + item.notification_id + "/retry")
          .then(function () {
            return loadDetail({ kind: "is-info", text: "알림을 다시 보냈습니다." });
          })
          .catch(function (err) {
            return loadDetail({ kind: "is-error", text: err.message });
          });
      });
      li.appendChild(retry);
    }
    return li;
  }

  // 연동 상태: n8n(Gmail) · AI
  function loadIntegrations() {
    var box = $("#integration-chips");
    if (!box) return;
    request("GET", "/api/integrations")
      .then(function (data) {
        box.innerHTML = "";
        var n8n = el("span", "integration-chip" + (data.n8n.mode === "n8n" ? " is-on" : ""));
        n8n.appendChild(el("span", "integration-dot"));
        n8n.appendChild(document.createTextNode(data.n8n.mode === "n8n" ? "n8n 연결됨" : "메일 미연결"));
        n8n.title = data.n8n.mode === "n8n" ? "알림을 n8n → Gmail 로 보냅니다." : "N8N_WEBHOOK_URL 이 비어 있어 메일을 보내지 않고 기록만 합니다.";
        var ai = el("span", "integration-chip" + (data.ai.mode === "ai" ? " is-on" : ""));
        ai.appendChild(el("span", "integration-dot"));
        ai.appendChild(document.createTextNode(data.ai.mode === "ai" ? "AI " + data.ai.model : "AI 꺼짐 · 규칙 기반"));
        var last = data.ai_logs[0];
        ai.title = last
          ? "최근 AI 기록: " + last.feature_label + " · " + (last.mode === "ai" ? "AI" : "규칙") + " · " + last.created_at.replace("T", " ")
          : "아직 AI 기록이 없습니다.";
        box.appendChild(n8n);
        box.appendChild(ai);

        var events = data.events;
        var pulling = events.pull && !events.last_error;
        var ev = el("span", "integration-chip" + (pulling ? " is-on" : ""));
        ev.appendChild(el("span", "integration-dot"));
        var text = "외부 이벤트 받는 중";
        var title =
          "n8n 이 POST /api/events 로 보내 주는 외부 이벤트를 반영합니다" +
          (events.inbound_auth === "secret" ? " (비밀 헤더 인증)." : " (이 컴퓨터에서 온 요청만).");
        if (events.pull && events.last_error) {
          text = "외부 이벤트 연결 확인 필요";
          title = "n8n 에서 이벤트를 가져오지 못했습니다: " + events.last_error;
        } else if (events.pull) {
          text = "외부 이벤트 자동 확인" + (events.sync_seconds ? " · " + events.sync_seconds + "초" : "");
          title =
            "SaveDeal 서버가 주기적으로 n8n 에서 개통 반려·입고 지연 같은 외부 이벤트를 가져와 반영하고, 새 고위험 예약을 점검합니다." +
            (events.last_run ? " 마지막 확인: " + events.last_run.replace("T", " ") : "");
        }
        ev.appendChild(document.createTextNode(text));
        ev.title = title;
        box.appendChild(ev);
        startEventWatch(events);
      })
      .catch(function () {
        box.innerHTML = "";
      });
  }

  // ── 외부 이벤트 ─────────────────────────────────────────────────
  // 외부 이벤트(개통 반려, 서류 도착 등)가 반영되면 화면을 다시 그린다.
  // 가져오기는 보통 서버의 백그라운드 작업이 한다. 그게 꺼져 있을 때만 화면이 대신 가져오기를 요청한다.
  var EVENT_CHECK_MS = 15000;
  var eventWatch = { started: false, lastId: null };

  function checkEvents() {
    return request("GET", "/api/events?limit=10").then(function (data) {
      if (eventWatch.lastId === null) {
        eventWatch.lastId = data.last_id;
        return;
      }
      if (data.last_id <= eventWatch.lastId) return;
      var fresh = data.items.filter(function (item) {
        return item.event_id > eventWatch.lastId && item.result === "APPLIED";
      });
      eventWatch.lastId = data.last_id;
      if (!fresh.length) return;
      var first = fresh[0];
      window.ccToast &&
        window.ccToast(
          "외부 이벤트 반영: " + first.reservation_id + " " + first.event_label + (fresh.length > 1 ? " 외 " + (fresh.length - 1) + "건" : "")
        );
      loadList();
      if (state.selectedId) loadDetail();
    });
  }

  function startEventWatch(config) {
    if (eventWatch.started) return;
    eventWatch.started = true;
    checkEvents().catch(function () {});
    // 연동 상태 칩(마지막 확인 시각·연결 오류)도 1분마다 새로 그린다
    window.setInterval(function () {
      if (!document.hidden) loadIntegrations();
    }, 60000);
    window.setInterval(function () {
      if (!document.hidden) checkEvents().catch(function () {});
    }, EVENT_CHECK_MS);
    if (config.pull && !config.background) {
      window.setInterval(function () {
        if (document.hidden) return;
        request("POST", "/api/events/sync")
          .then(checkEvents)
          .catch(function (err) {
            window.console && console.warn("외부 이벤트 가져오기 실패:", err.message);
          });
      }, 60000);
    }
  }

  function factorColumn(title, factors) {
    var column = el("div");
    column.appendChild(el("h4", null, title));
    var list = el("ul", "factor-list");
    if (factors.length === 0) list.appendChild(el("li", "muted", "해당 없음"));
    factors.forEach(function (factor) {
      var li = el("li");
      li.appendChild(el("span", null, factor.label));
      li.appendChild(el("span", "factor-points", "+" + factor.points));
      list.appendChild(li);
    });
    column.appendChild(list);
    return column;
  }

  function renderActionCard(reservationId, action) {
    var card = el("li", "action-card" + (action.can_record_result ? " is-approved" : ""));
    var top = el("div", "action-card-top");
    top.appendChild(el("span", "action-type", action.issue_label + " · " + action.type_label));
    top.appendChild(badge(action.status_label, ACTION_STATUS_TONES[action.status], action.status === "APPROVED" ? "circle-dashed" : null));
    card.appendChild(top);
    card.appendChild(el("span", "action-title", action.title));
    card.appendChild(el("p", "action-desc", action.description));

    var base = "/api/reservations/" + encodeURIComponent(reservationId) + "/actions/" + action.action_id;
    var buttons = el("div", "action-buttons");
    if (action.can_approve) {
      var approve = el("button", "btn-primary btn-small", "승인");
      approve.type = "button";
      approve.addEventListener("click", function () {
        runAction(approve, base + "/approve", "'" + action.title + "' 해결책을 승인했습니다. 실행 결과를 입력해 주세요.");
      });
      buttons.appendChild(approve);
    }
    if (action.can_record_result) {
      var succeed = withIcon(el("button", "btn-success btn-small"), "check", "실행 성공");
      succeed.type = "button";
      succeed.addEventListener("click", function () {
        runAction(succeed, base + "/succeed", "'" + action.title + "' 성공으로 문제를 해결했습니다.");
      });
      var fail = withIcon(el("button", "btn-danger-outline btn-small"), "x", "실행 실패");
      fail.type = "button";
      fail.addEventListener("click", function () {
        runAction(fail, base + "/fail", "'" + action.title + "' 실패. Agent가 새로운 대안을 생성했습니다.");
      });
      buttons.appendChild(succeed);
      buttons.appendChild(fail);
    }
    if (buttons.childNodes.length) card.appendChild(buttons);
    return card;
  }

  function runAction(button, url, successText) {
    document.querySelectorAll("#detail-body button").forEach(function (b) {
      b.disabled = true;
    });
    button.textContent = "처리 중...";
    request("POST", url)
      .then(function (detail) {
        renderDetail(detail, { kind: "is-info", text: successText });
        return loadList();
      })
      .catch(function (err) {
        return loadDetail({ kind: "is-error", text: err.message });
      });
  }

  // ── 초기화 ─────────────────────────────────────────────────────

  function setFilter(filter) {
    state.filter = filter;
    loadList();
  }

  function init() {
    document.querySelectorAll(".filter-tab, .summary-card").forEach(function (button) {
      button.addEventListener("click", function () {
        setFilter(button.dataset.filter);
      });
    });
    $("#detail-close").addEventListener("click", closePanel);
    $("#drawer-backdrop").addEventListener("click", closePanel);
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && state.selectedId) closePanel();
    });
    loadIntegrations();
    // 남은 시간·대기 시간은 1초마다, 점수·우선순위·건수는 1분마다 서버에서 새로 받아 흐르게 한다
    window.setInterval(function () {
      if (!document.hidden) tickTimes();
    }, 1000);
    window.setInterval(function () {
      if (!document.hidden) loadList();
    }, 60000);
    $("#send-report").addEventListener("click", function () {
      var button = $("#send-report");
      button.disabled = true;
      request("POST", "/api/notifications/daily-report")
        .then(function (result) {
          window.ccToast && window.ccToast("운영 리포트 " + result.status_label + (result.status === "DEMO" ? " (메일 미연결)" : ""));
        })
        .catch(function (err) {
          window.ccToast && window.ccToast("리포트를 보내지 못했습니다: " + err.message);
        })
        .finally(function () {
          button.disabled = false;
        });
    });
    // 최신화: 서버가 60초마다 하는 일(외부 이벤트 가져오기 + 고위험 점검)을 지금 바로 하고 화면을 새로 그린다
    $("#refresh-now").addEventListener("click", function () {
      var button = $("#refresh-now");
      var spinner = button.querySelector(".icon");
      button.disabled = true;
      spinner && spinner.classList.add("is-spinning");
      request("POST", "/api/events/sync")
        .then(function (result) {
          var applied = (result.counts && result.counts.APPLIED) || 0;
          var alerts = result.scan ? result.scan.new_alerts.length : 0;
          var message = !result.enabled
            ? "최신 상태로 새로 고쳤습니다."
            : applied
              ? "외부 이벤트 " + applied + "건을 반영했습니다."
              : "새로 들어온 외부 이벤트가 없습니다.";
          if (alerts) message += " 새 고위험 예약 " + alerts + "건을 알렸습니다.";
          window.ccToast && window.ccToast(message);
          // 방금 반영한 이벤트를 자동 확인이 다시 알리지 않게 기준을 맞춘다
          return request("GET", "/api/events?limit=1").then(function (data) {
            eventWatch.lastId = data.last_id;
          });
        })
        .catch(function (err) {
          window.ccToast && window.ccToast("외부 이벤트를 가져오지 못했습니다: " + err.message);
        })
        .then(function () {
          loadIntegrations();
          return Promise.all([loadList(), loadDetail()]);
        })
        .finally(function () {
          button.disabled = false;
          spinner && spinner.classList.remove("is-spinning");
        });
    });
    $("#reset-demo").addEventListener("click", function () {
      if (!window.confirm("모든 예약·해결책·처리이력을 지우고 초기 데이터로 되돌릴까요?")) return;
      request("POST", "/api/demo/reset").then(function () {
        closePanel();
        loadList();
      });
    });

    var initial = new URL(window.location.href).searchParams.get("reservation");
    loadList().then(function () {
      if (initial) selectReservation(initial);
    });
  }

  document.addEventListener("DOMContentLoaded", init);
})();
