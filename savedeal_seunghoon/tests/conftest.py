import shutil

import pytest

from app import create_app
from config import Config
from db.connection import ensure_database


class TestConfig(Config):
    DEBUG = True
    TESTING = True


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
