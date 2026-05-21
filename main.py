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


def _patch_webview_qt():
    """
    Patch pywebview's Qt backend without modifying library files:
      1. Fix TypeError crash when any feature permission is requested (e.g. on
         Ctrl+C): PyQt6 requires PermissionPolicy enum, not a bare integer.
      2. Enable JavascriptCanAccessClipboard + JavascriptCanPaste so that
         Ctrl+C copies text in all web components (editors, dialogs, tables).
    """
    try:
        import webview.platforms.qt as _qt
        from qtpy.QtWebEngineWidgets import QWebEnginePage as _Page, QWebEngineSettings as _Settings

        # ── Fix 1: permission handler ────────────────────────────────────────
        def _permission_handler(self, url, feature):
            _pp = getattr(_Page, 'PermissionPolicy', None)
            _granted = _pp.PermissionGrantedByUser if _pp is not None else 1
            self.setFeaturePermission(url, feature, _granted)

        _qt.BrowserView.WebPage.onFeaturePermissionRequested = _permission_handler

        # ── Fix 2: clipboard settings ────────────────────────────────────────
        _orig_init = _qt.BrowserView.__init__

        def _patched_init(self, window):
            _orig_init(self, window)
            try:
                wa = _Settings.WebAttribute
                self.profile.settings().setAttribute(wa.JavascriptCanAccessClipboard, True)
                self.profile.settings().setAttribute(wa.JavascriptCanPaste, True)
            except Exception:
                pass

        _qt.BrowserView.__init__ = _patched_init

        # ── Fix 3: force Ctrl+C/V/X/A via page actions ──────────────────────
        from qtpy.QtCore import Qt as _Qt

        def _key_press(self, event):
            if event.modifiers() == _Qt.KeyboardModifier.ControlModifier:
                _wa = _Page.WebAction
                _actions = {
                    _Qt.Key.Key_C: _wa.Copy,
                    _Qt.Key.Key_V: _wa.Paste,
                    _Qt.Key.Key_X: _wa.Cut,
                    _Qt.Key.Key_A: _wa.SelectAll,
                    _Qt.Key.Key_Z: _wa.Undo,
                    _Qt.Key.Key_Y: _wa.Redo,
                }
                _action = _actions.get(event.key())
                if _action is not None:
                    self.webview.page().triggerAction(_action)
                    return
            super(_qt.BrowserView, self).keyPressEvent(event)

        _qt.BrowserView.keyPressEvent = _key_press

    except Exception:
        pass


_patch_webview_qt()

from ui import main

if __name__ == "__main__":
    main()
