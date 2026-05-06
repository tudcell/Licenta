"""Event bus port and a no-op adapter for tests/CLI use."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Protocol


@dataclass(frozen=True)
class DomainEvent:
    name: str
    payload: Dict[str, Any]
    namespace: str = "/alerts"


class EventBus(Protocol):
    def publish(self, event: DomainEvent) -> None: ...


class NullEventBus:
    """Default adapter that drops events. Useful in unit tests."""

    def publish(self, event: DomainEvent) -> None:  # noqa: D401
        return None
