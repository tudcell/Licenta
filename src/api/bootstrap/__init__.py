"""Application bootstrap helpers used to slim the app factory."""

from .config import build_app_config, parse_cors_origins
from .frontend import register_frontend_routes
from .jwt import register_jwt_callbacks
from .seeding import seed_admin_user, seed_metadata_index
from .sockets import register_socket_handlers
from .wiring import build_services

__all__ = [
    "build_app_config",
    "parse_cors_origins",
    "register_frontend_routes",
    "register_jwt_callbacks",
    "register_socket_handlers",
    "seed_admin_user",
    "seed_metadata_index",
    "build_services",
]
