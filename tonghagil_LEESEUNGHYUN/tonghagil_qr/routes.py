"""통하길 QR Blueprint: 방문객이 QR 로 들어와 행사 안내·KT 부스 위치·구역별 통신 상태·스탬프 이벤트를 이용한다.

Command Center(command_center/app.py)에 Blueprint 로 등록되어 /qr/ 아래에서 허브와 같은 프로세스로 돈다.

방문객 화면 (휴대폰, 로그인 없음 · 쿠키로 구분)
    /qr/            행사 안내 홈      (포스터 QR 은 /qr/?src=poster)
    /qr/map         지도 · KT 부스 위치 · 구역별 통신 상태(모의)
    /qr/stamps      스탬프 5곳 · 다 모으면 쿠폰
    /qr/s/<token>   스탬프 지점 QR 이 가리키는 주소 → 스탬프 찍고 /qr/stamps 로
    /qr/chat        채팅 에이전트 (QR_CHAT_WEBHOOK_URL 이 없으면 고정 답변)
부스 담당자 화면 (허브 사이드바 · PIN)
    /qr/staff/      현황 · 관리자 에이전트 채팅 · 쿠폰 지급 · QR 인쇄 · 시연 초기화

주소는 모두 url_for 로 만든다. ngrok 같은 공개 주소로 들어와도 localhost 로 새지 않는다.
QR 코드에 넣는 주소만 QR_PUBLIC_BASE_URL(없으면 지금 접속한 주소) 기준의 전체 주소다.
"""
import hashlib
import hmac
import re
import secrets
import threading
import time
from urllib.parse import urlsplit

from flask import Blueprint, Response, abort, g, jsonify, redirect, render_template, request, url_for

from . import chat_client, config, network, qr_image
from .event import Event
from .store import QrStore, normalize_code

# static_url_path 는 url_prefix 뒤에 붙는다 → 실제 주소 /qr/static/...
qr_bp = Blueprint(
    "tonghagil_qr",
    __name__,
    url_prefix="/qr",
    template_folder="templates",
    static_folder="static",
    static_url_path="/static",
)

# 허브 사이드바에서 "통하길 QR" 항목이 켜져 보이게 한다. command_center/agents.json 의 id 와 같아야 한다.
AGENT_ID = "tonghagil-qr"
VISITOR_COOKIE = "tq_vid"
STAFF_COOKIE = "tq_staff"
VISITOR_DAYS = 7
STAFF_HOURS = 12
MAX_CHAT = 300
_VISITOR_ID = re.compile(r"^[A-Za-z0-9_-]{16,64}$")

event = Event(config.EVENT_FILE)
store = QrStore(config.DB_FILE)


# ───────────────────────────── 방문객 ─────────────────────────────

def _visitor_id():
    """쿠키의 방문객 ID. 처음 온 사람이면 새로 만들고, 응답할 때 쿠키를 심는다(_set_cookies)."""
    if "visitor_id" in g:
        return g.visitor_id
    vid = request.cookies.get(VISITOR_COOKIE, "")
    if not _VISITOR_ID.match(vid):
        vid = secrets.token_urlsafe(18)
        g.new_visitor = True
    source = "poster" if request.args.get("src") == "poster" else ""
    store.ensure_visitor(vid, source)  # 처음 만들 때만 기록된다 (포스터 QR 로 들어왔는지)
    g.visitor_id = vid
    return vid


@qr_bp.after_request
def _set_cookies(resp):
    if g.pop("new_visitor", False):
        resp.set_cookie(VISITOR_COOKIE, g.visitor_id, max_age=VISITOR_DAYS * 86400,
                        httponly=True, samesite="Lax", path=url_for(".home"))
    return resp


def _progress(vid):
    """(찍은 스탬프 ID 집합, 필요한 개수, 쿠폰 또는 None). 다 모았는데 쿠폰이 없으면 여기서 발급한다."""
    valid = {s["id"] for s in event.data["stamps"]}
    done = store.stamps_of(vid) & valid
    required = event.required_stamps
    coupon = store.coupon_of(vid)
    if coupon is None and len(done) >= required:
        coupon = store.issue_coupon(vid)
    return done, required, coupon


def _visitor_page(template, page, **ctx):
    vid = _visitor_id()
    store.log_view(vid, page)
    done, required, coupon = _progress(vid)
    return render_template(f"tonghagil_qr/{template}", ev=event.data, page=page,
                           done=done, required=required, coupon=coupon, **ctx)


@qr_bp.get("/")
def home():
    return _visitor_page("home.html", "home", net=network.snapshot(event.data))


@qr_bp.get("/map")
def map_view():
    """카카오맵 키와 위경도가 있으면 실제 지도, 아니면(또는 지도가 못 뜨면) 그림 약도."""
    net = network.snapshot(event.data)
    net_by_id = {z["id"]: z for z in net["zones"]}
    done = _progress(_visitor_id())[0]
    map_data = event.map_data(done, net_by_id) if config.KAKAO_MAP_KEY else None
    return _visitor_page("map.html", "map", net=net, net_by_id=net_by_id,
                         kakao_key=config.KAKAO_MAP_KEY if map_data else "", map_data=map_data,
                         zone_names={z["id"]: z["name"] for z in event.data["zones"]})


@qr_bp.get("/stamps")
def stamps():
    got = event.stamp(request.args.get("got", ""))
    return _visitor_page("stamps.html", "stamps", got=got, again=request.args.get("again") == "1",
                         bad=request.args.get("bad") == "1",
                         zone_names={z["id"]: z["name"] for z in event.data["zones"]})


@qr_bp.get("/s/<token>")
def stamp(token):
    """스탬프 지점에 붙은 QR 의 주소. 스탬프를 찍고 스탬프 화면으로 보낸다."""
    vid = _visitor_id()
    spot = event.stamp_by_token(token)
    if not spot:
        return redirect(url_for(".stamps", bad=1))
    is_new = store.add_stamp(vid, spot["id"])
    _progress(vid)  # 이번에 다 모았으면 쿠폰 발급
    return redirect(url_for(".stamps", got=spot["id"], again=None if is_new else 1))


@qr_bp.get("/chat")
def chat():
    return _visitor_page("chat.html", "chat", chat_connected=bool(config.CHAT_WEBHOOK_URL), max_chat=MAX_CHAT)


@qr_bp.post("/api/chat")
def chat_api():
    vid = _visitor_id()
    message = ((request.get_json(silent=True) or {}).get("message") or "").strip()
    if not message:
        return jsonify(error="궁금한 내용을 입력해 주세요."), 400
    if len(message) > MAX_CHAT:
        return jsonify(error=f"질문은 {MAX_CHAT}자까지 입력할 수 있어요."), 400
    store.log_view(vid, "chat_message")

    done, _, _ = _progress(vid)
    headers = {config.CHAT_SECRET_HEADER: config.CHAT_WEBHOOK_SECRET} if config.CHAT_WEBHOOK_SECRET else None
    try:
        answer = chat_client.reply(
            message, vid,
            webhook_url=config.CHAT_WEBHOOK_URL,
            timeout=config.CHAT_TIMEOUT,
            headers=headers,
            event_id=event.data["id"],
            context=event.context(),
            network=_network_summary(),
            stamps=[s["name"] for s in event.data["stamps"] if s["id"] in done],
        )
    except chat_client.ChatError as exc:
        return jsonify(error=str(exc)), 502
    return jsonify(reply=answer.text, source=answer.source)


@qr_bp.get("/api/network")
def network_api():
    return jsonify(network.snapshot(event.data))


@qr_bp.get("/api/me")
def me_api():
    """스탬프 화면이 쿠폰 지급 여부를 확인할 때 쓴다 (부스에서 지급하면 화면이 '지급 완료'로 바뀐다)."""
    done, required, coupon = _progress(_visitor_id())
    return jsonify(
        stamps=sorted(done),
        required=required,
        coupon={"code": coupon["code"], "redeemed": bool(coupon["redeemed_at"])} if coupon else None,
    )


def _network_summary():
    net = network.snapshot(event.data)
    return {
        "updated_at": net["updated_at"],
        "best": net["best"]["name"],
        "zones": [{k: z[k] for k in ("name", "label", "users", "speed_mbps")} for z in net["zones"]],
        "booth_queue": net["booth"]["queue"],
        "simulated": True,
    }


# ───────────────────────────── 부스 담당자 ─────────────────────────────

_login_fail = {"count": 0, "until": 0.0}
_login_lock = threading.Lock()


def _secret():
    path = config.DATA_DIR / ".secret"
    try:
        return path.read_bytes()
    except OSError:
        path.parent.mkdir(parents=True, exist_ok=True)
        key = secrets.token_bytes(32)
        path.write_bytes(key)
        return key


def _staff_token():
    # PIN 을 바꾸면 기존 로그인은 자동으로 풀린다
    return hmac.new(_secret(), config.STAFF_PIN.encode(), hashlib.sha256).hexdigest()


def _is_staff():
    return hmac.compare_digest(request.cookies.get(STAFF_COOKIE, ""), _staff_token())


def _staff_page(template, **ctx):
    return render_template(f"tonghagil_qr/{template}", active_agent_id=AGENT_ID, ev=event.data, **ctx)


@qr_bp.get("/staff/")
def staff():
    if not _is_staff():
        return _staff_page("staff_login.html", error=request.args.get("error"),
                           pin_is_default=config.STAFF_PIN_IS_DEFAULT)
    stats = store.stats([s["id"] for s in event.data["stamps"]])
    base = _public_base()
    return _staff_page(
        "staff.html",
        stats=stats,
        rate=lambda part, whole: f"{part / whole * 100:.0f}%" if whole else "-",
        recent=store.recent_redemptions(),
        result=request.args.get("result"),
        code=normalize_code(request.args.get("code")),
        targets=_qr_targets(base),
        public_base=base,
        visitor_url=base + url_for(".home"),
        base_is_local=_is_local(base),
        chat_connected=bool(config.CHAT_WEBHOOK_URL),
        staff_chat_connected=bool(config.STAFF_CHAT_WEBHOOK_URL),
        max_chat=MAX_CHAT,
        kakao_connected=bool(config.KAKAO_MAP_KEY),
        pin_is_default=config.STAFF_PIN_IS_DEFAULT,
        required=event.required_stamps,
    )


@qr_bp.post("/staff/login")
def staff_login():
    with _login_lock:
        if time.monotonic() < _login_fail["until"]:
            return redirect(url_for(".staff", error="wait"))
        if not hmac.compare_digest(request.form.get("pin", "").strip().encode(), config.STAFF_PIN.encode()):
            _login_fail["count"] += 1
            if _login_fail["count"] >= 5:  # 5번 틀리면 30초 동안 막는다 (PIN 무작위 대입 방지)
                _login_fail.update(count=0, until=time.monotonic() + 30)
            return redirect(url_for(".staff", error="pin"))
        _login_fail["count"] = 0
    resp = redirect(url_for(".staff"))
    resp.set_cookie(STAFF_COOKIE, _staff_token(), max_age=STAFF_HOURS * 3600,
                    httponly=True, samesite="Lax", path=url_for(".staff"))
    return resp


@qr_bp.post("/staff/logout")
def staff_logout():
    resp = redirect(url_for(".staff"))
    resp.delete_cookie(STAFF_COOKIE, path=url_for(".staff"))
    return resp


@qr_bp.post("/staff/redeem")
def staff_redeem():
    if not _is_staff():
        abort(403)
    code = request.form.get("code", "")
    status, _ = store.redeem(code)
    return redirect(url_for(".staff", result=status, code=normalize_code(code)) + "#redeem")


@qr_bp.post("/staff/reset")
def staff_reset():
    if not _is_staff():
        abort(403)
    store.reset()
    return redirect(url_for(".staff", result="reset"))


@qr_bp.post("/staff/api/chat")
def staff_chat_api():
    """담당자 화면의 관리자 에이전트. 방문객용과 다른 n8n 워크플로(QR_STAFF_CHAT_WEBHOOK_URL)로 간다.

    n8n 은 이 PC 의 DB 를 직접 못 읽으므로, 질문과 함께 지금 현황 숫자(stats)를 보낸다.
    n8n 에서 질문 종류(방문객 수 · 스탬프 진행 · 사은품)로 나눈 뒤 가지마다 필요한 숫자만 골라 쓰면 된다.
    """
    if not _is_staff():
        return jsonify(error="잠금이 풀렸어요. 화면을 새로고침하고 PIN을 다시 입력해 주세요."), 403
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify(error="궁금한 내용을 입력해 주세요."), 400
    if len(message) > MAX_CHAT:
        return jsonify(error=f"질문은 {MAX_CHAT}자까지 입력할 수 있어요."), 400

    # 담당자는 모두 같은 PIN 쿠키를 쓰므로, 대화 기억은 브라우저 탭이 만든 ID 로 나눈다
    session = str(data.get("session") or "")
    session_id = "staff-" + (session if _VISITOR_ID.match(session) else "shared")
    secret = config.STAFF_CHAT_WEBHOOK_SECRET
    try:
        answer = chat_client.reply(
            message, session_id,
            webhook_url=config.STAFF_CHAT_WEBHOOK_URL,
            timeout=config.CHAT_TIMEOUT,
            headers={config.CHAT_SECRET_HEADER: secret} if secret else None,
            event_id=event.data["id"],
            context=event.context(),
            network=_network_summary(),
            extra={"role": "staff", "stats": _staff_stats()},
        )
    except chat_client.ChatError as exc:
        return jsonify(error=str(exc)), 502
    return jsonify(reply=answer.text, source=answer.source)


def _staff_stats():
    """관리자 에이전트에 보내는 현황 숫자. 담당자 화면에 보이는 숫자와 같은 DB 에서 센다."""
    spots = event.data["stamps"]
    ids = [s["id"] for s in spots]
    stats = store.stats(ids)
    required = event.required_stamps
    by_count = store.stamp_counts(ids)
    return {
        "visitors": stats["visitors"],            # QR 로 들어온 방문객 수
        "from_poster": stats["from_poster"],      # 그중 포스터 QR 로 들어온 수
        "map_viewers": stats["map_viewers"],      # 지도·부스 안내를 본 방문객 수
        "chat_messages": stats["chat_messages"],  # 방문객이 채팅 에이전트에 보낸 질문 수
        "stamp": {
            "required": required,
            "joiners": stats["stamp_joiners"],    # 1개 이상 찍은 방문객
            "in_progress": sum(n for count, n in by_count.items() if count < required),   # 진행 중 (아직 다 못 모음)
            "completed": sum(n for count, n in by_count.items() if count >= required),    # 다 모음
            "by_count": {str(count): n for count, n in by_count.items()},                 # {"찍은 개수": 방문객 수}
            "per_spot": [{"name": s["name"], "count": stats["per_stamp"][s["id"]]} for s in spots],
            # 곧 다 모을 사람부터 최대 10명. 방문객은 이름이 없어서 쿠키 ID 를 줄인 별칭으로 부른다 (ID 자체는 안 보낸다)
            "closest": [{
                "visitor": "방문객 " + hashlib.sha256(v["visitor_id"].encode()).hexdigest()[:4].upper(),
                "count": len(v["stamp_ids"]),
                "left": required - len(v["stamp_ids"]),
                "remaining_spots": [s["name"] for s in spots if s["id"] not in v["stamp_ids"]],
                "last_stamp_at": v["last_at"][11:16],
            } for v in store.in_progress(ids, required)],
        },
        "coupon": {
            "issued": stats["coupons"],                         # 발급된 쿠폰 (= 사은품 받을 자격이 생긴 사람)
            "redeemed": stats["redeemed"],                      # 부스에서 사은품을 지급한 수
            "waiting": stats["coupons"] - stats["redeemed"],    # 발급됐지만 아직 안 받아 간 수
        },
    }


@qr_bp.get("/staff/qr/<kind>.svg")
def staff_qr(kind):
    """포스터·스탬프 지점에 붙일 QR 이미지. 스탬프 토큰이 들어 있어 담당자만 볼 수 있다."""
    if not _is_staff():
        abort(403)
    target = next((t for t in _qr_targets(_public_base()) if t["kind"] == kind), None)
    if not target:
        abort(404)
    try:
        svg = qr_image.svg(target["url"])
    except qr_image.QrUnavailable as exc:
        return Response(str(exc), status=503, mimetype="text/plain; charset=utf-8")
    return Response(svg, mimetype="image/svg+xml", headers={"Cache-Control": "no-store"})


@qr_bp.get("/staff/print")
def staff_print():
    if not _is_staff():
        return redirect(url_for(".staff"))
    base = _public_base()
    return render_template("tonghagil_qr/staff_print.html", ev=event.data, targets=_qr_targets(base),
                           public_base=base, base_is_local=_is_local(base))


def _public_base():
    if config.PUBLIC_BASE_URL:
        return config.PUBLIC_BASE_URL
    base = request.host_url.rstrip("/")
    # ngrok 같은 중계 서버 뒤에서는 Flask 가 접속 방식을 http 로 안다. 중계 서버가 알려 준 원래 방식(https)을 쓴다.
    proto = request.headers.get("X-Forwarded-Proto", "").split(",")[0].strip()
    if proto in ("http", "https") and not _is_local(base):
        base = f"{proto}://{base.split('://', 1)[1]}"
    return base


def _is_local(base):
    host = urlsplit(base).hostname or ""
    return host in ("localhost", "127.0.0.1", "0.0.0.0") or host.endswith(".local")


def _qr_targets(base):
    """QR 로 인쇄할 주소 목록: 포스터용 입장 QR 1개 + 스탬프 지점 QR."""
    targets = [{
        "kind": "entry",
        "label": "입장 QR",
        "sub": "포스터·안내판에 붙여요. 행사 안내 홈으로 연결돼요.",
        "url": base + url_for("tonghagil_qr.home", src="poster"),
    }]
    for no, spot in enumerate(event.data["stamps"], start=1):
        targets.append({
            "kind": spot["id"],
            "label": f"스탬프 {no}. {spot['name']}",
            "sub": spot["hint"],
            "url": base + url_for("tonghagil_qr.stamp", token=spot["token"]),
        })
    return targets
