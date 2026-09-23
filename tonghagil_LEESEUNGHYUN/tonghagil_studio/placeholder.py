"""샘플·데모용 포스터 SVG.

n8n을 연결하기 전에도 갤러리가 비어 보이지 않도록 제목·테마로 간단한 포스터를 그린다.
실제 서비스에서는 n8n이 만든 드라이브 이미지가 이 자리를 대신한다.
"""
import math
import random
from html import escape

W, H = 600, 800
FONT = "'Pretendard','Malgun Gothic','Apple SD Gothic Neo',sans-serif"

THEMES = {
    "fireworks": {"bg": ("#0b1235", "#3f1c78"), "text": "#ffffff", "palette": ["#ffd66b", "#ff6fae", "#7ee8ff", "#ffffff"], "deco": "sparks"},
    "spring": {"bg": ("#ffd3e2", "#fff7ec"), "text": "#6d1f42", "palette": ["#f58db0", "#ffb8cf", "#ffffff", "#9ed17b"], "deco": "petals"},
    "night-market": {"bg": ("#1d1027", "#8f3f16"), "text": "#fff2dc", "palette": ["#ffb347", "#ff7b54", "#ffe08a"], "deco": "lanterns"},
    "family": {"bg": ("#86c8f3", "#f3fbff"), "text": "#173d63", "palette": ["#ff8a5b", "#ffd166", "#7bd389", "#b28dff", "#ff6f91"], "deco": "balloons"},
    "lantern": {"bg": ("#0c1938", "#d9793a"), "text": "#ffffff", "palette": ["#ffcf7a", "#ffae57", "#fff1c1"], "deco": "lanterns"},
    "summer": {"bg": ("#22b1d6", "#ffe7a3"), "text": "#ffffff", "palette": ["#ff7a45", "#ffffff"], "deco": "sun"},
    "modern": {"bg": ("#1c1c1e", "#050505"), "text": "#ffffff", "palette": ["#ffffff", "#e3313f"], "deco": "lines"},
    "hip": {"bg": ("#ff3d8b", "#4d1fff"), "text": "#ffffff", "palette": ["#d7ff3a", "#1ee3cf", "#ffffff", "#ff9f1c"], "deco": "blobs"},
}

# 스튜디오의 '참고 스타일' → 데모 포스터 테마
STYLE_THEMES = {"vivid": "fireworks", "warm": "night-market", "modern": "modern", "hip": "hip"}


def theme_for_style(style_id):
    return STYLE_THEMES.get(style_id, "fireworks")


def render(theme, title, sub="", date=""):
    t = THEMES.get(theme, THEMES["fireworks"])
    rnd = random.Random(f"{theme}:{title}")
    lines = _wrap(title or "행사 포스터", 7)
    size = 78 if max(len(line) for line in lines) <= 5 else 62
    line_h = size * 1.18
    top = 400 - line_h * (len(lines) - 1) / 2

    title_svg = "".join(
        f'<text x="{W / 2}" y="{top + i * line_h:.0f}" text-anchor="middle" font-size="{size}" '
        f'font-weight="800" fill="{t["text"]}" filter="url(#shadow)">{escape(line)}</text>'
        for i, line in enumerate(lines)
    )
    sub_y = top + line_h * (len(lines) - 1) + 70
    sub_svg = (
        f'<text x="{W / 2}" y="{sub_y:.0f}" text-anchor="middle" font-size="26" font-weight="600" '
        f'fill="{t["text"]}" opacity=".92" filter="url(#shadow)">{escape(sub)}</text>' if sub else ""
    )
    date_svg = (
        f'<text x="{W / 2}" y="730" text-anchor="middle" font-size="22" font-weight="500" '
        f'fill="{t["text"]}" opacity=".85">{escape(date)}</text>' if date else ""
    )
    deco = "".join(DECORATIONS[t["deco"]](rnd, t["palette"]))

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{FONT}">'
        '<defs>'
        f'<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{t["bg"][0]}"/>'
        f'<stop offset="1" stop-color="{t["bg"][1]}"/></linearGradient>'
        '<filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">'
        '<feDropShadow dx="0" dy="3" stdDeviation="5" flood-color="#000" flood-opacity=".3"/></filter>'
        '<filter id="glow"><feGaussianBlur stdDeviation="8"/></filter>'
        '</defs>'
        f'<rect width="{W}" height="{H}" fill="url(#bg)"/>'
        f'{deco}{title_svg}{sub_svg}{date_svg}'
        '</svg>'
    )


def _wrap(text, width, max_lines=4):
    lines, current = [], ""
    for word in text.split():
        while len(word) > width:
            if current:
                lines.append(current)
                current = ""
            lines.append(word[:width])
            word = word[width:]
        if current and len(current) + 1 + len(word) > width:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        lines.append(current)
    return lines[:max_lines] or [text[:width]]


def _sparks(rnd, palette):
    out = []
    for _ in range(5):
        cx, cy, r = rnd.randint(70, 530), rnd.randint(50, 280), rnd.randint(45, 105)
        color = rnd.choice(palette)
        out.append(f'<circle cx="{cx}" cy="{cy}" r="{r * 0.6:.0f}" fill="{color}" opacity=".18" filter="url(#glow)"/>')
        for i in range(18):
            a = 2 * math.pi * i / 18
            x1, y1 = cx + r * 0.35 * math.cos(a), cy + r * 0.35 * math.sin(a)
            x2, y2 = cx + r * math.cos(a), cy + r * math.sin(a)
            out.append(f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" stroke="{color}" '
                       'stroke-width="2.2" stroke-linecap="round" opacity=".85"/>')
            out.append(f'<circle cx="{x2:.0f}" cy="{y2:.0f}" r="2.6" fill="{color}"/>')
    for _ in range(40):
        out.append(f'<circle cx="{rnd.randint(0, W)}" cy="{rnd.randint(0, H)}" r="{rnd.uniform(0.6, 1.8):.1f}" fill="#fff" opacity=".7"/>')
    return out


def _petals(rnd, palette):
    out = []
    for _ in range(46):
        x, y = rnd.randint(0, W), rnd.choice([rnd.randint(0, 260), rnd.randint(560, H)])
        out.append(f'<ellipse cx="{x}" cy="{y}" rx="{rnd.randint(7, 14)}" ry="{rnd.randint(4, 8)}" '
                   f'fill="{rnd.choice(palette)}" opacity=".85" transform="rotate({rnd.randint(0, 180)} {x} {y})"/>')
    return out


def _lanterns(rnd, palette):
    out = []
    for _ in range(18):
        x, y = rnd.randint(30, 570), rnd.choice([rnd.randint(20, 280), rnd.randint(560, 680)])
        s = rnd.uniform(0.7, 1.4)
        color = rnd.choice(palette)
        out.append(f'<circle cx="{x}" cy="{y}" r="{30 * s:.0f}" fill="{color}" opacity=".25" filter="url(#glow)"/>')
        out.append(f'<rect x="{x - 11 * s:.0f}" y="{y - 15 * s:.0f}" width="{22 * s:.0f}" height="{30 * s:.0f}" '
                   f'rx="{8 * s:.0f}" fill="{color}" opacity=".95"/>')
    return out


def _balloons(rnd, palette):
    out = []
    for _ in range(12):
        x, y, r = rnd.randint(40, 560), rnd.randint(40, 250), rnd.randint(24, 40)
        out.append(f'<path d="M{x} {y + r} q -8 30 4 60" stroke="#ffffff" stroke-width="1.5" fill="none" opacity=".8"/>')
        out.append(f'<ellipse cx="{x}" cy="{y}" rx="{r * 0.86:.0f}" ry="{r}" fill="{rnd.choice(palette)}"/>')
        out.append(f'<ellipse cx="{x - r * 0.3:.0f}" cy="{y - r * 0.35:.0f}" rx="{r * 0.18:.0f}" ry="{r * 0.28:.0f}" fill="#fff" opacity=".45"/>')
    return out


def _sun(rnd, palette):
    out = [
        f'<circle cx="470" cy="150" r="140" fill="{palette[0]}" opacity=".25" filter="url(#glow)"/>',
        f'<circle cx="470" cy="150" r="80" fill="{palette[0]}" opacity=".9"/>',
    ]
    for i in range(3):
        y = 610 + i * 40
        out.append(f'<path d="M0 {y} q 75 -24 150 0 t 150 0 t 150 0 t 150 0 V {H} H 0 Z" fill="#fff" opacity="{0.18 + i * 0.12:.2f}"/>')
    return out


def _lines(rnd, palette):
    out = [f'<circle cx="300" cy="400" r="230" fill="none" stroke="{palette[0]}" stroke-width="1" opacity=".35"/>']
    for i in range(14):
        x = -200 + i * 70
        out.append(f'<line x1="{x}" y1="0" x2="{x + 400}" y2="{H}" stroke="{palette[0]}" stroke-width="1" opacity=".12"/>')
    out.append(f'<rect x="270" y="150" width="60" height="6" fill="{palette[1]}"/>')
    return out


def _blobs(rnd, palette):
    out = []
    for _ in range(7):
        out.append(f'<circle cx="{rnd.randint(0, W)}" cy="{rnd.choice([rnd.randint(0, 260), rnd.randint(560, H)])}" '
                   f'r="{rnd.randint(40, 120)}" fill="{rnd.choice(palette)}" opacity=".75"/>')
    for _ in range(6):
        x, y = rnd.randint(40, 560), rnd.randint(40, 760)
        out.append(f'<path d="M{x} {y - 14} L{x + 4} {y - 4} L{x + 14} {y} L{x + 4} {y + 4} L{x} {y + 14} '
                   f'L{x - 4} {y + 4} L{x - 14} {y} L{x - 4} {y - 4} Z" fill="#fff"/>')
    return out


DECORATIONS = {
    "sparks": _sparks, "petals": _petals, "lanterns": _lanterns, "balloons": _balloons,
    "sun": _sun, "lines": _lines, "blobs": _blobs,
}
