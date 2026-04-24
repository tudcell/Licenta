"""Transaction module - canonical domain entity for audit events."""

import json
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
import uuid

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


@dataclass
class Transaction:
	transaction_type: TransactionType
	sender_address: str
	data: Dict[str, Any]
	timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
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

	def sign(self, private_key_hex: str):
		self.signature = DigitalSignature.sign_with_hex_key(private_key_hex, self.get_signable_data())

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
	def from_dict(cls, data: Dict[str, Any]) -> 'Transaction':
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
	def from_json(cls, json_string: str) -> 'Transaction':
		return cls.from_dict(json.loads(json_string))


class TransactionFactory:
	@staticmethod
	def create_login_event(user_id: str, sender_address: str, ip_address: str, user_agent: str = None, success: bool = True) -> Transaction:
		tx_type = TransactionType.LOGIN if success else TransactionType.LOGIN_FAILED
		return Transaction(
			transaction_type=tx_type,
			sender_address=sender_address,
			data={"user_id": user_id, "ip_address": ip_address, "user_agent": user_agent, "success": success},
			metadata={"category": "authentication", "risk_level": "low" if success else "medium"},
		)

	@staticmethod
	def create_data_access_event(user_id: str, sender_address: str, resource_id: str, action: str, success: bool = True) -> Transaction:
		type_map = {
			"read": TransactionType.DATA_READ,
			"write": TransactionType.DATA_WRITE,
			"delete": TransactionType.DATA_DELETE,
			"modify": TransactionType.DATA_MODIFY,
		}
		return Transaction(
			transaction_type=type_map.get(action, TransactionType.CUSTOM),
			sender_address=sender_address,
			data={"user_id": user_id, "resource_id": resource_id, "action": action, "success": success},
			metadata={"category": "data_access", "risk_level": "high" if action == "delete" else "low"},
		)

	@staticmethod
	def create_transfer_event(sender_address: str, recipient_address: str, amount: float, currency: str = "RON") -> Transaction:
		return Transaction(
			transaction_type=TransactionType.TRANSFER,
			sender_address=sender_address,
			data={"recipient": recipient_address, "amount": amount, "currency": currency},
			metadata={"category": "financial", "risk_level": "high" if amount > 10000 else "medium" if amount > 1000 else "low"},
		)


__all__ = ["Transaction", "TransactionType", "TransactionFactory"]

