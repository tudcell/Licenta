"""Flask application factory. Composition root for the audit system."""

from __future__ import annotations

import logging
import os

from flask import Flask
from flask_cors import CORS

from .bootstrap import (
    build_app_config,
    build_services,
    parse_cors_origins,
    register_frontend_routes,
    register_jwt_callbacks,
    register_socket_handlers,
    seed_admin_user,
    seed_metadata_index,
)
from .error_handlers import register_error_handlers
from .extensions import jwt, socketio
from .routes import (
    anomaly_bp,
    audit_bp,
    auth_bp,
    blockchain_bp,
    transaction_bp,
    wallet_bp,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__, static_folder=None)
    is_production = os.environ.get("APP_ENV", "development").lower() == "production"

    app.config.update(build_app_config(is_production=is_production, override=config))
    os.environ.setdefault("WALLET_ENCRYPTION_KEY", app.config["JWT_SECRET_KEY"])

    cors_origins = parse_cors_origins(
        os.environ.get(
            "CORS_ORIGINS",
            "http://localhost:5000,http://127.0.0.1:5000,http://localhost:5173,http://127.0.0.1:5173",
        )
    )
    CORS(app, resources={
        r"/api/*": {
            "origins": cors_origins,
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization", "X-Requested-With", "Accept"],
            "expose_headers": ["Content-Disposition", "X-Total-Count"],
            "supports_credentials": False,
            "max_age": 600,
        }
    })

    jwt.init_app(app)
    socketio.init_app(app, cors_allowed_origins=cors_origins, async_mode="threading")

    build_services(app, socketio)
    seed_metadata_index(app)
    seed_admin_user(app, is_production=is_production)

    register_jwt_callbacks(app, jwt)
    register_error_handlers(app)
    register_frontend_routes(app)

    for blueprint in (auth_bp, blockchain_bp, transaction_bp, wallet_bp, anomaly_bp, audit_bp):
        app.register_blueprint(blueprint)

    register_socket_handlers(socketio)
    return app


if __name__ == "__main__":
    app = create_app()
    print("Starting Blockchain Audit System...")
    print("Open http://localhost:5000 in your browser")
    socketio.run(
        app,
        debug=(os.environ.get("APP_ENV", "development").lower() != "production"),
        port=5000,
        host="127.0.0.1",
    )
