"""통하길 스튜디오 Blueprint: 채팅으로 행사 포스터를 요청하면 n8n이 이미지를 만들고, 갤러리에 보여 준다.

Command Center(command_center/app.py)에 Blueprint 로 등록되어 /studio/ 아래에서 허브와 같은 프로세스로 돈다.
따로 서버를 띄우지 않는다. 실행: 저장소 루트에서  python -m command_center.app  → http://localhost:5000/studio/

화면·API 주소는 모두 url_for 나 /studio/ 기준 상대 주소로 만든다.
그래서 ngrok 같은 공개 주소(https://…/studio/)로 들어와도 localhost 로 새지 않는다.
"""
import logging
import time
from io import BytesIO
from urllib.parse import urlencode

from flask import Blueprint, Response, abort, jsonify, render_template, request, send_file, url_for

from . import config, drive, placeholder
from .drive_store import DriveClient, DriveError, DriveFolderPosterStore, build_file_name
from .n8n_client import N8nError, request_poster
from .poster_store import JsonPosterStore

# static_url_path 는 url_prefix 뒤에 붙는다 → 실제 주소 /studio/static/...
studio_bp = Blueprint(
    "tonghagil_studio",
    __name__,
    url_prefix="/studio",
    template_folder="templates",
    static_folder="static",
    static_url_path="/static",
)

# 사이드바에서 "통하길 스튜디오" 항목이 켜져 보이게 한다. command_center/agents.json 의 id 와 같아야 한다.
AGENT_ID = "tonghagil-studio"
MAX_MESSAGE = 500
MAX_FIELD = 40  # 행사 이름 · 최고 사은품 글자 수

STYLES = [
    {"id": "vivid", "label": "화려한 축제", "hint": "화려한 불꽃과 네온 조명, 선명하고 강렬한 색감"},
    {"id": "warm", "label": "따뜻한 감성", "hint": "따뜻한 조명과 손글씨 느낌, 포근한 색감"},
    {"id": "modern", "label": "모던한", "hint": "미니멀한 구성과 굵은 타이포그래피, 절제된 색감"},
    {"id": "hip", "label": "힙한 감성", "hint": "스트리트 그래픽과 과감한 색 대비, 트렌디한 분위기"},
]
EVENT_TYPES = ["축제", "공연", "야시장", "가족 행사", "고객 감사제", "기타"]

# 저장소(posters.json, 드라이브 갤러리)에는 '/drive-image/…', '/placeholder.svg?…' 처럼 스튜디오 기준 주소로 저장한다.
# 화면에 내보낼 때 _localized() 가 /studio/ 를 붙인다. 붙는 위치가 바뀌어도 예전 기록이 그대로 보이게 하려는 것이다.
_LOCAL_PATHS = ("/drive-image/", "/placeholder.svg")
_URL_FIELDS = ("image_url", "share_url", "download_url")

log = logging.getLogger(__name__)


def _create_store():
    """DRIVE_FOLDER_ID 와 서비스 계정 키가 있으면 드라이브 폴더, 없으면 샘플/로컬 기록을 갤러리로 쓴다."""
    records = JsonPosterStore()
    if not config.DRIVE_FOLDER_ID:
        return records
    if not config.GOOGLE_SERVICE_ACCOUNT_FILE.exists():
        log.warning("DRIVE_FOLDER_ID 는 있지만 서비스 계정 키 파일이 없어 샘플 갤러리를 씁니다: %s",
                    config.GOOGLE_SERVICE_ACCOUNT_FILE)
        return records
    return DriveFolderPosterStore(
        DriveClient(config.GOOGLE_SERVICE_ACCOUNT_FILE),
        config.DRIVE_FOLDER_ID,
        records,
        EVENT_TYPES,
        cache_seconds=config.DRIVE_CACHE_SECONDS,
    )


store = _create_store()


@studio_bp.get("/")
def studio():
    return render_template(
        "tonghagil_studio/studio.html",
        active_agent_id=AGENT_ID,
        styles=STYLES,
        event_types=EVENT_TYPES,
        max_message=MAX_MESSAGE,
        max_field=MAX_FIELD,
        defaults=_current_event(),
        n8n_connected=bool(config.N8N_WEBHOOK_URL),
        drive_connected=isinstance(store, DriveFolderPosterStore),
    )


def _current_event():
    """'행사 이름'·'최고 사은품' 입력칸의 기본값. 통하길 QR 에 등록된 지금 행사(event.json)에서 가져온다.

    행사가 바뀌면 QR 의 event.json 만 고치면 스튜디오 기본값도 따라 바뀐다. 담당자는 화면에서 얼마든지 고쳐 쓸 수 있다.
    최고 사은품 = 준비 수량이 가장 적은 사은품. QR 쪽을 못 읽으면 빈칸으로 둔다(스튜디오는 QR 없이도 동작해야 한다).
    """
    try:
        from ..tonghagil_qr import config as qr_config
        from ..tonghagil_qr.event import Event

        data = Event(qr_config.EVENT_FILE).data
        gifts = data.get("benefit", {}).get("gifts", [])
        top = min(gifts, key=lambda g: int(g["quantity"]))["name"] if gifts else ""
        return {"event_name": str(data.get("name", ""))[:MAX_FIELD], "top_gift": str(top)[:MAX_FIELD]}
    except Exception:  # noqa: BLE001  (QR 모듈·파일이 없거나 형식이 달라도 스튜디오 화면은 떠야 한다)
        return {"event_name": "", "top_gift": ""}


@studio_bp.get("/api/posters")
def list_posters():
    if request.args.get("refresh") == "1" and isinstance(store, DriveFolderPosterStore):
        store.invalidate()
    try:
        return jsonify([_localized(p) for p in store.list()])
    except DriveError as exc:
        return jsonify(error=str(exc)), 502


@studio_bp.patch("/api/posters/<file_id>")
def update_poster(file_id):
    """제목·행사 유형 수정 → 드라이브 파일 이름도 '행사유형_제목_날짜.png' 로 바뀐다."""
    if not isinstance(store, DriveFolderPosterStore):
        return jsonify(error="구글 드라이브에 연결된 포스터만 수정할 수 있어요."), 400
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    event_type = data.get("event_type") or ""
    if not title:
        return jsonify(error="제목을 입력해 주세요."), 400
    if len(title) > 40:
        return jsonify(error="제목은 40자까지 입력할 수 있어요."), 400
    if event_type and event_type not in EVENT_TYPES:
        return jsonify(error="알 수 없는 행사 유형이에요."), 400
    try:
        poster = store.update(file_id, title, event_type)
    except KeyError:
        return jsonify(error="갤러리에 없는 포스터예요. 새로고침해 주세요."), 404
    except DriveError as exc:
        return jsonify(error=str(exc)), 502
    if poster is None:
        return jsonify(error="수정했지만 목록에서 포스터를 찾지 못했어요. 새로고침해 주세요."), 404
    return jsonify(_localized(poster))


@studio_bp.delete("/api/posters/<file_id>")
def delete_poster(file_id):
    """갤러리에서 빼고 드라이브의 '_보관함' 폴더로 옮긴다 (드라이브에서 되돌릴 수 있음)."""
    if not isinstance(store, DriveFolderPosterStore):
        return jsonify(error="구글 드라이브에 연결된 포스터만 삭제할 수 있어요."), 400
    try:
        store.archive(file_id)
    except KeyError:
        return jsonify(error="갤러리에 없는 포스터예요. 새로고침해 주세요."), 404
    except DriveError as exc:
        return jsonify(error=str(exc)), 502
    return "", 204


@studio_bp.get("/drive-image/<file_id>")
def drive_image(file_id):
    """드라이브 이미지를 서비스 계정으로 받아 대신 전달한다. ?download=1 이면 원본 파일을 내려받는다."""
    if not isinstance(store, DriveFolderPosterStore) or not drive.looks_like_file_id(file_id):
        abort(404)
    full = request.args.get("download") == "1"
    try:
        data, mimetype, name = store.image(file_id, full=full)
    except KeyError:
        abort(404)
    except DriveError as exc:
        return jsonify(error=str(exc)), 502
    if full:
        return send_file(BytesIO(data), mimetype=mimetype, as_attachment=True, download_name=name)
    return Response(data, mimetype=mimetype, headers={"Cache-Control": "public, max-age=604800"})


@studio_bp.post("/api/posters")
def create_poster():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    event_name = " ".join(str(data.get("event_name") or "").split())
    top_gift = " ".join(str(data.get("top_gift") or "").split())
    if not message and not event_name:
        return jsonify(error="행사 이름을 적거나 만들고 싶은 포스터를 설명해 주세요."), 400
    if len(message) > MAX_MESSAGE:
        return jsonify(error=f"설명은 {MAX_MESSAGE}자까지 입력할 수 있어요."), 400
    if len(event_name) > MAX_FIELD or len(top_gift) > MAX_FIELD:
        return jsonify(error=f"행사 이름과 최고 사은품은 {MAX_FIELD}자까지 입력할 수 있어요."), 400

    style = next((s for s in STYLES if s["id"] == data.get("style")), STYLES[0])
    event_type = data.get("event_type") if data.get("event_type") in EVENT_TYPES else "기타"
    title = event_name or _title_from(message)
    goal = _goal_sentence(event_name, top_gift)

    if config.N8N_WEBHOOK_URL:
        # chatInput 한 덩어리만 써도 되고, n8n 에서 eventName·topGift 를 따로 꺼내 써도 된다
        lines = [goal, message, "",
                 f"[행사 이름] {event_name}" if event_name else "",
                 f"[최고 사은품] {top_gift}" if top_gift else "",
                 f"[포스터 스타일] {style['label']} - {style['hint']}",
                 f"[행사 유형] {event_type}"]
        prompt = "\n".join(line for i, line in enumerate(lines) if line or i == 2).strip()
        headers = {config.N8N_SECRET_HEADER: config.N8N_WEBHOOK_SECRET} if config.N8N_WEBHOOK_SECRET else None
        try:
            image = request_poster(
                config.N8N_WEBHOOK_URL,
                prompt,
                session_id=data.get("session_id") or AGENT_ID,
                timeout=config.N8N_TIMEOUT,
                extra={
                    "fileName": build_file_name(title, event_type, None, "image/png"),
                    "title": title,
                    "eventType": event_type,
                    "style": style["label"],
                    "message": message,
                    "eventName": event_name,
                    "topGift": top_gift,
                },
                headers=headers,
            )
        except N8nError as exc:
            return jsonify(error=str(exc)), 502
        fields = {
            "image_url": image.image_url,
            "share_url": image.share_url,
            "download_url": image.download_url,
            "drive_file_id": image.file_id,
            "source": "n8n",
        }
    else:
        # 데모 모드: n8n 없이 화면 흐름만 확인할 수 있게 샘플 포스터를 만든다.
        time.sleep(1.2)
        query = urlencode({"theme": placeholder.theme_for_style(style["id"]), "title": title, "sub": event_type})
        url = f"/placeholder.svg?{query}"
        fields = {"image_url": url, "share_url": url, "download_url": url, "source": "demo"}

    poster = store.add(title=title, event_type=event_type, style=style["label"], prompt=message or goal, **fields)
    return jsonify(_localized(poster)), 201


def _goal_sentence(event_name, top_gift):
    """포스터가 무엇을 알려야 하는지 한 문장. 행사 이름·최고 사은품은 화면에서 바꿀 수 있는 값이다."""
    if event_name and top_gift:
        return f"'{event_name}'에서 최고 사은품 '{top_gift}'을(를) 받을 수 있는 기회를 알리는 홍보 포스터."
    if event_name:
        return f"'{event_name}'을(를) 알리는 홍보 포스터."
    if top_gift:
        return f"최고 사은품 '{top_gift}'을(를) 받을 수 있는 기회를 알리는 홍보 포스터."
    return ""


@studio_bp.get("/placeholder.svg")
def placeholder_svg():
    args = request.args
    svg = placeholder.render(
        theme=args.get("theme", ""),
        title=args.get("title", "")[:40],
        sub=args.get("sub", "")[:40],
        date=args.get("date", "")[:40],
    )
    return Response(svg, mimetype="image/svg+xml", headers={"Cache-Control": "public, max-age=86400"})


def _localized(poster):
    """'/drive-image/…', '/placeholder.svg?…' 를 이 Blueprint 아래 주소(/studio/…)로 바꾼 사본."""
    base = url_for(".studio")  # "/studio/"
    fixed = dict(poster)
    for key in _URL_FIELDS:
        value = fixed.get(key) or ""
        if value.startswith(_LOCAL_PATHS):
            fixed[key] = base + value.lstrip("/")
    return fixed


def _title_from(message, limit=18):
    first_line = message.splitlines()[0].strip()
    return first_line if len(first_line) <= limit else first_line[:limit].rstrip() + "…"
