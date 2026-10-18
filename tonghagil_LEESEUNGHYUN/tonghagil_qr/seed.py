"""시연용 더미 방문객 (data/seed.json).

현장에 이미 사람이 많이 다녀간 것처럼 보이게, 정해진 수의 가짜 방문객과 스탬프·쿠폰 기록을 DB 에 넣는다.
- id 가 'seed-' 로 시작한다. 24시간 자동 삭제와 '시연 기록 초기화'에서 빠진다(초기화 뒤에는 다시 넣는다).
- 시각은 '지금' 기준으로 만들고 10분마다 다시 만든다. 서버를 오래 켜 둬도 도착 예측이 늘 '진행 중'으로 보인다.
  무작위 값은 random_seed 로 고정해서, 다시 만들어도 누가 어느 스탬프를 찍었는지는 같다.
- 실제 QR 로 들어온 방문객 기록과 구글 시트의 사은품 수량은 건드리지 않는다.
"""
import json
import random
from datetime import datetime, timedelta

from .store import SEED_PREFIX, _CODE_ALPHABET


def load(path):
    """seed.json 내용. 파일이 없거나 enabled 가 false 면 None."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if data.get("enabled", True) else None


def _iso(dt):
    return dt.isoformat(timespec="seconds")


def build(cfg, stamp_ids, required, gifts, now=None):
    """더미 방문객 목록 → store.replace_seed 에 넘길 값.

    [{id, source, created_at, stamps: [(stamp_id, 시각)], views: [(page, 시각)], coupon: {...} 또는 None}]
    """
    rng = random.Random(cfg.get("random_seed", 2026))
    now = now or datetime.now()
    gift_ids = {g["name"]: g.get("id", "") for g in gifts}
    people = []
    n = 0
    for group in cfg.get("groups", []):
        k = max(0, min(int(group.get("stamps", 0)), len(stamp_ids)))
        done = k >= required
        for i in range(int(group.get("count", 0))):
            n += 1
            pace = rng.uniform(4, 9)  # 스탬프 하나에 걸린 시간(분)
            # 진행 중인 사람은 마지막 인증이 최근(1~25분 전), 완주한 사람은 조금 전에 끝낸 것으로
            idle = rng.uniform(35, 60) if done else rng.uniform(1, 25)
            last = now - timedelta(minutes=idle)
            first = last - timedelta(minutes=pace * max(k - 1, 0))
            spots = rng.sample(stamp_ids, k)  # 지점별 인증 수가 한쪽으로 몰리지 않게 무작위로 고른다
            created = first - timedelta(minutes=rng.uniform(1, 5))
            views = [("home", _iso(created))]
            if rng.random() < cfg.get("map_ratio", 0.4):
                views.append(("map", _iso(created + timedelta(minutes=1))))
            coupon = None
            if done:
                # 그룹에 정한 코드는 첫 사람에게만. 나머지는 무작위(고정된 random_seed 라 매번 같은 코드)
                code = (group.get("code") if i == 0 else None) or "".join(rng.choice(_CODE_ALPHABET) for _ in range(6))
                gift = group.get("gift")
                coupon = {
                    "code": code,
                    "issued_at": _iso(last),
                    "gift_id": str(gift_ids.get(gift, "seed")) if gift else None,
                    "gift_name": gift,
                    "drawn_at": _iso(last + timedelta(minutes=1)) if gift else None,
                    "redeemed_at": _iso(last + timedelta(minutes=3)) if gift and group.get("redeemed") else None,
                }
            people.append({
                "id": f"{SEED_PREFIX}visitor-{n:04d}",
                "source": "poster" if rng.random() < cfg.get("poster_ratio", 0.6) else "",
                "created_at": _iso(created),
                "stamps": [(sid, _iso(first + timedelta(minutes=pace * i))) for i, sid in enumerate(spots)],
                "views": views,
                "coupon": coupon,
            })
    return people
