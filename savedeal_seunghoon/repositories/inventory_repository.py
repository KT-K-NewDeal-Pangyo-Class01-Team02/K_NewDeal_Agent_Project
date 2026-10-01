from pathlib import Path

from db.connection import connect, ensure_database
from repositories.base_repository import BaseRepository

_COLUMNS = ["sku", "model", "color", "storage", "store_id", "quantity_on_hand", "expected_restock_date", "updated_at"]


class InventoryRepository:
    """매장 재고. db_path가 있으면 운영 DB(inventory 테이블), 없으면 data/inventory.json 을 읽는다."""

    def __init__(self, data_dir: Path, db_path=None):
        self.json_repo = BaseRepository(Path(data_dir) / "inventory.json", id_field="sku")
        self.db_path = db_path
        if db_path is not None:
            ensure_database(db_path)

    def load_all(self) -> list[dict]:
        if self.db_path is None:
            return self.json_repo.load_all()
        with connect(self.db_path) as conn:
            rows = conn.execute("SELECT * FROM inventory ORDER BY sku").fetchall()
        return [dict(row) for row in rows]

    def find_by_id(self, sku: str) -> dict | None:
        if self.db_path is None:
            return self.json_repo.find_by_id(sku)
        with connect(self.db_path) as conn:
            row = conn.execute("SELECT * FROM inventory WHERE sku = ?", (sku,)).fetchone()
        return dict(row) if row else None

    def upsert(self, item: dict) -> None:
        """같은 SKU가 있으면 갱신, 없으면 추가한다 (DB 모드 전용)."""
        row = {column: item[column] for column in _COLUMNS if column in item}
        columns = ", ".join(row)
        placeholders = ", ".join("?" for _ in row)
        updates = ", ".join(f"{column} = excluded.{column}" for column in row if column != "sku")
        with connect(self.db_path) as conn:
            conn.execute(
                f"INSERT INTO inventory ({columns}) VALUES ({placeholders}) ON CONFLICT(sku) DO UPDATE SET {updates}",
                tuple(row.values()),
            )
