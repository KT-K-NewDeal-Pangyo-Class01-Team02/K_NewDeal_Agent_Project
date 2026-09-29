import json
from pathlib import Path


class BaseRepository:
    """공통 JSON 파일 로더. 개별 리포지토리가 파일 경로와 id 필드를 지정한다."""

    def __init__(self, file_path: Path, id_field: str | None):
        self.file_path = Path(file_path)
        self.id_field = id_field

    def load_all(self) -> list[dict]:
        if not self.file_path.exists():
            return []
        with self.file_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def find_by_id(self, id_value: str) -> dict | None:
        if self.id_field is None:
            return None
        for item in self.load_all():
            if item.get(self.id_field) == id_value:
                return item
        return None
