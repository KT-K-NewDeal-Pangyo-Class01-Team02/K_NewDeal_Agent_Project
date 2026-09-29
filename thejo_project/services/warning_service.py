"""위험 경고 조회·가공.

데이터는 data/demo_data.py 에서 읽고, 화면에 필요한 값(남은 일수·등급 라벨·거래 정보)만 여기서 붙인다.
"""
from thejo_project.data import demo_data
from thejo_project.services import transaction_service

LEVEL_LABELS = {"high": "높음", "medium": "보통", "low": "낮음"}
KIND_LABELS = {"clawback": "인센티브 환수", "settlement": "정산 불일치", "margin": "마진 미달"}

# 조치 완료 처리. 데모라 프로세스 메모리에만 남는다. DB 가 붙으면 테이블로 옮긴다.
_acknowledged = set()


def _decorate(raw):
    warning = dict(raw)
    warning["days_left"] = (warning["check_date"] - demo_data.DEMO_TODAY).days
    warning["level_label"] = LEVEL_LABELS.get(warning["level"], warning["level"])
    warning["kind_label"] = KIND_LABELS.get(warning["kind"], warning["kind"])
    warning["acknowledged"] = warning["id"] in _acknowledged

    # 카드에 고객명·문자 상태를 보여 주려면 거래가 필요하다.
    warning["transaction"] = transaction_service.get_transaction(warning["transaction_id"])
    return warning


def get_warning_items(include_acknowledged=True):
    """위험 경고 목록. 위험 등급이 높고 기한이 급한 순서로 정렬한다."""
    order = {"high": 0, "medium": 1, "low": 2}
    items = [_decorate(raw) for raw in demo_data.get_warnings()]
    if not include_acknowledged:
        items = [w for w in items if not w["acknowledged"]]
    return sorted(items, key=lambda w: (w["acknowledged"], order.get(w["level"], 9), w["days_left"]))


def get_warning(warning_id):
    for warning in get_warning_items():
        if warning["id"] == warning_id:
            return warning
    return None


def acknowledge(warning_id):
    """조치 완료 표시. 없는 id 면 False."""
    if any(raw["id"] == warning_id for raw in demo_data.get_warnings()):
        _acknowledged.add(warning_id)
        return True
    return False


def reset_acknowledgements():
    """테스트용: 조치 완료 상태를 비운다."""
    _acknowledged.clear()


def total_expected_loss(kind=None):
    """아직 조치하지 않은 경고의 예상 손실 합계(원). kind 를 주면 그 종류만 더한다."""
    return sum(
        w["expected_loss"]
        for w in get_warning_items(include_acknowledged=False)
        if kind is None or w["kind"] == kind
    )
