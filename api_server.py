# ============================================================
# CardioTwin - Root Entrypoint Launcher
# Launches the CardioTwin Multimodal Digital Twin Backend Engine
# ============================================================

import sys
import os

# Add root and backend directory to module search path
root_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(root_dir, "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from backend.api_server import app, socketio, PORT


if __name__ == '__main__':
    print(f"[INFO] CardioTwin Master Server starting from {backend_dir}...")
    print(f"[INFO] Listening on http://0.0.0.0:{PORT}")
    socketio.run(app, host='0.0.0.0', port=PORT, debug=False, allow_unsafe_werkzeug=True)
