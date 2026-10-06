"""n8n Webhook 호출 (SaveDeal → n8n → Gmail).

구조는 팀 통하길 스튜디오의 n8n_client.py 를 참고했다(그 파일은 수정하지 않음).
보내는 JSON (n8n 에서는 $json.body.<이름> 으로 꺼낸다):
    kind, subject, text, to(선택), notification_id, idempotency_key, reservation_id(선택)
"""
import requests


class N8nError(Exception):
    """화면에 그대로 보여 줄 수 있는 메시지를 담은 오류."""


def fetch_events(events_url: str, timeout: float, secret: str = "", secret_header: str = "") -> list[dict]:
    """가져오기 모드: n8n Webhook 을 불러 외부 이벤트 목록을 받는다 (SaveDeal → n8n 방향이라 ngrok 없이도 된다).
    n8n 의 'Respond to Webhook'(모든 항목) 응답인 [{...}, ...] 또는 {"events": [...]} 를 받는다."""
    body = send(events_url, {"action": "fetch_events"}, timeout, secret, secret_header)
    if isinstance(body, dict):
        body = body.get("events", body.get("data", []))
    if not isinstance(body, list):
        raise N8nError("n8n 응답에서 이벤트 목록을 찾지 못했습니다. 'Respond to Webhook' 노드가 목록(JSON)을 돌려주는지 확인해 주세요.")
    # n8n 항목 형식({"json": {...}})이 그대로 오면 풀어 준다. 시트가 비어 있을 때 오는 빈 항목({})은 버린다.
    items = [item.get("json", item) if isinstance(item, dict) else item for item in body]
    return [item for item in items if item not in ({}, None, "")]


def send(webhook_url: str, payload: dict, timeout: float, secret: str = "", secret_header: str = ""):
    headers = {secret_header: secret} if secret and secret_header else {}
    try:
        response = requests.post(webhook_url, json=payload, headers=headers, timeout=timeout)
    except requests.Timeout as exc:
        raise N8nError("n8n 응답 시간이 초과됐습니다. 잠시 후 다시 시도해 주세요.") from exc
    except requests.RequestException as exc:
        raise N8nError("n8n에 연결하지 못했습니다. 주소와 워크플로 활성화 상태를 확인해 주세요.") from exc

    if response.status_code in (401, 403):
        raise N8nError("n8n 인증에 실패했습니다. .env 의 N8N_WEBHOOK_SECRET 과 Webhook 의 Header Auth 값이 같은지 확인해 주세요.")
    if response.status_code == 404:
        raise N8nError("n8n 주소를 찾을 수 없습니다. 워크플로가 활성화(Active)됐는지, 테스트 주소(/webhook-test/)가 아니라 "
                       "운영 주소(/webhook/)인지 확인해 주세요.")
    if response.status_code >= 400:
        raise N8nError(f"n8n이 오류를 반환했습니다 (HTTP {response.status_code}).")
    try:
        return response.json()
    except ValueError:
        return {"raw": response.text[:200]}
