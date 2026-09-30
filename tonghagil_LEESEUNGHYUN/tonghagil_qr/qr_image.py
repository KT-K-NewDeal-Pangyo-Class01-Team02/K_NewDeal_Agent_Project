"""QR 코드 이미지(SVG) 만들기. segno(순수 파이썬, 의존성 없음)를 쓴다.

segno 가 없는 환경에서도 허브와 통하길 QR 화면은 뜨고, QR 이미지 주소만 안내 메시지(503)를 돌려준다.
"""
from io import BytesIO


class QrUnavailable(Exception):
    pass


def svg(data, scale=8):
    try:
        import segno
    except ModuleNotFoundError as exc:
        raise QrUnavailable("QR 이미지를 만들려면 segno 가 필요해요: pip install segno") from exc
    buf = BytesIO()
    segno.make(data, error="m").save(buf, kind="svg", scale=scale, border=2, dark="#151a23", xmldecl=False)
    return buf.getvalue()
