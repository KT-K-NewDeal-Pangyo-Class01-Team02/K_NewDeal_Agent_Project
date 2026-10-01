// 엑셀·CSV 업로드 화면. 검증·저장 판단은 서버(/api/uploads)가 하고, 이 파일은 결과를 그리기만 한다.
(function () {
  "use strict";

  var SVG_NS = "http://www.w3.org/2000/svg";
  var STATUS_LABELS = { PREVIEW: "확인 대기", COMMITTED: "등록 완료", CANCELLED: "취소" };
  var STATUS_TONES = { PREVIEW: "tone-warning", COMMITTED: "tone-success", CANCELLED: "" };
  // 표시용 이름 (서버가 정규화한 코드 값을 사람이 읽는 말로 바꾼다)
  var VALUE_LABELS = {
    line_type: { NEW: "신규가입", MNP: "번호이동", CHANGE: "기기변경" },
    previous_carrier: { SKT: "SK텔레콤", LGU: "LG U+", MVNO: "알뜰폰" },
  };

  var state = { kind: null, file: null, batch: null };

  function $(selector) {
    return document.querySelector(selector);
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
    var use = document.createElementNS(SVG_NS, "use");
    use.setAttribute("href", "#icon-" + name);
    svg.appendChild(use);
    return svg;
  }

  function stateBlock(kind, title, desc) {
    var icons = { loading: "loader-circle", empty: "inbox", error: "triangle-alert", done: "circle-check" };
    var block = el("div", "state-block" + (kind === "error" ? " is-error" : ""));
    block.appendChild(icon(icons[kind], "state-icon" + (kind === "loading" ? " is-spinning" : "")));
    block.appendChild(el("span", "state-title", title));
    if (desc) block.appendChild(el("span", "state-desc", desc));
    return block;
  }

  function badge(text, tone) {
    return el("span", "badge" + (tone ? " " + tone : ""), text);
  }

  function request(method, url, body) {
    return fetch(url, { method: method, body: body })
      .then(function (response) {
        return response.json();
      })
      .then(function (data) {
        if (!data.success) throw new Error((data.error && data.error.message) || "요청을 처리하지 못했습니다.");
        return data.data;
      });
  }

  function showError(message) {
    var box = $("#upload-error");
    box.textContent = message || "";
    box.hidden = !message;
  }

  function formatValue(key, value) {
    if (value === null || value === undefined || value === "") return "-";
    if (VALUE_LABELS[key]) return VALUE_LABELS[key][value] || value;
    if (value === true) return "예";
    if (value === false) return "아니오";
    if (Array.isArray(value)) return value.join(", ") || "-";
    if (typeof value === "number") return value.toLocaleString("ko-KR");
    return String(value);
  }

  // ── 1. 종류 선택 ─────────────────────────────────────────────

  function selectKind(kind) {
    state.kind = kind;
    document.querySelectorAll(".kind-columns").forEach(function (box) {
      box.hidden = box.dataset.kind !== kind;
    });
    $("#template-link").href = window.SD_TEMPLATE_URL.replace("__KIND__", kind);
    resetPreview();
  }

  // ── 2. 파일 선택 ─────────────────────────────────────────────

  function setFile(file) {
    state.file = file || null;
    $("#dropzone-title").textContent = file ? file.name : "파일을 끌어다 놓거나 눌러서 선택하세요";
    $("#dropzone").classList.toggle("has-file", Boolean(file));
    $("#preview-button").disabled = !file;
    showError("");
    resetPreview();
  }

  function resetPreview() {
    state.batch = null;
    $("#preview-panel").hidden = true;
    $("#preview-body").innerHTML = "";
  }

  function runPreview() {
    if (!state.file) return;
    showError("");
    var button = $("#preview-button");
    button.disabled = true;
    var panel = $("#preview-panel");
    panel.hidden = false;
    $("#preview-body").innerHTML = "";
    $("#preview-body").appendChild(stateBlock("loading", "파일을 읽고 행별로 검증하는 중입니다..."));

    var form = new FormData();
    form.append("kind", state.kind);
    form.append("file", state.file);
    request("POST", "/api/uploads", form)
      .then(function (batch) {
        state.batch = batch;
        renderPreview(batch);
        loadHistory();
      })
      .catch(function (err) {
        panel.hidden = true;
        showError(err.message);
      })
      .finally(function () {
        button.disabled = !state.file;
      });
  }

  // ── 3. 검증 결과 ─────────────────────────────────────────────

  function stat(label, value, tone) {
    var box = el("div", "upload-stat" + (tone ? " " + tone : ""));
    box.appendChild(el("span", "upload-stat-label", label));
    box.appendChild(el("strong", "upload-stat-value num", String(value)));
    return box;
  }

  function renderPreview(batch) {
    var body = $("#preview-body");
    body.innerHTML = "";

    var stats = el("div", "upload-stats");
    stats.appendChild(stat("전체 행", batch.total_rows));
    stats.appendChild(stat("정상", batch.valid_rows, "tone-success"));
    stats.appendChild(stat("오류", batch.error_rows, batch.error_rows ? "tone-danger" : ""));
    body.appendChild(stats);

    if (batch.errors.length) {
      body.appendChild(el("h3", "upload-subtitle", "오류 행 (등록에서 제외됩니다)"));
      var errorList = el("ul", "upload-errors");
      batch.errors.forEach(function (item) {
        var li = el("li");
        li.appendChild(el("span", "upload-error-row num", item.row + "행"));
        li.appendChild(el("span", null, item.messages.join(" / ")));
        errorList.appendChild(li);
      });
      body.appendChild(errorList);
    }

    if (batch.preview && batch.preview.length) {
      var title = "등록할 행 미리보기" + (batch.valid_rows > batch.preview.length ? " (처음 " + batch.preview.length + "행)" : "");
      body.appendChild(el("h3", "upload-subtitle", title));
      var wrap = el("div", "table-wrap");
      var table = el("table", "data-table");
      var head = el("tr");
      head.appendChild(el("th", "col-num", "행"));
      batch.columns.forEach(function (column) {
        head.appendChild(el("th", null, column.label));
      });
      var thead = el("thead");
      thead.appendChild(head);
      table.appendChild(thead);
      var tbody = el("tbody");
      batch.preview.forEach(function (row) {
        var tr = el("tr");
        tr.appendChild(el("td", "col-num", row._row));
        batch.columns.forEach(function (column) {
          var td = el("td", column.key === "memo" ? "cell-memo" : null, formatValue(column.key, row[column.key]));
          if (column.key === "memo" && row.memo) td.title = row.memo;
          tr.appendChild(td);
        });
        tbody.appendChild(tr);
      });
      table.appendChild(tbody);
      wrap.appendChild(table);
      body.appendChild(wrap);
    }

    var actions = el("div", "upload-actions");
    var commit = el("button", "btn-primary");
    commit.type = "button";
    commit.disabled = batch.valid_rows === 0;
    commit.appendChild(icon("check", "icon-sm"));
    commit.appendChild(document.createTextNode("정상 " + batch.valid_rows + "건 등록하기"));
    commit.addEventListener("click", function () {
      runCommit(commit);
    });
    var cancel = el("button", "btn-text", "취소");
    cancel.type = "button";
    cancel.addEventListener("click", runCancel);
    actions.appendChild(commit);
    actions.appendChild(cancel);
    body.appendChild(actions);
  }

  // ── 4. 등록 ──────────────────────────────────────────────────

  function runCommit(button) {
    if (!state.batch) return;
    button.disabled = true;
    button.textContent = "등록 중...";
    request("POST", "/api/uploads/" + state.batch.batch_id + "/commit")
      .then(function (batch) {
        setFileInputEmpty(); // 파일 선택을 비우면 결과 영역도 비워지므로, 완료 화면보다 먼저
        renderDone(batch);
        loadHistory();
      })
      .catch(function (err) {
        showError(err.message);
        button.disabled = false;
        button.textContent = "다시 시도";
      });
  }

  function runCancel() {
    if (!state.batch) return;
    request("POST", "/api/uploads/" + state.batch.batch_id + "/cancel").then(function () {
      setFileInputEmpty();
      loadHistory();
    });
  }

  function setFileInputEmpty() {
    $("#upload-file").value = "";
    setFile(null);
  }

  function resultText(batch) {
    var r = batch.result || {};
    if (batch.kind === "reservations") {
      var parts = ["예약 " + (r.created || 0) + "건 등록"];
      if (r.with_issues !== undefined) parts.push("문제 감지 " + r.with_issues + "건");
      if (r.high_risk !== undefined) parts.push("고위험 " + r.high_risk + "건");
      if (r.due_today !== undefined) parts.push("오늘 마감 " + r.due_today + "건");
      return parts.join(" · ");
    }
    return "신규 " + (r.created || 0) + "건 · 갱신 " + (r.updated || 0) + "건";
  }

  function renderDone(batch) {
    var panel = $("#preview-panel");
    panel.hidden = false;
    var body = $("#preview-body");
    body.innerHTML = "";
    var desc =
      batch.kind === "reservations"
        ? "사전검증과 해결책 생성까지 끝났습니다. 예약 운영 화면에서 우선순위대로 확인하세요."
        : "새 예약의 사전검증부터 이 데이터가 쓰입니다.";
    body.appendChild(stateBlock("done", batch.kind_label + " 등록 완료 · " + resultText(batch), desc));
    if (batch.kind === "reservations") {
      var link = el("a", "btn-primary", "예약 운영 화면으로");
      link.href = "/savedeal";
      var actions = el("div", "upload-actions is-center");
      actions.appendChild(link);
      body.appendChild(actions);
    }
  }

  // ── 최근 업로드 ──────────────────────────────────────────────

  function loadHistory() {
    request("GET", "/api/uploads")
      .then(function (data) {
        var tbody = $("#history-rows");
        tbody.innerHTML = "";
        if (!data.items.length) {
          var row = el("tr");
          var cell = el("td", "table-state");
          cell.colSpan = 6;
          cell.appendChild(stateBlock("empty", "아직 업로드한 파일이 없습니다."));
          row.appendChild(cell);
          tbody.appendChild(row);
          return;
        }
        data.items.forEach(function (batch) {
          var tr = el("tr");
          tr.appendChild(el("td", "num", batch.created_at.replace("T", " ").slice(5, 16)));
          tr.appendChild(el("td", null, batch.kind_label));
          var file = el("td", "cell-file", batch.filename || "-");
          file.title = batch.filename || "";
          tr.appendChild(file);
          tr.appendChild(el("td", "col-num", batch.valid_rows));
          tr.appendChild(el("td", "col-num", batch.error_rows));
          var status = el("td");
          status.appendChild(badge(STATUS_LABELS[batch.status] || batch.status, STATUS_TONES[batch.status]));
          if (batch.status === "COMMITTED") status.appendChild(el("span", "cell-sub", resultText(batch)));
          tr.appendChild(status);
          tbody.appendChild(tr);
        });
      })
      .catch(function () {
        var tbody = $("#history-rows");
        tbody.innerHTML = "";
        var row = el("tr");
        var cell = el("td", "table-state");
        cell.colSpan = 6;
        cell.appendChild(stateBlock("error", "최근 업로드를 불러오지 못했습니다."));
        row.appendChild(cell);
        tbody.appendChild(row);
      });
  }

  function init() {
    var checked = document.querySelector('input[name="kind"]:checked');
    state.kind = checked ? checked.value : "reservations";
    document.querySelectorAll('input[name="kind"]').forEach(function (radio) {
      radio.addEventListener("change", function () {
        selectKind(radio.value);
      });
    });

    var input = $("#upload-file");
    input.addEventListener("change", function () {
      setFile(input.files[0]);
    });
    var zone = $("#dropzone");
    ["dragenter", "dragover"].forEach(function (type) {
      zone.addEventListener(type, function (event) {
        event.preventDefault();
        zone.classList.add("is-dragover");
      });
    });
    ["dragleave", "drop"].forEach(function (type) {
      zone.addEventListener(type, function () {
        zone.classList.remove("is-dragover");
      });
    });
    zone.addEventListener("drop", function (event) {
      event.preventDefault();
      if (event.dataTransfer.files.length) setFile(event.dataTransfer.files[0]);
    });
    $("#preview-button").addEventListener("click", runPreview);
    loadHistory();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
