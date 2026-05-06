"""Static asset and SPA fallback routes for the frontend bundle."""

from __future__ import annotations

import os

from flask import Flask, send_from_directory

from ..responses import api_error


def register_frontend_routes(app: Flask) -> None:
    api_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    project_root = os.path.dirname(os.path.dirname(api_root))
    frontend_dist_dir = os.path.join(project_root, "frontend", "dist")
    static_dir = os.path.join(api_root, "static")

    @app.route("/")
    def index():
        if os.path.exists(os.path.join(frontend_dist_dir, "index.html")):
            return send_from_directory(frontend_dist_dir, "index.html")
        if os.path.exists(os.path.join(static_dir, "index.html")):
            return send_from_directory(static_dir, "index.html")
        return api_error("Dashboard not found. Place files in src/api/static/", 404)

    @app.route("/assets/<path:filename>")
    def serve_frontend_assets(filename):
        if os.path.exists(os.path.join(frontend_dist_dir, "assets", filename)):
            return send_from_directory(os.path.join(frontend_dist_dir, "assets"), filename)
        return api_error("Asset not found", 404, error_code="NOT_FOUND")

    @app.route("/<path:filename>")
    def serve_frontend_file(filename):
        candidate = os.path.join(frontend_dist_dir, filename)
        if os.path.exists(candidate) and os.path.isfile(candidate):
            return send_from_directory(frontend_dist_dir, filename)
        if os.path.exists(os.path.join(frontend_dist_dir, "index.html")) and not filename.startswith("api/"):
            return send_from_directory(frontend_dist_dir, "index.html")
        return api_error("Resource not found", 404, error_code="NOT_FOUND")

    @app.route("/static/<path:filename>")
    def serve_static(filename):
        return send_from_directory(static_dir, filename)
