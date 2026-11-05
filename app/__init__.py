"""Problem tree builder: turns a completed hazard workbook into a problem tree and a Word document."""
import os
import secrets

from flask import Flask, abort, request, session

from . import storage


def current_user():
    """The name people type on the Start or Upload page, kept in their session. There are no sign-ins.
    If Azure sign-in is ever switched on, its header takes priority."""
    return request.headers.get("X-MS-CLIENT-PRINCIPAL-NAME") or session.get("name", "")


def clean_name(value):
    return " ".join(str(value or "").split())[:60]


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
        DATABASE_PATH=os.environ.get("DATABASE_PATH", os.path.join(app.instance_path, "app.db")),
        MAX_CONTENT_LENGTH=10 * 1024 * 1024,      # 10 MB is far more than a hazard workbook needs
        CLASSIFICATION=os.environ.get("CLASSIFICATION", "Internal"),
        # Shown in the footer of every page
        REPO_URL=os.environ.get("REPO_URL", "https://github.com/jackwharrison/ifrc-scenario-planning"),
        SUPPORT_EMAIL=os.environ.get("SUPPORT_EMAIL", "jack.harrison@ifrc.org"),
        SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "true").lower() == "true",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if test_config:
        app.config.update(test_config)
    if not os.environ.get("SECRET_KEY") and not app.config.get("TESTING"):
        app.logger.warning("SECRET_KEY is not set. Sessions will reset on every restart. Set it in the App Service settings.")

    storage.init_db(app)

    @app.before_request
    def csrf_protect():
        if request.method == "POST":
            token = session.get("csrf")
            sent = request.form.get("csrf") or request.headers.get("X-CSRF-Token")
            if not token or sent != token:
                abort(400, "The form expired. Go back, reload the page and try again.")
            if "your_name" in request.form:
                session["name"] = clean_name(request.form["your_name"])

    @app.context_processor
    def inject():
        if "csrf" not in session:
            session["csrf"] = secrets.token_hex(16)
        return {"csrf_token": session["csrf"], "user": current_user(),
                "repo_url": app.config["REPO_URL"], "support_email": app.config["SUPPORT_EMAIL"]}

    @app.get("/health")
    def health():
        return {"status": "ok"}

    from .routes import bp
    app.register_blueprint(bp)
    return app
