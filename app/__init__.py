"""Google Reviews Monitoring & Intelligence — App Factory"""
import os
import logging
from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from datetime import datetime, timezone
import uuid

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()

def create_app(config_name=None):
    app = Flask(__name__)

    # Load config
    if config_name == 'testing':
        app.config.from_object('app.config.TestingConfig')
    else:
        app.config.from_object('app.config.Config')

    # Init extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    # Register blueprints
    from app.routes.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from app.routes.health import bp as health_bp
    app.register_blueprint(health_bp)

    from app.routes.dashboard import bp as dashboard_bp
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')

    from app.routes.discovery import bp as discovery_bp
    app.register_blueprint(discovery_bp)

    from app.routes.google import google_bp
    app.register_blueprint(google_bp)

    # Error handlers
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify(success=False, data=None, meta=_meta(), errors=[{"code": "BAD_REQUEST", "message": str(e), "field": None, "retryable": False}]), 400

    @app.errorhandler(401)
    def unauthorized(e):
        return jsonify(success=False, data=None, meta=_meta(), errors=[{"code": "UNAUTHORIZED", "message": "Authentication required", "field": None, "retryable": False}]), 401

    @app.errorhandler(403)
    def forbidden(e):
        return jsonify(success=False, data=None, meta=_meta(), errors=[{"code": "FORBIDDEN", "message": "Insufficient permissions", "field": None, "retryable": False}]), 403

    @app.errorhandler(404)
    def not_found(e):
        return jsonify(success=False, data=None, meta=_meta(), errors=[{"code": "NOT_FOUND", "message": "Resource not found", "field": None, "retryable": False}]), 404

    @app.errorhandler(500)
    def internal_error(e):
        db.session.rollback()
        return jsonify(success=False, data=None, meta=_meta(), errors=[{"code": "INTERNAL_ERROR", "message": "Internal server error", "field": None, "retryable": True}]), 500

    # Setup logging (redact secrets)
    _setup_logging(app)

    return app


def _meta():
    return {"trace_id": str(uuid.uuid4()), "timestamp": datetime.now(timezone.utc).isoformat(), "pagination": None}


def _setup_logging(app):
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    handler.setFormatter(formatter)
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)

    # Secret redaction filter
    class SecretFilter(logging.Filter):
        BLOCKED = ['password', 'secret', 'token', 'key', 'credential']

        def filter(self, record):
            msg = record.getMessage().lower()
            return not any(b in msg for b in self.BLOCKED)

    # Do NOT add secret filter to app.logger — it would block all auth logs
    # Instead, we ensure no secrets are logged explicitly in code
