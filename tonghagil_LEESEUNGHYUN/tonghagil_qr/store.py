"""방문객·스탬프·쿠폰·화면 조회 기록 (SQLite, data/qr.db).

방문객은 로그인 없이 브라우저 쿠키의 무작위 ID 로 구분한다. 개인정보는 저장하지 않는다.
여러 휴대폰이 동시에 스탬프를 찍어도 안전하도록 JSON 파일 대신 SQLite 를 쓴다.
"""
import secrets
import sqlite3
import threading
from contextlib import closing
from datetime import datetime, timedelta
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
    redeemed_at TEXT,
    gift_id TEXT,
    gift_name TEXT,
    drawn_at TEXT
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
        with self._connect() as db, db:
            db.executescript(_SCHEMA)
            # 예전에 만든 DB 에는 사은품 뽑기 열이 없다. 있는 기록은 그대로 두고 열만 더한다.
            have = {row["name"] for row in db.execute("PRAGMA table_info(coupons)")}
            for column in ("gift_id", "gift_name", "drawn_at"):
                if column not in have:
                    db.execute(f"ALTER TABLE coupons ADD COLUMN {column} TEXT")

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
        """사은품 증정 처리. 방문객이 뽑기를 마친 쿠폰만 증정할 수 있다(무엇을 줄지 정해져야 하므로).
        → ('ok' | 'already' | 'not_drawn' | 'not_found', 쿠폰 또는 None)"""
        code = normalize_code(code)
        with self._lock, self._connect() as db, db:
            row = db.execute("SELECT * FROM coupons WHERE code = ?", (code,)).fetchone()
            if not row:
                return "not_found", None
            if row["redeemed_at"]:
                return "already", dict(row)
            if not row["gift_name"]:
                return "not_drawn", dict(row)
            db.execute("UPDATE coupons SET redeemed_at = ? WHERE code = ?", (_now(), code))
            return "ok", dict(db.execute("SELECT * FROM coupons WHERE code = ?", (code,)).fetchone())

    def set_gift(self, visitor_id, gift_id, gift_name):
        """뽑기 결과를 쿠폰에 남긴다. 아직 뽑지 않은 쿠폰에만 기록된다(한 사람 한 번). → 기록했으면 True"""
        return self._write(
            "UPDATE coupons SET gift_id = ?, gift_name = ?, drawn_at = ? WHERE visitor_id = ? AND gift_name IS NULL",
            (str(gift_id), gift_name, _now(), visitor_id)) == 1

    def coupon_list(self, limit=200):
        """담당자 화면의 쿠폰 목록. 증정을 기다리는 것(뽑기 완료) → 아직 안 뽑은 것 → 증정 끝난 것 순서."""
        return [dict(r) for r in self._rows(
            "SELECT code, issued_at, drawn_at, redeemed_at, gift_name FROM coupons ORDER BY "
            "CASE WHEN redeemed_at IS NOT NULL THEN 2 WHEN gift_name IS NULL THEN 1 ELSE 0 END, "
            "CASE WHEN redeemed_at IS NOT NULL THEN redeemed_at END DESC, COALESCE(drawn_at, issued_at) LIMIT ?", (limit,))]

    def gift_counts(self):
        """{사은품 이름: 지금까지 뽑힌 수}"""
        return {r["gift_name"]: r["n"] for r in self._rows(
            "SELECT gift_name, COUNT(*) AS n FROM coupons WHERE gift_name IS NOT NULL GROUP BY gift_name")}

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
            f"SELECT visitor_id, COUNT(*) AS n, MIN(created_at) AS first_at, MAX(created_at) AS last_at, "
            f"GROUP_CONCAT(stamp_id) AS ids FROM stamps "
            f"WHERE stamp_id IN ({marks}) GROUP BY visitor_id HAVING n < ? ORDER BY n DESC, last_at DESC LIMIT ?",
            (*stamp_ids, required, limit))
        return [{"visitor_id": r["visitor_id"], "stamp_ids": set(r["ids"].split(",")),
                 "first_at": r["first_at"], "last_at": r["last_at"]} for r in rows]

    def waiting_coupons(self, limit=10):
        """쿠폰은 발급됐지만 아직 부스에서 받아 가지 않은 방문객. 먼저 완료한 순서. → [{visitor_id, issued_at}]"""
        return [dict(r) for r in self._rows(
            "SELECT visitor_id, issued_at FROM coupons WHERE redeemed_at IS NULL ORDER BY issued_at LIMIT ?", (limit,))]

    def purge_inactive(self, hours):
        """마지막 활동(접속·화면 조회·스탬프·쿠폰)이 hours 시간보다 오래된 방문객의 기록을 모두 지운다. → 지운 방문객 수

        처음 접속한 시각이 아니라 마지막 활동 기준이다. 스탬프를 모으는 중인 사람의 기록이 중간에 사라지지 않게 하려는 것이다.
        """
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat(timespec="seconds")
        with self._lock, self._connect() as db, db:
            ids = [(r[0],) for r in db.execute(
                "SELECT v.id FROM visitors v WHERE v.created_at < ? "
                "AND NOT EXISTS (SELECT 1 FROM views w WHERE w.visitor_id = v.id AND w.created_at >= ?) "
                "AND NOT EXISTS (SELECT 1 FROM stamps s WHERE s.visitor_id = v.id AND s.created_at >= ?) "
                "AND NOT EXISTS (SELECT 1 FROM coupons c WHERE c.visitor_id = v.id AND (c.issued_at >= ? OR c.redeemed_at >= ?))",
                (cutoff,) * 5)]
            for table, column in (("views", "visitor_id"), ("stamps", "visitor_id"), ("coupons", "visitor_id"), ("visitors", "id")):
                db.executemany(f"DELETE FROM {table} WHERE {column} = ?", ids)
            return len(ids)

    def reset(self):
        """시연 리허설용: 모든 방문객·스탬프·쿠폰·조회 기록을 지운다."""
        with self._lock, self._connect() as db, db:
            for table in ("views", "coupons", "stamps", "visitors"):
                db.execute(f"DELETE FROM {table}")


def normalize_code(code):
    return "".join(ch for ch in (code or "").upper() if ch.isalnum())[:12]
