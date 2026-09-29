"""구글 드라이브 폴더를 포스터 갤러리로 쓰는 저장소 (서비스 계정 + Drive API).

n8n이 만든 이미지가 드라이브 폴더에 쌓이면, 이 저장소가 그 폴더의 이미지 목록을 읽어 갤러리에 보여 준다.
- 목록: Drive API files.list (폴더 안 이미지, 최신순). 너무 자주 부르지 않도록 잠깐 캐시한다.
- 이미지: 비공개 파일도 보이도록 Flask가 서비스 계정으로 받아서 대신 전달한다 (/drive-image/<id>).
- 스튜디오에서 요청한 포스터의 제목·행사 유형·요청 문구는 posters.json 에 기록해 두고 파일 ID로 합친다.
- 수정: 드라이브 파일 이름을 '행사유형_제목_날짜.확장자' 로 바꾼다.
- 삭제: 파일 소유자만 휴지통에 버릴 수 있으므로, 폴더 안 '_보관함' 하위 폴더로 옮긴다 (드라이브에서 되돌릴 수 있음).
  → 서비스 계정을 폴더에 '편집자'로 공유해야 수정·삭제가 된다.
"""
import re
import threading
import time
from datetime import datetime
from pathlib import Path

import requests
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import AuthorizedSession
from google.oauth2 import service_account

from tonghagil_studio import drive

API = "https://www.googleapis.com/drive/v3/files"
SCOPES = ["https://www.googleapis.com/auth/drive"]
FOLDER_MIME = "application/vnd.google-apps.folder"
ARCHIVE_FOLDER_NAME = "_보관함"
_THUMB_SIZE = re.compile(r"=s\d+$")
_EXTENSIONS = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "image/gif": ".gif"}


class DriveError(Exception):
    """화면에 그대로 보여 줄 수 있는 메시지를 담은 오류."""


class DriveClient:
    """서비스 계정으로 Drive API 를 부르는 얇은 클라이언트."""

    def __init__(self, key_file, timeout=30):
        self.key_file = Path(key_file)
        self.timeout = timeout
        self._session = None

    def list_images(self, folder_id, limit=300):
        files, page_token = [], None
        while len(files) < limit:
            params = {
                "q": f"'{folder_id}' in parents and mimeType contains 'image/' and trashed = false",
                "fields": "nextPageToken, files(id, name, mimeType, createdTime, webViewLink)",
                "orderBy": "createdTime desc",
                "pageSize": 100,
                "supportsAllDrives": "true",
                "includeItemsFromAllDrives": "true",
            }
            if page_token:
                params["pageToken"] = page_token
            data = self._request("GET", API, params).json()
            files.extend(data.get("files", []))
            page_token = data.get("nextPageToken")
            if not page_token:
                break
        return files[:limit]

    def check_folder(self, folder_id):
        """폴더에 접근할 수 없으면 DriveError (목록이 비었을 때 원인을 알려 주려고 쓴다)."""
        self._request("GET", f"{API}/{folder_id}", {"fields": "id", "supportsAllDrives": "true"})

    def get_thumbnail(self, file_id, size=1000):
        meta = self._request("GET", f"{API}/{file_id}", {"fields": "thumbnailLink", "supportsAllDrives": "true"}).json()
        link = meta.get("thumbnailLink")
        if not link:
            return self.get_content(file_id)
        # 썸네일 주소는 비공개 파일이면 인증이 필요하므로 같은 세션으로 받는다
        resp = self._request("GET", _THUMB_SIZE.sub(f"=s{size}", link))
        return resp.content, resp.headers.get("Content-Type", "image/jpeg")

    def get_content(self, file_id):
        resp = self._request("GET", f"{API}/{file_id}", {"alt": "media", "supportsAllDrives": "true"})
        return resp.content, resp.headers.get("Content-Type", "application/octet-stream")

    def rename(self, file_id, name):
        self._request("PATCH", f"{API}/{file_id}", {"fields": "id, name", "supportsAllDrives": "true"}, {"name": name})

    def move(self, file_id, from_folder, to_folder):
        params = {"addParents": to_folder, "removeParents": from_folder, "fields": "id", "supportsAllDrives": "true"}
        self._request("PATCH", f"{API}/{file_id}", params, {})

    def find_or_create_folder(self, parent_id, name):
        escaped = name.replace("\\", "\\\\").replace("'", "\\'")
        found = self._request("GET", API, {
            "q": f"'{parent_id}' in parents and name = '{escaped}' and mimeType = '{FOLDER_MIME}' and trashed = false",
            "fields": "files(id)",
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
        }).json().get("files", [])
        if found:
            return found[0]["id"]
        created = self._request("POST", API, {"fields": "id", "supportsAllDrives": "true"},
                                {"name": name, "mimeType": FOLDER_MIME, "parents": [parent_id]}).json()
        return created["id"]

    @property
    def session(self):
        if self._session is None:
            try:
                creds = service_account.Credentials.from_service_account_file(str(self.key_file), scopes=SCOPES)
            except (OSError, ValueError) as exc:
                raise DriveError(f"서비스 계정 키 파일을 읽지 못했어요: {self.key_file}") from exc
            self._session = AuthorizedSession(creds)
        return self._session

    def _request(self, method, url, params=None, json=None):
        try:
            resp = self.session.request(method, url, params=params, json=json, timeout=self.timeout)
        except GoogleAuthError as exc:
            raise DriveError("구글 인증에 실패했어요. 서비스 계정 키 파일이 올바른지 확인해 주세요.") from exc
        except requests.RequestException as exc:
            raise DriveError("구글 드라이브에 연결하지 못했어요. 인터넷 연결을 확인해 주세요.") from exc

        if resp.status_code < 400:
            return resp
        reason, message = _google_error(resp)
        if resp.status_code == 404:
            raise DriveError("드라이브 폴더나 파일을 찾을 수 없어요. 폴더 ID와, 폴더를 서비스 계정 이메일에 공유했는지 확인해 주세요.")
        if resp.status_code == 403 and reason in ("accessNotConfigured", "SERVICE_DISABLED"):
            raise DriveError("Google Drive API 가 꺼져 있어요. 구글 클라우드 콘솔에서 Google Drive API 를 '사용'으로 켜 주세요.")
        if resp.status_code == 403:
            raise DriveError(f"이 작업을 할 권한이 없어요. 드라이브 폴더를 서비스 계정 이메일에 '편집자'로 공유했는지 확인해 주세요. ({message})")
        raise DriveError(f"구글 드라이브 오류 (HTTP {resp.status_code}): {message}")


class DriveFolderPosterStore:
    """JsonPosterStore 와 같은 list()/add() 를 가진, 드라이브 폴더 기반 저장소."""

    def __init__(self, client, folder_id, records, event_types, cache_seconds=60, cache_dir=None):
        self.client = client
        self.folder_id = folder_id
        self.records = records  # JsonPosterStore: 스튜디오에서 요청한 포스터의 부가 정보
        self.event_types = event_types
        self.cache_seconds = cache_seconds
        self.cache_dir = Path(cache_dir) if cache_dir else records.path.parent / "drive_cache"
        self._lock = threading.Lock()
        self._cached_at = None
        self._posters = []
        self._files = {}  # 파일 ID → 드라이브 파일 정보 (허용된 파일인지 확인 + 다운로드 이름)
        self._archive_id = None

    def list(self):
        with self._lock:
            if self._cached_at is not None and time.monotonic() - self._cached_at < self.cache_seconds:
                return self._posters

        files = self.client.list_images(self.folder_id)
        if not files:
            self.client.check_folder(self.folder_id)

        records = self.records.list()
        by_file = {r["drive_file_id"]: r for r in records if r.get("drive_file_id")}
        posters = [self._to_poster(f, by_file.get(f["id"])) for f in files]
        # 데모 모드로 만든 포스터(드라이브에 없는 것)도 같이 보여 준다
        posters += [r for r in records if r.get("source") == "demo"]
        posters.sort(key=lambda p: p.get("created_at", ""), reverse=True)

        known = {fid: {"name": f"{r.get('title', fid)}.png"} for fid, r in by_file.items()}
        known.update({f["id"]: f for f in files})
        with self._lock:
            self._posters = posters
            self._files = known
            self._cached_at = time.monotonic()
        return posters

    def add(self, **fields):
        file_id = fields.get("drive_file_id")
        if file_id:
            fields.update(image_url=image_url(file_id), download_url=download_url(file_id))
        record = self.records.add(**fields)
        self.invalidate()
        return {**record, "id": file_id} if file_id else record

    def update(self, file_id, title, event_type):
        """제목·행사 유형을 바꾸고, 드라이브 파일 이름도 '행사유형_제목_날짜.확장자' 로 바꾼다."""
        info = self._known_file(file_id)
        name = build_file_name(title, event_type, info.get("createdTime"), info.get("mimeType"), info.get("name", ""))
        self.client.rename(file_id, name)
        self.records.update_by_file_id(file_id, title=title, event_type=event_type)
        self.invalidate()
        return next((p for p in self.list() if p["id"] == file_id), None)

    def archive(self, file_id):
        """갤러리에서 빼고 드라이브의 '_보관함' 폴더로 옮긴다."""
        self._known_file(file_id)
        if self._archive_id is None:
            self._archive_id = self.client.find_or_create_folder(self.folder_id, ARCHIVE_FOLDER_NAME)
        self.client.move(file_id, self.folder_id, self._archive_id)
        (self.cache_dir / f"{file_id}.thumb").unlink(missing_ok=True)
        self.invalidate()

    def invalidate(self):
        with self._lock:
            self._cached_at = None

    def image(self, file_id, full=False):
        """(바이트, MIME 타입, 파일 이름). 이 폴더/스튜디오와 관계없는 파일이면 KeyError."""
        info = self._known_file(file_id)
        name = info.get("name") or file_id
        if full:
            data, mimetype = self.client.get_content(file_id)
            if "." not in name:
                name += _EXTENSIONS.get(mimetype.split(";")[0], "")
            return data, mimetype, name

        path = self.cache_dir / f"{file_id}.thumb"
        if path.exists():
            data = path.read_bytes()
            return data, _sniff_image_type(data), name
        data, mimetype = self.client.get_thumbnail(file_id)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)
        return data, mimetype, name

    def _known_file(self, file_id):
        if file_id not in self._files:
            self.invalidate()
            self.list()
        if file_id not in self._files:
            raise KeyError(file_id)
        return self._files[file_id]

    def _to_poster(self, file, record):
        file_id = file["id"]
        title, event_type = parse_file_name(file["name"], self.event_types)
        poster = {
            "id": file_id,
            "title": title,
            "event_type": event_type,
            "created_at": _local_iso(file.get("createdTime")),
            "image_url": image_url(file_id),
            "download_url": download_url(file_id),
            "share_url": file.get("webViewLink") or drive.share_url(file_id),
            "drive_file_id": file_id,
            "source": "drive",
        }
        if record:
            poster.update({k: record[k] for k in ("title", "event_type", "style", "prompt") if record.get(k)})
        return poster


def image_url(file_id):
    return f"/drive-image/{file_id}"


def download_url(file_id):
    return f"/drive-image/{file_id}?download=1"


def parse_file_name(name, event_types):
    """'축제_한강 불꽃축제_20261003.png' → ('한강 불꽃축제', '축제'). 규칙에 안 맞으면 (파일 이름, '')."""
    stem = name.rsplit(".", 1)[0] if "." in name else name
    parts = [p.strip() for p in stem.split("_") if p.strip()]
    if len(parts) >= 2 and parts[0] in event_types:
        return parts[1], parts[0]
    return stem, ""


def build_file_name(title, event_type, created_time, mimetype, old_name=""):
    """parse_file_name 의 반대. ('한강 불꽃축제', '축제', …) → '축제_한강 불꽃축제_20261003.png'."""
    title = re.sub(r"[_/\\]+", " ", title).strip()
    ext = Path(old_name).suffix if "." in old_name else _EXTENSIONS.get(mimetype or "", "")
    date = _local_iso(created_time)[:10].replace("-", "")
    parts = [event_type, title, date] if event_type else [title, date]
    return "_".join(p for p in parts if p) + ext


def _local_iso(value):
    """드라이브의 UTC 시각 → 이 컴퓨터 시간대 기준 'YYYY-MM-DDTHH:MM:SS' (posters.json 과 같은 형식)."""
    if not value:
        return ""
    moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return moment.astimezone().replace(tzinfo=None).isoformat(timespec="seconds")


def _sniff_image_type(data):
    if data.startswith(b"\x89PNG"):
        return "image/png"
    if data.startswith(b"GIF8"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def _google_error(resp):
    """(reason, message). 예: ('insufficientFilePermissions', 'The user does not have …')"""
    try:
        error = resp.json()["error"]
        reasons = [e.get("reason") for e in error.get("errors", [])]
        reasons += [d.get("reason") for d in error.get("details", []) if isinstance(d, dict)]
        return next((r for r in reasons if r), ""), error.get("message", "")
    except (ValueError, KeyError, TypeError, AttributeError):
        return "", resp.text[:200]
