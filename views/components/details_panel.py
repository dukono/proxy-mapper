"""DetailsPanel component — request/response side-by-side viewer."""

import json
import html as html_mod
from nicegui import ui
from utils import format_size, format_duration, get_status_color, get_method_color

ui.add_css('.details-panel * { user-select: text !important; cursor: text; }')


def _copy_btn(text: str):
    import json as _json
    encoded = _json.dumps(text)
    # Avoid navigator.clipboard — it triggers a Qt permission dialog in pywebview
    # that crashes due to a PyQt6 enum type mismatch. Use execCommand fallback only.
    js = (
        "(function(){"
        f"  var t={encoded};"
        "  var el=document.createElement('textarea');"
        "  el.value=t;"
        "  el.style.position='fixed';"
        "  el.style.top='0';"
        "  el.style.left='0';"
        "  el.style.opacity='0';"
        "  document.body.appendChild(el);"
        "  el.focus();"
        "  el.select();"
        "  document.execCommand('copy');"
        "  document.body.removeChild(el);"
        "})()"
    )
    async def do_copy():
        await ui.run_javascript(js)
        ui.notify('Copied!', type='positive', timeout=1500)
    ui.button(icon='content_copy', on_click=do_copy) \
        .props('flat round dense size=xs').classes('text-gray-500 hover:text-white w-6 h-6')


def _render_kv_list(items):
    with ui.column().classes('w-full gap-0'):
        for k, v in items:
            with ui.row().classes('w-full gap-0 border-b border-gray-700/40 hover:bg-gray-800/40 items-start'):
                ui.label(k).classes('text-xs text-blue-400 font-mono shrink-0 leading-tight px-2 py-1 w-40').style('user-select:text;cursor:text;')
                ui.label(v).classes('text-xs text-gray-300 font-mono flex-1 break-all leading-tight px-2 py-1').style('user-select:text;cursor:text;')


def _render_body(content: str | None, empty_msg: str = "No body content"):
    if not content:
        with ui.row().classes('w-full h-full items-center justify-center'):
            ui.label(empty_msg).classes('text-gray-600 text-sm italic')
        return
    try:
        parsed = json.loads(content)
        pretty = json.dumps(parsed, indent=2)
    except Exception:
        pretty = content

    escaped = html_mod.escape(pretty)
    with ui.column().classes('w-full min-w-0 relative'):
        with ui.row().classes('absolute top-1 right-2 z-10'):
            _copy_btn(pretty)
        ui.html(
            f'<pre style="margin:0;white-space:pre-wrap;word-break:break-all;user-select:text;cursor:text;">{escaped}</pre>'
        ).classes(
            'w-full max-w-full min-w-0 text-xs text-gray-300 font-mono bg-gray-950 rounded p-3 overflow-auto'
        )


def _vertical_tabs(tab_names: list, tab_labels: list):
    """Render vertical tab sidebar + panels, return panels widget."""
    with ui.element('div').classes('w-12 h-full bg-gray-800/50 border-r border-gray-700 flex flex-col'):
        tabs = ui.tabs().classes('w-full h-full').props('vertical dense')
        with tabs:
            for name, label in zip(tab_names, tab_labels):
                ui.tab(name, label=label).classes('text-xs px-1 py-1 min-h-0')
    panels = ui.tab_panels(tabs, value=tab_names[0]).classes('flex-1 h-full')
    return panels


class DetailsPanel:
    """Side-by-side request / response detail panel with vertical tabs."""

    def __init__(self, ui_instance=None):
        self._container = None
        self._ui = ui_instance

    def render(self, container, entry=None):
        self._container = container
        container.clear()

        if entry is None:
            with container:
                with ui.column().classes('w-full h-full items-center justify-center gap-2'):
                    ui.icon('arrow_upward', size='32px').classes('text-gray-700')
                    ui.label("Select a request to inspect it").classes('text-gray-600 text-sm')
            return

        with container:
            with ui.element('div').classes('flex w-full h-full details-panel'):
                self._render_request(entry)
                self._render_response(entry)

    # ── request panel ────────────────────────────────────────────────────────

    def _render_request(self, entry):
        with ui.element('div').classes('w-1/2 h-full flex flex-col border-r border-gray-700'):
            # Title bar
            original_url = entry.original_url or entry.request.url
            with ui.row().classes('w-full bg-gray-800/80 px-3 py-1.5 border-b border-gray-700 items-center gap-2 shrink-0'):
                method = entry.request.method
                ui.label(method).classes(
                    f'text-xs font-mono font-bold px-2 py-0.5 rounded bg-gray-700/80 {get_method_color(method)}'
                )
                ui.label(original_url).classes('text-xs text-gray-400 font-mono flex-1 truncate leading-tight')
                _copy_btn(original_url)

            with ui.element('div').classes('flex flex-1 min-h-0'):
                qry_count = len(entry.request.query_params) if entry.request.query_params else 0
                qry_label = f'Q{qry_count}' if qry_count else 'Qry'
                panels = _vertical_tabs(['Header', 'Query', 'Body'], ['Hdr', qry_label, 'Bdy'])
                with panels:
                    with ui.tab_panel('Header').classes('p-0 h-full'):
                        with ui.scroll_area().classes('w-full h-full'):
                            if entry.request.headers:
                                _render_kv_list([(h.name, h.value) for h in entry.request.headers])
                            else:
                                ui.label("No headers").classes('text-gray-600 text-xs italic p-4')

                    with ui.tab_panel('Query').classes('p-0 h-full'):
                        with ui.scroll_area().classes('w-full h-full'):
                            if entry.request.query_params:
                                _render_kv_list(entry.request.query_params.items())
                            else:
                                with ui.column().classes('w-full h-full items-center justify-center'):
                                    ui.label("No query parameters").classes('text-gray-600 text-xs italic')

                    with ui.tab_panel('Body').classes('p-0 h-full'):
                        with ui.scroll_area().classes('w-full h-full p-2'):
                            _render_body(entry.request.content)

    # ── response panel ───────────────────────────────────────────────────────

    def _render_response(self, entry):
        with ui.element('div').classes('w-1/2 h-full flex flex-col'):
            # Title bar
            with ui.row().classes('w-full bg-gray-800/80 px-3 py-1.5 border-b border-gray-700 items-center gap-2 shrink-0'):
                if entry.response:
                    code = entry.response.status_code
                    ui.label(f"HTTP {code}").classes(
                        f'text-xs font-mono font-bold px-2 py-0.5 rounded bg-gray-700/80 {get_status_color(code)}'
                    )
                    ui.label(
                        f"{format_duration(entry.response.duration_ms)}  ·  {format_size(entry.response.size)}"
                    ).classes('text-xs text-gray-500 font-mono flex-1')
                    if entry.mocked:
                        ui.button('✏ MOCK', on_click=lambda e=entry: self._open_mock_editor(e)) \
                            .props('dense no-caps') \
                            .classes('text-xs font-bold') \
                            .style('background:rgba(168,85,247,0.2); color:#c084fc; padding:1px 8px; border-radius:4px; border:1px solid rgba(168,85,247,0.4);') \
                            .tooltip('Edit mapping')
                        n_conflicts = self._count_conflicts_for_entry(entry)
                        if n_conflicts:
                            ui.icon('warning_amber', size='16px') \
                                .classes('text-yellow-400') \
                                .tooltip(f'⚠ {n_conflicts} conflicto(s) detectado(s) para este mapping')
                else:
                    with ui.row().classes('items-center gap-2 flex-1'):
                        ui.html('<span style="display:inline-block;width:10px;height:10px;border-radius:50%;border:2px solid #60a5fa;border-top-color:transparent;animation:spin .8s linear infinite;"></span>')
                        ui.label("Waiting for response…").classes('text-xs text-gray-500 italic')

            with ui.element('div').classes('flex flex-1 min-h-0'):
                panels = _vertical_tabs(['Header', 'Body'], ['Hdr', 'Bdy'])
                with panels:
                    with ui.tab_panel('Header').classes('p-0 h-full'):
                        with ui.scroll_area().classes('w-full h-full'):
                            if entry.response and entry.response.headers:
                                _render_kv_list([(h.name, h.value) for h in entry.response.headers])
                            else:
                                ui.label("No headers").classes('text-gray-600 text-xs italic p-4')

                    with ui.tab_panel('Body').classes('p-0 h-full'):
                        with ui.scroll_area().classes('w-full h-full p-2'):
                            content = entry.response.content if entry.response else None
                            msg = "Pending…" if not entry.response else "No body content"
                            _render_body(content, empty_msg=msg)

    def _count_conflicts_for_entry(self, entry) -> int:
        """Number of conflicting mappings for the given traffic entry."""
        import os
        if not self._ui or not hasattr(self._ui, 'mapping_loader'):
            return 0
        fi = self._ui.mapping_loader.file_info
        if not fi:
            return 0
        mapping_file_abs = getattr(entry, 'mapping_file', None)
        if not mapping_file_abs:
            return 0
        try:
            from config import get_global_config
            mappings_dir = get_global_config().get_mappings_dir()
            rel = os.path.relpath(mapping_file_abs, mappings_dir)
        except Exception:
            return 0
        rule_id = None
        for rid, info in fi.items():
            if info.get('request_file') == rel:
                rule_id = rid
                break
        if not rule_id:
            return 0
        if hasattr(self._ui, 'mappings_view') and getattr(self._ui.mappings_view, '_conflict_cache', None):
            pairs = self._ui.mappings_view._conflict_cache.get('pairs', [])
        else:
            try:
                from views.mappings import detect_conflicts
                pairs = detect_conflicts(fi)
            except Exception:
                return 0
        return sum(1 for a, b in pairs if a == rule_id or b == rule_id)

    def _open_mock_editor(self, entry):
        """Open MappingEditorDialog for the mapping that served this entry."""
        import os
        from dialogs.mapping_editor import MappingEditorDialog
        from config import get_global_config

        if not self._ui or not hasattr(self._ui, 'mapping_loader'):
            return

        entry_rule_id = getattr(entry, 'rule_id', None)
        # mapping_file is an absolute path; file_info stores relative paths
        mapping_file_abs = getattr(entry, 'mapping_file', None)
        fi = self._ui.mapping_loader.file_info

        # Convert absolute mapping_file to relative (to mappings_dir) for lookup
        rel_source = None
        if mapping_file_abs:
            try:
                mappings_dir = get_global_config().get_mappings_dir()
                rel_source = os.path.relpath(mapping_file_abs, mappings_dir)
            except Exception:
                rel_source = mapping_file_abs

        # Resolve current rule_id: entry.rule_id may be stale if mappings were
        # reloaded after the request was captured (rules get new IDs on each load).
        rule_id = None
        if entry_rule_id and entry_rule_id in fi:
            rule_id = entry_rule_id
        elif rel_source:
            for rid, info in fi.items():
                if info.get('request_file') == rel_source:
                    rule_id = rid
                    break

        if not rule_id:
            ui.notify("Mapping file not found", type='negative')
            return

        mapping_data = fi.get(rule_id)
        if mapping_data:
            MappingEditorDialog(self._ui).show_edit(rule_id, mapping_data)
        else:
            ui.notify("Mapping file not found", type='negative')
