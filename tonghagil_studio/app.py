"""통하길 스튜디오: 채팅으로 행사 포스터를 요청하면 n8n이 이미지를 만들고, 갤러리에 보여 준다.

실행 (프로젝트 루트에서):  python -m tonghagil_studio.app
"""
import time

from flask import Flask, Response, jsonify, render_template, request, url_for

from shared.layout import init_layout
from tonghagil_studio import config, placeholder
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
store = JsonPosterStore()


@app.get("/")
def studio():
    return render_template(
        "studio.html",
        styles=STYLES,
        event_types=EVENT_TYPES,
        max_message=MAX_MESSAGE,
        n8n_connected=bool(config.N8N_WEBHOOK_URL),
    )


@app.get("/api/posters")
def list_posters():
    return jsonify(store.list())


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
