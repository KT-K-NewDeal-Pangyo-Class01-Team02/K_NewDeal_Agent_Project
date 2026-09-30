(function () {
  "use strict";

  var ALTERNATIVE_LABELS = {
    NEARBY_STORE_TRANSFER: "인근 매장 재고 이동",
    COLOR_STORAGE_CHANGE: "색상/용량 변경 제안",
    DATE_CHANGE: "수령일 변경 제안",
    DOWN_PAYMENT: "선납금 제안",
    DOCUMENT_REQUEST: "서류 제출 요청",
  };

  var VERDICT_META = {
    feasible: { label: "즉시 가능", icon: "circle-check", className: "status-feasible", feasibility: "높음" },
    conditional: { label: "조건부 가능", icon: "triangle-alert", className: "status-conditional", feasibility: "보통" },
    high_risk: { label: "개통 어려움", icon: "octagon-x", className: "status-high-risk", feasibility: "낮음" },
  };

  var INVENTORY_STATUS_LABELS = {
    available: "재고 확보",
    conditional: "조건부 확보",
    unavailable: "재고 확보 어려움",
  };

  var RISK_LEVEL_LABELS = {
    low: "낮음",
    medium: "보통",
    high: "높음",
  };

  var SVG_NS = "http://www.w3.org/2000/svg";

  function svgIcon(name) {
    var svg = document.createElementNS(SVG_NS, "svg");
    svg.setAttribute("class", "icon icon-sm");
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("focusable", "false");
    var use = document.createElementNS(SVG_NS, "use");
    use.setAttribute("href", "#icon-" + name);
    svg.appendChild(use);
    return svg;
  }

  // 로딩 · 오류를 대시보드와 같은 모양으로 그린다
  function stateBlock(kind, title, desc) {
    var block = el("div", { className: "state-block" + (kind === "error" ? " is-error" : "") });
    var stateIcon = svgIcon(kind === "loading" ? "loader-circle" : "triangle-alert");
    stateIcon.setAttribute("class", "icon state-icon" + (kind === "loading" ? " is-spinning" : ""));
    block.appendChild(stateIcon);
    block.appendChild(el("span", { className: "state-title", text: title }));
    if (desc) block.appendChild(el("span", { className: "state-desc", text: desc }));
    return block;
  }

  function $(selector, scope) {
    return (scope || document).querySelector(selector);
  }

  function el(tag, options) {
    var node = document.createElement(tag);
    options = options || {};
    if (options.className) node.className = options.className;
    if (options.text !== undefined) node.textContent = options.text;
    return node;
  }

  function loadDeviceCatalog() {
    var script = document.getElementById("device-catalog");
    if (!script) return [];
    try {
      return JSON.parse(script.textContent);
    } catch (err) {
      return [];
    }
  }

  function uniqueValues(items, key) {
    var seen = [];
    items.forEach(function (item) {
      if (seen.indexOf(item[key]) === -1) seen.push(item[key]);
    });
    return seen;
  }

  function fillSelect(select, values, placeholder) {
    select.innerHTML = "";
    var placeholderOption = el("option", { text: placeholder });
    placeholderOption.value = "";
    placeholderOption.disabled = true;
    placeholderOption.selected = true;
    select.appendChild(placeholderOption);
    values.forEach(function (value) {
      var option = el("option", { text: value });
      option.value = value;
      select.appendChild(option);
    });
    select.disabled = values.length === 0;
  }

  function setupDeviceSelectors(catalog) {
    var modelSelect = $("#device_model");
    var colorSelect = $("#device_color");
    var storageSelect = $("#device_storage");

    fillSelect(modelSelect, uniqueValues(catalog, "model"), "모델을 선택하세요");
    fillSelect(colorSelect, [], "모델을 먼저 선택하세요");
    fillSelect(storageSelect, [], "색상을 먼저 선택하세요");

    modelSelect.addEventListener("change", function () {
      var colors = uniqueValues(
        catalog.filter(function (item) {
          return item.model === modelSelect.value;
        }),
        "color"
      );
      fillSelect(colorSelect, colors, "색상을 선택하세요");
      fillSelect(storageSelect, [], "색상을 먼저 선택하세요");
    });

    colorSelect.addEventListener("change", function () {
      var storages = uniqueValues(
        catalog.filter(function (item) {
          return item.model === modelSelect.value && item.color === colorSelect.value;
        }),
        "storage"
      );
      fillSelect(storageSelect, storages, "용량을 선택하세요");
      updateDevicePreview(catalog);
    });

    modelSelect.addEventListener("change", function () {
      updateDevicePreview(catalog);
    });
    storageSelect.addEventListener("change", function () {
      updateDevicePreview(catalog);
    });
  }

  // 선택한 모델(·색상·용량)의 사진을 보여 준다. 색상 선택 전에는 모델 대표 사진.
  function updateDevicePreview(catalog) {
    var model = $("#device_model").value;
    var color = $("#device_color").value;
    var storage = $("#device_storage").value;
    var preview = $("#device-preview");
    if (!preview) return;
    var candidates = catalog.filter(function (item) {
      return item.model === model && (!color || item.color === color);
    });
    var match = candidates.filter(function (item) { return item.image_url; })[0];
    if (!model || !match) {
      preview.hidden = true;
      return;
    }
    $("#device-preview-img").src = match.image_url;
    $("#device-preview-img").alt = model;
    $("#device-preview-model").textContent = model;
    $("#device-preview-option").textContent = [color, storage].filter(Boolean).join(" · ") || "색상을 선택하세요";
    preview.hidden = false;
  }

  function showError(message) {
    var box = $("#form-error");
    box.textContent = message || "";
    box.hidden = !message;
  }

  function buildPayload(form) {
    var data = new FormData(form);
    return {
      customer_id: data.get("customer_id"),
      store_id: data.get("store_id"),
      line_type: data.get("line_type"),
      previous_carrier: data.get("line_type") === "MNP" ? data.get("previous_carrier") || null : null,
      desired_activation_date: data.get("desired_activation_date"),
      device: {
        model: data.get("device_model"),
        color: data.get("device_color"),
        storage: data.get("device_storage"),
      },
    };
  }

  function validatePayload(payload) {
    var missing = [];
    if (!payload.customer_id) missing.push("고객번호");
    if (!payload.store_id) missing.push("방문 매장");
    if (!payload.line_type) missing.push("가입유형");
    if (payload.line_type === "MNP" && !payload.previous_carrier) missing.push("기존 통신사");
    if (!payload.device.model) missing.push("단말 모델");
    if (!payload.device.color) missing.push("색상");
    if (!payload.device.storage) missing.push("용량");
    if (!payload.desired_activation_date) missing.push("희망 수령일");
    return missing;
  }

  function renderLoading() {
    var content = $("#result-content");
    content.innerHTML = "";
    content.appendChild(stateBlock("loading", "사전검증을 실행하는 중입니다..."));
  }

  function renderApiError(message) {
    var content = $("#result-content");
    content.innerHTML = "";
    content.appendChild(stateBlock("error", "사전검증을 완료하지 못했습니다.", message));
  }

  function renderIssueList(title, issues) {
    var section = el("div", { className: "result-section" });
    section.appendChild(el("h3", { text: title }));
    if (!issues || issues.length === 0) {
      section.appendChild(el("p", { className: "muted", text: "확인된 위험 사유가 없습니다." }));
      return section;
    }
    var list = el("ul", { className: "issue-list" });
    issues.forEach(function (issue) {
      list.appendChild(el("li", { text: issue }));
    });
    section.appendChild(list);
    return section;
  }

  function renderAlternatives(alternatives) {
    var section = el("div", { className: "result-section" });
    section.appendChild(el("h3", { text: "대체조건 목록" }));
    if (!alternatives || alternatives.length === 0) {
      section.appendChild(el("p", { className: "muted", text: "제안할 대체조건이 없습니다." }));
      return section;
    }
    var list = el("ul", { className: "alternative-list" });
    alternatives.forEach(function (alt) {
      var label = ALTERNATIVE_LABELS[alt.type] || alt.type;
      var item = el("li");
      item.appendChild(el("span", { className: "alternative-type", text: label }));
      item.appendChild(el("span", { className: "alternative-detail", text: JSON.stringify(alt.detail) }));
      list.appendChild(item);
    });
    section.appendChild(list);
    return section;
  }

  function renderChecklist(data) {
    var section = el("div", { className: "result-section" });
    section.appendChild(el("h3", { text: "개통 준비도 체크리스트" }));

    var lookup = data.lookup || {};
    var checks = (data.activation_risk_check && data.activation_risk_check.checks) || {};
    var inventoryStatus = data.inventory_check && data.inventory_check.status;

    var items = [
      { label: "고객 정보 확인", ok: lookup.customer_found },
      { label: "매장 정보 확인", ok: lookup.store_found },
      { label: "기기 정보 확인", ok: lookup.device_found },
      { label: "재고 확보", ok: inventoryStatus === "available" },
      { label: "할부한도 충족", ok: checks.installment_limit_ok },
      { label: "미납 없음", ok: checks.overdue_payment === false },
      { label: "보유 회선 한도 이내", ok: checks.line_limit_ok },
      { label: "본인인증 완료", ok: checks.identity_verified },
      {
        label: "서류 제출 완료",
        ok: Array.isArray(checks.missing_documents) && checks.missing_documents.length === 0,
      },
    ];

    var list = el("ul", { className: "checklist" });
    items.forEach(function (item) {
      var li = el("li", { className: item.ok ? "checklist-ok" : "checklist-fail" });
      var state = item.ok ? "완료" : "미충족";
      li.appendChild(svgIcon(item.ok ? "circle-check" : "circle-x"));
      li.appendChild(document.createTextNode(item.label + " - " + state));
      list.appendChild(li);
    });
    section.appendChild(list);
    return section;
  }

  function renderResult(data) {
    var content = $("#result-content");
    content.innerHTML = "";

    var verdictMeta = VERDICT_META[data.overall_verdict] || {
      label: data.overall_verdict,
      icon: "info",
      className: "status-unknown",
      feasibility: "-",
    };

    var summary = el("div", { className: "result-summary " + verdictMeta.className });
    var badge = el("p", { className: "status-badge" });
    badge.appendChild(svgIcon(verdictMeta.icon));
    badge.appendChild(document.createTextNode(data.overall_verdict + " · " + verdictMeta.label));
    summary.appendChild(badge);

    var scoreRow = el("div", { className: "score-row" });

    var feasibilityBox = el("div", { className: "score-box" });
    feasibilityBox.appendChild(el("span", { className: "score-label", text: "이행 가능성" }));
    feasibilityBox.appendChild(el("span", { className: "score-value", text: verdictMeta.feasibility }));
    scoreRow.appendChild(feasibilityBox);

    var churnBox = el("div", { className: "score-box" });
    churnBox.appendChild(el("span", { className: "score-label", text: "예약이탈 위험 점수" }));
    var churnValue =
      data.churn_risk_score === null || data.churn_risk_score === undefined
        ? "준비 중"
        : String(data.churn_risk_score);
    churnBox.appendChild(el("span", { className: "score-value muted", text: churnValue }));
    scoreRow.appendChild(churnBox);

    summary.appendChild(scoreRow);
    content.appendChild(summary);

    var inventoryCheck = data.inventory_check || {};
    var inventoryHeading =
      "재고·일정 위험 목록 (" +
      (INVENTORY_STATUS_LABELS[inventoryCheck.status] || inventoryCheck.status) +
      ")";
    content.appendChild(renderIssueList(inventoryHeading, inventoryCheck.issues));

    var riskCheck = data.activation_risk_check || {};
    var riskHeading =
      "개통위험 목록 (위험도: " + (RISK_LEVEL_LABELS[riskCheck.risk_level] || riskCheck.risk_level) + ")";
    content.appendChild(renderIssueList(riskHeading, riskCheck.issues));

    content.appendChild(renderAlternatives(data.alternatives));

    var nbaSection = el("div", { className: "result-section" });
    nbaSection.appendChild(el("h3", { text: "Next Best Action" }));
    nbaSection.appendChild(
      el("p", {
        className: "muted",
        text: data.recommended_action
          ? String(data.recommended_action)
          : "NBA 추천 기능은 다음 단계에서 제공됩니다.",
      })
    );
    content.appendChild(nbaSection);

    content.appendChild(renderChecklist(data));
  }

  var lastPayload = null;

  function setRegisterVisible(visible) {
    var box = $("#register-box");
    if (box) box.hidden = !visible;
    var errorBox = $("#register-error");
    if (errorBox) errorBox.hidden = true;
  }

  function setupRegisterButton() {
    var button = $("#register-button");
    if (!button) return;
    button.addEventListener("click", function () {
      if (!lastPayload) return;
      button.disabled = true;
      button.textContent = "등록 중...";
      fetch("/api/reservations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(lastPayload),
      })
        .then(function (response) {
          return response.json();
        })
        .then(function (body) {
          if (!body.success) throw new Error((body.error && body.error.message) || "예약 등록에 실패했습니다.");
          window.location.href = "/savedeal?reservation=" + encodeURIComponent(body.data.reservation_id);
        })
        .catch(function (err) {
          var errorBox = $("#register-error");
          errorBox.textContent = err.message || "서버와 통신할 수 없습니다.";
          errorBox.hidden = false;
          button.disabled = false;
          button.textContent = "이 조건으로 예약 등록";
        });
    });
  }

  function init() {
    var form = $("#precheck-form");
    if (!form) return;

    setupRegisterButton();

    // 번호이동을 고를 때만 '기존 통신사' 칸을 보여 준다
    var lineType = $("#line_type");
    var carrierField = $("#previous-carrier-field");
    if (lineType && carrierField) {
      lineType.addEventListener("change", function () {
        carrierField.hidden = lineType.value !== "MNP";
      });
    }

    var catalog = loadDeviceCatalog();
    setupDeviceSelectors(catalog);

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      showError("");

      var payload = buildPayload(form);
      var missing = validatePayload(payload);
      if (missing.length > 0) {
        showError("다음 항목을 입력해주세요: " + missing.join(", "));
        return;
      }

      setRegisterVisible(false);
      lastPayload = null;

      var submitButton = $("#submit-button");
      submitButton.disabled = true;
      submitButton.textContent = "검증 중...";
      renderLoading();

      fetch("/api/precheck", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      })
        .then(function (response) {
          return response.json().then(function (body) {
            return { ok: response.ok, body: body };
          });
        })
        .then(function (result) {
          if (!result.ok || !result.body.success) {
            var message =
              (result.body.error && result.body.error.message) || "사전검증 요청이 실패했습니다.";
            renderApiError(message);
            return;
          }
          renderResult(result.body.data);
          lastPayload = payload;
          setRegisterVisible(true);
        })
        .catch(function () {
          renderApiError("서버와 통신할 수 없습니다. 잠시 후 다시 시도해주세요.");
        })
        .finally(function () {
          submitButton.disabled = false;
          submitButton.textContent = "사전검증 실행";
        });
    });
  }

  document.addEventListener("DOMContentLoaded", init);
})();
