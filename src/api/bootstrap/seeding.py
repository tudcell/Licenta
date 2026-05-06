"""Startup-time seeding for the metadata index and the bootstrap admin."""

from __future__ import annotations

import logging
import os

from flask import Flask

from src.utils.password_security import hash_password

logger = logging.getLogger("blockchain_audit")


def _index_already_populated(app: Flask) -> bool:
    _, total = app.metadata_store.search_transactions(page=1, per_page=1)
    return total > 0


def seed_metadata_index(app: Flask) -> None:
    if _index_already_populated(app):
        logger.info("Metadata index already populated; skipping rescan")
        return
    for block in app.blockchain:
        for tx in block.transactions:
            is_flagged = bool(tx.metadata.get("flagged"))
            app.metadata_store.index_transaction(tx, block.index, tx_status="MINED", is_flagged=is_flagged)
    logger.info("Existing transactions indexed in SQLite")


def seed_admin_user(app: Flask, *, is_production: bool) -> None:
    admin_pass = os.environ.get("ADMIN_PASSWORD")
    if app.metadata_store.get_user("admin"):
        return
    if is_production and (not admin_pass or admin_pass == "admin123"):
        raise RuntimeError("Set a strong ADMIN_PASSWORD before starting in production")
    admin_pass = admin_pass or "admin123"
    app.metadata_store.create_user(
        username="admin",
        password_hash=hash_password(admin_pass),
        role="admin",
    )
    logger.info("Admin user created")
