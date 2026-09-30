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
    var row = el("tr", "reservation-row" + (item.is_open ? "" : " is-closed") + (item.is_overdue ? " is-overdue" : ""));
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
    customer.appendChild(el("span", "cell-sub", item.reservation_id + " · " + item.line_type_label));
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
      var deadlineLabel = el("span", "cell-main cell-strong" + (item.is_overdue ? " deadline-overdue" : ""));
      if (item.is_overdue) deadlineLabel.appendChild(icon("alarm-clock"));
      deadlineLabel.appendChild(document.createTextNode(item.deadline_label));
      deadline.appendChild(deadlineLabel);
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
      scores.appendChild(
        scoreTile("처리 마감", detail.deadline_label, detail.deadline_display, detail.is_overdue ? "tone-danger" : null)
      );
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
      dl.appendChild(el("dd", null, pair[1]));
    });
    info.appendChild(dl);
    body.appendChild(info);

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
    $("#reset-demo").addEventListener("click", function () {
      if (!window.confirm("모든 예약·해결책·처리이력을 지우고 데모 데이터로 되돌릴까요?")) return;
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
