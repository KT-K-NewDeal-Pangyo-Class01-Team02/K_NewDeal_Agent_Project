"""포스터 목록 저장소.

지금은 data/posters.json 에 기록한다. n8n이 구글 드라이브에 올린 포스터는 이미지 파일이 아니라
드라이브 링크만 저장하고, 화면에서는 드라이브의 이미지를 그대로 불러온다.
posters.json 이 아직 없으면 sample_posters.json(더미 데이터)을 보여 준다.

드라이브 폴더가 설정되면 app.py 가 DriveFolderPosterStore(drive_store.py)를 갤러리로 쓰고,
이 저장소는 스튜디오에서 요청한 포스터의 부가 정보(제목·행사 유형·요청 문구) 기록용으로만 쓰인다.
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

    def update_by_file_id(self, file_id, **fields):
        """드라이브 파일 ID로 기록을 찾아 필드를 바꾼다. 스튜디오 밖에서 만든 파일이라 기록이 없으면 그냥 넘어간다."""
        if not self.path.exists():
            return
        with self._lock:
            posters = self._read()
            changed = False
            for poster in posters:
                if poster.get("drive_file_id") == file_id:
                    poster.update(fields)
                    changed = True
            if changed:
                self._write(posters)

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
