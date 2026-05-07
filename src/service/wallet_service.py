"""Wallet use-cases orchestrating ownership and indexing rules."""

from __future__ import annotations

from typing import Tuple

from src.domain.authorization import Principal, Role
from src.domain.entities.wallet import WalletManager
from src.domain.errors import (
    AuthError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from src.infrastructure.persistence.sqlite import TransactionIndexRepository, UserRepository
from src.utils.pagination import build_pagination_metadata, paginate_sequence


class WalletService:
    def __init__(
            self,
            wallet_manager: WalletManager,
            users: UserRepository,
            transactions: TransactionIndexRepository,
    ):
        self._wallet_manager = wallet_manager
        self._users = users
        self._transactions = transactions

    def list_wallets(self, principal: Principal, page: int, per_page: int) -> Tuple[dict, dict]:
        current_user = self._users.get(principal.username)
        all_wallets = self._wallet_manager.list_wallets()
        visible_wallets = self._filter_visible_wallets(all_wallets, principal.role, current_user)
        paginated_wallets, pagination = paginate_sequence(visible_wallets, page, per_page)
        return {"wallets": paginated_wallets, "count": len(paginated_wallets)}, pagination

    def create_wallet(self, principal: Principal, name: str, assign_to_user: str | None) -> dict:
        clean_name = name.strip()
        if not clean_name or len(clean_name) < 2:
            raise ValidationError("Wallet name must have at least 2 characters")

        user = self._users.get(principal.username)
        if not user:
            raise AuthError("Authenticated user not found")

        requested_owner = assign_to_user or principal.username
        is_admin = principal.role is Role.ADMIN
        if not is_admin and requested_owner != principal.username:
            raise ForbiddenError("Only admins can assign wallets to other users")

        owner_user = self._users.get(requested_owner)
        if not owner_user:
            raise NotFoundError(f"User '{requested_owner}' not found", error_code="USER_NOT_FOUND")

        if not is_admin and user.get("wallet_name") and user["wallet_name"] != clean_name:
            raise ConflictError("User already has an assigned wallet", error_code="WALLET_ALREADY_ASSIGNED")

        try:
            wallet = self._wallet_manager.create_wallet(clean_name, metadata={"owner": requested_owner})
        except ValueError as exc:
            raise ConflictError(str(exc), error_code="WALLET_EXISTS") from exc

        if not self._users.assign_wallet(requested_owner, clean_name):
            raise NotFoundError(
                f"Could not assign wallet to user '{requested_owner}'",
                error_code="USER_NOT_FOUND",
            )

        return {
            "wallet": wallet.to_dict(),
            "assigned_to": requested_owner,
            "wallet_name": clean_name,
        }

    def get_wallet_details(self, principal: Principal, wallet_name: str, page: int, per_page: int) -> Tuple[dict, dict]:
        wallet = self._wallet_manager.get_wallet(wallet_name)
        if not wallet:
            raise NotFoundError(f"Wallet '{wallet_name}' not found", error_code="WALLET_NOT_FOUND")

        user = self._users.get(principal.username)
        if principal.role is not Role.ADMIN and user and user.get("wallet_name") != wallet_name:
            raise ForbiddenError("Access forbidden to this wallet")

        entries, total = self._transactions.search(
            sender=wallet.address,
            page=page,
            per_page=per_page,
        )
        indexed_txs = [entry.to_legacy_dict() for entry in entries]

        return {
            "wallet": wallet.to_dict(),
            "transactions": indexed_txs,
            "transaction_count": total,
        }, build_pagination_metadata(page, per_page, total)

    @staticmethod
    def _filter_visible_wallets(wallets: list[dict], role: Role, user: dict | None) -> list[dict]:
        if role is Role.ADMIN:
            return wallets
        if not user or not user.get("wallet_name"):
            return []
        assigned_wallet_name = user["wallet_name"]
        return [wallet for wallet in wallets if wallet["name"] == assigned_wallet_name]
