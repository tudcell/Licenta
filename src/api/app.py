"""
Flask API for the blockchain audit system.
Main application factory with safer defaults for production use.
"""

import os
import sys
import logging
import secrets
from datetime import datetime, timezone, timedelta

from flask import Flask, send_from_directory, request
from flask_cors import CORS
from flask_socketio import emit
from flask_jwt_extended import decode_token

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.domain.entities.blockchain import Blockchain, BlockchainConfig
from src.domain.entities.wallet import WalletManager
from src.service.transaction_analyzer import TransactionAnalyzer
from src.repository.analyzer_repository import AnalyzerRepository
from src.repository.blockchain_repository import BlockchainRepository
from src.repository.metadata_repository import MetadataRepository
from src.repository.model_repository import ModelRepository
from src.repository.snapshot_repository import SnapshotRepository
from src.repository.wallet_repository import WalletRepository
from src.service.anomaly_service import AnomalyService
from src.service.auth_service import AuthService
from src.service.audit_service import AuditService
from src.service.blockchain_service import BlockchainService
from src.service.transaction_service import TransactionService
from src.service.wallet_service import WalletService

from .extensions import jwt, socketio
from .database import MetadataStore
from .auth import hash_password
from .responses import api_error

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('blockchain_audit')


def _parse_cors_origins(raw_value: str):
    if not raw_value:
        return ['http://localhost:5000']
    return [item.strip() for item in raw_value.split(',') if item.strip()]


def create_app(config: dict = None) -> Flask:
    app = Flask(__name__, static_folder=None)
    environment = os.environ.get('APP_ENV', 'development').lower()
    is_production = environment == 'production'

    jwt_secret = os.environ.get('JWT_SECRET_KEY')
    if is_production and not jwt_secret:
        raise RuntimeError('JWT_SECRET_KEY must be set in production')
    jwt_secret = jwt_secret or ('dev-insecure-change-me-please-set-jwt-secret-key' if not is_production else secrets.token_hex(32))

    app.config.update({
        'APP_ENV': environment,
        'JWT_SECRET_KEY': jwt_secret,
        'JWT_ACCESS_TOKEN_EXPIRES': timedelta(hours=1),
        'JWT_REFRESH_TOKEN_EXPIRES': timedelta(days=30),
        'JWT_TOKEN_LOCATION': ['headers'],
        'JWT_HEADER_NAME': 'Authorization',
        'JWT_HEADER_TYPE': 'Bearer',
        'MAX_CONTENT_LENGTH': 16 * 1024 * 1024,
    })
    if config:
        app.config.update(config)

    os.environ.setdefault('WALLET_ENCRYPTION_KEY', app.config['JWT_SECRET_KEY'])

    cors_origins = _parse_cors_origins(
        os.environ.get(
            'CORS_ORIGINS',
            'http://localhost:5000,http://127.0.0.1:5000,http://localhost:5173,http://127.0.0.1:5173'
        )
    )
    CORS(app, resources={
        r"/api/*": {
            "origins": cors_origins,
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization", "X-Requested-With", "Accept"],
            "expose_headers": ["Content-Disposition", "X-Total-Count"],
            "supports_credentials": False,
            "max_age": 600
        }
    })

    jwt.init_app(app)
    socketio.init_app(app, cors_allowed_origins=cors_origins, async_mode='threading')

    data_dir = os.environ.get('DATA_DIR', 'data')
    os.makedirs(data_dir, exist_ok=True)

    blockchain_config = BlockchainConfig(
        difficulty=3,
        max_transactions_per_block=50,
        data_dir=os.path.join(data_dir, 'blockchain'),
        auto_save=True
    )
    app.blockchain = Blockchain(blockchain_config)
    app.wallet_manager = WalletManager(os.path.join(data_dir, 'wallets'))
    app.analyzer = TransactionAnalyzer(blockchain=app.blockchain, auto_train=False, min_training_samples=30)
    app.model_repository = ModelRepository()
    app.snapshot_repository = SnapshotRepository()
    app.snapshot_retention_count = max(1, int(os.environ.get('SNAPSHOT_RETENTION_COUNT', app.config.get('SNAPSHOT_RETENTION_COUNT', 20))))

    app.ml_model_path = os.environ.get('ML_MODEL_PATH', os.path.join(data_dir, 'ml_model.pkl'))
    if os.path.exists(app.ml_model_path):
        try:
            app.analyzer.detector = app.model_repository.load_detector(app.ml_model_path)
            logger.info("ML model loaded from %s", app.ml_model_path)
        except Exception as e:
            logger.warning("Could not load ML model: %s", e)

    app.metadata_store = MetadataStore(db_path=os.environ.get('METADATA_DB', os.path.join(data_dir, 'audit_metadata.db')))
    app.blockchain_repository = BlockchainRepository(app.blockchain)
    app.analyzer_repository = AnalyzerRepository(app.analyzer)
    app.metadata_repository = MetadataRepository(app.metadata_store)
    app.wallet_repository = WalletRepository(app.wallet_manager)
    app.auth_service = AuthService(app.metadata_repository)
    app.transaction_service = TransactionService(app.wallet_repository, app.metadata_repository, app.analyzer_repository)
    app.wallet_service = WalletService(app.wallet_repository, app.metadata_repository)
    app.blockchain_service = BlockchainService(app.blockchain_repository, app.analyzer_repository, app.metadata_repository)
    app.anomaly_service = AnomalyService(
        analyzer_repository=app.analyzer_repository,
        blockchain_repository=app.blockchain_repository,
        metadata_repository=app.metadata_repository,
        wallet_repository=app.wallet_repository,
        model_repository=app.model_repository,
    )
    app.audit_service = AuditService(app.analyzer_repository, app.snapshot_repository)

    for block in app.blockchain:
        for tx in block.transactions:
            is_flagged = bool(tx.metadata.get('flagged'))
            app.metadata_store.index_transaction(tx, block.index, tx_status='MINED', is_flagged=is_flagged)
    logger.info("Existing transactions indexed in SQLite")

    admin_pass = os.environ.get('ADMIN_PASSWORD')
    if not app.metadata_store.get_user('admin'):
        if is_production and (not admin_pass or admin_pass == 'admin123'):
            raise RuntimeError('Set a strong ADMIN_PASSWORD before starting in production')
        admin_pass = admin_pass or 'admin123'
        app.metadata_store.create_user(username='admin', password_hash=hash_password(admin_pass), role='admin')
        logger.info("Admin user created")

    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        return app.metadata_repository.is_token_revoked(jwt_payload['jti'])

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return api_error("Access token has expired", 401, error_code="TOKEN_EXPIRED")

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return api_error("Invalid token", 401, error_code="TOKEN_INVALID")

    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return api_error("Authentication required", 401, error_code="TOKEN_MISSING")

    @app.errorhandler(400)
    def bad_request(error):
        return api_error("Invalid request", 400, error_code="BAD_REQUEST")

    @app.errorhandler(404)
    def not_found(error):
        return api_error("Resource not found", 404, error_code="NOT_FOUND")

    @app.errorhandler(405)
    def method_not_allowed(error):
        return api_error("HTTP method not allowed", 405, error_code="METHOD_NOT_ALLOWED")

    @app.errorhandler(500)
    def internal_error(error):
        logger.exception("Internal server error")
        return api_error("Internal server error", 500, error_code="INTERNAL_ERROR")

    frontend_dist_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        'frontend',
        'dist'
    )

    @app.route('/')
    def index():
        if os.path.exists(os.path.join(frontend_dist_dir, 'index.html')):
            return send_from_directory(frontend_dist_dir, 'index.html')
        static_dir = os.path.join(os.path.dirname(__file__), 'static')
        if os.path.exists(os.path.join(static_dir, 'index.html')):
            return send_from_directory(static_dir, 'index.html')
        return api_error("Dashboard not found. Place files in src/api/static/", 404)

    @app.route('/assets/<path:filename>')
    def serve_frontend_assets(filename):
        if os.path.exists(os.path.join(frontend_dist_dir, 'assets', filename)):
            return send_from_directory(os.path.join(frontend_dist_dir, 'assets'), filename)
        return api_error("Asset not found", 404, error_code="NOT_FOUND")

    @app.route('/<path:filename>')
    def serve_frontend_file(filename):
        candidate = os.path.join(frontend_dist_dir, filename)
        if os.path.exists(candidate) and os.path.isfile(candidate):
            return send_from_directory(frontend_dist_dir, filename)
        if os.path.exists(os.path.join(frontend_dist_dir, 'index.html')) and not filename.startswith('api/'):
            return send_from_directory(frontend_dist_dir, 'index.html')
        return api_error("Resource not found", 404, error_code="NOT_FOUND")

    @app.route('/static/<path:filename>')
    def serve_static(filename):
        static_dir = os.path.join(os.path.dirname(__file__), 'static')
        return send_from_directory(static_dir, filename)

    from .routes import auth_bp, blockchain_bp, transaction_bp, wallet_bp, anomaly_bp, audit_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(blockchain_bp)
    app.register_blueprint(transaction_bp)
    app.register_blueprint(wallet_bp)
    app.register_blueprint(anomaly_bp)
    app.register_blueprint(audit_bp)

    def _get_socket_token(auth_payload=None):
        if auth_payload and isinstance(auth_payload, dict) and auth_payload.get('token'):
            return auth_payload['token']
        header = request.headers.get('Authorization', '')
        if header.startswith('Bearer '):
            return header.split(' ', 1)[1].strip()
        return request.args.get('token')

    @socketio.on('connect', namespace='/alerts')
    def handle_connect(auth=None):
        token = _get_socket_token(auth)
        if not token:
            logger.warning('Rejected WebSocket client without token')
            raise ConnectionRefusedError('Authentication token required')
        try:
            decoded = decode_token(token)
        except Exception:
            logger.warning('Rejected WebSocket client with invalid token')
            raise ConnectionRefusedError('Invalid authentication token')
        logger.info("WebSocket client connected: %s", decoded.get('sub'))
        emit('connected', {
            'message': 'Connected to alerts stream',
            'timestamp': datetime.now(timezone.utc).isoformat()
        })

    @socketio.on('disconnect', namespace='/alerts')
    def handle_disconnect():
        logger.info("WebSocket client disconnected")

    @socketio.on('subscribe_alerts', namespace='/alerts')
    def handle_subscribe(data):
        severity_filter = data.get('severity', 'all') if data else 'all'
        emit('subscribed', {'filter': severity_filter, 'message': f'Subscribed to alerts: {severity_filter}'})

    return app


if __name__ == '__main__':
    app = create_app()
    print("Starting Blockchain Audit System...")
    print("Open http://localhost:5000 in your browser")
    socketio.run(app, debug=(os.environ.get('APP_ENV', 'development').lower() != 'production'), port=5000, host='127.0.0.1')
