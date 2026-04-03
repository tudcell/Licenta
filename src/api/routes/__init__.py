"""
API Routes package.
Contains all Flask Blueprints for different API endpoints.
"""

from .auth_routes import auth_bp
from .blockchain_routes import blockchain_bp
from .transaction_routes import transaction_bp
# from .quarantine_routes import quarantine_bp  # Removed
from .wallet_routes import wallet_bp
from .anomaly_routes import anomaly_bp
from .audit_routes import audit_bp

__all__ = [
    'auth_bp',
    'blockchain_bp',
    'transaction_bp',
    # 'quarantine_bp',
    'wallet_bp',
    'anomaly_bp',
    'audit_bp',
]

