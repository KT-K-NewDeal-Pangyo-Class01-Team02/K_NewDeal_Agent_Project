"""통하길 QR Blueprint: 방문객이 QR 로 들어와 행사 안내·KT 부스 위치·구역별 통신 상태·스탬프 이벤트를 이용한다.

Command Center(command_center/app.py)에 Blueprint 로 등록되어 /qr/ 아래에서 허브와 같은 프로세스로 돈다.

방문객 화면 (휴대폰, 로그인 없음 · 쿠키로 구분)
    /qr/            행사 안내 홈      (포스터 QR 은 /qr/?src=poster)
    /qr/map         지도 · KT 부스 위치 · 구역별 통신 상태(모의)
    /qr/stamps      스탬프 5곳 · 다 모으면 쿠폰
    /qr/s/<token>   스탬프 지점 QR 이 가리키는 주소 → 스탬프 찍고 /qr/stamps 로
    /qr/chat        안내 챗봇 (지금은 고정 답변, 나중에 n8n)
부스 담당자 화면 (허브 사이드바 · PIN)
    /qr/staff/      현황 · 쿠폰 지급 · QR 인쇄 · 시연 초기화

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
    net = network.snapshot(event.data)
    return _visitor_page("map.html", "map", net=net, net_by_id={z["id"]: z for z in net["zones"]})


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
        base_is_local=_is_local(base),
        chat_connected=bool(config.CHAT_WEBHOOK_URL),
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
    return config.PUBLIC_BASE_URL or request.host_url.rstrip("/")


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
