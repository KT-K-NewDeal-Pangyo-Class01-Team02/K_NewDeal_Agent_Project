"""n8n 웹훅에 캠페인 파라미터를 보내고 기획안 텍스트를 받아 온다.

브라우저가 아니라 Flask 서버가 대신 호출하기 때문에, 예전 index.html 에서 나던
CORS 문제가 생기지 않는다.
"""
import requests

# n8n 이 기획안을 담아 보내는 키 후보들 (워크플로에 따라 이름이 조금씩 다르다)
PLAN_KEYS = ("plan", "output", "text", "result", "message", "data")


class N8nError(Exception):
    """n8n 호출이 실패했거나, 응답에서 기획안을 찾지 못했을 때."""


def request_plan(webhook_url, payload, timeout=120):
    """웹훅에 payload 를 POST 하고 기획안 텍스트를 돌려준다."""
    try:
        response = requests.post(webhook_url, json=payload, timeout=timeout)
    except requests.Timeout:
        raise N8nError(f"n8n 이 {int(timeout)}초 안에 응답하지 않았어요. 잠시 뒤 다시 시도해 주세요.")
    except requests.RequestException as exc:
        raise N8nError(f"n8n 에 연결하지 못했어요: {exc}")

    if response.status_code >= 400:
        raise N8nError(f"n8n 이 오류를 돌려줬어요 (HTTP {response.status_code}). 워크플로가 활성화돼 있는지 확인해 주세요.")

    plan = _extract_plan(_parse(response))
    if not plan:
        raise N8nError("n8n 응답에서 기획안 내용을 찾지 못했어요. 워크플로의 'Respond to Webhook' 출력을 확인해 주세요.")
    return plan


def _parse(response):
    try:
        return response.json()
    except ValueError:
        return response.text


def _extract_plan(data):
    """{"plan": "..."} · [{"output": "..."}] · 그냥 문자열 등 어떤 모양이든 텍스트를 뽑아낸다."""
    if isinstance(data, str):
        return data.strip()
    if isinstance(data, list):
        for item in data:
            found = _extract_plan(item)
            if found:
                return found
        return ""
    if isinstance(data, dict):
        for key in PLAN_KEYS:
            if key in data:
                found = _extract_plan(data[key])
                if found:
                    return found
    return ""
