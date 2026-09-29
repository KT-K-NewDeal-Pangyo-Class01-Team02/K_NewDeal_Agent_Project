import json

from db.connection import connect, ensure_database

_COLUMNS = [
    "reservation_id",
    "customer_id",
    "customer_name",
    "customer_phone",
    "store_id",
    "device_model",
    "device_color",
    "device_storage",
    "line_type",
    "desired_activation_date",
    "activation_deadline",
    "status",
    "issues",
    "retry_count",
    "customer_waiting_since",
    "created_at",
    "updated_at",
    "completed_at",
]


def _to_dict(row) -> dict:
    item = dict(row)
    item["issues"] = json.loads(item["issues"] or "[]")
    item["device"] = {
        "model": item.pop("device_model"),
        "color": item.pop("device_color"),
        "storage": item.pop("device_storage"),
    }
    return item


def _to_row(reservation: dict) -> dict:
    row = {key: value for key, value in reservation.items() if key not in ("device", "issues")}
    device = reservation.get("device")
    if device is not None:
        row["device_model"] = device["model"]
        row["device_color"] = device["color"]
        row["device_storage"] = device["storage"]
    if "issues" in reservation:
        row["issues"] = json.dumps(reservation["issues"], ensure_ascii=False)
    return {key: value for key, value in row.items() if key in _COLUMNS}


class ReservationRepository:
    """예약 운영 데이터(SQLite). db_path에는 DB 파일 경로나 데이터 폴더를 넘긴다."""

    def __init__(self, db_path):
        self.db_path = db_path
        ensure_database(db_path)

    def load_all(self) -> list[dict]:
        with connect(self.db_path) as conn:
            rows = conn.execute("SELECT * FROM reservations ORDER BY reservation_id").fetchall()
        return [_to_dict(row) for row in rows]

    def find_by_id(self, reservation_id: str) -> dict | None:
        with connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM reservations WHERE reservation_id = ?", (reservation_id,)
            ).fetchone()
        return _to_dict(row) if row else None

    def insert(self, reservation: dict) -> None:
        row = _to_row(reservation)
        columns = ", ".join(row)
        placeholders = ", ".join("?" for _ in row)
        with connect(self.db_path) as conn:
            conn.execute(f"INSERT INTO reservations ({columns}) VALUES ({placeholders})", tuple(row.values()))

    def update(self, reservation_id: str, fields: dict) -> None:
        row = _to_row(fields)
        if not row:
            return
        assignments = ", ".join(f"{column} = ?" for column in row)
        with connect(self.db_path) as conn:
            conn.execute(
                f"UPDATE reservations SET {assignments} WHERE reservation_id = ?",
                (*row.values(), reservation_id),
            )

    def next_id(self) -> str:
        with connect(self.db_path) as conn:
            rows = conn.execute("SELECT reservation_id FROM reservations").fetchall()
        numbers = [int(row[0][1:]) for row in rows if row[0][1:].isdigit()]
        return f"R{max(numbers, default=2000) + 1}"
