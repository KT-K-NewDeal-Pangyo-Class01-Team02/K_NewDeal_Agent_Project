import json
from pathlib import Path

from db.connection import connect, ensure_database
from repositories.base_repository import BaseRepository

_LIST_FIELDS = ("required_documents", "submitted_documents")
_BOOL_FIELDS = ("identity_verified", "overdue_payment", "contact_response_pending")
_COLUMNS = [
    "customer_id",
    "name",
    "phone",
    "identity_verified",
    "verification_method",
    "required_documents",
    "submitted_documents",
    "overdue_payment",
    "installment_limit",
    "existing_lines_count",
    "max_lines_allowed",
    "updated_at",
]


def _to_dict(row) -> dict:
    item = dict(row)
    for field in _LIST_FIELDS:
        item[field] = json.loads(item[field] or "[]")
    for field in ("identity_verified", "overdue_payment"):
        item[field] = bool(item[field])
    return item


class CustomerRepository:
    """고객 기준정보. db_path가 있으면 운영 DB(customers 테이블), 없으면 data/customers.json 을 읽는다."""

    def __init__(self, data_dir: Path, db_path=None):
        self.json_repo = BaseRepository(Path(data_dir) / "customers.json", id_field="customer_id")
        self.db_path = db_path
        if db_path is not None:
            ensure_database(db_path)

    def load_all(self) -> list[dict]:
        if self.db_path is None:
            return self.json_repo.load_all()
        with connect(self.db_path) as conn:
            rows = conn.execute("SELECT * FROM customers ORDER BY customer_id").fetchall()
        return [_to_dict(row) for row in rows]

    def find_by_id(self, customer_id: str) -> dict | None:
        if self.db_path is None:
            return self.json_repo.find_by_id(customer_id)
        with connect(self.db_path) as conn:
            row = conn.execute("SELECT * FROM customers WHERE customer_id = ?", (customer_id,)).fetchone()
        return _to_dict(row) if row else None

    def upsert(self, customer: dict) -> None:
        """같은 고객번호가 있으면 갱신, 없으면 추가한다 (DB 모드 전용)."""
        row = {}
        for column in _COLUMNS:
            if column not in customer:
                continue
            value = customer[column]
            if column in _LIST_FIELDS:
                value = json.dumps(value or [], ensure_ascii=False)
            elif column in _BOOL_FIELDS and value is not None:
                value = int(bool(value))
            row[column] = value
        columns = ", ".join(row)
        placeholders = ", ".join("?" for _ in row)
        updates = ", ".join(f"{column} = excluded.{column}" for column in row if column != "customer_id")
        with connect(self.db_path) as conn:
            conn.execute(
                f"INSERT INTO customers ({columns}) VALUES ({placeholders}) "
                f"ON CONFLICT(customer_id) DO UPDATE SET {updates}",
                tuple(row.values()),
            )
