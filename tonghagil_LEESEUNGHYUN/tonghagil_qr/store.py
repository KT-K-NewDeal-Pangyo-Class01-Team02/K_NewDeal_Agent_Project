"""방문객·스탬프·쿠폰·화면 조회 기록 (SQLite, data/qr.db).

방문객은 로그인 없이 브라우저 쿠키의 무작위 ID 로 구분한다. 개인정보는 저장하지 않는다.
여러 휴대폰이 동시에 스탬프를 찍어도 안전하도록 JSON 파일 대신 SQLite 를 쓴다.
"""
import secrets
import sqlite3
import threading
from contextlib import closing
from datetime import datetime
from pathlib import Path

# 쿠폰 코드: 헷갈리는 글자(0/O, 1/I/L)를 뺀 6자리
_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS visitors (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS stamps (
    visitor_id TEXT NOT NULL,
    stamp_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (visitor_id, stamp_id)
);
CREATE TABLE IF NOT EXISTS coupons (
    visitor_id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    issued_at TEXT NOT NULL,
    redeemed_at TEXT
);
CREATE TABLE IF NOT EXISTS views (
    visitor_id TEXT NOT NULL,
    page TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def _now():
    return datetime.now().isoformat(timespec="seconds")


class QrStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._connect() as db:
            db.executescript(_SCHEMA)

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return closing(db)

    def _write(self, sql, params=()):
        with self._lock, self._connect() as db, db:
            return db.execute(sql, params).rowcount

    def _rows(self, sql, params=()):
        with self._connect() as db:
            return db.execute(sql, params).fetchall()

    # ── 방문객 ──
    def ensure_visitor(self, visitor_id, source=""):
        self._write("INSERT OR IGNORE INTO visitors (id, source, created_at) VALUES (?, ?, ?)",
                    (visitor_id, source[:30], _now()))

    def log_view(self, visitor_id, page):
        self._write("INSERT INTO views (visitor_id, page, created_at) VALUES (?, ?, ?)", (visitor_id, page, _now()))

    # ── 스탬프 ──
    def add_stamp(self, visitor_id, stamp_id):
        """처음 찍은 스탬프면 True, 이미 찍었으면 False."""
        return self._write("INSERT OR IGNORE INTO stamps (visitor_id, stamp_id, created_at) VALUES (?, ?, ?)",
                           (visitor_id, stamp_id, _now())) == 1

    def stamps_of(self, visitor_id):
        return {r["stamp_id"] for r in self._rows("SELECT stamp_id FROM stamps WHERE visitor_id = ?", (visitor_id,))}

    # ── 쿠폰 ──
    def issue_coupon(self, visitor_id):
        """방문객의 쿠폰. 이미 있으면 그대로 돌려준다."""
        with self._lock, self._connect() as db, db:
            row = db.execute("SELECT * FROM coupons WHERE visitor_id = ?", (visitor_id,)).fetchone()
            if row:
                return dict(row)
            while True:
                code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(6))
                try:
                    db.execute("INSERT INTO coupons (visitor_id, code, issued_at) VALUES (?, ?, ?)", (visitor_id, code, _now()))
                    break
                except sqlite3.IntegrityError:
                    continue  # 코드가 겹치면 다시 뽑는다
            return dict(db.execute("SELECT * FROM coupons WHERE visitor_id = ?", (visitor_id,)).fetchone())

    def coupon_of(self, visitor_id):
        rows = self._rows("SELECT * FROM coupons WHERE visitor_id = ?", (visitor_id,))
        return dict(rows[0]) if rows else None

    def redeem(self, code):
        """쿠폰 사용 처리. → ('ok' | 'already' | 'not_found', 쿠폰 또는 None)"""
        code = normalize_code(code)
        with self._lock, self._connect() as db, db:
            row = db.execute("SELECT * FROM coupons WHERE code = ?", (code,)).fetchone()
            if not row:
                return "not_found", None
            if row["redeemed_at"]:
                return "already", dict(row)
            db.execute("UPDATE coupons SET redeemed_at = ? WHERE code = ?", (_now(), code))
            return "ok", dict(db.execute("SELECT * FROM coupons WHERE code = ?", (code,)).fetchone())

    # ── 담당자 화면 ──
    def stats(self, stamp_ids):
        def one(sql, params=()):
            return self._rows(sql, params)[0][0]

        visitors = one("SELECT COUNT(*) FROM visitors")
        per_stamp = {r["stamp_id"]: r["n"] for r in self._rows("SELECT stamp_id, COUNT(*) AS n FROM stamps GROUP BY stamp_id")}
        return {
            "visitors": visitors,
            "from_poster": one("SELECT COUNT(*) FROM visitors WHERE source = 'poster'"),
            "map_viewers": one("SELECT COUNT(DISTINCT visitor_id) FROM views WHERE page = 'map'"),
            "stamp_joiners": one("SELECT COUNT(DISTINCT visitor_id) FROM stamps"),
            "stamps_total": one("SELECT COUNT(*) FROM stamps"),
            "per_stamp": {sid: per_stamp.get(sid, 0) for sid in stamp_ids},
            "coupons": one("SELECT COUNT(*) FROM coupons"),
            "redeemed": one("SELECT COUNT(*) FROM coupons WHERE redeemed_at IS NOT NULL"),
            "chat_messages": one("SELECT COUNT(*) FROM views WHERE page = 'chat_message'"),
        }

    def stamp_counts(self, stamp_ids):
        """{찍은 개수: 그 개수만큼 찍은 방문객 수}. 예) {1: 3, 2: 1} = 1개 찍은 사람 3명, 2개 찍은 사람 1명."""
        if not stamp_ids:
            return {}
        marks = ",".join("?" * len(stamp_ids))
        rows = self._rows(
            f"SELECT n, COUNT(*) AS visitors FROM (SELECT COUNT(*) AS n FROM stamps WHERE stamp_id IN ({marks}) "
            "GROUP BY visitor_id) GROUP BY n ORDER BY n", tuple(stamp_ids))
        return {r["n"]: r["visitors"] for r in rows}

    def in_progress(self, stamp_ids, required, limit=10):
        """아직 다 못 모은 방문객을 많이 찍은 순서로. → [{visitor_id, stamp_ids(찍은 것), last_at(마지막 인증 시각)}]"""
        if not stamp_ids:
            return []
        marks = ",".join("?" * len(stamp_ids))
        rows = self._rows(
            f"SELECT visitor_id, COUNT(*) AS n, MAX(created_at) AS last_at, GROUP_CONCAT(stamp_id) AS ids FROM stamps "
            f"WHERE stamp_id IN ({marks}) GROUP BY visitor_id HAVING n < ? ORDER BY n DESC, last_at DESC LIMIT ?",
            (*stamp_ids, required, limit))
        return [{"visitor_id": r["visitor_id"], "stamp_ids": set(r["ids"].split(",")), "last_at": r["last_at"]} for r in rows]

    def recent_redemptions(self, limit=8):
        return [dict(r) for r in self._rows(
            "SELECT code, issued_at, redeemed_at FROM coupons WHERE redeemed_at IS NOT NULL ORDER BY redeemed_at DESC LIMIT ?",
            (limit,))]

    def reset(self):
        """시연 리허설용: 모든 방문객·스탬프·쿠폰·조회 기록을 지운다."""
        with self._lock, self._connect() as db, db:
            for table in ("views", "coupons", "stamps", "visitors"):
                db.execute(f"DELETE FROM {table}")


def normalize_code(code):
    return "".join(ch for ch in (code or "").upper() if ch.isalnum())[:12]
