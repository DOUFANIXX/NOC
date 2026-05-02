from __future__ import annotations

import secrets
import time
from pathlib import Path

from flask import Flask, g, render_template, request, session
from werkzeug.middleware.proxy_fix import ProxyFix

from app.db import init_app as init_db_app, init_db
from app.routes import admin, audit, auth, dashboard, health, inventory, jobs, monitoring, settings, switches
from app.services import audit_service
from app.services.job_runner import JobManager, SchedulerThread
from app.services.logging_service import configure_logging
from app.services.monitoring_service import MonitoringService
from app.services.shell_service import build_shell_context
from app.services.switch_inventory_service import seed_inventory_from_files
from app.services.user_service import ensure_bootstrap_admin, get_user_by_id
from app.utils.csrf import csrf_input, ensure_csrf_token, validate_csrf
from app.utils.helpers import humanize_timestamp, replace_query_params
from config.settings import build_settings


def _ensure_secret_key(instance_path: Path) -> str:
    secret_path = instance_path / "secret_key.txt"
    if secret_path.exists():
        return secret_path.read_text(encoding="utf-8").strip()
    secret = secrets.token_hex(32)
    instance_path.mkdir(parents=True, exist_ok=True)
    secret_path.write_text(secret, encoding="utf-8")
    return secret


def create_app(test_config: dict | None = None) -> Flask:
    root_path = Path(__file__).resolve().parent.parent
    app = Flask(__name__, instance_relative_config=False)
    app.config.update(build_settings(root_path))
    if test_config:
        app.config.update(test_config)

    if app.config["TRUST_PROXY"]:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

    Path(app.config["INSTANCE_PATH"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["LOG_DIR"]).mkdir(parents=True, exist_ok=True)

    if not app.config["SECRET_KEY"]:
        app.config["SECRET_KEY"] = _ensure_secret_key(Path(app.config["INSTANCE_PATH"]))

    configure_logging(app)
    init_db_app(app)

    with app.app_context():
        init_db()
        seed_inventory_from_files(app)
        ensure_bootstrap_admin(app)

    @app.before_request
    def load_current_user():
        ensure_csrf_token()
        g.request_id = secrets.token_hex(6)
        user_id = session.get("user_id")
        g.user = get_user_by_id(user_id)
        if g.user and request.endpoint not in {"auth.login", "auth.logout", "static", "health.healthcheck"}:
            now = int(time.time())
            last_activity_at = int(session.get("last_activity_at") or 0)
            idle_timeout_seconds = max(60, int(app.config["SESSION_IDLE_TIMEOUT_MINUTES"]) * 60)
            if last_activity_at and now - last_activity_at > idle_timeout_seconds:
                try:
                    audit_service.log_event(
                        "auth.session_expired",
                        "user",
                        str(g.user["id"]),
                        {
                            "outcome": "expired",
                            "summary": f"Session expired after {app.config['SESSION_IDLE_TIMEOUT_MINUTES']} minutes of inactivity.",
                            "username": g.user["username"],
                            "idle_timeout_minutes": app.config["SESSION_IDLE_TIMEOUT_MINUTES"],
                        },
                    )
                except Exception:
                    app.logger.exception("Failed to record session expiry for user_id=%s", g.user["id"])
                session.clear()
                g.user = None
                flash(
                    f"You were signed out after {app.config['SESSION_IDLE_TIMEOUT_MINUTES']} minutes of inactivity.",
                    "warning",
                )
                return redirect(url_for("auth.login", next=request.full_path))
            session["last_activity_at"] = now
        request.environ["current_user_id"] = g.user["id"] if g.user else None
        request.environ["job_manager"] = app.extensions["job_manager"]
        if request.method == "POST" and request.endpoint not in {"health.healthcheck"}:
            validate_csrf()

    @app.context_processor
    def inject_globals():
        current_user = g.get("user")
        return {
            "csrf_input": csrf_input,
            "current_user": current_user,
            "current_theme_mode": (current_user or {}).get("ui_preference", "dark"),
            "humanize_timestamp": humanize_timestamp,
            "query_with": lambda **updates: replace_query_params(request.args, **updates),
            "query_with_param": lambda name, value: replace_query_params(request.args, **{name: value}),
            **build_shell_context(app, current_user, request.endpoint),
        }

    @app.errorhandler(400)
    def bad_request(error):
        return render_template("error.html", title="Bad Request", message=str(error)), 400

    @app.errorhandler(403)
    def forbidden(error):
        message = "You do not have permission to access this area."
        if request.path.startswith("/switches/change"):
            message = "This workflow requires an operator or admin role."
        elif request.path.startswith("/admin/"):
            message = "This area requires an admin role."
        elif request.path.startswith("/inventory/run/"):
            message = "Manual scan controls require an operator or admin role."
        elif request.path == "/" or request.path.startswith("/jobs") or request.path.startswith("/audit") or request.path.startswith("/settings"):
            message = "This area requires an operator or admin role."
        if g.get("user"):
            try:
                audit_service.log_event(
                    "auth.permission_denied",
                    "route",
                    request.path,
                    {
                        "outcome": "denied",
                        "summary": message,
                        "path": request.path,
                        "method": request.method,
                    },
                )
            except Exception:
                app.logger.exception("Failed to record permission denial for %s", request.path)
        return render_template("error.html", title="Forbidden", message=message), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template("error.html", title="Not Found", message=str(error)), 404

    @app.errorhandler(500)
    def server_error(error):
        reference = getattr(g, "request_id", secrets.token_hex(6))
        app.logger.exception("Unhandled server error reference=%s", reference)
        return render_template(
            "error.html",
            title="Server Error",
            message=f"An internal error occurred. Reference: {reference}",
        ), 500

    app.register_blueprint(auth.bp)
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(monitoring.bp)
    app.register_blueprint(inventory.bp)
    app.register_blueprint(switches.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(jobs.bp)
    app.register_blueprint(audit.bp)
    app.register_blueprint(settings.bp)
    app.register_blueprint(health.bp)

    job_manager = JobManager(app)
    app.extensions["job_manager"] = job_manager

    monitoring_service = MonitoringService(app)
    app.extensions["monitoring_service"] = monitoring_service

    if not app.config["TESTING"]:
        if app.config["SCHEDULER_ENABLED"]:
            app.logger.info("Background scheduler is enabled with a %s-second tick.", app.config["SCHEDULER_TICK_SECONDS"])
        else:
            app.logger.warning("Background scheduler is disabled. Daily schedules will not run until SCHEDULER_ENABLED=true.")
        scheduler = SchedulerThread(app, job_manager)
        scheduler.start()
        app.extensions["scheduler"] = scheduler
        if app.config["MONITORING_ENABLED"]:
            app.logger.info("Monitoring service is enabled with a %s-second refresh.", app.config["MONITOR_REFRESH_SECONDS"])
        monitoring_service.start()

    return app
