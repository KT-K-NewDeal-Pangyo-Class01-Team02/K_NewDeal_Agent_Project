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
    desired_activation_date TEXT NOT NULL,
    activation_deadline     TEXT NOT NULL,
    -- ACTION_REQUIRED / IN_PROGRESS / READY / COMPLETED / CANCELLED
    status                  TEXT NOT NULL,
    -- 미해결 문제 목록 JSON: [{"code": "STOCK_SHORTAGE", "detail": {...}}, ...]
    issues                  TEXT NOT NULL DEFAULT '[]',
    retry_count             INTEGER NOT NULL DEFAULT 0,
    customer_waiting_since  TEXT NOT NULL,
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

CREATE INDEX IF NOT EXISTS idx_actions_reservation ON proposed_actions (reservation_id);
CREATE INDEX IF NOT EXISTS idx_history_reservation ON action_history (reservation_id);
