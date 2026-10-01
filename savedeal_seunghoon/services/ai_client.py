"""OpenAI Chat Completions 호출. 키는 .env 의 OPENAI_API_KEY 에만 둔다 (git에 올리지 않음).
SDK 대신 requests 로 직접 호출해 의존성을 늘리지 않는다."""
import json
import time

import requests

OPENAI_URL = "https://api.openai.com/v1/chat/completions"


class AIError(Exception):
    """AI 호출 실패. 호출한 쪽은 규칙 기반 결과로 대체한다."""


class OpenAIClient:
    provider = "openai"

    def __init__(self, api_key: str, model: str, timeout: float = 20):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def chat(self, system: str, user: str, json_mode: bool = False) -> tuple[str, int]:
        """(응답 글, 걸린 시간 ms). json_mode 면 JSON 객체 문자열을 돌려받는다."""
        body = {
            "model": self.model,
            "temperature": 0.3,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        started = time.perf_counter()
        try:
            response = requests.post(
                OPENAI_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=body,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise AIError(f"OpenAI에 연결하지 못했습니다: {exc.__class__.__name__}") from exc
        latency = int((time.perf_counter() - started) * 1000)
        if response.status_code == 401:
            raise AIError("OpenAI API 키가 올바르지 않습니다.")
        if response.status_code == 429:
            raise AIError("OpenAI 사용 한도를 넘었거나 크레딧이 부족합니다.")
        if response.status_code >= 400:
            raise AIError(f"OpenAI 오류 (HTTP {response.status_code}).")
        try:
            text = response.json()["choices"][0]["message"]["content"].strip()
        except (ValueError, KeyError, IndexError) as exc:
            raise AIError("OpenAI 응답 형식을 해석하지 못했습니다.") from exc
        if json_mode:
            try:
                json.loads(text)
            except ValueError as exc:
                raise AIError("AI가 JSON 형식으로 답하지 않았습니다.") from exc
        return text, latency
