"""Base UI class with initialization and shared utilities."""

import os
from typing import List, Optional, Dict
from queue import Queue

from nicegui import ui, app

from models import TrafficEntry
from config import get_global_config, get_global_proxy, get_global_queue
from utils import format_size, format_duration, get_status_color, get_method_color, get_logger
from services import MappingLoader

log = get_logger("UI")


class ProxyUIBase:
    """Base class for Proxy UI with initialization and common utilities."""

    def __init__(self):
        # Use global proxy (shared across reloads)
        self.proxy = get_global_proxy()
        self.update_queue = get_global_queue()
        self.config = get_global_config()

        # Restore traffic from storage or empty
        self.traffic: List[TrafficEntry] = app.storage.general.get('traffic', [])
        if not isinstance(self.traffic, list):
            self.traffic = []

        self.selected_entry: Optional[TrafficEntry] = None
        self.filter_text = ""
        self.auto_scroll = True
        self.paused = False

        # UI references
        self.details_panel = None
        self.main_tabs = None
        self.traffic_list = None
        self.start_btn = None

        # Mapping service — single source of truth for file_info
        self.mapping_loader = MappingLoader(self.proxy, self.config)

    # ── backward compat: views still access ui._mapping_file_info ────────────
    @property
    def _mapping_file_info(self) -> Dict:
        return self.mapping_loader.file_info

    def init(self):
        """Initialize the UI."""
        from config.globals import get_global_traffic, set_global_traffic, increment_traffic_version

        self.setup_ui()

        # Register callback to receive traffic from proxy
        def on_traffic_update(entry):
            """Callback when new traffic arrives from proxy."""
            global_traffic = get_global_traffic()
            
            # Check if entry with same ID already exists
            existing_idx = None
            for idx, existing in enumerate(global_traffic):
                if existing.id == entry.id:
                    existing_idx = idx
                    break
            
            if existing_idx is not None:
                # Update existing entry (preserve position)
                global_traffic[existing_idx] = entry
            else:
                # Insert new entry at beginning
                global_traffic.insert(0, entry)
            
            # Keep max 500 entries
            if len(global_traffic) > 500:
                global_traffic[:] = global_traffic[:500]
            set_global_traffic(global_traffic)
            increment_traffic_version()   # ← marca que algo cambió

        self.proxy.set_callback(on_traffic_update)

        # Copy global traffic to instance
        self.traffic = list(get_global_traffic())
        self.render_traffic_list()

        # Register a timer for this specific page instance
        ui.timer(0.3, self.process_updates)

        # Restore button state based on proxy status
        ui.timer(0.5, self._sync_button_state, once=True)

        # Auto-start proxy if not running
        if not self.proxy.running:
            ui.timer(0.8, self._auto_start_proxy, once=True)

        # Auto-load mappings from current profile
        ui.timer(1.0, self._auto_load_mappings, once=True)

    def _auto_start_proxy(self):
        """Auto-start proxy on initialization."""
        try:
            self.proxy.start_in_thread()
            if self.start_btn:
                self.start_btn.set_text("STOP")
                self.start_btn.classes('bg-red-600', remove='bg-green-600')
            ui.notify(f"Proxy auto-started on port {self.proxy.port}", type='positive')
        except Exception as e:
            ui.notify(f"Failed to auto-start proxy: {str(e)}", type='negative')

    def _auto_load_mappings(self):
        """Reload all mappings from the current profile directory."""
        import threading
        from config.globals import is_mappings_loaded, set_mappings_loaded
        if is_mappings_loaded():
            self.refresh_mappings()
            return
        try:
            count = self.mapping_loader.load_all()
            if count == 0:
                log.warning("No mappings loaded (directory empty or not found)")
            else:
                set_mappings_loaded(True)
            self.refresh_mappings()
            # Pre-compute conflict detection in background so it's ready when tab opens
            if hasattr(self, 'mappings_view'):
                mv = self.mappings_view
                def _bg():
                    try:
                        mv._conflict_cache = None
                        mv._get_conflicts()
                    except Exception:
                        pass
                threading.Thread(target=_bg, daemon=True).start()
        except Exception as e:
            log.error("Error auto-loading mappings: %s", e)

    def _sync_button_state(self):
        """Synchronize button state with proxy status."""
        if self.start_btn:
            if self.proxy.running:
                self.start_btn.set_text("STOP")
                self.start_btn.classes('bg-red-600', remove='bg-green-600')
            else:
                self.start_btn.set_text("START")
                self.start_btn.classes('bg-green-600', remove='bg-red-600')

    # Utility methods
    format_size = staticmethod(format_size)
    format_duration = staticmethod(format_duration)
    get_status_color = staticmethod(get_status_color)
    get_method_color = staticmethod(get_method_color)

    def setup_ui(self):
        """Set up the main UI. Override in subclasses."""
        raise NotImplementedError

    def render_traffic_list(self):
        """Render the traffic list. Override in subclasses."""
        raise NotImplementedError

    def process_updates(self):
        """Process update queue. Override in subclasses."""
        raise NotImplementedError
