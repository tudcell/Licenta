"""Adapter that publishes domain events through a Flask-SocketIO instance."""

from __future__ import annotations

from src.domain.events import DomainEvent


class SocketIOEventBus:
    def __init__(self, socketio):
        self._socketio = socketio

    def publish(self, event: DomainEvent) -> None:
        self._socketio.emit(event.name, event.payload, namespace=event.namespace)
