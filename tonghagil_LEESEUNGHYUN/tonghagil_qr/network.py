"""구역별 통신 상태 (모의 데이터).

실제 기지국 데이터 대신, event.json 의 구역별 수용 인원(capacity)과 기본 혼잡도(base)에
시간에 따라 천천히 오르내리는 물결 + 30초마다 바뀌는 작은 흔들림을 더해 '살아 있는' 값처럼 보이게 만든다.
같은 30초 안에서는 누가 봐도 같은 값이 나온다(시드 고정).
나중에 실제 데이터가 생기면 snapshot() 만 바꾸면 된다.
"""
import math
import random
import time
from datetime import datetime

REFRESH_SECONDS = 30
STATUS_LEVELS = [(0.60, "good", "원활"), (0.85, "busy", "보통"), (1.01, "jam", "혼잡")]


def snapshot(event_data, now=None):
    now = time.time() if now is None else now
    tick = int(now // REFRESH_SECONDS)
    zones = [_zone(z, now, tick) for z in event_data["zones"]]
    best = min(zones, key=lambda z: z["load"])

    booth_zone = next(z for z in zones if z["id"] == event_data["booth"]["zone"])
    rnd = random.Random(f"booth:{tick}")
    queue = max(0, round(booth_zone["load"] * 10 + rnd.uniform(-3, 3)))
    return {
        "updated_at": datetime.fromtimestamp(tick * REFRESH_SECONDS).strftime("%H:%M:%S"),
        "refresh_seconds": REFRESH_SECONDS,
        "zones": zones,
        "best": {"id": best["id"], "name": best["name"]},
        "booth": {"queue": queue, "wait_min": math.ceil(queue * 1.5)},
        "simulated": True,
    }


def _zone(zone, now, tick):
    offset = sum(map(ord, zone["id"]))  # 구역마다 물결이 다른 시점에 오르내리게
    wave = math.sin(now / 900 + offset)
    rnd = random.Random(f"{zone['id']}:{tick}")
    load = min(0.98, max(0.08, zone["base"] + 0.14 * wave + rnd.uniform(-0.05, 0.05)))
    level, label = next((lv, lb) for limit, lv, lb in STATUS_LEVELS if load < limit)
    return {
        "id": zone["id"],
        "name": zone["name"],
        "load": round(load, 3),
        "users": round(zone["capacity"] * load),
        "speed_mbps": max(6, round(480 * (1 - load) ** 1.4)),
        "level": level,
        "label": label,
    }
