from routes.main import main_bp
from routes.pages import pages_bp
from routes.precheck import precheck_bp
from routes.reservations import reservations_bp


def register_routes(app):
    app.register_blueprint(pages_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(precheck_bp)
    app.register_blueprint(reservations_bp)
