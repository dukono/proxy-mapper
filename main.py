#!/usr/bin/env python3
"""
Proxy Monitor - A modern Python proxy with UI for monitoring and mocking HTTP traffic.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Single-instance lock ───────────────────────────────────────────────────
# NiceGUI re-executes main.py via runpy for 404 handling (run_name='__main__').
# We use an env-var flag so only the *real* entry point runs the lock check.
_IS_NICEGUI_RERUN = os.environ.get("_PROXYMONITOR_STARTED") == "1"

if not _IS_NICEGUI_RERUN:
    os.environ["_PROXYMONITOR_STARTED"] = "1"   # mark for any future re-runs

    import socket as _socket

    _LOCK_PORT = 47321

    def _acquire_single_instance_lock():
        sock = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        sock.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 0)
        try:
            sock.bind(("127.0.0.1", _LOCK_PORT))
            sock.listen(1)
            return sock
        except OSError:
            sock.close()
            return None

    _lock_socket = _acquire_single_instance_lock()

    if _lock_socket is None:
        import webbrowser
        webbrowser.open("http://127.0.0.1:8081")
        print("Proxy Monitor is already running. Opening UI in browser.")
        sys.exit(0)

# ── Force Qt backend for pywebview ────────────────────────────────────────
os.environ["PYWEBVIEW_GUI"] = "qt"
os.environ["QT_QPA_DESKTOP_FILE_NAME"] = "proxymonitor"

from ui import main

if __name__ == "__main__":
    main()
