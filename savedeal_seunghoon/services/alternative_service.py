from pathlib import Path

from repositories.inventory_repository import InventoryRepository
from services.inventory_service import STATUS_AVAILABLE


class AlternativeService:
    """재고·일정 검증과 개통위험 검증 결과를 바탕으로 대체조건을 생성한다."""

    def __init__(self, data_dir: Path, db_path=None):
        self.inventory_repo = InventoryRepository(data_dir, db_path)

    def generate(
        self,
        store_id: str,
        device: dict,
        inventory_result: dict,
        risk_result: dict,
    ) -> list[dict]:
        alternatives = []

        for option in inventory_result["nearby_options"]:
            alternatives.append(
                {
                    "type": "NEARBY_STORE_TRANSFER",
                    "detail": {
                        "store_id": option["store_id"],
                        "quantity_on_hand": option["quantity_on_hand"],
                        "expected_available_date": option["expected_available_date"],
                    },
                }
            )

        if inventory_result["status"] != STATUS_AVAILABLE:
            for spec in self._find_alternative_specs(store_id, device):
                alternatives.append(
                    {
                        "type": "COLOR_STORAGE_CHANGE",
                        "detail": {
                            "model": spec["model"],
                            "color": spec["color"],
                            "storage": spec["storage"],
                            "quantity_on_hand": spec["quantity_on_hand"],
                        },
                    }
                )

        if inventory_result["status"] != STATUS_AVAILABLE and inventory_result["expected_available_date"]:
            alternatives.append(
                {
                    "type": "DATE_CHANGE",
                    "detail": {"suggested_date": inventory_result["expected_available_date"]},
                }
            )

        shortfall_amount = risk_result["checks"].get("shortfall_amount")
        if shortfall_amount:
            alternatives.append(
                {
                    "type": "DOWN_PAYMENT",
                    "detail": {"shortfall_amount": shortfall_amount},
                }
            )

        missing_documents = risk_result["checks"].get("missing_documents") or []
        if missing_documents:
            alternatives.append(
                {
                    "type": "DOCUMENT_REQUEST",
                    "detail": {"missing_documents": missing_documents},
                }
            )

        return alternatives

    def _find_alternative_specs(self, store_id: str, device: dict) -> list[dict]:
        alternatives = []
        for item in self.inventory_repo.load_all():
            if (
                item["store_id"] == store_id
                and item["model"] == device["model"]
                and (item["color"] != device["color"] or item["storage"] != device["storage"])
                and item["quantity_on_hand"] > 0
            ):
                alternatives.append(item)
        return alternatives
