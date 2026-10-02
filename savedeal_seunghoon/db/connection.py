import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"
DB_FILENAME = "savedeal.db"


def resolve_db_path(location) -> Path:
    """DB 파일 경로 또는 데이터 폴더를 받는다. 폴더면 그 안의 savedeal.db를 쓴다."""
    path = Path(location)
    return path / DB_FILENAME if path.is_dir() else path


@contextmanager
def connect(db_path):
    conn = sqlite3.connect(resolve_db_path(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# 나중에 추가된 칸. CREATE TABLE IF NOT EXISTS 는 기존 테이블에 칸을 더하지 않으므로 직접 추가한다.
ADDED_COLUMNS = {"reservations": {"previous_carrier": "TEXT", "memo": "TEXT", "memo_insight": "TEXT"}}


def init_schema(db_path) -> None:
    path = resolve_db_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as conn:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        for table, columns in ADDED_COLUMNS.items():
            existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
            for column, column_type in columns.items():
                if column not in existing:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")


_ensured_paths: set[Path] = set()


def ensure_database(db_path) -> None:
    """테이블을 만들고, 예약이 하나도 없으면 시연용 mock 데이터를 넣는다. 경로마다 한 번만 확인한다."""
    path = resolve_db_path(db_path)
    if path in _ensured_paths and path.exists():
        return
    # 시드 도중 리포지토리가 다시 이 함수를 불러도 재귀하지 않도록 먼저 표시한다.
    _ensured_paths.add(path)
    init_schema(path)
    with connect(db_path) as conn:
        customers = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        count = conn.execute("SELECT COUNT(*) FROM reservations").fetchone()[0]
    from db.seed import seed_demo_data, seed_reference_data

    if customers == 0:
        seed_reference_data(db_path)
    if count == 0:
        seed_demo_data(db_path)
    else:
        # 이미 만들어진 DB: 코드에서 바뀐 mock 데이터가 있으면 해당 부분만 고친다 (db/demo_migrations.py)
        from db.demo_migrations import upgrade

        upgrade(db_path)


def reset_database(db_path) -> None:
    """모든 운영 데이터를 지우고 mock 데이터로 다시 채운다 (시연 초기화용)."""
    init_schema(db_path)
    with connect(db_path) as conn:
        conn.execute("DELETE FROM action_history")
        conn.execute("DELETE FROM proposed_actions")
        conn.execute("DELETE FROM reservations")
        conn.execute("DELETE FROM customers")
        conn.execute("DELETE FROM inventory")
        conn.execute("DELETE FROM upload_batches")
        conn.execute("DELETE FROM notifications")
        conn.execute("DELETE FROM ai_logs")
        conn.execute(
            "DELETE FROM sqlite_sequence WHERE name IN "
            "('action_history', 'proposed_actions', 'upload_batches', 'notifications', 'ai_logs')"
        )
    from db.seed import seed_demo_data, seed_reference_data

    seed_reference_data(db_path)
    seed_demo_data(db_path)
