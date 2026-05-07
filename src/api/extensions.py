"""
Flask extensions initialization.
Extensions are initialized here and configured in create_app().
"""

from flask_jwt_extended import JWTManager
from flask_socketio import SocketIO

# JWT Manager for authentication
jwt = JWTManager()

# SocketIO for real-time WebSocket communication
socketio = SocketIO()
