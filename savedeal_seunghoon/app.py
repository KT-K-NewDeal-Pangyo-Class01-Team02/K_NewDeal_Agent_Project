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
    app = create_app()
    app.run(host="0.0.0.0", port=app.config["PORT"], debug=app.config["DEBUG"])
