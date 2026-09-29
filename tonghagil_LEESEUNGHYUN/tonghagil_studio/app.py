"""통하길 스튜디오: 채팅으로 행사 포스터를 요청하면 n8n이 이미지를 만들고, 갤러리에 보여 준다.

실행: VS Code 실행(▶) 버튼, 또는 tonghagil_LEESEUNGHYUN 폴더에서  python -m tonghagil_studio.app
"""
import sys
import time
from io import BytesIO
from pathlib import Path

if not __package__:
    # 'python app.py'(VS Code 실행 버튼)로 직접 실행해도 shared/ 와 tonghagil_studio 를 찾을 수 있게 한다
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flask import Flask, Response, abort, jsonify, render_template, request, send_file, url_for

from shared.layout import init_layout
from tonghagil_studio import config, drive, placeholder
from tonghagil_studio.drive_store import DriveClient, DriveError, DriveFolderPosterStore
from tonghagil_studio.n8n_client import N8nError, request_poster
from tonghagil_studio.poster_store import JsonPosterStore

AGENT_ID = "tonghagil-studio"
MAX_MESSAGE = 500

STYLES = [
    {"id": "vivid", "label": "화려한 축제", "hint": "화려한 불꽃과 네온 조명, 선명하고 강렬한 색감"},
    {"id": "warm", "label": "따뜻한 감성", "hint": "따뜻한 조명과 손글씨 느낌, 포근한 색감"},
    {"id": "modern", "label": "모던한", "hint": "미니멀한 구성과 굵은 타이포그래피, 절제된 색감"},
    {"id": "hip", "label": "힙한 감성", "hint": "스트리트 그래픽과 과감한 색 대비, 트렌디한 분위기"},
]
EVENT_TYPES = ["축제", "공연", "야시장", "가족 행사", "고객 감사제", "기타"]

app = Flask(__name__)
init_layout(app, active_agent_id=AGENT_ID)


def _create_store():
    """DRIVE_FOLDER_ID 와 서비스 계정 키가 있으면 드라이브 폴더, 없으면 샘플/로컬 기록을 갤러리로 쓴다."""
    records = JsonPosterStore()
    if not config.DRIVE_FOLDER_ID:
        return records
    if not config.GOOGLE_SERVICE_ACCOUNT_FILE.exists():
        app.logger.warning("DRIVE_FOLDER_ID 는 있지만 서비스 계정 키 파일이 없어 샘플 갤러리를 씁니다: %s",
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


@app.get("/")
def studio():
    return render_template(
        "studio.html",
        styles=STYLES,
        event_types=EVENT_TYPES,
        max_message=MAX_MESSAGE,
        n8n_connected=bool(config.N8N_WEBHOOK_URL),
        drive_connected=isinstance(store, DriveFolderPosterStore),
    )


@app.get("/api/posters")
def list_posters():
    if request.args.get("refresh") == "1" and isinstance(store, DriveFolderPosterStore):
        store.invalidate()
    try:
        return jsonify(store.list())
    except DriveError as exc:
        return jsonify(error=str(exc)), 502


@app.patch("/api/posters/<file_id>")
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
    return jsonify(poster)


@app.delete("/api/posters/<file_id>")
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


@app.get("/drive-image/<file_id>")
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


@app.post("/api/posters")
def create_poster():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify(error="만들고 싶은 포스터를 설명해 주세요."), 400
    if len(message) > MAX_MESSAGE:
        return jsonify(error=f"설명은 {MAX_MESSAGE}자까지 입력할 수 있어요."), 400

    style = next((s for s in STYLES if s["id"] == data.get("style")), STYLES[0])
    event_type = data.get("event_type") if data.get("event_type") in EVENT_TYPES else "기타"
    title = _title_from(message)

    if config.N8N_WEBHOOK_URL:
        prompt = f"{message}\n\n[포스터 스타일] {style['label']} - {style['hint']}\n[행사 유형] {event_type}"
        try:
            image = request_poster(
                config.N8N_WEBHOOK_URL,
                prompt,
                session_id=data.get("session_id") or AGENT_ID,
                timeout=config.N8N_TIMEOUT,
                extra={"message": message, "style": style["label"], "eventType": event_type},
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
        url = url_for("placeholder_svg", theme=placeholder.theme_for_style(style["id"]), title=title, sub=event_type)
        fields = {"image_url": url, "share_url": url, "download_url": url, "source": "demo"}

    poster = store.add(title=title, event_type=event_type, style=style["label"], prompt=message, **fields)
    return jsonify(poster), 201


@app.get("/placeholder.svg")
def placeholder_svg():
    args = request.args
    svg = placeholder.render(
        theme=args.get("theme", ""),
        title=args.get("title", "")[:40],
        sub=args.get("sub", "")[:40],
        date=args.get("date", "")[:40],
    )
    return Response(svg, mimetype="image/svg+xml", headers={"Cache-Control": "public, max-age=86400"})


def _title_from(message, limit=18):
    first_line = message.splitlines()[0].strip()
    return first_line if len(first_line) <= limit else first_line[:limit].rstrip() + "…"


if __name__ == "__main__":
    app.run(port=config.STUDIO_PORT, debug=True)
