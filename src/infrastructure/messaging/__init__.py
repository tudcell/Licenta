"""Outbound messaging adapters (event publishing, notifications)."""

from .socketio_event_bus import SocketIOEventBus

__all__ = ["SocketIOEventBus"]
