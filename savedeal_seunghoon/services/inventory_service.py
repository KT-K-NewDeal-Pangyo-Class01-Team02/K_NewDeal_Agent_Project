from datetime import date, timedelta
from pathlib import Path

from repositories.inventory_repository import InventoryRepository
from repositories.store_repository import StoreRepository
from repositories.threshold_repository import ThresholdRepository

STATUS_AVAILABLE = "available"
STATUS_CONDITIONAL = "conditional"
STATUS_UNAVAILABLE = "unavailable"

DEFAULT_TRANSFER_LEAD_DAYS = 1


def _find_item(items: list[dict], store_id: str, model: str, color: str, storage: str) -> dict | None:
    for item in items:
        if (
            item.get("store_id") == store_id
            and item.get("model") == model
            and item.get("color") == color
            and item.get("storage") == storage
        ):
            return item
    return None


class InventoryService:
    """희망 모델·색상·용량의 재고와 입고 일정을 검증하고 available/conditional/unavailable로 분류한다."""

    def __init__(self, data_dir: Path, db_path=None):
        self.inventory_repo = InventoryRepository(data_dir, db_path)
        self.store_repo = StoreRepository(data_dir)
        self.threshold_repo = ThresholdRepository(data_dir)

    def check(self, store_id: str, device: dict, desired_date_str: str) -> dict:
        desired_date = date.fromisoformat(desired_date_str)
        model, color, storage = device["model"], device["color"], device["storage"]

        inventory_items = self.inventory_repo.load_all()
        current_item = _find_item(inventory_items, store_id, model, color, storage)
        current_qty = current_item["quantity_on_hand"] if current_item else 0
        current_store = {"store_id": store_id, "in_stock": current_qty > 0, "quantity_on_hand": current_qty}

        if current_qty > 0:
            return {
                "status": STATUS_AVAILABLE,
                "current_store": current_store,
                "source_store_id": store_id,
                "expected_available_date": None,
                "schedule_match": True,
                "nearby_options": [],
                "issues": [],
            }

        restock_date_str = current_item.get("expected_restock_date") if current_item else None
        restock_date = date.fromisoformat(restock_date_str) if restock_date_str else None

        if restock_date is not None and restock_date <= desired_date:
            return {
                "status": STATUS_AVAILABLE,
                "current_store": current_store,
                "source_store_id": store_id,
                "expected_available_date": restock_date_str,
                "schedule_match": True,
                "nearby_options": [],
                "issues": [],
            }

        status = STATUS_UNAVAILABLE
        source_store_id = None
        expected_available_date = None
        schedule_match = False
        issues = []

        if restock_date is not None and restock_date > desired_date:
            status = STATUS_CONDITIONAL
            expected_available_date = restock_date_str
            issues.append(f"입고 예정일({restock_date_str})이 희망일({desired_date_str})보다 늦습니다.")

        nearby_options = self._find_nearby_options(inventory_items, store_id, model, color, storage, desired_date)

        if nearby_options:
            issues.append("인근 매장에서 재고 이동이 가능합니다.")
            if status == STATUS_UNAVAILABLE:
                status = STATUS_CONDITIONAL
                best = nearby_options[0]
                source_store_id = best["store_id"]
                expected_available_date = best["expected_available_date"]
                schedule_match = best["schedule_match"]
        elif status == STATUS_UNAVAILABLE:
            issues.append("현재 매장 및 인근 매장 모두 재고가 없습니다.")

        return {
            "status": status,
            "current_store": current_store,
            "source_store_id": source_store_id,
            "expected_available_date": expected_available_date,
            "schedule_match": schedule_match,
            "nearby_options": nearby_options,
            "issues": issues,
        }

    def _find_nearby_options(
        self,
        inventory_items: list[dict],
        store_id: str,
        model: str,
        color: str,
        storage: str,
        desired_date: date,
    ) -> list[dict]:
        store = self.store_repo.find_by_id(store_id)
        nearby_store_ids = store.get("nearby_store_ids", []) if store else []
        transfer_lead_days = (
            self.threshold_repo.load().get("inventory", {}).get("transfer_lead_days", DEFAULT_TRANSFER_LEAD_DAYS)
        )

        options = []
        for nearby_id in nearby_store_ids:
            nearby_item = _find_item(inventory_items, nearby_id, model, color, storage)
            if nearby_item and nearby_item["quantity_on_hand"] > 0:
                expected_date = date.today() + timedelta(days=transfer_lead_days)
                options.append(
                    {
                        "store_id": nearby_id,
                        "quantity_on_hand": nearby_item["quantity_on_hand"],
                        "transfer_lead_days": transfer_lead_days,
                        "expected_available_date": expected_date.isoformat(),
                        "schedule_match": expected_date <= desired_date,
                    }
                )
        return options
