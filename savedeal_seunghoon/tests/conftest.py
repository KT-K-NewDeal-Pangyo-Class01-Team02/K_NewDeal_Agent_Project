import shutil

import pytest

from app import create_app
from config import Config
from db.connection import ensure_database


class TestConfig(Config):
    DEBUG = True
    TESTING = True
    # 개발자 .env 에 실제 주소·키가 있어도 테스트에서는 외부로 나가지 않는다
    N8N_WEBHOOK_URL = ""
    N8N_WEBHOOK_SECRET = ""
    N8N_EVENTS_URL = ""
    OPENAI_API_KEY = ""


@pytest.fixture(autouse=True)
def block_real_network(monkeypatch):
    """테스트 중 실제 HTTP 요청(n8n, OpenAI)이 나가면 실패시킨다. 필요한 테스트는 직접 가짜로 바꿔 끼운다."""
    import requests

    def refuse(*args, **kwargs):
        raise AssertionError("테스트에서 실제 네트워크 요청을 보내려고 했습니다.")

    monkeypatch.setattr(requests, "post", refuse)


@pytest.fixture(scope="session")
def seeded_db_template(tmp_path_factory):
    path = tmp_path_factory.mktemp("db") / "template.db"
    ensure_database(path)
    return path


@pytest.fixture
def db_path(tmp_path, seeded_db_template):
    """테스트마다 mock 데이터가 채워진 새 SQLite DB 사본을 쓴다 (시드는 한 번만 실행)."""
    path = tmp_path / "savedeal_test.db"
    shutil.copy(seeded_db_template, path)
    return path


@pytest.fixture
def app(db_path):
    class _Config(TestConfig):
        DB_PATH = db_path

    return create_app(_Config)


@pytest.fixture
def client(app):
    return app.test_client()
