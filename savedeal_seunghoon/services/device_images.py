"""단말(모델·색상)에 맞는 썸네일 이미지를 찾는다. 이미지 파일과 출처는 static/img/devices/CREDITS.md 참고.

색상별 사진이 있으면 그 사진을, 없으면 모델 대표 사진을 쓴다. 대표 사진은 실제 색상과 다를 수 있어서
is_representative 로 알려 준다. 둘 다 없으면 None (화면은 기본 아이콘을 보여 준다).
"""

IMAGE_DIR = "img/devices"

# (모델, 색상) → 파일
COLOR_IMAGES = {
    ("Galaxy Z Fold8", "Silver"): "galaxy-z-fold8-silver.png",
    ("Galaxy Z Fold8", "Lavender"): "galaxy-z-fold8-lavender.png",
    ("Galaxy Z Fold8", "Black"): "galaxy-z-fold8-black.png",
    ("iPhone 18 Pro", "Silver"): "iphone-18-pro-silver.png",
    ("iPhone 18 Pro", "Light Blue"): "iphone-18-pro-light-blue.png",
    ("iPhone 18 Pro", "Burgundy"): "iphone-18-pro-burgundy.png",
    ("iPhone 16", "Blue"): "iphone-16-blue.png",
    ("iPhone 16 Pro", "Desert Titanium"): "iphone-16-pro-desert-titanium.png",
    ("Galaxy S25 Ultra", "Titanium Gray"): "galaxy-s25-ultra-titanium-gray.png",
}

# 모델 → 대표 파일 (색상별 사진이 없을 때)
MODEL_IMAGES = {
    "Galaxy Z Fold8": "galaxy-z-fold8-silver.png",
    "iPhone 18 Pro": "iphone-18-pro-silver.png",
    "GalaxyZ Fold6": "galaxy-z-fold6.png",
    "iPhone 16": "iphone-16-blue.png",
    "iPhone 16 Pro": "iphone-16-pro-desert-titanium.png",
    "Galaxy S25 Ultra": "galaxy-s25-ultra-titanium-gray.png",
}


def image_for(device: dict) -> dict | None:
    """{"path": "img/devices/파일", "is_representative": bool} 또는 None."""
    exact = COLOR_IMAGES.get((device["model"], device["color"]))
    if exact:
        return {"path": f"{IMAGE_DIR}/{exact}", "is_representative": False}
    fallback = MODEL_IMAGES.get(device["model"])
    if fallback:
        return {"path": f"{IMAGE_DIR}/{fallback}", "is_representative": True}
    return None
