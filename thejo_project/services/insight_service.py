"""인사이트를 화면에서 바로 쓸 수 있는 모양으로 만든다.

data/insight_data.py 가 가져온 행에 **기존 거래 정보**를 붙인다.
거래가 조회되는 건만 '거래 확인'(문자 모달) 버튼을 켠다. 없는 값을 지어내지 않는다.
"""
from thejo_project.data import insight_data
from thejo_project.services import transaction_service


def get_view_data(force_refresh=False):
    """화면용 인사이트. 쓸 수 없으면 None (호출한 쪽이 데모 데이터로 돌아간다).

        {"report_date": "2026-10-01", "opportunities": [...], "high_risks": [...]}
    """
    data = insight_data.get_latest_insights(force_refresh=force_refresh)
    if not data:
        return None

    return {
        "report_date": data["report_date"],
        "opportunities": data["opportunities"],
        "high_risks": [_attach_transaction(row) for row in data["high_risks"]],
    }


def _attach_transaction(row):
    """거래 ID 가 기존 거래 데이터에서 조회되면 붙인다. 안 되면 transaction=None.

    템플릿은 transaction 이 있을 때만 '거래 확인' 버튼을 그린다.
    """
    row = dict(row)
    tx_id = row.get("transaction_id") or ""
    row["transaction"] = transaction_service.get_transaction(tx_id) if tx_id else None
    return row
