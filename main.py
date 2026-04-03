"""
Main entry point for the blockchain audit system.
Starts the Flask web server with WebSocket support.

Features:
- Real-time WebSocket (Flask-SocketIO)
- JWT authentication
- SQLite metadata store
- Standardized API responses
- Pagination on all endpoints
"""

import os
import socket
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.api.app import create_app
from src.api.extensions import socketio


def _is_port_available(host: str, port: int) -> bool:
    """Return True when the host:port can be bound by this process."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
            return True
        except OSError:
            return False


def main():
    """Main startup function."""
    # Create application
    app = create_app()

    # Configuration
    host = os.environ.get('HOST', '127.0.0.1')
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'True').lower() == 'true'

    if not _is_port_available(host, port):
        print(f"[ERROR] Port {host}:{port} is already in use.")
        print("        Another app instance may already be running.")
        print("        Stop the running process first, then start again.")
        raise SystemExit(1)

    base_url = f"http://{host}:{port}/"
    print(f"  Open dashboard: {base_url}")
    print("  Note: if your IDE opens the browser automatically, do not click the URL again.")
    print(f"  WebSocket: ws://{host}:{port}/alerts")
    print(f"  Debug mode: {debug}")
    print()
    print("  Auth (JWT):")
    print("    POST /api/auth/login      - Authentication (get token)")
    print("    POST /api/auth/refresh    - Refresh token")
    print("    POST /api/auth/logout     - Logout")
    print("    POST /api/auth/register   - Create user (admin only)")
    print()
    print("  Blockchain:")
    print("    GET  /api/health          - Health check (public)")
    print("    GET  /api/blockchain      - Paginated blockchain")
    print("    GET  /api/blockchain/stats - Statistics")
    print("    GET  /api/block/<index>   - Specific block")
    print("    POST /api/mine            - Mine block")
    print()
    print("  Transactions:")
    print("    GET  /api/transactions    - Paginated transactions + filters")
    print("    GET  /api/transaction/<id> - Transaction with Merkle proof")
    print("    POST /api/transaction     - Create transaction")
    print("    GET  /api/mempool         - Pending transactions")
    print()
    print("  Anomalies:")
    print("    POST /api/anomaly/train   - Train detector")
    print("    GET  /api/anomaly/stats   - Anomaly statistics")
    print("    GET  /api/alerts          - Paginated alerts + filters")
    print("    PUT  /api/alerts/<id>/resolve - Mark alert resolved")
    print()
    print("  Audit:")
    print("    GET  /api/audit/integrity - Check integrity")
    print("    GET  /api/audit/export    - Export log (admin only)")
    print()
    print("  Demo:")
    print("    POST /api/demo/generate   - Generate test data")
    print()
    print("  Default login: admin / admin123 (development only)")
    print("  Press Ctrl+C to stop the server.")
    print("=" * 64)

    # Start server with WebSocket support
    # socketio.run() replaces app.run() to support WebSocket
    socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True, use_reloader=False)


if __name__ == '__main__':
    main()
