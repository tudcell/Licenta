"""
Transaction module - the fundamental data unit in the blockchain.
Each transaction represents an audit event that must be recorded.
"""

import json
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from dataclasses import dataclass, field, asdict
import uuid

from src.domain.crypto.hashing import HashUtils
from src.domain.crypto.digital_signature import DigitalSignature


class TransactionType(Enum):
    """
    Supported transaction/audit event types.
    """
    # Authentication events
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    LOGIN_FAILED = "LOGIN_FAILED"

    # Access events
    ACCESS_GRANTED = "ACCESS_GRANTED"
    ACCESS_DENIED = "ACCESS_DENIED"

    # Data events
    DATA_READ = "DATA_READ"
    DATA_WRITE = "DATA_WRITE"
    DATA_DELETE = "DATA_DELETE"
    DATA_MODIFY = "DATA_MODIFY"

    # System events
    CONFIG_CHANGE = "CONFIG_CHANGE"
    PERMISSION_CHANGE = "PERMISSION_CHANGE"
    USER_CREATED = "USER_CREATED"
    USER_DELETED = "USER_DELETED"

    # Transfer (for demonstrations)
    TRANSFER = "TRANSFER"

    # Generic
    CUSTOM = "CUSTOM"


@dataclass
class Transaction:
    """
    Represents a transaction/audit event in the system.

    Each transaction contains:
    - Unique identifier
    - Timestamp
    - Event type
    - Event-specific details
    - Digital signature for authenticity
    """

    transaction_type: TransactionType
    sender_address: str  # Address/ID of the entity generating the event
    data: Dict[str, Any]  # Event-specific data
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    transaction_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    signature: Optional[str] = None
    public_key: Optional[str] = None

    # Metadata for ML
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_signable_data(self) -> Dict[str, Any]:
        """
        Returns the data that needs to be signed.
        Does not include the signature itself (would be circular).
        """
        return {
            "transaction_id": self.transaction_id,
            "transaction_type": self.transaction_type.value,
            "sender_address": self.sender_address,
            "data": self.data,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }

    def calculate_hash(self) -> str:
        """
        Calculates the transaction hash for inclusion in Merkle Tree.
        """
        return HashUtils.hash_object(self.get_signable_data())

    def sign(self, private_key_hex: str):
        """
        Signs the transaction with the private key.

        Args:
            private_key_hex: The private key in hex format
        """
        signable_data = self.get_signable_data()
        self.signature = DigitalSignature.sign_with_hex_key(private_key_hex, signable_data)

    def verify_signature(self) -> bool:
        """
        Verifies the transaction signature.

        Returns:
            True only when both the public key and signature are present and valid.
        """
        if not self.signature or not self.public_key:
            return False

        signable_data = self.get_signable_data()
        return DigitalSignature.verify_with_hex_key(
            self.public_key,
            signable_data,
            self.signature
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the transaction to dictionary."""
        return {
            "transaction_id": self.transaction_id,
            "transaction_type": self.transaction_type.value,
            "sender_address": self.sender_address,
            "data": self.data,
            "timestamp": self.timestamp,
            "signature": self.signature,
            "public_key": self.public_key,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Transaction':
        """Deserializes the transaction from dictionary."""
        return cls(
            transaction_id=data["transaction_id"],
            transaction_type=TransactionType(data["transaction_type"]),
            sender_address=data["sender_address"],
            data=data["data"],
            timestamp=data["timestamp"],
            signature=data.get("signature"),
            public_key=data.get("public_key"),
            metadata=data.get("metadata", {})
        )

    def to_json(self) -> str:
        """Serializes to JSON."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, json_string: str) -> 'Transaction':
        """Deserializes from JSON."""
        return cls.from_dict(json.loads(json_string))

    def __str__(self) -> str:
        return f"TX[{self.transaction_id[:8]}] {self.transaction_type.value} from {self.sender_address[:16]}..."

    def __repr__(self) -> str:
        return self.__str__()


# Factory functions for common transaction types
class TransactionFactory:
    """
    Factory for easy creation of typical transactions.
    """

    @staticmethod
    def create_login_event(
        user_id: str,
        sender_address: str,
        ip_address: str,
        user_agent: str = None,
        success: bool = True
    ) -> Transaction:
        """Creates a login event."""
        tx_type = TransactionType.LOGIN if success else TransactionType.LOGIN_FAILED
        return Transaction(
            transaction_type=tx_type,
            sender_address=sender_address,
            data={
                "user_id": user_id,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "success": success
            },
            metadata={
                "category": "authentication",
                "risk_level": "low" if success else "medium"
            }
        )

    @staticmethod
    def create_data_access_event(
        user_id: str,
        sender_address: str,
        resource_id: str,
        action: str,  # read, write, delete
        success: bool = True
    ) -> Transaction:
        """Creates a data access event."""
        type_map = {
            "read": TransactionType.DATA_READ,
            "write": TransactionType.DATA_WRITE,
            "delete": TransactionType.DATA_DELETE,
            "modify": TransactionType.DATA_MODIFY
        }
        return Transaction(
            transaction_type=type_map.get(action, TransactionType.CUSTOM),
            sender_address=sender_address,
            data={
                "user_id": user_id,
                "resource_id": resource_id,
                "action": action,
                "success": success
            },
            metadata={
                "category": "data_access",
                "risk_level": "high" if action == "delete" else "low"
            }
        )

    @staticmethod
    def create_transfer_event(
        sender_address: str,
        recipient_address: str,
        amount: float,
        currency: str = "RON"
    ) -> Transaction:
        """Creates a transfer event."""
        return Transaction(
            transaction_type=TransactionType.TRANSFER,
            sender_address=sender_address,
            data={
                "recipient": recipient_address,
                "amount": amount,
                "currency": currency
            },
            metadata={
                "category": "financial",
                "risk_level": "high" if amount > 10000 else "medium" if amount > 1000 else "low"
            }
        )


