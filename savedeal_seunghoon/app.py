from flask import Flask

from config import Config
from db.connection import ensure_database
from routes import register_routes
from routes.layout import init_layout


def create_app(config_class: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)
    ensure_database(app.config["DB_PATH"])
    register_routes(app)
    init_layout(app)
    return app


if __name__ == "__main__":
    from services.event_sync import start_background_sync

    app = create_app()
    # 서버로 켤 때만: n8n 에서 외부 이벤트 가져오기 + 정기 점검을 주기적으로 (테스트·스크립트에서는 돌지 않음)
    start_background_sync(app)
    app.run(host="0.0.0.0", port=app.config["PORT"], debug=app.config["DEBUG"])
