-- SAVEDEAL 운영 DB. 시각은 모두 로컬 시각 ISO 문자열(YYYY-MM-DDTHH:MM:SS)로 저장한다.

CREATE TABLE IF NOT EXISTS reservations (
    reservation_id          TEXT PRIMARY KEY,
    customer_id             TEXT NOT NULL,
    customer_name           TEXT NOT NULL,
    customer_phone          TEXT,
    store_id                TEXT NOT NULL,
    device_model            TEXT NOT NULL,
    device_color            TEXT NOT NULL,
    device_storage          TEXT NOT NULL,
    line_type               TEXT NOT NULL,
    -- 번호이동(MNP) 고객의 기존 통신사: SKT / LGU / MVNO (번호이동이 아니면 NULL)
    previous_carrier        TEXT,
    desired_activation_date TEXT NOT NULL,
    activation_deadline     TEXT NOT NULL,
    -- ACTION_REQUIRED / IN_PROGRESS / READY / COMPLETED / CANCELLED
    status                  TEXT NOT NULL,
    -- 미해결 문제 목록 JSON: [{"code": "STOCK_SHORTAGE", "detail": {...}}, ...]
    issues                  TEXT NOT NULL DEFAULT '[]',
    retry_count             INTEGER NOT NULL DEFAULT 0,
    customer_waiting_since  TEXT NOT NULL,
    -- 업로드 명단의 자유 메모와 그 해석 결과(JSON: AI 또는 규칙 기반)
    memo                    TEXT,
    memo_insight            TEXT,
    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL,
    completed_at            TEXT
);

CREATE TABLE IF NOT EXISTS proposed_actions (
    action_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    reservation_id TEXT NOT NULL REFERENCES reservations (reservation_id),
    issue_code     TEXT NOT NULL,
    action_type    TEXT NOT NULL,
    title          TEXT NOT NULL,
    description    TEXT NOT NULL,
    detail         TEXT NOT NULL DEFAULT '{}',
    -- PROPOSED / APPROVED / SUCCEEDED / FAILED / DISCARDED
    status         TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    decided_at     TEXT
);

CREATE TABLE IF NOT EXISTS action_history (
    history_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    reservation_id TEXT NOT NULL REFERENCES reservations (reservation_id),
    action_id      INTEGER REFERENCES proposed_actions (action_id),
    event_type     TEXT NOT NULL,
    description    TEXT NOT NULL,
    created_at     TEXT NOT NULL
);

-- 고객 기준정보 (교육용 가상 데이터만. 실제 개인정보를 넣지 않는다)
CREATE TABLE IF NOT EXISTS customers (
    customer_id          TEXT PRIMARY KEY,
    name                 TEXT,
    phone                TEXT,
    identity_verified    INTEGER,
    verification_method  TEXT,
    required_documents   TEXT NOT NULL DEFAULT '[]',
    submitted_documents  TEXT NOT NULL DEFAULT '[]',
    overdue_payment      INTEGER,
    installment_limit    INTEGER,
    existing_lines_count INTEGER,
    max_lines_allowed    INTEGER,
    updated_at           TEXT
);

-- 매장 재고
CREATE TABLE IF NOT EXISTS inventory (
    sku                   TEXT PRIMARY KEY,
    model                 TEXT NOT NULL,
    color                 TEXT NOT NULL,
    storage               TEXT NOT NULL,
    store_id              TEXT NOT NULL,
    quantity_on_hand      INTEGER NOT NULL DEFAULT 0,
    expected_restock_date TEXT,
    updated_at            TEXT
);

-- 엑셀·CSV 업로드: 미리보기 → 확정. 원본 파일은 저장하지 않고 검증한 행만 잠시 보관한다
CREATE TABLE IF NOT EXISTS upload_batches (
    batch_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    kind         TEXT NOT NULL,       -- reservations / customers / inventory
    filename     TEXT,
    status       TEXT NOT NULL,       -- PREVIEW / COMMITTED / CANCELLED
    total_rows   INTEGER NOT NULL DEFAULT 0,
    valid_rows   INTEGER NOT NULL DEFAULT 0,
    error_rows   INTEGER NOT NULL DEFAULT 0,
    rows         TEXT NOT NULL DEFAULT '[]',
    errors       TEXT NOT NULL DEFAULT '[]',
    result       TEXT,
    created_at   TEXT NOT NULL,
    committed_at TEXT
);

-- 알림 (n8n → Gmail). n8n 주소가 없으면 DEMO 로 기록만 한다
CREATE TABLE IF NOT EXISTS notifications (
    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind            TEXT NOT NULL,    -- UPLOAD_SUMMARY / HIGH_RISK / CUSTOMER_NOTICE / DAILY_REPORT
    reservation_id  TEXT,
    action_id       INTEGER,
    subject         TEXT NOT NULL,
    body            TEXT NOT NULL,
    status          TEXT NOT NULL,    -- SENT / FAILED / DEMO
    attempts        INTEGER NOT NULL DEFAULT 0,
    last_error      TEXT,
    created_at      TEXT NOT NULL,
    sent_at         TEXT
);

-- AI 사용 기록 (실제 AI 호출인지, 규칙 기반 대체인지 남긴다)
CREATE TABLE IF NOT EXISTS ai_logs (
    log_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    feature        TEXT NOT NULL,     -- MEMO_INSIGHT / CUSTOMER_NOTICE / STAFF_BRIEFING
    reservation_id TEXT,
    mode           TEXT NOT NULL,     -- ai / rule
    provider       TEXT,
    model          TEXT,
    success        INTEGER NOT NULL,
    latency_ms     INTEGER,
    error          TEXT,
    created_at     TEXT NOT NULL
);

-- 외부 이벤트 (개통 전산·물류 등 → n8n → SaveDeal). external_id 가 같은 이벤트는 한 번만 반영한다
CREATE TABLE IF NOT EXISTS inbound_events (
    event_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id    TEXT NOT NULL UNIQUE,
    source         TEXT,
    reservation_id TEXT,
    event_type     TEXT,
    payload        TEXT NOT NULL DEFAULT '{}',
    result         TEXT NOT NULL,     -- APPLIED / SKIPPED / ERROR
    message        TEXT,
    received_at    TEXT NOT NULL
);

-- 고위험 알림을 이미 보낸 예약 (정기 점검이 같은 예약을 반복해서 알리지 않도록)
CREATE TABLE IF NOT EXISTS risk_alerts (
    reservation_id TEXT PRIMARY KEY,
    alerted_at     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_actions_reservation ON proposed_actions (reservation_id);
CREATE INDEX IF NOT EXISTS idx_history_reservation ON action_history (reservation_id);
