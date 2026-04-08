"""Transaction service orchestrating wallet signing, anomaly analysis and indexing."""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.domain import TransactionType
from src.repository import MetadataRepository, WalletRepository


class TransactionService:
    def __init__(self, wallet_repository: WalletRepository, metadata_repository: MetadataRepository, analyzer):
        self.wallet_repository = wallet_repository
        self.metadata_repository = metadata_repository
        self.analyzer = analyzer

    def create_transaction(self, username: str, role: str, payload: Dict[str, Any]):
        user = self.metadata_repository.get_user(username)
        if not user:
            return {'error': 'AUTH_FAILED'}, 401

        requested_wallet_name = payload.get('wallet_name') or user.get('wallet_name') or username
        if user.get('wallet_name') and requested_wallet_name != user['wallet_name'] and role != 'admin':
            return {'error': 'WALLET_FORBIDDEN'}, 403

        wallet = self.wallet_repository.get_wallet(requested_wallet_name)
        if wallet is None:
            wallet = self.wallet_repository.create_wallet(requested_wallet_name, metadata={'owner': username})

        if not user.get('wallet_name'):
            self.metadata_repository.assign_wallet_to_user(username, requested_wallet_name)

        tx_metadata: Dict[str, object] = dict(payload.get('metadata', {}))
        tx_metadata.setdefault('submitted_by', username)
        tx_metadata.setdefault('flagged', False)

        tx = wallet.create_and_sign_transaction(
            transaction_type=TransactionType(payload['transaction_type']),
            data=payload['data'],
            metadata=tx_metadata,
        )

        report = self.analyzer.add_transaction(tx)

        if not report.signature_valid:
            self.metadata_repository.index_transaction(tx, tx_status='REJECTED', is_flagged=True)
            self.metadata_repository.save_alert(report)
            return {'transaction': tx.to_dict(), 'analysis': report.to_dict(), 'error': 'INVALID_SIGNATURE'}, 400

        if not report.added_to_mempool:
            self.metadata_repository.index_transaction(tx, tx_status='REJECTED', is_flagged=report.is_suspicious)
            if report.is_suspicious:
                self.metadata_repository.save_alert(report)
            return {'transaction': tx.to_dict(), 'analysis': report.to_dict(), 'error': 'MEMPOOL_REJECTED'}, 409

        tx_status = 'FLAGGED' if report.flagged_for_review else 'PENDING'
        self.metadata_repository.index_transaction(tx, tx_status=tx_status, is_flagged=report.flagged_for_review)

        alert_id = None
        if report.is_suspicious:
            alert_id = self.metadata_repository.save_alert(report)

        return {
            'transaction': tx.to_dict(),
            'analysis': report.to_dict(),
            'alert_id': alert_id,
        }, 201

    def list_transactions(self, sender=None, tx_type=None, status=None, flagged=None, page: int = 1, per_page: int = 20):
        return self.metadata_repository.search_transactions(sender=sender, tx_type=tx_type, status=status, flagged=flagged, page=page, per_page=per_page)

    def get_transaction_details(self, transaction_id: str, blockchain_repository):
        proof = blockchain_repository.verify_transaction_proof(transaction_id)
        index_record = self.metadata_repository.get_transaction_index(transaction_id)
        return proof, index_record

    def analyze_transaction(self, transaction_id: str):
        return self.analyzer.analyze_transaction(transaction_id)
