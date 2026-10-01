"""통하길 QR 안내 챗봇.

지금은 n8n 연결 전이라 고정 답변("테스트 단계입니다")만 돌려준다.
.env 에 QR_CHAT_WEBHOOK_URL 을 넣으면 같은 화면·같은 API 그대로 n8n 이 답한다 (화면 코드는 바꿀 필요 없음).

n8n 워크플로 (예정):
    Webhook(POST, Header Auth) → AI Agent(또는 규칙) → Respond to Webhook({"reply": "…"})

보내는 JSON (n8n 에서는 $json.body.<이름>):
    chatInput   방문객이 입력한 질문
    sessionId   방문객 ID (쿠키). 대화 기억(Memory) 노드의 키로 쓰면 된다
    eventId     행사 ID
    context     행사 요약 (행사명·일시·장소·부스·혜택·구역·스탬프 지점) → 답변 근거로 넣으면 잘못된 안내가 줄어든다
    network     지금 구역별 통신 상태 (모의) → "어디가 잘 터져요?" 같은 질문에 쓴다
    stamps      이 방문객이 찍은 스탬프 이름 목록
    action      "sendMessage" (n8n Chat Trigger 호환용)

받는 응답: {"reply": "…"} 권장. "output"(n8n AI Agent 기본), "text", "message", "answer" 도 알아듣고,
배열(n8n 기본 응답)이나 글자만 온 응답도 받는다.
"""
import json
import re
import sys
from dataclasses import dataclass

import requests

TEST_REPLY = "테스트 단계입니다"
_REPLY_KEYS = ("reply", "output", "text", "message", "answer")
_CODE_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$")


class ChatError(Exception):
    """방문객 화면에 그대로 보여 줄 수 있는 메시지를 담은 오류."""


@dataclass
class ChatReply:
    text: str
    source: str  # "fixed" (n8n 연결 전) | "n8n"


def reply(message, session_id, *, webhook_url, timeout, headers=None, event_id="", context=None, network=None, stamps=None):
    if not webhook_url:
        return ChatReply(TEST_REPLY, "fixed")

    payload = {
        "action": "sendMessage",
        "sessionId": session_id,
        "chatInput": message,
        "eventId": event_id,
        "context": context or {},
        "network": network or {},
        "stamps": stamps or [],
    }
    try:
        resp = requests.post(webhook_url, json=payload, headers=headers or {}, timeout=timeout)
    except requests.Timeout as exc:
        raise ChatError("답변이 늦어지고 있어요. 잠시 후 다시 물어봐 주세요.") from exc
    except requests.RequestException as exc:
        raise ChatError("채팅 에이전트에 연결하지 못했어요. 잠시 후 다시 시도해 주세요.") from exc

    if resp.status_code in (401, 403):
        raise ChatError("채팅 에이전트 인증에 실패했어요. (담당자: QR_CHAT_WEBHOOK_SECRET 과 n8n Header Auth 값 확인)")
    if resp.status_code == 404:
        raise ChatError("채팅 에이전트 주소를 찾을 수 없어요. (담당자: n8n 워크플로 활성화와 /webhook/ 운영 주소 확인)")
    if resp.status_code >= 400:
        # n8n 이 알려 준 이유를 서버 창과 화면에 같이 남긴다 (예: "No Respond to Webhook node found in the workflow")
        print(f"[통하길 QR] n8n 챗봇 오류 HTTP {resp.status_code}: {resp.text[:500]}", file=sys.stderr)
        detail = _error_detail(resp)
        raise ChatError(f"채팅 에이전트가 오류를 돌려줬어요 (HTTP {resp.status_code}{detail}). 담당자: n8n Executions 확인")

    try:
        data = resp.json()
    except ValueError:
        data = resp.text
    text = parse_reply(data)
    if not text:
        raise ChatError("채팅 에이전트가 빈 답변을 보냈어요. (담당자: Respond to Webhook 의 reply 값 확인)")
    return ChatReply(text, "n8n")


def _error_detail(resp):
    """n8n 오류 응답({"message": "…"})에서 이유 한 줄을 꺼낸다. 없으면 빈 글자."""
    try:
        message = resp.json().get("message")
    except (ValueError, AttributeError):
        return ""
    if not isinstance(message, str) or not message.strip():
        return ""
    return ": " + message.strip()[:120]


def parse_reply(data):
    """n8n 응답에서 답변 글을 찾는다.

    AI Agent 에게 {"intent": …, "reply": …} JSON 으로 답하라고 시키면 n8n 은 그 JSON 을 **글자 그대로**
    output 에 담아 보낸다(```json 코드블록으로 감싸기도 한다). 그런 글자는 풀어서 reply 만 꺼낸다.
    """
    if isinstance(data, list):
        data = data[0] if data else ""
    if isinstance(data, str):
        text = _CODE_FENCE.sub("", data).strip()
        if text.startswith("{"):
            try:
                inner = json.loads(text)
            except ValueError:
                return text
            return parse_reply(inner) or text
        return text
    if isinstance(data, dict):
        for key in _REPLY_KEYS:
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return parse_reply(value)  # output 안에 JSON 글자가 들어 있을 수 있다
        for value in data.values():  # {"json": {"reply": …}} 처럼 한 겹 싸인 경우
            if isinstance(value, (dict, list)):
                found = parse_reply(value)
                if found:
                    return found
    return ""
