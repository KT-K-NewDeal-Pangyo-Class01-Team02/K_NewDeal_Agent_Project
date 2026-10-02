"""mock 데이터 자동 업그레이드.

DB(savedeal.db)는 git에 올라가지 않아서, 코드에서 mock 데이터를 바꿔도 이미 만들어진 DB에는 반영되지 않는다.
그래서 DB에 'mock 데이터 버전'을 기록해 두고, 앱이 켜질 때 버전이 낮으면 바뀐 부분만 고친다.

- 고치는 대상은 mock 예약(R2001~R2017) 중 **예전 값을 그대로 가진 것**뿐이다.
  업로드·신규 등록한 예약이나 사용자가 바꾼 값은 건드리지 않는다.
- mock 데이터를 다시 바꿀 때는 DEMO_DATA_VERSION 을 올리고 MIGRATIONS 에 단계를 하나 추가한다.
"""
import json

from db.connection import connect

DEMO_DATA_VERSION = 2
META_KEY = "demo_data_version"

# v2: 사진 품질이 나쁜 Galaxy S25 Ultra · iPhone 16 Pro 를 mock 예약에서 뺐다 (예약번호: 예전 단말 → 새 단말)
_V2_DEVICE_CHANGES = {
    "R2005": ({"model": "Galaxy S25 Ultra", "color": "Titanium Gray", "storage": "256GB"},
              {"model": "iPhone 18 Pro", "color": "Burgundy", "storage": "256GB"}),
    "R2012": ({"model": "Galaxy S25 Ultra", "color": "Titanium Gray", "storage": "256GB"},
              {"model": "Galaxy Z Fold8", "color": "Black", "storage": "256GB"}),
    "R2014": ({"model": "iPhone 16 Pro", "color": "Desert Titanium", "storage": "256GB"},
              {"model": "GalaxyZ Fold6", "color": "Black", "storage": "256GB"}),
    "R2017": ({"model": "Galaxy S25 Ultra", "color": "Titanium Gray", "storage": "256GB"},
              {"model": "iPhone 18 Pro", "color": "Silver", "storage": "256GB"}),
}


def _migrate_v2(conn) -> int:
    changed = 0
    for reservation_id, (old, new) in _V2_DEVICE_CHANGES.items():
        cursor = conn.execute(
            """UPDATE reservations SET device_model = ?, device_color = ?, device_storage = ?
               WHERE reservation_id = ? AND device_model = ? AND device_color = ? AND device_storage = ?""",
            (new["model"], new["color"], new["storage"], reservation_id, old["model"], old["color"], old["storage"]),
        )
        changed += cursor.rowcount
    return changed


MIGRATIONS = {2: _migrate_v2}


def _ensure_meta_table(conn) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS app_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")


def get_version(db_path) -> int | None:
    with connect(db_path) as conn:
        _ensure_meta_table(conn)
        row = conn.execute("SELECT value FROM app_meta WHERE key = ?", (META_KEY,)).fetchone()
    return int(row["value"]) if row else None


def set_version(db_path, version: int = DEMO_DATA_VERSION) -> None:
    with connect(db_path) as conn:
        _ensure_meta_table(conn)
        conn.execute(
            "INSERT INTO app_meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (META_KEY, json.dumps(version)),
        )


def upgrade(db_path) -> dict:
    """버전이 낮으면 단계별로 고치고 버전을 올린다. 기록이 없는 DB는 버전 1(처음 배포한 mock 데이터)로 본다."""
    current = get_version(db_path) or 1
    applied = {}
    with connect(db_path) as conn:
        for version in sorted(v for v in MIGRATIONS if v > current):
            applied[version] = MIGRATIONS[version](conn)
    if current < DEMO_DATA_VERSION:
        set_version(db_path)
    return applied
