from db.connection import connect


class ActionHistoryRepository:
    def __init__(self, db_path):
        self.db_path = db_path

    def list_by_reservation(self, reservation_id: str) -> list[dict]:
        with connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM action_history WHERE reservation_id = ? ORDER BY created_at, history_id",
                (reservation_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def add(
        self,
        reservation_id: str,
        event_type: str,
        description: str,
        created_at: str,
        action_id: int | None = None,
    ) -> None:
        with connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO action_history (reservation_id, action_id, event_type, description, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (reservation_id, action_id, event_type, description, created_at),
            )
