"""Socket.IO connection handlers for the /alerts namespace."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from flask import request
from flask_jwt_extended import decode_token
from flask_socketio import emit

logger = logging.getLogger("blockchain_audit")


def _read_token(auth_payload=None) -> str | None:
    if auth_payload and isinstance(auth_payload, dict) and auth_payload.get("token"):
        return auth_payload["token"]
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header.split(" ", 1)[1].strip()
    return request.args.get("token")


def register_socket_handlers(socketio) -> None:
    @socketio.on("connect", namespace="/alerts")
    def handle_connect(auth=None):
        token = _read_token(auth)
        if not token:
            logger.warning("Rejected WebSocket client without token")
            raise ConnectionRefusedError("Authentication token required")
        try:
            decoded = decode_token(token)
        except Exception as exc:
            logger.warning("Rejected WebSocket client with invalid token: %s", exc)
            raise ConnectionRefusedError("Invalid authentication token")
        logger.info("WebSocket client connected: %s", decoded.get("sub"))
        emit("connected", {
            "message": "Connected to alerts stream",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    @socketio.on("disconnect", namespace="/alerts")
    def handle_disconnect():
        logger.info("WebSocket client disconnected")

    @socketio.on("subscribe_alerts", namespace="/alerts")
    def handle_subscribe(data):
        severity_filter = data.get("severity", "all") if data else "all"
        emit("subscribed", {"filter": severity_filter, "message": f"Subscribed to alerts: {severity_filter}"})
