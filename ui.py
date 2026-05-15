"""
Refactored UI module using new modular structure.
"""

import os
import json
from typing import List, Optional, Dict

from nicegui import ui, app

from models import TrafficEntry
from config import get_global_config, get_global_proxy, get_global_queue
from utils import format_size, format_duration, get_status_color, get_method_color, get_logger
from strategies import MappingStrategyFactory
from ui_components.base import ProxyUIBase

log = get_logger("UI")


class ProxyUIRefactored(ProxyUIBase):
    """Refactored Proxy UI class."""

    def __init__(self):
        super().__init__()

    def setup_ui(self):
        """Set up the main UI layout."""
        ui.page_title("Proxy Monitor")
        ui.dark_mode().enable()
        # Global fix: intercept Ctrl+C to avoid navigator.clipboard permission
        # request that crashes pywebview due to PyQt6 enum type mismatch.
        ui.add_head_html('''<script>
        document.addEventListener("keydown", function(e) {
            if ((e.ctrlKey || e.metaKey) && e.key === "c") {
                var sel = window.getSelection();
                if (sel && sel.toString().length > 0) {
                    e.preventDefault();
                    var el = document.createElement("textarea");
                    el.value = sel.toString();
                    el.style.cssText = "position:fixed;top:0;left:0;opacity:0;";
                    document.body.appendChild(el);
                    el.focus();
                    el.select();
                    document.execCommand("copy");
                    document.body.removeChild(el);
                }
            }
        }, true);
        </script>''')
        ui.add_css('''
            .traffic-row:hover { background-color: #374151 !important; }
            .traffic-row.selected { background-color: #1e40af !important; }
            .details-panel { border-left: 1px solid #374151; }
            .nicegui-content { padding: 0 !important; }
            .nav-btn { border-bottom: 2px solid transparent; border-radius: 0 !important; }
            .nav-btn.active { border-bottom: 2px solid #3b82f6; color: #ffffff !important; }
            .main-panels {
                position: fixed !important;
                top: 44px !important;
                left: 0 !important; right: 0 !important; bottom: 0 !important;
                overflow: hidden !important;
            }

            /* ── Global compact field style (matches filter-bar) ── */
            .q-field--outlined.q-field--dense .q-field__control {
                min-height: 28px !important;
                height: 28px !important;
                background: #1f2937 !important;
                border-radius: 4px !important;
            }
            .q-field--outlined.q-field--dense .q-field__control:before {
                border-color: #374151 !important;
            }
            .q-field--outlined.q-field--dense .q-field__control:hover:before {
                border-color: #4b5563 !important;
            }
            .q-field--outlined.q-field--dense.q-field--focused .q-field__control:after {
                border-color: #3b82f6 !important;
            }
            .q-field--outlined.q-field--dense .q-field__native,
            .q-field--outlined.q-field--dense .q-field__input,
            .q-field--outlined.q-field--dense .q-field__prefix,
            .q-field--outlined.q-field--dense .q-field__suffix {
                min-height: 28px !important;
                height: 28px !important;
                line-height: 28px !important;
                color: #d1d5db !important;
                font-size: 12px !important;
                padding-top: 0 !important;
                padding-bottom: 0 !important;
            }
            .q-field--outlined.q-field--dense .q-field__marginal {
                height: 28px !important;
                color: #6b7280 !important;
            }
            .q-field--outlined.q-field--dense .q-field__label {
                font-size: 12px !important;
                color: #6b7280 !important;
            }
            .q-field--outlined.q-field--dense { padding-bottom: 0 !important; }

            /* ── All text selectable globally ── */
            body * { user-select: text !important; cursor: default; }
            button, .q-btn, .q-tab, [role="button"] { cursor: pointer !important; }
            input, textarea, [contenteditable] { cursor: text !important; }
        ''')

        self._active_tab = 'monitor'

        with ui.header().classes('bg-gray-900 border-b border-gray-700') \
                .style('height:44px; min-height:44px; padding:0; overflow:hidden;'):
            with ui.row().style('display:flex; flex-wrap:nowrap; width:100%; height:100%; align-items:center; padding:0 12px; gap:4px; min-width:0;'):

                # Logo
                ui.label("Proxy Monitor").style('white-space:nowrap; flex-shrink:0; font-size:13px; font-weight:700; color:white;')

                # Nav tabs (plain buttons, no Quasar tabs widget)
                self._btn_monitor = ui.button('MONITOR', on_click=lambda: self._switch_tab('monitor')) \
                    .props('flat no-caps dense').classes('nav-btn active') \
                    .style('flex-shrink:0; font-size:11px; font-weight:700; letter-spacing:.05em; color:#9ca3af; height:44px; padding:0 10px;')
                self._btn_mappings = ui.button('MAPPINGS', on_click=lambda: self._switch_tab('mappings')) \
                    .props('flat no-caps dense').classes('nav-btn') \
                    .style('flex-shrink:0; font-size:11px; font-weight:700; letter-spacing:.05em; color:#9ca3af; height:44px; padding:0 10px;')

                # Profile selector
                profile_names = [p.name for p in self.config.profiles]
                self.profile_select = ui.select(
                    options=profile_names,
                    value=self.config.current_profile,
                    on_change=lambda e: self._on_profile_change(e.value)
                ).props('dark outlined dense').style('width:100px; flex-shrink:0;')

                ui.button(icon='settings', on_click=self._show_profile_manager) \
                    .props('flat round dense').style('flex-shrink:0; color:#9ca3af;').tooltip('Profiles')

                ui.button(icon='security', on_click=self._show_cert_settings) \
                    .props('flat round dense').style('flex-shrink:0; color:#9ca3af;').tooltip('Certificate Settings')

                # Spacer
                ui.element('div').style('flex:1; min-width:0;')

                # Right controls
                ui.button(icon='pause', on_click=self.toggle_pause) \
                    .props('flat round dense color=white').style('flex-shrink:0;').tooltip('Pause/Resume')
                ui.button(icon='delete', on_click=self.clear_traffic) \
                    .props('flat round dense color=white').style('flex-shrink:0;').tooltip('Clear')
                self.start_btn = ui.button('START', on_click=self.toggle_proxy) \
                    .props('dense no-caps') \
                    .style('flex-shrink:0; background:#16a34a; color:white; font-size:11px; font-weight:700; padding:0 12px; height:28px; white-space:nowrap; border-radius:4px;')

        # Content panels — shown/hidden via display
        self._panel_monitor = ui.element('div').classes('main-panels').style('display:block;')
        with self._panel_monitor:
            self.setup_monitor_panel()

        self._panel_mappings = ui.element('div').classes('main-panels').style('display:none;')
        with self._panel_mappings:
            self.setup_mappings_panel()

    def _switch_tab(self, tab: str):
        self._active_tab = tab
        if tab == 'monitor':
            self._btn_monitor.classes('active')
            self._btn_mappings.classes(remove='active')
            self._panel_monitor.style('display:block;')
            self._panel_mappings.style('display:none;')
        else:
            self._btn_mappings.classes('active')
            self._btn_monitor.classes(remove='active')
            self._panel_monitor.style('display:none;')
            self._panel_mappings.style('display:block;')
            self.refresh_mappings()

    def setup_monitor_panel(self):
        from views.monitor import MonitorView
        self.monitor_view = MonitorView(self)
        self.monitor_view.setup()

    def setup_mappings_panel(self):
        from views.mappings import MappingsView
        self.mappings_view = MappingsView(self)
        self.mappings_view.setup()

    def render_traffic_list(self):
        if hasattr(self, 'monitor_view'):
            self.monitor_view.render_traffic_list()

    def render_details_content(self):
        if hasattr(self, 'monitor_view'):
            self.monitor_view.render_details_content()

    def refresh_mappings(self):
        if hasattr(self, 'mappings_view'):
            self.mappings_view.refresh()

    def process_updates(self):
        from config.globals import get_global_traffic, get_global_traffic_version

        if self.paused:
            return

        current_version = get_global_traffic_version()
        if current_version == getattr(self, '_last_traffic_version', -1):
            return  # nada cambió

        self._last_traffic_version = current_version
        self.traffic = list(get_global_traffic())
        self.render_traffic_list()

    def toggle_pause(self):
        self.paused = not self.paused

    def clear_traffic(self):
        from config.globals import set_global_traffic
        set_global_traffic([])
        self.traffic = []
        self.render_traffic_list()

    def set_filter(self, text: str):
        self.filter_text = text
        self.render_traffic_list()

    def toggle_proxy(self):
        """Toggle proxy start/stop — always uses the sync-safe stop()."""
        if self.proxy.running:
            self.proxy.stop()               # ← fixed: was calling async stop()
            self.start_btn.set_text("START")
            self.start_btn.classes('bg-green-600', remove='bg-red-600')
        else:
            self.proxy.start_in_thread()
            self.start_btn.set_text("STOP")
            self.start_btn.classes('bg-red-600', remove='bg-green-600')

    def select_entry(self, entry: TrafficEntry):
        self.selected_entry = entry
        self.render_details_content()

    def _on_profile_change(self, profile_name: str):
        from config.globals import set_mappings_loaded
        log.info("Changing profile to: %s", profile_name)
        self.config.set_current_profile(profile_name)
        ui.notify(f"Switched to profile: {profile_name}", type='positive')
        set_mappings_loaded(False)   # force reload for the new profile
        self._auto_load_mappings()
        if hasattr(self, 'mappings_view'):
            self.mappings_view.refresh()

    def _show_profile_manager(self):
        from dialogs.profile_manager import ProfileManagerDialog
        ProfileManagerDialog(self).show()

    def _show_cert_settings(self):
        from dialogs.cert_settings import CertSettingsDialog
        CertSettingsDialog().show()


def create_ui() -> ProxyUIRefactored:
    return ProxyUIRefactored()


# Backwards compatibility
ProxyUI = ProxyUIRefactored

# ---------------------------------------------------------------------------
# Register API router + CORS middleware at module level.
# NiceGUI may re-run this script (via runpy) for 404 handling, so we guard
# against double-registration.
# ---------------------------------------------------------------------------
from api import router as api_router
from fastapi.middleware.cors import CORSMiddleware
from nicegui import app as nicegui_app

# Only include the router if none of its routes are already registered
_api_routes = {r.path for r in nicegui_app.routes}
if not any(r.path.startswith("/api") for r in nicegui_app.routes):
    nicegui_app.include_router(api_router)

try:
    nicegui_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
except RuntimeError:
    pass  # Middleware already added (NiceGUI re-ran this script)


def main():
    from nicegui import app as nicegui_app
    # Force pywebview to use Qt backend directly, skipping the GTK attempt
    nicegui_app.native.start_args['gui'] = 'qt'
    nicegui_app.native.window_args['width'] = 1480  # ← ancho
    nicegui_app.native.window_args['height'] = 800

    proxy_ui = ProxyUIRefactored()
    proxy_ui.init()
    ui.run(title="Proxy Monitor", port=8081, reload=False, show=False, native=True)
