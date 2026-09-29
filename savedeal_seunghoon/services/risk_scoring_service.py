"""예약의 이탈위험 점수(churn_risk_score)와 처리 우선순위(priority_score)를 규칙 기반으로 계산한다.

점수는 DB에 저장하지 않고 조회할 때마다 다시 계산한다. 그래서 해결책을 승인하거나 시간이 흐르면
다음 조회에서 우선순위가 자동으로 바뀐다.
"""
from datetime import datetime

from services.codes import (
    CLOSED_STATUSES,
    ISSUE_ACTIVATION_REJECTED,
    ISSUE_CUSTOMER_NO_RESPONSE,
    ISSUE_IDENTITY_FAILED,
    ISSUE_INSTALLMENT_LIMIT,
    ISSUE_LABELS,
    ISSUE_MISSING_DOCUMENTS,
    ISSUE_OVERDUE_PAYMENT,
    ISSUE_STOCK_SHORTAGE,
    RISK_LABELS,
)

RISK_HIGH = "high"
RISK_MEDIUM = "medium"
RISK_LOW = "low"

# 이탈위험: 문제 원인별 기본 점수
CHURN_ISSUE_POINTS = {
    ISSUE_STOCK_SHORTAGE: 25,
    ISSUE_CUSTOMER_NO_RESPONSE: 25,
    ISSUE_INSTALLMENT_LIMIT: 20,
    ISSUE_ACTIVATION_REJECTED: 20,
    ISSUE_OVERDUE_PAYMENT: 20,
    ISSUE_IDENTITY_FAILED: 15,
    ISSUE_MISSING_DOCUMENTS: 10,
}
CHURN_WAITING_POINTS = (15, 10, 5)  # 48시간 이상 / 24시간 이상 / 6시간 이상
CHURN_RETRY_POINTS = 5
CHURN_RETRY_MAX = 15
CHURN_DEADLINE_OVERDUE_POINTS = 15
CHURN_DEADLINE_24H_POINTS = 10
CHURN_HIGH_THRESHOLD = 45
CHURN_MEDIUM_THRESHOLD = 25

# 우선순위 가중치
PRIORITY_RISK_POINTS = {RISK_HIGH: 30, RISK_MEDIUM: 15, RISK_LOW: 5}
PRIORITY_WAITING_POINTS = (10, 6, 3)
PRIORITY_RETRY_POINTS = 4
PRIORITY_RETRY_MAX = 12
PRIORITY_ISSUE_POINTS = {
    ISSUE_STOCK_SHORTAGE: 8,
    ISSUE_MISSING_DOCUMENTS: 5,
    ISSUE_ACTIVATION_REJECTED: 10,
}


def hours_until(deadline: str, now: datetime) -> float:
    return (datetime.fromisoformat(deadline) - now).total_seconds() / 3600


def hours_since(since: str, now: datetime) -> float:
    return max(0.0, (now - datetime.fromisoformat(since)).total_seconds() / 3600)


def _deadline_points(hours_left: float) -> int:
    if hours_left < 0:
        return 30
    if hours_left <= 6:
        return 25
    if hours_left <= 24:
        return 20
    if hours_left <= 72:
        return 10
    return 0


def _waiting_points(hours_waited: float, table: tuple[int, int, int]) -> int:
    over_48, over_24, over_6 = table
    if hours_waited >= 48:
        return over_48
    if hours_waited >= 24:
        return over_24
    if hours_waited >= 6:
        return over_6
    return 0


def risk_level_for(churn_score: int) -> str:
    if churn_score >= CHURN_HIGH_THRESHOLD:
        return RISK_HIGH
    if churn_score >= CHURN_MEDIUM_THRESHOLD:
        return RISK_MEDIUM
    return RISK_LOW


def calculate_churn_risk(reservation: dict, now: datetime) -> dict:
    """미해결 문제, 고객 대기시간, 재시도 횟수, 마감 임박 여부로 이탈위험 점수(0~100)를 계산한다.
    문제가 하나도 없으면 대기·마감만으로는 이탈위험을 올리지 않는다."""
    if reservation["status"] in CLOSED_STATUSES:
        return {"score": 0, "level": RISK_LOW, "factors": []}

    factors = []
    for issue in reservation["issues"]:
        points = CHURN_ISSUE_POINTS.get(issue["code"], 0)
        if points:
            factors.append({"label": ISSUE_LABELS.get(issue["code"], issue["code"]), "points": points})

    waited = hours_since(reservation["customer_waiting_since"], now)
    waiting = _waiting_points(waited, CHURN_WAITING_POINTS)
    if waiting:
        factors.append({"label": f"고객 대기 {int(waited)}시간", "points": waiting})

    retry_count = reservation["retry_count"]
    retry = min(retry_count * CHURN_RETRY_POINTS, CHURN_RETRY_MAX)
    if retry:
        factors.append({"label": f"재시도 {retry_count}회", "points": retry})

    hours_left = hours_until(reservation["activation_deadline"], now)
    if hours_left < 0:
        factors.append({"label": "개통 마감 초과", "points": CHURN_DEADLINE_OVERDUE_POINTS})
    elif hours_left <= 24:
        factors.append({"label": "마감 24시간 이내", "points": CHURN_DEADLINE_24H_POINTS})

    if not reservation["issues"]:
        factors = []

    score = min(100, sum(factor["points"] for factor in factors))
    return {"score": score, "level": risk_level_for(score), "factors": factors}


def calculate_priority(reservation: dict, now: datetime, churn: dict | None = None) -> dict:
    """완료·취소 예약은 0점. 미완료 예약은 위험도, 마감, 대기시간, 재시도, 재고, 서류, 개통반려 점수의 합."""
    if reservation["status"] in CLOSED_STATUSES:
        return {"score": 0, "factors": []}

    churn = churn or calculate_churn_risk(reservation, now)
    factors = [
        {"label": f"위험도 {RISK_LABELS[churn['level']]}", "points": PRIORITY_RISK_POINTS[churn["level"]]}
    ]

    hours_left = hours_until(reservation["activation_deadline"], now)
    deadline = _deadline_points(hours_left)
    if deadline:
        label = "개통 마감 초과" if hours_left < 0 else f"마감까지 {int(hours_left)}시간"
        factors.append({"label": label, "points": deadline})

    waited = hours_since(reservation["customer_waiting_since"], now)
    waiting = _waiting_points(waited, PRIORITY_WAITING_POINTS)
    if waiting:
        factors.append({"label": f"고객 대기 {int(waited)}시간", "points": waiting})

    retry_count = reservation["retry_count"]
    retry = min(retry_count * PRIORITY_RETRY_POINTS, PRIORITY_RETRY_MAX)
    if retry:
        factors.append({"label": f"재시도 {retry_count}회", "points": retry})

    issue_codes = {issue["code"] for issue in reservation["issues"]}
    for code, points in PRIORITY_ISSUE_POINTS.items():
        if code in issue_codes:
            factors.append({"label": ISSUE_LABELS[code], "points": points})

    return {"score": sum(factor["points"] for factor in factors), "factors": factors}
