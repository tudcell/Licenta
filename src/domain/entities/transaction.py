"""Transaction module - canonical domain entity for audit events."""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from src.domain.policies import DigitalSignature, HashUtils


class TransactionType(Enum):
    """Supported transaction/audit event types."""

    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    LOGIN_FAILED = "LOGIN_FAILED"
    ACCESS_GRANTED = "ACCESS_GRANTED"
    ACCESS_DENIED = "ACCESS_DENIED"
    DATA_READ = "DATA_READ"
    DATA_WRITE = "DATA_WRITE"
    DATA_DELETE = "DATA_DELETE"
    DATA_MODIFY = "DATA_MODIFY"
    CONFIG_CHANGE = "CONFIG_CHANGE"
    PERMISSION_CHANGE = "PERMISSION_CHANGE"
    USER_CREATED = "USER_CREATED"
    USER_DELETED = "USER_DELETED"
    TRANSFER = "TRANSFER"
    CUSTOM = "CUSTOM"


class TransactionStatus(str, Enum):
    """Lifecycle states for indexed transactions."""

    PENDING = "PENDING"
    FLAGGED = "FLAGGED"
    MINED = "MINED"
    REJECTED = "REJECTED"


@dataclass
class Transaction:
    transaction_type: TransactionType
    sender_address: str
    data: Dict[str, Any]
    # Timezone-aware UTC: produces "...+00:00" suffix so JavaScript's
    # `new Date(iso)` parses it as UTC and `toLocaleString()` converts to
    # the viewer's local timezone. A naive timestamp would be parsed as
    # local time by the browser, making the user's own transaction look
    # like it happened "hours ago".
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    transaction_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    signature: Optional[str] = None
    public_key: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_signable_data(self) -> Dict[str, Any]:
        return {
            "transaction_id": self.transaction_id,
            "transaction_type": self.transaction_type.value,
            "sender_address": self.sender_address,
            "data": self.data,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    def calculate_hash(self) -> str:
        return HashUtils.hash_object(self.get_signable_data())

    def verify_signature(self) -> bool:
        if not self.signature or not self.public_key:
            return False
        return DigitalSignature.verify_with_hex_key(self.public_key, self.get_signable_data(), self.signature)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transaction_id": self.transaction_id,
            "transaction_type": self.transaction_type.value,
            "sender_address": self.sender_address,
            "data": self.data,
            "timestamp": self.timestamp,
            "signature": self.signature,
            "public_key": self.public_key,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Transaction":
        return cls(
            transaction_id=data["transaction_id"],
            transaction_type=TransactionType(data["transaction_type"]),
            sender_address=data["sender_address"],
            data=data["data"],
            timestamp=data["timestamp"],
            signature=data.get("signature"),
            public_key=data.get("public_key"),
            metadata=data.get("metadata", {}),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, json_string: str) -> "Transaction":
        return cls.from_dict(json.loads(json_string))


__all__ = ["Transaction", "TransactionType", "TransactionStatus"]
