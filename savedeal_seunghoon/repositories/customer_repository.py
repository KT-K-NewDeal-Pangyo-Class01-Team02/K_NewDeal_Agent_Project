from pathlib import Path

from repositories.base_repository import BaseRepository


class CustomerRepository(BaseRepository):
    def __init__(self, data_dir: Path):
        super().__init__(Path(data_dir) / "customers.json", id_field="customer_id")
