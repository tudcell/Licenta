"""Per-type validation/normalization for transaction payloads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.domain.entities.transaction import TransactionType
from src.domain.errors import ValidationError


_AUTH_TYPES = {
    TransactionType.LOGIN,
    TransactionType.LOGIN_FAILED,
    TransactionType.ACCESS_GRANTED,
    TransactionType.ACCESS_DENIED,
    TransactionType.LOGOUT,
}

_DATA_TYPES = {
    TransactionType.DATA_READ,
    TransactionType.DATA_WRITE,
    TransactionType.DATA_DELETE,
    TransactionType.DATA_MODIFY,
}

_DATA_ACTION_DEFAULTS = {
    TransactionType.DATA_READ: "read",
    TransactionType.DATA_WRITE: "write",
    TransactionType.DATA_DELETE: "delete",
    TransactionType.DATA_MODIFY: "modify",
}


@dataclass
class TransactionRequest:
    transaction_type: TransactionType
    data: Dict[str, Any]
    wallet_name: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


def parse_transaction_request(raw: Optional[dict], username: str) -> TransactionRequest:
    """Parse and validate a transaction creation request.

    Raises ValidationError on any structural or per-type rule violation.
    """
    if not isinstance(raw, dict):
        raise ValidationError("Transaction data missing")

    errors: List[dict] = []
    missing = [field for field in ("transaction_type", "data") if field not in raw]
    if missing:
        raise ValidationError(
            f"Missing fields: {', '.join(missing)}",
            errors=[{"field": field, "message": "required field"} for field in missing],
        )

    try:
        tx_type = TransactionType(raw["transaction_type"])
    except ValueError:
        raise ValidationError(
            f"Invalid transaction type: {raw['transaction_type']}",
            error_code="INVALID_TX_TYPE",
            errors=[{"valid_types": [item.value for item in TransactionType]}],
        )

    wallet_name = raw.get("wallet_name")
    if wallet_name is not None and (not isinstance(wallet_name, str) or not wallet_name.strip()):
        errors.append({"field": "wallet_name", "message": "must be a non-empty string"})

    metadata = raw.get("metadata")
    if metadata is not None and not isinstance(metadata, dict):
        errors.append({"field": "metadata", "message": "must be an object"})

    payload = raw.get("data")
    if not isinstance(payload, dict):
        errors.append({"field": "data", "message": "must be an object"})
        raise ValidationError("Invalid transaction payload", errors=errors)

    validated = dict(payload)
    _normalize_payload(tx_type, validated, username, errors)

    if errors:
        raise ValidationError("Invalid transaction payload", errors=errors)

    return TransactionRequest(
        transaction_type=tx_type,
        data=validated,
        wallet_name=wallet_name,
        metadata=metadata,
    )


def _normalize_payload(tx_type: TransactionType, validated: dict, username: str, errors: List[dict]) -> None:
    def require_non_empty_str(field_name: str) -> None:
        value = validated.get(field_name)
        if not isinstance(value, str) or not value.strip():
            errors.append({"field": f"data.{field_name}", "message": "required non-empty string"})

    if tx_type in _AUTH_TYPES:
        validated.setdefault("user_id", username)

    if tx_type in {TransactionType.LOGIN, TransactionType.LOGIN_FAILED}:
        require_non_empty_str("ip_address")
        validated.setdefault("success", tx_type == TransactionType.LOGIN)

    if tx_type in {TransactionType.ACCESS_GRANTED, TransactionType.ACCESS_DENIED}:
        validated.setdefault("success", tx_type == TransactionType.ACCESS_GRANTED)

    if tx_type == TransactionType.LOGOUT:
        session_duration = validated.get("session_duration")
        if session_duration is not None:
            try:
                parsed = int(session_duration)
            except (TypeError, ValueError):
                errors.append({"field": "data.session_duration", "message": "must be an integer >= 0"})
            else:
                if parsed < 0:
                    errors.append({"field": "data.session_duration", "message": "must be an integer >= 0"})
                else:
                    validated["session_duration"] = parsed

    if tx_type in _DATA_TYPES:
        validated.setdefault("user_id", username)
        require_non_empty_str("resource_id")
        validated.setdefault("action", _DATA_ACTION_DEFAULTS[tx_type])
        success = validated.get("success")
        if success is not None and not isinstance(success, bool):
            errors.append({"field": "data.success", "message": "must be boolean"})
        if success is None:
            validated["success"] = True

    if tx_type == TransactionType.TRANSFER:
        require_non_empty_str("recipient")
        amount = validated.get("amount")
        try:
            parsed_amount = float(amount)
        except (TypeError, ValueError):
            errors.append({"field": "data.amount", "message": "required number > 0"})
        else:
            if parsed_amount <= 0:
                errors.append({"field": "data.amount", "message": "required number > 0"})
            else:
                validated["amount"] = parsed_amount
        validated.setdefault("currency", "RON")
