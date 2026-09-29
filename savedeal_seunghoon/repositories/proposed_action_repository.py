import json

from db.connection import connect


def _to_dict(row) -> dict:
    item = dict(row)
    item["detail"] = json.loads(item["detail"] or "{}")
    return item


class ProposedActionRepository:
    def __init__(self, db_path):
        self.db_path = db_path

    def list_by_reservation(self, reservation_id: str) -> list[dict]:
        with connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM proposed_actions WHERE reservation_id = ? ORDER BY action_id",
                (reservation_id,),
            ).fetchall()
        return [_to_dict(row) for row in rows]

    def list_all(self) -> list[dict]:
        with connect(self.db_path) as conn:
            rows = conn.execute("SELECT * FROM proposed_actions ORDER BY action_id").fetchall()
        return [_to_dict(row) for row in rows]

    def find_by_id(self, action_id: int) -> dict | None:
        with connect(self.db_path) as conn:
            row = conn.execute("SELECT * FROM proposed_actions WHERE action_id = ?", (action_id,)).fetchone()
        return _to_dict(row) if row else None

    def insert(self, action: dict) -> int:
        with connect(self.db_path) as conn:
            cursor = conn.execute(
                """INSERT INTO proposed_actions
                   (reservation_id, issue_code, action_type, title, description, detail, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    action["reservation_id"],
                    action["issue_code"],
                    action["action_type"],
                    action["title"],
                    action["description"],
                    json.dumps(action.get("detail", {}), ensure_ascii=False),
                    action["status"],
                    action["created_at"],
                ),
            )
            return cursor.lastrowid

    def update_status(self, action_id: int, status: str, decided_at: str | None) -> None:
        with connect(self.db_path) as conn:
            conn.execute(
                "UPDATE proposed_actions SET status = ?, decided_at = ? WHERE action_id = ?",
                (status, decided_at, action_id),
            )
