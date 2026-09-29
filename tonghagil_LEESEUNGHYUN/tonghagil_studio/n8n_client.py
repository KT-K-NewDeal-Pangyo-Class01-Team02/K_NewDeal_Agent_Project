"""n8n 포스터 생성 워크플로 호출.

워크플로 (Webhook 방식):
    Webhook(POST) → Generate an image → Upload file(프로젝트이미지 폴더) → Respond to Webhook({"fileId": …})

보내는 JSON (n8n 에서는 $json.body.<이름> 으로 꺼낸다):
    chatInput  이미지 프롬프트 (설명 + 스타일 + 행사 유형)
    fileName   드라이브에 저장할 파일 이름  예) 축제_한강 불꽃축제_20261003.png
    title, eventType, style, message   참고용 원본 값
    action, sessionId                  Chat Trigger 호환용 (Chat URL 로 보내도 동작)

응답에서 구글 드라이브 파일 ID(또는 드라이브 링크)를 찾아 이미지 주소를 만든다. 필드 이름은 상관없다.
"""
import re
from dataclasses import dataclass
from typing import Optional

import requests

from tonghagil_studio import drive


class N8nError(Exception):
    """화면에 그대로 보여 줄 수 있는 메시지를 담은 오류."""


@dataclass
class GeneratedImage:
    image_url: str
    share_url: str
    download_url: str
    file_id: Optional[str] = None


def request_poster(webhook_url, prompt, session_id, timeout, extra=None, headers=None):
    payload = {
        "action": "sendMessage",
        "sessionId": session_id,
        "chatInput": prompt,
        **(extra or {}),
    }
    try:
        resp = requests.post(webhook_url, json=payload, headers=headers or {}, timeout=timeout)
    except requests.Timeout as exc:
        raise N8nError("n8n 응답 시간이 초과됐어요. 잠시 후 다시 시도해 주세요.") from exc
    except requests.RequestException as exc:
        raise N8nError("n8n에 연결하지 못했어요. 주소와 워크플로 활성화 상태를 확인해 주세요.") from exc

    if resp.status_code in (401, 403):
        raise N8nError("n8n 인증에 실패했어요. .env 의 N8N_WEBHOOK_SECRET 과 n8n Webhook 의 Header Auth 값이 같은지 확인해 주세요.")
    if resp.status_code == 404:
        raise N8nError("n8n 주소를 찾을 수 없어요. 워크플로가 활성화(Active)되어 있는지, "
                       "테스트 주소(/webhook-test/)가 아니라 운영 주소(/webhook/)인지 확인해 주세요.")
    if resp.status_code >= 400:
        raise N8nError(f"n8n이 오류를 반환했어요 (HTTP {resp.status_code}).")

    try:
        data = resp.json()
    except ValueError:
        data = resp.text
    return parse_result(data)


_URL_RE = re.compile(r"https?://[^\s\"'<>)\]]+")
_IMAGE_EXT_RE = re.compile(r"\.(png|jpe?g|webp|gif)(\?|$)", re.IGNORECASE)
_ID_KEYS = ("fileId", "file_id", "driveFileId", "id")


def parse_result(data):
    """n8n 응답(JSON 또는 텍스트)에서 이미지 위치를 찾는다."""
    strings = list(_iter_strings(data))

    # 1) 드라이브 공유 링크 (Share file / Edit Fields 결과)
    for text in strings:
        file_id = drive.extract_file_id(text)
        if file_id:
            return _from_drive(file_id)

    # 2) 링크 없이 파일 ID만 넘어온 경우 (Upload file 결과의 id 등)
    for key in _ID_KEYS:
        for value in _iter_key(data, key):
            if drive.looks_like_file_id(value):
                return _from_drive(value)

    # 3) 드라이브가 아닌 일반 이미지 주소
    for text in strings:
        for url in _URL_RE.findall(text):
            if _IMAGE_EXT_RE.search(url):
                return GeneratedImage(image_url=url, share_url=url, download_url=url)

    raise N8nError("n8n 응답에서 이미지 링크를 찾지 못했어요. 마지막 노드가 드라이브 공유 링크를 내보내는지 확인해 주세요.")


def _from_drive(file_id):
    return GeneratedImage(
        image_url=drive.image_url(file_id),
        share_url=drive.share_url(file_id),
        download_url=drive.download_url(file_id),
        file_id=file_id,
    )


def _iter_strings(data):
    if isinstance(data, str):
        yield data
    elif isinstance(data, dict):
        for value in data.values():
            yield from _iter_strings(value)
    elif isinstance(data, list):
        for value in data:
            yield from _iter_strings(value)


def _iter_key(data, key):
    if isinstance(data, dict):
        for k, value in data.items():
            if k == key:
                yield value
            yield from _iter_key(value, key)
    elif isinstance(data, list):
        for value in data:
            yield from _iter_key(value, key)
