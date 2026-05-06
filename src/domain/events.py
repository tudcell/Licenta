"""Domain events and the EventBus contract.

DomainEvent is a value object — it describes *what happened*, not *how*
it gets delivered. Concrete event-bus adapters live under infrastructure.
"""

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
    """Adapter that drops events. Used in unit tests and CLI tooling."""

    def publish(self, event: DomainEvent) -> None:
        return None
