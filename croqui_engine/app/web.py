from __future__ import annotations

from flask import Flask, redirect, url_for
from flask_login import LoginManager

from croqui_engine.core.config import ensure_data_dirs, settings
from croqui_engine.storage.database import init_db
from croqui_engine.storage.repositories import UserRepository

login_manager = LoginManager()
login_manager.login_view = "auth.login"


def create_app() -> Flask:
    ensure_data_dirs()
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["SECRET_KEY"] = settings.secret_key
    app.config["MAX_CONTENT_LENGTH"] = settings.max_upload_mb * 1024 * 1024

    init_db()
    login_manager.init_app(app)

    from croqui_engine.app.routes.api_routes import bp as api_bp
    from croqui_engine.app.routes.auth_routes import bp as auth_bp
    from croqui_engine.app.routes.job_routes import bp as job_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(job_bp)
    app.register_blueprint(api_bp)

    @app.route("/")
    def index():
        return redirect(url_for("jobs.dashboard"))

    return app


@login_manager.user_loader
def load_user(user_id: str):
    return UserRepository().get(user_id)


app = create_app()
