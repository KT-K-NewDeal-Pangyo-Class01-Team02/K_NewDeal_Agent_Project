"""구글 드라이브 공유 링크를 화면에 바로 띄울 수 있는 주소로 바꾸는 도우미.

드라이브 공유 링크(https://drive.google.com/file/d/<ID>/view)는 웹페이지라서 <img> 에 바로 넣을 수 없다.
파일 ID만 뽑아서 썸네일 주소로 바꾸면 '링크가 있는 모든 사용자' 공개 파일은 이미지로 보인다.
"""
import re

_ID_PATTERNS = [
    re.compile(r"drive\.google\.com/file/d/([\w-]{20,})"),
    re.compile(r"(?:drive|docs)\.google\.com/(?:open|uc|thumbnail)\?(?:[^\s\"'#]*&)?id=([\w-]{20,})"),
    re.compile(r"lh3\.googleusercontent\.com/d/([\w-]{20,})"),
]
_BARE_ID = re.compile(r"^[\w-]{25,}$")


def extract_file_id(text):
    """드라이브 링크 문자열에서 파일 ID를 찾는다. 없으면 None."""
    for pattern in _ID_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1)
    return None


def looks_like_file_id(value):
    return isinstance(value, str) and bool(_BARE_ID.match(value))


def image_url(file_id, width=1200):
    return f"https://drive.google.com/thumbnail?id={file_id}&sz=w{width}"


def download_url(file_id):
    return f"https://drive.google.com/uc?export=download&id={file_id}"


def share_url(file_id):
    return f"https://drive.google.com/file/d/{file_id}/view"
