"""Monitor view — coordinator for traffic list and request details."""

import json
from nicegui import ui

from config import get_global_config
from utils import get_logger
from .components import (
    TrafficFilter,
    TrafficTable,
    DetailsPanel,
    EditRepeatDialog,
    send_via_proxy,
    headers_for_repeat,
)

log = get_logger("MONITOR")

_CSS = '''
    @keyframes spin { 0%{transform:rotate(0deg)} 100%{transform:rotate(360deg)} }
    .monitor-table .q-table tbody tr { cursor:pointer !important; }
    .monitor-table .q-table thead th { background:#111827 !important; color:#6b7280 !important;
        font-size:10px !important; text-transform:uppercase; letter-spacing:.05em; }
    .monitor-table .q-table tbody td { padding: 3px 6px !important; border-bottom: 1px solid rgba(55,65,81,0.5) !important; }
    .monitor-table .q-table th:first-child,
    .monitor-table .q-table td:first-child { display:none !important; }
'''

_FILTER_BAR_CSS = '''<style>
    .filter-bar .q-field { padding-bottom:0 !important; }
    .filter-bar .q-field__control,
    .filter-bar .q-field--dense .q-field__control,
    .filter-bar .q-field--outlined.q-field--dense .q-field__control {
        min-height:24px !important; height:24px !important;
        padding-top:0 !important; padding-bottom:0 !important;
    }
    .filter-bar .q-field__native,
    .filter-bar .q-field__input {
        min-height:24px !important; height:24px !important;
        padding-top:0 !important; padding-bottom:0 !important;
        line-height:24px !important; font-size:11px !important;
    }
    .filter-bar .q-field__marginal,
    .filter-bar .q-field__append,
    .filter-bar .q-field__prepend {
        min-height:24px !important; height:24px !important;
    }
</style>'''


class MonitorView:
    """Coordinator: filter bar + traffic table + details panel."""

    def __init__(self, ui_instance):
        self.ui = ui_instance
        self._filter = TrafficFilter(on_change=self._refresh_table)
        self._table  = TrafficTable(
            on_select=self._on_select,
            on_contextmenu=self._on_contextmenu,
            on_delete=self._on_delete_entries,
        )
        self._details = DetailsPanel(ui_instance)
        self._table_container   = None
        self._details_container = None
        self._counter_label     = None
        self._filter_row        = None

    # ── setup ─────────────────────────────────────────────────────────────────

    def setup(self):
        ui.add_css(_CSS)
        ui.add_head_html(_FILTER_BAR_CSS)

        with ui.column().classes('w-full h-full flex flex-col gap-0'):

            # ── Card 1: filter bar + traffic table ────────────────────────────
            with ui.card().classes('w-full flex-[60] bg-gray-900 monitor-table overflow-hidden').style('margin:0; border-radius:0; border-bottom:1px solid #374151;'):
                with ui.column().classes('w-full h-full'):

                    # Filter bar (hidden by default, shown with Ctrl+F)
                    self._filter_row = ui.row().classes('filter-bar w-full items-center gap-2 px-2 shrink-0 border-b border-gray-700/50').style(
                            'height:38px; min-height:38px; overflow:hidden; flex-wrap:nowrap; display:none;')
                    with self._filter_row:
                        self._filter.render()
                        # Request counter badge
                        self._counter_label = ui.badge('0', color='grey-8') \
                            .props('rounded').classes('text-xs font-mono shrink-0 ml-1')

                    # Table
                    self._table_container = ui.row().classes('w-full flex-1')
                    self._refresh_table()

            # ── Card 2: request / response details ────────────────────────────
            with ui.card().classes('w-full flex-[40] bg-gray-900 overflow-hidden').style('margin:0; border-radius:0;'):
                self._details_container = ui.row().classes('w-full h-full')
                self._details.render(self._details_container)

        # Keyboard handler (registered once, outside cards)
        self._table.setup_keyboard()
        ui.keyboard(on_key=self._on_key, ignore=[])

    # ── public refresh API ────────────────────────────────────────────────────

    def render_traffic_list(self):
        self._refresh_table()

    def render_details_content(self):
        self._details.render(self._details_container, self.ui.selected_entry)

    # ── private ───────────────────────────────────────────────────────────────

    def _refresh_table(self):
        filtered = self._filter.filter(self.ui.traffic)
        self._table.render(self._table_container, filtered)

        # Update counter
        if self._counter_label:
            total    = len(self.ui.traffic)
            shown    = len(filtered)
            label    = f"{shown}" if shown == total else f"{shown}/{total}"
            self._counter_label.set_text(label)
            self._counter_label.props(f"color={'grey-7' if shown == total else 'blue-8'} rounded")

    def _on_select(self, entry):
        self.ui.select_entry(entry)

    def _on_contextmenu(self, entry, x, y):
        op = entry.operation_type  # 'normal', 'mock', 'redirect'

        menu_items = [
            ('↺  Repeat',          lambda e=entry: self._repeat(e)),
            ('✎  Edit and Repeat', lambda e=entry: self._edit_and_repeat(e)),
        ]

        if op == 'mock':
            menu_items.append(('✏️  Edit Mock', lambda e=entry: self._edit_mapping(e)))
        elif op == 'redirect':
            menu_items.append(('✏️  Edit Redirect', lambda e=entry: self._edit_mapping(e)))
        else:
            # Normal (real) request — offer to create a new mapping from it
            menu_items.append(('➕  Add as Mapping', lambda e=entry: self._create_mapping(e)))

        self._table.show_context_menu(entry, x, y, menu_items)

    def _repeat(self, entry):
        url = entry.original_url or entry.request.url
        ui.notify(f"↺ {entry.request.method} {url[:60]}", type='info', timeout=2000)
        send_via_proxy(
            entry.request.method, url,
            headers=headers_for_repeat(entry.request.headers),
            body=entry.request.content,
        )

    def _edit_and_repeat(self, entry):
        EditRepeatDialog(self.ui).show(entry)

    def _edit_mapping(self, entry):
        """Edit existing mapping for this request."""
        from config.globals import get_global_proxy
        import json as _json
        from pathlib import Path

        proxy = get_global_proxy()
        if not proxy or not proxy.get_rules_engine():
            ui.notify("No mapping engine available", type='negative')
            return

        rules_engine = proxy.get_rules_engine()

        # Build request_data identical to what ProxyAddon.request() builds
        raw_path     = entry.request.path
        clean_path   = raw_path.split('?')[0]
        query_string = raw_path.split('?')[1] if '?' in raw_path else ""

        request_data = {
            "url":          entry.request.url,
            "host":         entry.request.host,
            "path":         clean_path,
            "path_full":    raw_path,
            "query_string": query_string,
            "method":       entry.request.method,
            "headers":      {h.name: h.value for h in entry.request.headers},
            "query_params": entry.request.query_params or {},
            "body":         entry.request.content or "",
        }

        matching_rules = rules_engine.find_matching_rules(request_data)

        if not matching_rules:
            ui.notify("No mapping found for this request", type='negative')
            return

        rule = matching_rules[0]

        # ── Primary path: rule carries its source_file directly ──────────────
        mapping_data = None

        if rule.source_file:
            mappings_dir = self.ui.config.get_mappings_dir()
            full_path    = Path(mappings_dir) / rule.source_file
            try:
                content      = _json.loads(full_path.read_text())
                response     = content.get("response", {})
                body_file    = content.get("request", {}).get("bodyFileName") or response.get("bodyFileName", "")
                profile      = self.ui.config.get_current_profile()
                mapping_type = profile.mapping_type if profile else "default"
                mapping_data = {
                    "request_file":  rule.source_file,
                    "response_file": body_file,
                    "full_json":     _json.dumps(content, indent=2),
                    "mapping_type":  mapping_type,
                }
            except Exception as exc:
                log.warning("Could not read source_file %s: %s", rule.source_file, exc)

        # ── Fallback: look up file_info index by rule ID ─────────────────────
        if mapping_data is None and hasattr(self.ui, 'mapping_loader'):
            mapping_data = self.ui.mapping_loader.file_info.get(rule.id)

        if mapping_data:
            from dialogs.mapping_editor import MappingEditorDialog
            MappingEditorDialog(self.ui).show_edit(rule.id, mapping_data)
        else:
            ui.notify("Mapping data not found", type='negative')

    def _create_mapping(self, entry):
        """Create new mapping pre-filled with the captured request data."""
        from dialogs.mapping_editor import MappingEditorDialog

        config = get_global_config()
        profile = config.get_current_profile()
        mapping_type = profile.mapping_type if profile else 'Wire'

        method     = entry.request.method
        raw_path   = entry.request.path          # includes ?query=string
        clean_path = raw_path.split('?')[0]
        query_params = entry.request.query_params or {}
        status     = entry.response.status_code if entry.response else 200

        # Derive a safe filename from the last path segment
        last_segment = clean_path.rstrip('/').split('/')[-1] or 'mapping'
        suggested_filename = f"{method.lower()}-{last_segment}.json"

        # Try to use the actual response body as body file content
        resp_body = ''
        if entry.response and entry.response.content:
            try:
                resp_body = json.dumps(json.loads(entry.response.content), indent=2)
            except Exception:
                resp_body = entry.response.content[:5000]

        if mapping_type == 'Wire':
            body_filename = f"responses/{method.lower()}-{last_segment}.json"
            mapping_template = {
                "request": {
                    "method": method,
                    "urlPath": clean_path,
                },
                "response": {
                    "status": status,
                    "headers": {"Content-Type": "application/json"},
                    "bodyFileName": body_filename,
                    "transformers": ["body-transformer"],
                }
            }
            # Add ALL query params as equalTo matchers
            if query_params:
                mapping_template["request"]["queryParameters"] = {
                    k: {"equalTo": v} for k, v in query_params.items()
                }
            body_content = resp_body or '{\n  "message": "Mock response"\n}'
        else:
            body_filename = ''
            # For default type: include full path + query string as matchValue
            if query_params:
                qs = '&'.join(f"{k}={v}" for k, v in query_params.items())
                match_value = f"{clean_path}?{qs}"
            else:
                match_value = clean_path

            mapping_template = {
                "request": {
                    "method": method,
                    "matchType": "contains",
                    "matchValue": match_value,
                },
                "response": {
                    "status": status,
                    "headers": {"Content-Type": "application/json"},
                    "body": resp_body or '{"message": "Mock response"}',
                }
            }
            body_content = ''

        mapping_data = {
            "full_json":     json.dumps(mapping_template, indent=2),
            "request_file":  suggested_filename,
            "response_file": body_filename,
            "_body_content": body_content,
        }

        MappingEditorDialog(self.ui).show_create(mapping_data)

    def _on_delete_entries(self, entry_ids: list):
        """Remove entries by id from the global traffic list."""
        from config.globals import get_global_traffic, set_global_traffic, increment_traffic_version
        id_set = set(entry_ids)
        traffic = get_global_traffic()
        traffic[:] = [e for e in traffic if e.id not in id_set]
        set_global_traffic(traffic)
        self.ui.traffic = traffic
        increment_traffic_version()
        # Clear details if selected entry was deleted
        if self.ui.selected_entry and self.ui.selected_entry.id in id_set:
            self.ui.selected_entry = None
            self._details.render(self._details_container)
        count = len(id_set)
        ui.notify(f"Deleted {count} entr{'y' if count == 1 else 'ies'}", type='warning', timeout=2000)
        self._refresh_table()

    def _on_key(self, e):
        if not e.action.keydown:
            return
        if e.modifiers.ctrl and str(e.key) == 'f':
            self._show_filter()
        elif str(e.key) == 'Escape' and self._filter_row:
            self._hide_filter()

    def _show_filter(self):
        if self._filter_row:
            self._filter_row.style('display:flex;')
        if hasattr(self._filter, '_input_ref'):
            self._filter._input_ref.run_method('focus')

    def _hide_filter(self):
        if self._filter_row:
            self._filter_row.style('display:none;')
        if hasattr(self._filter, '_input_ref'):
            self._filter._input_ref.set_value('')
            self._filter._set_text('')
