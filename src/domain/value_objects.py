"""Shared value objects: enums for risk and severity levels."""

from __future__ import annotations

from enum import Enum


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @classmethod
    def from_string(cls, value: str | None, default: "RiskLevel" = None) -> "RiskLevel":
        try:
            return cls((value or "").lower())
        except ValueError:
            return default or cls.LOW
