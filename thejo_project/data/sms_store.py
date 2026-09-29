"""문자 발송 기록 저장소.

DB 가 없어서 JSON 파일 한 개에 쌓는다. 통하길 스튜디오의 poster_store 와 같은 방식이다.
페이지를 새로고침해도 발송 완료 상태가 남아야 하므로 메모리가 아니라 파일에 쓴다.
DB 가 붙으면 이 파일의 load/append 본문만 바꾸면 된다.
"""
import json
import os
import tempfile
import threading
from pathlib import Path

SMS_LOG_FILE = Path(__file__).resolve().parent / "sms_log.json"

# Flask 개발 서버는 요청을 여러 스레드로 처리한다. 같은 파일에 동시에 쓰지 않게 막는다.
_lock = threading.Lock()


def load_all():
    """발송 기록 전체. 파일이 없거나 깨졌으면 빈 목록."""
    if not SMS_LOG_FILE.exists():
        return []
    try:
        with SMS_LOG_FILE.open(encoding="utf-8") as f:
            records = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
    return records if isinstance(records, list) else []


def append(record):
    """기록 한 건 추가. 저장된 record 를 그대로 돌려준다."""
    with _lock:
        records = load_all()
        records.append(record)
        _write(records)
    return record


def latest_by_transaction():
    """거래별 **마지막** 발송 기록. {transaction_id: record}

    화면에서 '문자 안내 완료' 배지와 발송 시각을 보여 줄 때 쓴다.
    """
    latest = {}
    for record in load_all():
        if record.get("sms_status") == "발송 완료":
            latest[record.get("transaction_id")] = record
    return latest


def next_sms_id():
    """SMS-0001 형식의 다음 번호."""
    return f"SMS-{len(load_all()) + 1:04d}"


def clear():
    """테스트용: 기록을 모두 지운다."""
    with _lock:
        _write([])


def _write(records):
    """같은 폴더에 임시 파일로 쓰고 바꿔치운다. 쓰다가 죽어도 기존 파일이 깨지지 않는다."""
    SMS_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(SMS_LOG_FILE.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, SMS_LOG_FILE)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
