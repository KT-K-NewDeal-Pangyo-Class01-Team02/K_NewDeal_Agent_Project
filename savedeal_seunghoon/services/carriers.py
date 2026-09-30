"""통신사 코드와 표시 정보. 이 서비스는 KT 매장 기준이라, 번호이동은 항상 '기존 통신사 → KT'다.
로고 파일과 출처는 static/img/carriers/CREDITS.md 참고."""

HOME_CARRIER = "KT"

CARRIERS = {
    "KT": {"label": "KT", "logo": "img/carriers/kt.png"},
    "SKT": {"label": "SK텔레콤", "logo": "img/carriers/skt.png"},
    "LGU": {"label": "LG U+", "logo": "img/carriers/lguplus.png"},
    "MVNO": {"label": "알뜰폰", "logo": None},
}

# 번호이동 고객이 떠나 오는 통신사 (KT 제외)
PREVIOUS_CARRIER_CODES = ["SKT", "LGU", "MVNO"]


def carrier_info(code: str | None) -> dict | None:
    """{"code", "label", "logo_url"} 또는 None. 로고가 없는 통신사(알뜰폰)는 logo_url이 None."""
    carrier = CARRIERS.get(code) if code else None
    if carrier is None:
        return None
    logo = carrier["logo"]
    return {"code": code, "label": carrier["label"], "logo_url": f"/static/{logo}" if logo else None}


def carrier_change(line_type: str, previous_carrier: str | None) -> dict | None:
    """번호이동이면 {"from": 기존 통신사 | None, "to": KT, "label": "LG U+ → KT"}, 아니면 None."""
    if line_type != "MNP":
        return None
    source = carrier_info(previous_carrier)
    target = carrier_info(HOME_CARRIER)
    source_label = source["label"] if source else "기존 통신사 미입력"
    return {"from": source, "to": target, "label": f"{source_label} → {target['label']}"}
