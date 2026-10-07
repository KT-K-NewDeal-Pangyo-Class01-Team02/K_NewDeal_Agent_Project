"""더 줘 테스트. 저장소 루트에서 python -m unittest thejo_project.tests.test_thejo -v

테스트는 실제 문자 발송 기록(thejo_project/data/sms_log.json)을 건드리지 않는다.
테스트 모듈이 import 되기 전에 이 패키지가 먼저 import 되므로, 여기서 기록 파일을 임시 폴더로 돌린다.
(이게 없으면 sms_store.clear() 가 실제 발송 기록과 '문자 안내 완료' 배지를 지워 버린다.)
"""
import atexit
import shutil
import tempfile
from pathlib import Path

from thejo_project.data import sms_store

_tmp = tempfile.mkdtemp(prefix="thejo_test_")
sms_store.SMS_LOG_FILE = Path(_tmp) / "sms_log.json"
atexit.register(shutil.rmtree, _tmp, ignore_errors=True)
