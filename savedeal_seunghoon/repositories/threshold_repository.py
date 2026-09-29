import json
from pathlib import Path


class ThresholdRepository:
    """thresholds.json은 목록이 아닌 단일 설정 객체이므로 BaseRepository를 쓰지 않는다."""

    def __init__(self, data_dir: Path):
        self.file_path = Path(data_dir) / "thresholds.json"

    def load(self) -> dict:
        if not self.file_path.exists():
            return {}
        with self.file_path.open("r", encoding="utf-8") as f:
            return json.load(f)
