"""행사 정보(data/event.json) 읽기.

행사명·부스·혜택·구역·스탬프 지점은 모두 이 파일 한 곳에서 온다. 화면, 챗봇(n8n 에 넘기는 context),
포스터 문구가 같은 값을 쓰게 해서 안내가 서로 어긋나지 않게 하려는 것이다.
파일을 고치면 서버를 다시 켜지 않아도 다음 요청부터 반영된다(수정 시각을 보고 다시 읽는다).
"""
import json
import threading
from pathlib import Path


class EventError(Exception):
    """event.json 을 읽을 수 없거나 형식이 틀렸다."""


class Event:
    def __init__(self, path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._mtime = None
        self._data = None

    @property
    def data(self):
        try:
            mtime = self.path.stat().st_mtime
        except OSError as exc:
            raise EventError(f"행사 정보 파일이 없어요: {self.path}") from exc
        with self._lock:
            if self._data is None or mtime != self._mtime:
                self._data = _load(self.path)
                self._mtime = mtime
            return self._data

    def stamp_by_token(self, token):
        return next((s for s in self.data["stamps"] if s["token"] == token), None)

    def stamp(self, stamp_id):
        return next((s for s in self.data["stamps"] if s["id"] == stamp_id), None)

    def zone(self, zone_id):
        return next((z for z in self.data["zones"] if z["id"] == zone_id), None)

    @property
    def required_stamps(self):
        return min(self.data["benefit"].get("required_stamps", len(self.data["stamps"])), len(self.data["stamps"]))

    def context(self):
        """챗봇(n8n)에 넘길 행사 요약. 스탬프 토큰처럼 방문객에게 보이면 안 되는 값은 뺀다."""
        d = self.data
        zones = {z["id"]: z["name"] for z in d["zones"]}
        return {
            "name": d["name"],
            "date": d["date_label"],
            "time": d["time_label"],
            "venue": d["venue"],
            "notices": d.get("notices", []),
            "booth": {k: d["booth"][k] for k in ("name", "location", "hours", "services")} | {"zone": zones.get(d["booth"]["zone"], "")},
            "benefit": d["benefit"],
            "zones": [{"name": z["name"], "desc": z.get("desc", "")} for z in d["zones"]],
            "stamps": [{"name": s["name"], "zone": zones.get(s["zone"], ""), "hint": s["hint"]} for s in d["stamps"]],
        }


def _load(path):
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        raise EventError(f"행사 정보 파일을 읽지 못했어요: {path} ({exc})") from exc
    for key in ("id", "name", "booth", "benefit", "zones", "stamps"):
        if key not in data:
            raise EventError(f"행사 정보 파일에 '{key}' 항목이 없어요: {path}")
    zone_ids = {z["id"] for z in data["zones"]}
    for item in data["stamps"] + [data["booth"]]:
        if item.get("zone") not in zone_ids:
            raise EventError(f"'{item.get('name')}' 의 zone '{item.get('zone')}' 이 zones 에 없어요.")
    tokens = [s["token"] for s in data["stamps"]]
    if len(set(tokens)) != len(tokens):
        raise EventError("스탬프 token 이 겹쳐요. 스탬프마다 다른 값을 넣어 주세요.")
    return data
