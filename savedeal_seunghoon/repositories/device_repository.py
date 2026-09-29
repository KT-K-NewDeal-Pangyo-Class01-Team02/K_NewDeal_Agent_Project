from pathlib import Path

from repositories.base_repository import BaseRepository


class DeviceRepository(BaseRepository):
    """devices.json은 단일 id가 아닌 model/color/storage 조합으로 조회한다."""

    def __init__(self, data_dir: Path):
        super().__init__(Path(data_dir) / "devices.json", id_field=None)

    def find_by_spec(self, model: str, color: str, storage: str) -> dict | None:
        for item in self.load_all():
            if (
                item.get("model") == model
                and item.get("color") == color
                and item.get("storage") == storage
            ):
                return item
        return None
