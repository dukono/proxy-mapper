"""DetailsPanel component — request/response side-by-side viewer."""

import json
import html as html_mod
from nicegui import ui
from utils import format_size, format_duration, get_status_color, get_method_color

ui.add_css('.details-panel * { user-select: text !important; cursor: text; }')


def _copy_btn(text: str):
    import json as _json
    encoded = _json.dumps(text)
    js = (
        "(function(){"
        f"  var t={encoded};"
        "  if(navigator.clipboard&&window.isSecureContext){"
        "    navigator.clipboard.writeText(t).catch(function(){"
        "      _fallbackCopy(t);"
        "    });"
        "  } else { _fallbackCopy(t); }"
        "  function _fallbackCopy(s){"
        "    var el=document.createElement('textarea');"
        "    el.value=s; el.style.position='fixed'; el.style.opacity='0';"
        "    document.body.appendChild(el); el.focus(); el.select();"
        "    document.execCommand('copy');"
        "    document.body.removeChild(el);"
        "  }"
        "  return true;"
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
                panels = _vertical_tabs(['Header', 'Query', 'Body'], ['Hdr', 'Qry', 'Bdy'])
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
                else:
                    ui.label("Pending…").classes('text-xs text-gray-600 italic flex-1')

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

    def _open_mock_editor(self, entry):
        """Open MappingEditorDialog for the mapping that served this entry."""
        from dialogs.mapping_editor import MappingEditorDialog
        from pathlib import Path
        import json as _json

        if not self._ui:
            return

        # Try to find the rule that matched this entry
        rule_id    = getattr(entry, 'rule_id', None)
        source_file = getattr(entry, 'mapping_file', None) or getattr(entry, 'source_file', None)

        mapping_data = None

        # Primary: load from source_file
        if source_file:
            mappings_dir = self._ui.config.get_mappings_dir()
            full_path = Path(mappings_dir) / source_file
            try:
                content = _json.loads(full_path.read_text())
                response = content.get('response', {})
                body_file = response.get('bodyFileName', '')
                profile = self._ui.config.get_current_profile()
                mapping_type = profile.mapping_type if profile else 'default'
                mapping_data = {
                    'request_file':  source_file,
                    'response_file': body_file,
                    'full_json':     _json.dumps(content, indent=2),
                    'mapping_type':  mapping_type,
                }
            except Exception:
                pass

        # Fallback: look up in mapping_loader file_info
        if mapping_data is None and rule_id and hasattr(self._ui, 'mapping_loader'):
            mapping_data = self._ui.mapping_loader.file_info.get(rule_id)

        if mapping_data and rule_id:
            MappingEditorDialog(self._ui).show_edit(rule_id, mapping_data)
        elif mapping_data:
            # No rule_id but we have the file — open in create mode pre-filled
            MappingEditorDialog(self._ui).show_create(mapping_data)
        else:
            ui.notify("Mapping file not found", type='negative')
