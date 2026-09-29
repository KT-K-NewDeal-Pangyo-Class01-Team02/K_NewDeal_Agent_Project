from pathlib import Path

from repositories.base_repository import BaseRepository


class StoreRepository(BaseRepository):
    def __init__(self, data_dir: Path):
        super().__init__(Path(data_dir) / "stores.json", id_field="store_id")
