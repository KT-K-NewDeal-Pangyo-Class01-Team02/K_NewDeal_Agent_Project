"""n8n 조회용 Webhook 에서 Google Sheets `daily_insights` 최신 데이터를 가져온다.

여기는 **데이터 접근 계층**이다. 거래 조회나 화면 가공은 하지 않는다 (services/insight_service.py 가 한다).

규칙
  - 실패하면 예외를 밖으로 던지지 않고 None 을 돌려준다. 호출한 쪽이 데모 데이터로 돌아간다.
  - 로그에는 원인만 남기고 **Webhook URL 과 토큰은 절대 찍지 않는다**.
  - requests 대신 표준 urllib 을 쓴다 (sms_service 와 같은 방식, 새 패키지를 늘리지 않기 위해).
"""
import json
import logging
import threading
import time
import urllib.error
import urllib.request

from thejo_project import config

log = logging.getLogger(__name__)

CATEGORY_OPPORTUNITY = "추가 수익 기회"
CATEGORY_RISK = "확인해야 할 위험"
SEVERITY_HIGH = "높음"

# 캐시: 매 페이지 요청마다 외부 호출이 나가지 않게 한다.
_cache = {"value": None, "expires_at": 0.0}
_lock = threading.Lock()


# ── 공개 함수 ────────────────────────────────────────────────────────────
def get_latest_insights(force_refresh=False):
    """최신 인사이트. 실패하거나 URL 이 없으면 None.

    돌려주는 모양:
        {"report_date": "2026-10-01", "opportunities": [...], "high_risks": [...]}
    """
    if not config.N8N_INSIGHTS_WEBHOOK_URL:
        return None

    now = time.monotonic()
    with _lock:
        if not force_refresh and now < _cache["expires_at"]:
            return _cache["value"]

    value = _fetch_and_build()

    with _lock:
        _cache["value"] = value
        # 성공은 길게, 실패는 짧게 캐시한다. n8n 이 죽었을 때 페이지마다 5초씩 기다리지 않게.
        ttl = config.INSIGHTS_CACHE_SECONDS if value else config.INSIGHTS_FAILURE_CACHE_SECONDS
        _cache["expires_at"] = time.monotonic() + ttl
    return value


def clear_cache():
    """테스트용."""
    with _lock:
        _cache["value"] = None
        _cache["expires_at"] = 0.0


# ── 내부 ─────────────────────────────────────────────────────────────────
def _fetch_and_build():
    try:
        raw = _get_json(config.N8N_INSIGHTS_WEBHOOK_URL, config.N8N_INSIGHTS_TOKEN,
                        config.N8N_INSIGHTS_TIMEOUT)
    except urllib.error.HTTPError as exc:
        log.warning("인사이트 조회 실패: 서버가 HTTP %s 를 돌려줬습니다.", exc.code)
        return None
    except urllib.error.URLError as exc:
        log.warning("인사이트 조회 실패: 연결하지 못했습니다 (%s).", type(exc.reason).__name__)
        return None
    except TimeoutError:
        log.warning("인사이트 조회 실패: %s초 안에 응답이 오지 않았습니다.", config.N8N_INSIGHTS_TIMEOUT)
        return None
    except json.JSONDecodeError:
        log.warning("인사이트 조회 실패: 응답이 JSON 이 아닙니다.")
        return None
    except Exception as exc:  # 어떤 경우에도 화면이 500 으로 죽지 않게 한다
        log.warning("인사이트 조회 실패: 예상치 못한 오류 (%s).", type(exc).__name__)
        return None

    items = _as_items(raw)
    if not items:
        log.warning("인사이트 조회 결과가 비어 있습니다. 데모 데이터를 씁니다.")
        return None

    rows = [_normalise(item) for item in items if isinstance(item, dict)]
    rows = _dedupe_by_id(rows)
    rows = _only_latest_report_date(rows)
    if not rows:
        log.warning("인사이트에 쓸 수 있는 행이 없습니다. 데모 데이터를 씁니다.")
        return None

    return {
        "report_date": rows[0]["report_date"],
        "opportunities": [r for r in rows if r["category"] == CATEGORY_OPPORTUNITY],
        "high_risks": [
            r for r in rows
            if r["category"] == CATEGORY_RISK and r["severity"] == SEVERITY_HIGH
        ],
    }


def _get_json(url, token, timeout):
    headers = {"Accept": "application/json"}
    if token:
        headers["X-Thejo-Token"] = token
    request = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8", "replace")
    if not body.strip():
        return None
    return json.loads(body)


def _as_items(raw):
    """원시 배열과 {"items": [...]} 를 모두 받는다."""
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        for key in ("items", "data", "results"):
            if isinstance(raw.get(key), list):
                return raw[key]
        # n8n 이 단일 객체 하나만 돌려주는 경우
        if raw.get("insight_id"):
            return [raw]
    return []


def _normalise(item):
    """필드가 비거나 없어도 화면이 깨지지 않도록 기본값을 채운다."""
    return {
        "insight_id": _text(item.get("insight_id")),
        "report_date": _text(item.get("report_date")),
        "category": _text(item.get("category")),
        "severity": _text(item.get("severity")),
        "device_model_name": _text(item.get("device_model_name")),
        "plan_code": _text(item.get("plan_code")),
        "transaction_id": _text(item.get("transaction_id")),
        "customer_name_masked": _text(item.get("customer_name_masked")),
        "current_sales": _int(item.get("current_sales")),
        "additional_sales_needed": _int(item.get("additional_sales_needed")),
        "amount": _int(item.get("amount")),
        "reason": _text(item.get("reason")),
        "created_at": _text(item.get("created_at")),
    }


def _text(value):
    return "" if value is None else str(value).strip()


def _int(value):
    """"1,100,000" · 9 · "9" · 9.0 · "" · None 을 모두 안전하게 정수로."""
    if value is None:
        return 0
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip().replace(",", "").replace(" ", "")
    if not text:
        return 0
    try:
        return int(float(text))
    except ValueError:
        return 0


def _dedupe_by_id(rows):
    """insight_id 가 같으면 created_at 이 가장 최신인 것만 남긴다.

    created_at 은 'YYYY-MM-DD HH:MM:SS' 라 문자열 비교로도 시간 순서가 맞는다.
    id 가 비어 있는 행은 합치지 않고 그대로 둔다.
    """
    best = {}
    loose = []
    for row in rows:
        key = row["insight_id"]
        if not key:
            loose.append(row)
            continue
        current = best.get(key)
        if current is None or row["created_at"] >= current["created_at"]:
            best[key] = row
    return list(best.values()) + loose


def _only_latest_report_date(rows):
    """report_date 가 가장 최신인 날짜의 행만 남긴다."""
    dates = [r["report_date"] for r in rows if r["report_date"]]
    if not dates:
        return rows
    latest = max(dates)
    return [r for r in rows if r["report_date"] == latest]
