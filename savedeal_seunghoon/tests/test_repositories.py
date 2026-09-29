from config import Config
from repositories.customer_repository import CustomerRepository
from repositories.device_repository import DeviceRepository
from repositories.inventory_repository import InventoryRepository
from repositories.reservation_repository import ReservationRepository
from repositories.store_repository import StoreRepository


def test_customer_repository_find_by_id():
    repo = CustomerRepository(Config.DATA_DIR)
    assert repo.find_by_id("C001") is not None
    assert repo.find_by_id("UNKNOWN") is None


def test_store_repository_find_by_id():
    repo = StoreRepository(Config.DATA_DIR)
    store = repo.find_by_id("S001")
    assert store is not None
    assert store["name"] == "강남점"


def test_device_repository_find_by_spec():
    repo = DeviceRepository(Config.DATA_DIR)
    assert repo.find_by_spec("GalaxyZ Fold6", "Black", "256GB") is not None
    assert repo.find_by_spec("Unknown", "X", "Y") is None


def test_inventory_repository_find_by_id():
    repo = InventoryRepository(Config.DATA_DIR)
    item = repo.find_by_id("SKU001")
    assert item is not None
    assert item["quantity_on_hand"] == 3


def test_reservation_repository_load_all():
    repo = ReservationRepository(Config.DATA_DIR)
    reservations = repo.load_all()
    assert isinstance(reservations, list)
    assert len(reservations) >= 1
