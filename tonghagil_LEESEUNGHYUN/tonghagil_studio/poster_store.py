"""포스터 목록 저장소.

지금은 data/posters.json 에 기록한다. n8n이 구글 드라이브에 올린 포스터는 이미지 파일이 아니라
드라이브 링크만 저장하고, 화면에서는 드라이브의 이미지를 그대로 불러온다.
posters.json 이 아직 없으면 sample_posters.json(더미 데이터)을 보여 준다.

나중에 '드라이브 폴더에 있는 이미지 전체'를 직접 읽어 오고 싶다면,
list()/add() 를 가진 다른 저장소 클래스(예: DriveFolderPosterStore)를 만들어 app.py 에서 바꿔 끼우면 된다.
"""
import json
import threading
import uuid
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"


class JsonPosterStore:
    def __init__(self, path=DATA_DIR / "posters.json", seed_path=DATA_DIR / "sample_posters.json"):
        self.path = path
        self.seed_path = seed_path
        self._lock = threading.Lock()

    def list(self):
        """최신순 포스터 목록."""
        posters = self._read()
        return sorted(posters, key=lambda p: p.get("created_at", ""), reverse=True)

    def add(self, **fields):
        poster = {
            "id": uuid.uuid4().hex[:12],
            "created_at": datetime.now().isoformat(timespec="seconds"),
            **fields,
        }
        with self._lock:
            posters = self._read()
            posters.append(poster)
            self._write(posters)
        return poster

    def _read(self):
        path = self.path if self.path.exists() else self.seed_path
        with path.open(encoding="utf-8") as f:
            return json.load(f)

    def _write(self, posters):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(posters, f, ensure_ascii=False, indent=2)
        tmp.replace(self.path)
