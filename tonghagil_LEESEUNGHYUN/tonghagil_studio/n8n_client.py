"""n8n 포스터 생성 워크플로 호출.

현재 워크플로:
    When chat message received → Generate an image → Upload file → Share file → Edit Fields

Chat Trigger 의 Chat URL 로 채팅 위젯과 똑같은 요청(action=sendMessage, chatInput)을 보낸다.
나중에 트리거를 Webhook 노드로 바꿔도 같은 요청이 그대로 동작하도록 message/style 등도 함께 보낸다.

응답에서 구글 드라이브 링크나 파일 ID를 찾아 이미지 주소를 만든다.
마지막 노드(Edit Fields)가 어떤 필드 이름을 쓰든, 드라이브 링크가 들어 있기만 하면 찾아낸다.
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


def request_poster(webhook_url, prompt, session_id, timeout, extra=None):
    payload = {
        "action": "sendMessage",
        "sessionId": session_id,
        "chatInput": prompt,
        **(extra or {}),
    }
    try:
        resp = requests.post(webhook_url, json=payload, timeout=timeout)
    except requests.Timeout as exc:
        raise N8nError("n8n 응답 시간이 초과됐어요. 잠시 후 다시 시도해 주세요.") from exc
    except requests.RequestException as exc:
        raise N8nError("n8n에 연결하지 못했어요. 주소와 워크플로 활성화 상태를 확인해 주세요.") from exc

    if resp.status_code == 404:
        raise N8nError("n8n 주소를 찾을 수 없어요. 워크플로가 활성화(Active)되어 있는지 확인해 주세요.")
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
