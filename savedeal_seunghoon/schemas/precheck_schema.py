REQUIRED_FIELDS = ["customer_id", "store_id", "device", "desired_activation_date", "line_type"]
REQUIRED_DEVICE_FIELDS = ["model", "color", "storage"]
VALID_LINE_TYPES = {"NEW", "MNP", "CHANGE"}


class PrecheckValidationError(Exception):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


def validate_precheck_request(payload: dict | None) -> None:
    if not isinstance(payload, dict):
        raise PrecheckValidationError(["요청 본문은 JSON 객체여야 합니다."])

    errors = []

    for field in REQUIRED_FIELDS:
        if field not in payload:
            errors.append(f"필수 필드가 없습니다: {field}")

    device = payload.get("device")
    if device is not None:
        if not isinstance(device, dict):
            errors.append("device는 객체여야 합니다.")
        else:
            for field in REQUIRED_DEVICE_FIELDS:
                if field not in device:
                    errors.append(f"device에 필수 필드가 없습니다: {field}")

    line_type = payload.get("line_type")
    if line_type is not None and line_type not in VALID_LINE_TYPES:
        errors.append(f"line_type은 {sorted(VALID_LINE_TYPES)} 중 하나여야 합니다.")

    if errors:
        raise PrecheckValidationError(errors)
