"""고객 안내 문자: 템플릿 치환 · SMS/LMS 판정 · 발송(n8n 또는 데모).

n8n Webhook URL 은 **이 계층에서만** 읽는다. 템플릿이나 JS 로 절대 내려보내지 않는다.
requests 대신 표준 라이브러리 urllib 을 쓴다 (새 패키지를 늘리지 않기 위해).
"""
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone

from thejo_project import config
from thejo_project.data import sms_store

TEMPLATE_BY_ID = {t["id"]: t for t in config.SMS_TEMPLATES}


# ── 템플릿 ───────────────────────────────────────────────────────────────
def template_choices():
    """모달의 템플릿 칩에 쓸 목록 (본문은 보내지 않는다. 치환은 서버가 한다)."""
    return [{"id": t["id"], "label": t["label"]} for t in config.SMS_TEMPLATES]


def render_template(template_id, tx):
    """템플릿의 {중괄호} 변수를 거래 데이터로 치환한 문자 본문.

    tx 는 transaction_service.get_transaction() 이 돌려준 dict.
    """
    template = TEMPLATE_BY_ID.get(template_id)
    if not template:
        raise KeyError(template_id)

    end = tx["maintenance_end_date"]
    values = {
        "{고객명}": tx["customer_name"],
        "{요금제명}": tx["plan_name"],
        "{유지 종료일}": f"{end.year}년 {end.month}월 {end.day}일",
        "{남은일수}": str(tx["remaining_days"]),
        "{혜택금액}": f"{tx['benefit_amount']:,}",
        "{매장전화번호}": tx["store_phone"],
    }
    body = template["body"]
    for key, value in values.items():
        body = body.replace(key, value)
    return body


def rendered_templates(tx):
    """거래 하나에 대해 3개 템플릿을 미리 치환해 둔다. 모달이 한 번에 받아 간다."""
    return [
        {"id": t["id"], "label": t["label"], "body": render_template(t["id"], tx)}
        for t in config.SMS_TEMPLATES
    ]


# ── SMS / LMS 판정 ───────────────────────────────────────────────────────
def message_bytes(text):
    """한글 등 ASCII 밖 문자는 2바이트로 센다 (EUC-KR 기준). JS 와 같은 규칙."""
    return sum(1 if ord(ch) < 128 else 2 for ch in text or "")


def message_kind(text):
    """90바이트 이하면 SMS, 넘으면 LMS."""
    return "SMS" if message_bytes(text) <= config.SMS_BYTE_LIMIT else "LMS"


# ── 발송 ─────────────────────────────────────────────────────────────────
def send_sms(payload):
    """문자 발송 요청. (결과 dict, HTTP 상태코드) 를 돌려준다.

    N8N_SMS_WEBHOOK_URL 이 있으면 그리로 POST 하고, 없으면 데모 성공을 돌려준다.
    성공·실패 모두 sms_store 에 기록한다.
    """
    requested_at = _now()
    record = {
        "sms_id": sms_store.next_sms_id(),
        "transaction_id": payload.get("transaction_id"),
        "customer_id": payload.get("customer_id"),
        "customer_phone": payload.get("customer_phone"),
        "template_id": payload.get("template_id"),
        "message": payload.get("message"),
        "sms_status": "발송 완료",
        "requested_at": requested_at,
        "sent_at": None,
        "error_message": None,
        "n8n_response": None,
    }

    if not config.N8N_SMS_WEBHOOK_URL:
        # 개발 단계: 실제 발송 없이 성공 처리
        record["sent_at"] = _now()
        record["n8n_response"] = {"demo": True}
        sms_store.append(record)
        return {
            "success": True,
            "demo": True,
            "message": "데모 모드로 문자 발송 요청이 처리되었습니다.",
            "sms_id": record["sms_id"],
            "sent_at": record["sent_at"],
        }, 200

    try:
        response = _post_json(config.N8N_SMS_WEBHOOK_URL, payload, config.N8N_SMS_TIMEOUT)
    except Exception as exc:  # 네트워크 오류·타임아웃·HTTP 오류를 한데 모은다
        record["sms_status"] = "발송 실패"
        record["error_message"] = _reason(exc)
        sms_store.append(record)
        return {"success": False, "error": record["error_message"]}, 502

    record["sent_at"] = _now()
    record["n8n_response"] = response
    sms_store.append(record)
    return {
        "success": True,
        "demo": False,
        "message": "문자 발송 요청이 완료되었습니다.",
        "sms_id": record["sms_id"],
        "sent_at": record["sent_at"],
    }, 200


def _post_json(url, payload, timeout):
    """n8n 으로 JSON POST. 본문이 JSON 이 아니면 문자열 그대로 돌려준다."""
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8", "replace")
    try:
        return json.loads(body) if body.strip() else {}
    except json.JSONDecodeError:
        return {"raw": body[:500]}


def _reason(exc):
    if isinstance(exc, urllib.error.HTTPError):
        return f"문자 발송 서버가 오류를 돌려줬어요 (HTTP {exc.code}). 잠시 후 다시 시도해 주세요."
    if isinstance(exc, urllib.error.URLError):
        return "문자 발송 서버에 연결하지 못했어요. 네트워크를 확인해 주세요."
    if isinstance(exc, TimeoutError):
        return "문자 발송 서버 응답이 너무 늦어요. 잠시 후 다시 시도해 주세요."
    return "문자를 보내지 못했어요. 잠시 후 다시 시도해 주세요."


def _now():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
