"""Wallet use-cases orchestrating ownership and indexing rules."""

from __future__ import annotations

from typing import Tuple

from src.domain.authorization import Role
from src.domain.entities.wallet import WalletManager
from src.domain.errors import (
    AuthError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from src.infrastructure.metadata_store import MetadataStore
from src.utils.pagination import build_pagination_metadata, paginate_sequence


class WalletService:
    def __init__(self, wallet_manager: WalletManager, metadata_store: MetadataStore):
        self.wallet_manager = wallet_manager
        self.metadata_store = metadata_store

    def list_wallets(self, username: str, role: str, page: int, per_page: int) -> Tuple[dict, dict]:
        current_user = self.metadata_store.get_user(username)
        all_wallets = self.wallet_manager.list_wallets()
        visible_wallets = self._filter_visible_wallets(all_wallets, role, current_user)
        paginated_wallets, pagination = paginate_sequence(visible_wallets, page, per_page)
        return {"wallets": paginated_wallets, "count": len(paginated_wallets)}, pagination

    def create_wallet(self, username: str, role: str, name: str, assign_to_user: str | None) -> dict:
        clean_name = name.strip()
        if not clean_name or len(clean_name) < 2:
            raise ValidationError("Wallet name must have at least 2 characters")

        user = self.metadata_store.get_user(username)
        if not user:
            raise AuthError("Authenticated user not found")

        requested_owner = assign_to_user or username
        is_admin = role == Role.ADMIN.value
        if not is_admin and requested_owner != username:
            raise ForbiddenError("Only admins can assign wallets to other users")

        owner_user = self.metadata_store.get_user(requested_owner)
        if not owner_user:
            raise NotFoundError(f"User '{requested_owner}' not found", error_code="USER_NOT_FOUND")

        if not is_admin and user.get("wallet_name") and user["wallet_name"] != clean_name:
            raise ConflictError("User already has an assigned wallet", error_code="WALLET_ALREADY_ASSIGNED")

        try:
            wallet = self.wallet_manager.create_wallet(clean_name, metadata={"owner": requested_owner})
        except ValueError as exc:
            raise ConflictError(str(exc), error_code="WALLET_EXISTS") from exc

        if not self.metadata_store.assign_wallet_to_user(requested_owner, clean_name):
            raise NotFoundError(
                f"Could not assign wallet to user '{requested_owner}'",
                error_code="USER_NOT_FOUND",
            )

        return {
            "wallet": wallet.to_dict(include_private_key=False),
            "assigned_to": requested_owner,
            "wallet_name": clean_name,
        }

    def get_wallet_details(self, username: str, role: str, wallet_name: str, page: int, per_page: int) -> Tuple[dict, dict]:
        wallet = self.wallet_manager.get_wallet(wallet_name)
        if not wallet:
            raise NotFoundError(f"Wallet '{wallet_name}' not found", error_code="WALLET_NOT_FOUND")

        user = self.metadata_store.get_user(username)
        if role != Role.ADMIN.value and user and user.get("wallet_name") != wallet_name:
            raise ForbiddenError("Access forbidden to this wallet")

        indexed_txs, total = self.metadata_store.search_transactions(
            sender=wallet.address,
            page=page,
            per_page=per_page,
        )

        return {
            "wallet": wallet.to_dict(include_private_key=False),
            "transactions": indexed_txs,
            "transaction_count": total,
        }, build_pagination_metadata(page, per_page, total)

    @staticmethod
    def _filter_visible_wallets(wallets: list[dict], role: str, user: dict | None) -> list[dict]:
        if role == Role.ADMIN.value:
            return wallets
        if not user or not user.get("wallet_name"):
            return []
        assigned_wallet_name = user["wallet_name"]
        return [wallet for wallet in wallets if wallet["name"] == assigned_wallet_name]
