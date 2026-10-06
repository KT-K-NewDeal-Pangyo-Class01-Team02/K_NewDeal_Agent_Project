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


def find_opportunity(insight_id="", device_model_name="", plan_code=""):
    """시뮬레이션할 추가 수익 기회 하나를 최신 인사이트에서 찾는다. → (row, report_date)

    insight_id 가 있으면 그것으로, 없으면 단말기 + 요금제 조합으로 찾는다.
    화면과 같은 캐시를 쓰므로 카드에 보이던 값과 같은 값으로 계산된다. 못 찾으면 row 는 None.
    """
    data = get_view_data()
    if not data:
        return None, None
    rows = data["opportunities"]
    if insight_id:
        match = next((r for r in rows if r["insight_id"] == insight_id), None)
    elif device_model_name or plan_code:
        match = next((r for r in rows
                      if r["device_model_name"] == device_model_name and r["plan_code"] == plan_code), None)
    else:
        match = None
    return match, data["report_date"]


def _attach_transaction(row):
    """거래 ID 가 기존 거래 데이터에서 조회되면 붙인다. 안 되면 transaction=None.

    템플릿은 transaction 이 있을 때만 '거래 확인' 버튼을 그린다.
    """
    row = dict(row)
    tx_id = row.get("transaction_id") or ""
    row["transaction"] = transaction_service.get_transaction(tx_id) if tx_id else None
    return row
