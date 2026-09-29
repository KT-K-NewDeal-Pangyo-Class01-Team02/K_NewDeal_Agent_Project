from config import Config
from services.activation_risk_service import ActivationRiskService

DEVICE = {"model": "GalaxyZ Fold6", "color": "Black", "storage": "256GB"}


def test_low_risk_when_all_conditions_ok():
    service = ActivationRiskService(Config.DATA_DIR)

    result = service.check("C001", DEVICE)

    assert result["risk_level"] == "low"
    assert result["issues"] == []


def test_high_risk_for_overdue_customer():
    service = ActivationRiskService(Config.DATA_DIR)

    result = service.check("C002", DEVICE)

    assert result["risk_level"] == "high"
    assert result["checks"]["overdue_payment"] is True


def test_medium_risk_for_missing_documents():
    service = ActivationRiskService(Config.DATA_DIR)

    result = service.check("C003", DEVICE)

    assert result["risk_level"] == "medium"
    assert result["checks"]["missing_documents"] == ["가족관계증명서"]


def test_medium_risk_for_installment_shortfall():
    service = ActivationRiskService(Config.DATA_DIR)

    result = service.check("C004", DEVICE)

    assert result["risk_level"] == "medium"
    assert result["checks"]["installment_limit_ok"] is False
    assert result["checks"]["shortfall_amount"] == 1800000 - 500000


def test_high_risk_for_unknown_customer():
    service = ActivationRiskService(Config.DATA_DIR)

    result = service.check("UNKNOWN", DEVICE)

    assert result["risk_level"] == "high"
