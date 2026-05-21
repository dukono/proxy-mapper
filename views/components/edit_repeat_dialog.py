"""EditRepeatDialog — request editor dialog matching the app dark theme."""

import json as _json
import html as _html
import time
import asyncio

import requests as req_lib
from nicegui import ui, context

from .proxy_sender import HOP_BY_HOP, PROXY_URL

# ── Dark-mode overrides for json_editor (vanilla JSONEditor uses light theme) ─
_JSON_EDITOR_CSS = '''
<style>
/* ── Menu bar (text/tree/table + action buttons) ── */
.jse-menu {
  background: #1f2937 !important;
  border-bottom: 1px solid #374151 !important;
}
.jse-menu button,
.jse-menu .jse-button {
  color: #d1d5db !important;
  background: transparent !important;
}
.jse-menu button:hover,
.jse-menu .jse-button:hover { background: #374151 !important; }
.jse-menu button.jse-selected,
.jse-menu .jse-button.jse-selected {
  background: #1e3a5f !important;
  color: #93c5fd !important;
}

/* ══ FILL LAYOUT ════════════════════════════════════ */
nicegui-json-editor {
  display: flex !important;
  flex-direction: column !important;
  flex: 1 !important;
  min-height: 0 !important;
  width: 100% !important;
  height: 100% !important;
}
nicegui-json-editor > div,
nicegui-json-editor .jse-main {
  flex: 1 !important;
  min-height: 0 !important;
  width: 100% !important;
  height: 100% !important;
  display: flex !important;
  flex-direction: column !important;
}
nicegui-json-editor .jse-contents {
  flex: 1 !important;
  min-height: 0 !important;
  overflow: auto !important;
}
nicegui-json-editor .cm-editor  { flex: 1 !important; height: 100% !important; }
nicegui-json-editor .cm-scroller { flex: 1 !important; overflow: auto !important; }

/* ══ RAW EDITOR (Quasar QEditor) ═══════════════════ */
.raw-editor .q-editor {
  display: flex !important;
  flex-direction: column !important;
  flex: 1 !important;
  min-height: 0 !important;
  height: 100% !important;
  background: #030712 !important;
  border: 1px solid #374151 !important;
  border-radius: 4px !important;
}
.raw-editor .q-editor__toolbar {
  background: #1f2937 !important;
  border-bottom: 1px solid #374151 !important;
  flex-shrink: 0 !important;
}
.raw-editor .q-editor__toolbar .q-btn   { color: #9ca3af !important; }
.raw-editor .q-editor__toolbar .q-btn:hover { background: #374151 !important; }
.raw-editor .q-editor__toolbar .q-separator { background: #374151 !important; }
.raw-editor .q-editor__content {
  flex: 1 !important;
  min-height: 0 !important;
  overflow: auto !important;
  background: #030712 !important;
  color: #e5e7eb !important;
  font-family: monospace !important;
  font-size: 13px !important;
  padding: 12px !important;
  line-height: 1.6 !important;
  caret-color: #e5e7eb !important;
}
.raw-editor .q-editor__content:focus { outline: none !important; }

/* ══ KV EDITOR ══════════════════════════════════════ */
.kv-value-field { display:flex; flex:1; min-width:0; }
.kv-value-field,
.kv-value-field * { pointer-events: auto !important; }
.kv-value-field .q-field { flex:1; min-width:0; margin:0 !important; }
.kv-value-field .q-field__inner { padding:0 !important; margin:0 !important; }
.kv-value-field .q-field__control,
.kv-value-field .q-field__control-container { padding:0 !important; min-height:0 !important; height:auto !important; }
.kv-value-field .q-field__bottom { display:none !important; }
.kv-value-field .q-field__native,
.kv-value-field .q-field__native textarea { padding:2px 6px !important; min-height:0 !important; line-height:1.35 !important; margin:0 !important; }
.kv-value-field textarea { min-height:0 !important; overflow-y:auto !important; margin:0 !important; max-height:72px !important; cursor:text !important; }
.kv-list { gap:0 !important; }
.kv-list > div { margin:0 !important; }

/* ══ TABS / PANELS FLEX CHAIN ═══════════════════════ */
nicegui-tabs,
nicegui-tabs > .q-tabs {
  flex-shrink: 0 !important;
  flex-grow: 0 !important;
  width: 100% !important;
}
nicegui-tab-panels {
  display: flex !important;
  flex-direction: column !important;
  flex: 1 !important;
  min-height: 0 !important;
  width: 100% !important;
  overflow: hidden !important;
}
nicegui-tab-panel {
  display: flex !important;
  flex-direction: column !important;
  flex: 1 !important;
  min-height: 0 !important;
  width: 100% !important;
  overflow: hidden !important;
  height: 100% !important;
}
.body-panels,
.sub-panels {
  flex: 1 !important;
  min-height: 0 !important;
  width: 100% !important;
  display: flex !important;
  flex-direction: column !important;
  overflow: hidden !important;
}
.body-panels .q-tab-panels,
.sub-panels  .q-tab-panels {
  flex: 1 !important;
  min-height: 0 !important;
  width: 100% !important;
  display: flex !important;
  flex-direction: column !important;
  overflow: hidden !important;
}
.body-panels .q-tab-panel,
.body-panels .q-panel-parent,
.body-panels .q-panel,
.sub-panels  .q-tab-panel,
.sub-panels  .q-panel-parent,
.sub-panels  .q-panel {
  flex: 1 !important;
  min-height: 0 !important;
  width: 100% !important;
  display: flex !important;
  flex-direction: column !important;
  overflow: hidden !important;
  padding: 0 !important;
}
/* Exception: panels that need scroll (e.g. Raw HTTP preview) */
.body-panels .q-tab-panel.panel-scrollable,
.sub-panels  .q-tab-panel.panel-scrollable {
  overflow: auto !important;
}

/* ══ RAW BODY TEXTAREA ══════════════════════════════ */
.raw-body-ta {
  flex: 1 !important;
  min-height: 0 !important;
  display: flex !important;
  flex-direction: column !important;
  width: 100% !important;
  height: 100% !important;
}
.raw-body-ta .q-field,
.raw-body-ta .q-field__inner,
.raw-body-ta .q-field__control,
.raw-body-ta .q-field__control-container,
.raw-body-ta .q-field__native {
  flex: 1 !important;
  min-height: 0 !important;
  height: 100% !important;
  display: flex !important;
  flex-direction: column !important;
  padding: 0 !important;
  margin: 0 !important;
}
.raw-body-ta textarea {
  flex: 1 !important;
  min-height: 0 !important;
  height: 100% !important;
  resize: none !important;
  overflow: auto !important;
  font-family: monospace !important;
  font-size: 13px !important;
  line-height: 1.6 !important;
  padding: 10px !important;
  background: #030712 !important;
  color: #e5e7eb !important;
  border: 1px solid #374151 !important;
  border-radius: 4px !important;
  box-sizing: border-box !important;
}
</style>'''


class EditRepeatDialog:
    """Full-screen dark-theme overlay to edit and resend a request."""

    def __init__(self, ui_instance=None):
        self._ui_instance = ui_instance

    def show(self, entry):
        url    = entry.original_url or entry.request.url
        method = entry.request.method
        headers_list = [
            {'enabled': True, 'key': h.name, 'value': h.value}
            for h in entry.request.headers if h.name.lower() not in HOP_BY_HOP
        ]
        query_list = [
            {'enabled': True, 'key': k, 'value': v}
            for k, v in (entry.request.query_params or {}).items()
        ]
        body_str = entry.request.content or ''
        try:
            body_display = _json.dumps(_json.loads(body_str), indent=2)
        except Exception:
            body_display = body_str

        body_state = {'text': body_display, 'raw_ta_id': None}

        state = {
            'method_sel': None, 'url_inp': None, 'send_btn': None,
            'body_state': body_state,
            'headers_list': headers_list,
            'query_list': query_list,
            'resp_status': None, 'resp_meta': None,
            'resp_body': None, 'resp_hdrs': None,
            'resp_badge': None, 'resp_badge_label': None, 'resp_badge_file': None,
            '_badge_click_handler': None,
        }

        with context.client.content:
            overlay = ui.element('div').style(
                'position:fixed; inset:0; z-index:9999;'
                'display:flex; flex-direction:column;'
                'background:#030712;'
            )
            # Inject dark CSS for json_editor once per overlay
            ui.add_head_html(_JSON_EDITOR_CSS)

        with overlay:
            # ── TOP BAR ───────────────────────────────────────────────────────
            with ui.row().classes('w-full px-3 py-2 bg-gray-900 border-b border-gray-700 items-center gap-2').style('flex-shrink:0'):
                state['method_sel'] = ui.select(
                    options=['GET','POST','PUT','PATCH','DELETE','HEAD','OPTIONS'],
                    value=method,
                ).props('outlined dense dark').classes('w-28 font-mono')

                state['url_inp'] = ui.input(value=url, placeholder='https://...') \
                    .props('outlined dense dark').classes('flex-1 font-mono text-sm')

                state['send_btn'] = ui.button('Send', icon='send') \
                    .classes('bg-blue-600 text-white px-5 text-sm')

                ui.button(icon='close', on_click=overlay.delete) \
                    .props('flat round dense color=grey-5').tooltip('Close')

            # ── MAIN SPLIT ────────────────────────────────────────────────────
            with ui.element('div').style(
                'flex:1; min-height:0; overflow:hidden;'
                'display:flex; flex-direction:row;'
            ).classes('w-full'):

                # ── LEFT: Request ─────────────────────────────────────────────
                with ui.element('div').style(
                    'width:50%; display:flex; flex-direction:column; overflow:hidden;'
                    'border-right:1px solid #374151;'
                ):
                    with ui.row().classes('px-3 py-1.5 bg-gray-900/60 border-b border-gray-700 items-center').style('flex-shrink:0'):
                        ui.label('REQUEST').classes('text-xs font-bold text-gray-500 tracking-widest')

                    req_tabs = ui.tabs(value='Header') \
                        .classes('bg-gray-900/40 border-b border-gray-700') \
                        .style('flex-shrink:0') \
                        .props('dense align=left dark')
                    with req_tabs:
                        ui.tab('Header', icon='list_alt').classes('text-xs text-gray-400')
                        ui.tab('Query',  icon='search').classes('text-xs text-gray-400')
                        ui.tab('Body',   icon='data_object').classes('text-xs text-gray-400')
                        ui.tab('Raw',    icon='code').classes('text-xs text-gray-400')

                    with ui.tab_panels(req_tabs, value='Header') \
                            .classes('bg-gray-950 body-panels').props('dark') \
                            .style('flex:1; min-height:0; overflow:hidden;'):

                        with ui.tab_panel('Header').classes('p-0 panel-scrollable'):
                            hdr_col = ui.column().classes('w-full kv-list').style('gap:0;')
                            self._render_kv_editor(hdr_col, headers_list)

                        with ui.tab_panel('Query').classes('p-0 panel-scrollable'):
                            qry_col = ui.column().classes('w-full kv-list').style('gap:0;')
                            self._render_kv_editor(qry_col, query_list)

                        # M2 — Body: RAW textarea + JSON editor sub-tabs
                        with ui.tab_panel('Body').classes('p-0').style(
                            'display:flex; flex-direction:column; height:100%; overflow:hidden;'
                        ):
                            # define handler after editor is created — placeholder for now
                            _body_tab_handlers = []

                            def _on_body_tab_change(e):
                                for h in _body_tab_handlers:
                                    h(e)

                            body_sub = ui.tabs(value='RAW', on_change=_on_body_tab_change) \
                                .classes('bg-gray-900/60 border-b border-gray-700') \
                                .style('flex-shrink:0') \
                                .props('dense align=left dark')
                            with body_sub:
                                ui.tab('RAW',  icon='code').classes('text-xs text-gray-400')
                                ui.tab('JSON', icon='data_object').classes('text-xs text-gray-400')

                            with ui.tab_panels(body_sub, value='RAW') \
                                    .classes('bg-gray-950 sub-panels').props('dark') \
                                    .style('flex:1; min-height:0; overflow:hidden;'):

                                # RAW — NiceGUI textarea, syncs directly via on_change
                                with ui.tab_panel('RAW').classes('p-0').style(
                                    'display:flex; flex-direction:column; height:100%; overflow:hidden; padding:8px;'
                                ):
                                    raw_ta_id = f'raw-ta-{id(body_state)}'
                                    body_state['raw_ta_id'] = raw_ta_id

                                    def _on_raw_change(e):
                                        body_state['text'] = e.value

                                    raw_nicegui_ta = ui.textarea(
                                        value=body_display,
                                        on_change=_on_raw_change,
                                    ).classes('raw-body-ta').props('borderless dark autogrow=false')

                                    # keep raw_ta reference for compat with json→raw sync
                                    class _RawTaProxy:
                                        def set_value(self, v):
                                            raw_nicegui_ta.set_value(v)
                                            body_state['text'] = v
                                    raw_ta = _RawTaProxy()

                                # JSON — container; editor is built/rebuilt on each tab activation
                                with ui.tab_panel('JSON').classes('p-0').style(
                                    'display:flex; flex-direction:column; height:100%; overflow:hidden;'
                                ):
                                    json_container = ui.element('div').style(
                                        'flex:1; width:100%; height:100%; display:flex; flex-direction:column; overflow:hidden;'
                                    )

                                    def _rebuild_json_editor():
                                        json_container.clear()
                                        with json_container:
                                            txt = body_state.get('text', '')
                                            try:
                                                content = {'json': _json.loads(txt)} if txt.strip() else {'json': {}}
                                            except Exception:
                                                content = {'text': txt}

                                            def _on_body_json_change(e):
                                                try:
                                                    c = e.content
                                                    if isinstance(c, dict):
                                                        if 'json' in c:
                                                            new_txt = _json.dumps(c['json'], indent=2)
                                                            body_state['text'] = new_txt
                                                            raw_ta.set_value(new_txt)
                                                        elif 'text' in c:
                                                            body_state['text'] = c['text']
                                                            raw_ta.set_value(c['text'])
                                                except Exception:
                                                    pass

                                            ui.json_editor(
                                                {'content': content},
                                                on_change=_on_body_json_change,
                                            ).style('flex:1; width:100%; height:100%; overflow:hidden;')

                                    def _sync_json_tab(e):
                                        if getattr(e, 'value', None) == 'JSON':
                                            _rebuild_json_editor()

                                    _body_tab_handlers.append(_sync_json_tab)

                        # Raw HTTP tab (read-only preview)
                        with ui.tab_panel('Raw').classes('p-0 panel-scrollable'):
                            lines = [f"{method} {url}"]
                            lines += [f"{h['key']}: {h['value']}" for h in headers_list if h['enabled']]
                            if body_display:
                                lines += ['', body_display]
                            ui.html(
                                '<pre style="margin:0;padding:12px;font-size:12px;'
                                'font-family:monospace;color:#6b7280;background:#030712;'
                                'white-space:pre-wrap;word-break:break-all;">'
                                + _html.escape('\n'.join(lines)) + '</pre>'
                            )

                # ── RIGHT: Response ───────────────────────────────────────────
                with ui.element('div').style(
                    'width:50%; display:flex; flex-direction:column; overflow:hidden;'
                ):
                    with ui.row().classes('px-3 py-1.5 bg-gray-900/60 border-b border-gray-700 items-center gap-3').style('flex-shrink:0'):
                        ui.label('RESPONSE').classes('text-xs font-bold text-gray-500 tracking-widest')
                        state['resp_status'] = ui.label('') \
                            .classes('text-sm font-mono font-bold text-gray-600 ml-2')
                        state['resp_meta'] = ui.label('') \
                            .classes('text-xs font-mono text-gray-600 flex-1')
                        # Mock/redirect badge — hidden until a response arrives
                        badge_row = ui.row().classes('items-center gap-1 ml-1')
                        badge_row.set_visibility(False)
                        state['resp_badge'] = badge_row
                        with badge_row:
                            badge_btn = ui.button('') \
                                .props('flat dense no-caps') \
                                .classes('text-xs font-bold px-2 py-0 rounded bg-gray-700/80 text-purple-300 min-h-0') \
                                .on('click', lambda _: state['_badge_click_handler'] and state['_badge_click_handler']())
                            state['resp_badge_label'] = badge_btn
                            badge_file = ui.label('') \
                                .classes('text-xs font-mono text-gray-500 truncate max-w-xs')
                            state['resp_badge_file'] = badge_file

                    resp_tabs = ui.tabs(value='Body') \
                        .classes('bg-gray-900/40 border-b border-gray-700') \
                        .style('flex-shrink:0') \
                        .props('dense align=left dark')
                    with resp_tabs:
                        ui.tab('Body',   icon='data_object').classes('text-xs text-gray-400')
                        ui.tab('Header', icon='list_alt').classes('text-xs text-gray-400')
                        ui.tab('Raw',    icon='code').classes('text-xs text-gray-400')

                    # store ref so _send can rebuild the raw HTTP preview
                    state['resp_tabs'] = resp_tabs

                    with ui.tab_panels(resp_tabs, value='Body') \
                            .classes('bg-gray-950 body-panels').props('dark') \
                            .style('flex:1; min-height:0; overflow:hidden;'):

                        with ui.tab_panel('Body').classes('p-0').style(
                            'display:flex; flex-direction:column; height:100%; overflow:hidden;'
                        ):
                            state['resp_body'] = ui.column() \
                                .classes('w-full') \
                                .style('flex:1; min-height:0; display:flex; flex-direction:column; overflow:hidden;')
                            with state['resp_body']:
                                self._render_empty_response()

                        with ui.tab_panel('Header').classes('p-0 panel-scrollable'):
                            state['resp_hdrs'] = ui.column().classes('w-full')

                        with ui.tab_panel('Raw').classes('p-0 panel-scrollable'):
                            state['resp_raw'] = ui.column().classes('w-full h-full')
                            with state['resp_raw']:
                                ui.label('Press Send to view raw HTTP here') \
                                    .classes('text-gray-600 text-xs italic p-4')

        async def _fire_send(_=None):
            await self._send(state)

        state['send_btn'].on_click(_fire_send)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _render_empty_response(self):
        with ui.column().classes('w-full h-full items-center justify-center gap-3'):
            ui.icon('send', size='40px').classes('text-gray-700')
            ui.label('Press Send to see the response here') \
                .classes('text-gray-500 text-sm')
            ui.label('Results will appear in RAW and JSON tabs') \
                .classes('text-gray-600 text-xs')

    # ── kv editor ───────────────────────────────���────────────────────────────

    def _render_kv_editor(self, container, items: list):
        hdr_cls   = 'w-full px-2 py-1 bg-gray-800/60 border-b border-gray-700 items-center'
        props_inp = 'dense borderless dark'
        props_chk = 'dense color=blue'

        def refresh():
            container.clear()
            with container:
                with ui.row().classes(hdr_cls):
                    ui.element('div').classes('w-6')
                    ui.label('Key').classes('w-40 shrink-0 text-xs font-bold text-gray-500')
                    ui.label('Value').classes('flex-1 text-xs font-bold text-gray-500')
                    ui.element('div').classes('w-8')

                for i, row in enumerate(items):
                    with ui.row().classes(
                        'w-full px-2 border-b border-gray-700/40 items-center gap-1'
                        ' hover:bg-gray-800/30'
                    ).style('padding-top:2px; padding-bottom:2px;'):
                        ui.checkbox(value=row['enabled'],
                            on_change=lambda e, i=i: items.__setitem__(i, {**items[i], 'enabled': e.value})
                        ).props(props_chk).classes('w-6 shrink-0')

                        ui.input(
                            value=row['key'], placeholder='Key',
                            on_change=lambda e, i=i: items.__setitem__(i, {**items[i], 'key': e.value})
                        ).classes('w-40 shrink-0 text-xs font-mono text-blue-300').props(props_inp)

                        # Wrap in kv-value-field so our CSS strips Quasar's internal padding
                        with ui.element('div').classes('kv-value-field'):
                            ui.textarea(
                                value=row['value'], placeholder='Value…',
                                on_change=lambda e, i=i: items.__setitem__(i, {**items[i], 'value': e.value})
                            ).style(
                                'width:100%; font-family:monospace; font-size:12px;'
                                'color:#d1d5db; background:#1f2937;'
                                'border:1px solid #374151; border-radius:4px;'
                                'max-height:72px; overflow-y:auto !important;'
                            ).props('borderless dark rows=2')

                        ui.button(icon='delete',
                            on_click=lambda _, i=i: [items.pop(i), refresh()]
                        ).props('flat round dense size=xs color=grey-6').classes('w-8 shrink-0')

                # ── Add row ───────────────────────────────────────────────────
                with ui.row().classes(
                    'w-full px-2 py-1 items-center gap-1'
                    ' border-t border-gray-700/60 bg-gray-900/30'
                ):
                    ui.element('div').classes('w-6 shrink-0')

                    add_key_inp = ui.input(placeholder='＋ New key…') \
                        .classes('w-40 shrink-0 text-xs font-mono text-gray-500 italic') \
                        .props(props_inp)

                    def _on_add_key_enter(e, _inp=add_key_inp):
                        if isinstance(e.args, dict) and e.args.get('key') == 'Enter':
                            val = _inp.value.strip()
                            if val:
                                items.append({'enabled': True, 'key': val, 'value': ''})
                                refresh()

                    add_key_inp.on('keydown', _on_add_key_enter)
                    ui.label('← type here to add a new field') \
                        .classes('flex-1 text-xs text-gray-600 italic')

        refresh()

    # ── send ──────────────────────────────────────────────────────────────────

    async def _send(self, state: dict):
        proxies    = {'http': PROXY_URL, 'https': PROXY_URL}
        target_url = state['url_inp'].value.strip()
        method     = state['method_sel'].value

        body_text  = state['body_state'].get('text', '')
        body_data  = body_text.encode() if body_text else None

        state['send_btn'].props('loading')

        lbl = state['resp_status']
        if lbl:
            lbl.set_text('Sending…')
            lbl.classes('text-gray-500',
                        remove='text-green-400 text-yellow-400 text-orange-400 text-red-400')
        if state['resp_meta']:
            state['resp_meta'].set_text('')

        loop = asyncio.get_running_loop()

        # Strip query string from URL — params come exclusively from the editor
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(target_url)
        clean_url = urlunparse(parsed._replace(query=''))

        # Build headers and params from editor state (only enabled rows with non-empty keys)
        req_headers = {
            row['key']: row['value']
            for row in state['headers_list']
            if row.get('enabled') and row.get('key', '').strip()
        }
        req_params = {
            row['key']: row['value']
            for row in state['query_list']
            if row.get('enabled') and row.get('key', '').strip()
        }

        def do_request():
            return req_lib.request(
                method, clean_url,
                headers=req_headers,
                params=req_params,
                data=body_data,
                timeout=30, verify=False, allow_redirects=False,
                proxies=proxies,
            )

        t0 = time.time()
        try:
            resp = await loop.run_in_executor(None, do_request)
            elapsed = int((time.time() - t0) * 1000)

            color = ('text-green-400'  if resp.status_code < 300
                     else 'text-yellow-400' if resp.status_code < 400
                     else 'text-orange-400' if resp.status_code < 500
                     else 'text-red-400')

            try:
                resp_json_obj = resp.json()
                body_pretty   = _json.dumps(resp_json_obj, indent=2)
                is_json       = True
            except Exception:
                resp_json_obj = None
                body_pretty   = resp.text[:50_000]
                is_json       = False

            resp_headers = list(resp.headers.items())

            if lbl:
                lbl.set_text(f'{resp.status_code} {resp.reason}')
                lbl.classes(color,
                    remove='text-gray-500 text-green-400 text-yellow-400 text-orange-400 text-red-400')

            # ── Mock / Redirect badge from proxy metadata headers ──────────
            proxy_op      = resp.headers.get('X-Proxy-Operation', '')
            proxy_file    = resp.headers.get('X-Proxy-File', '')
            proxy_profile = resp.headers.get('X-Proxy-Profile', '')
            if state.get('resp_badge'):
                state['resp_badge'].set_visibility(False)
            if proxy_op and state.get('resp_badge_label'):
                is_redirect = proxy_op == 'redirect'
                badge_text  = 'REDIRECT' if is_redirect else 'MOCK'
                badge_color = 'text-blue-300' if is_redirect else 'text-purple-300'
                hover_color = 'hover:bg-blue-700/60' if is_redirect else 'hover:bg-purple-700/60'

                # Build tooltip with full path info
                tooltip_parts = []
                if proxy_profile:
                    tooltip_parts.append(f'Perfil: {proxy_profile}')
                if proxy_file:
                    tooltip_parts.append(proxy_file)
                tooltip_text = '\n'.join(tooltip_parts) if tooltip_parts else proxy_op

                # Make badge clickable if we have a file to edit and a ui_instance
                can_edit = bool(proxy_file and self._ui_instance)

                badge_lbl = state['resp_badge_label']
                badge_lbl.set_text(badge_text)
                badge_lbl.classes(
                    f'{badge_color} {hover_color} {"cursor-pointer" if can_edit else ""}',
                    remove='text-purple-300 text-blue-300 cursor-pointer '
                           'hover:bg-purple-700/60 hover:bg-blue-700/60'
                )
                badge_lbl.tooltip(tooltip_text)

                if can_edit:
                    def _open_mapping_editor(pf=proxy_file, pi=self._ui_instance):
                        import json as _j
                        from pathlib import Path
                        try:
                            mappings_dir = pi.config.get_mappings_dir()
                            full_path = Path(mappings_dir) / pf
                            content = _j.loads(full_path.read_text())
                            response = content.get('response', {})
                            body_file = (content.get('request', {}).get('bodyFileName')
                                         or response.get('bodyFileName', ''))
                            profile = pi.config.get_current_profile()
                            mapping_type = profile.mapping_type if profile else 'default'
                            mapping_data = {
                                'request_file':  pf,
                                'response_file': body_file,
                                'full_json':     _j.dumps(content, indent=2),
                                'mapping_type':  mapping_type,
                            }
                            from dialogs.mapping_editor import MappingEditorDialog
                            MappingEditorDialog(pi).show_edit('', mapping_data)
                        except Exception as exc:
                            ui.notify(f'Error opening mapping: {exc}', type='negative')

                    state['_badge_click_handler'] = _open_mapping_editor
                    badge_lbl.props(remove='disable')
                else:
                    state['_badge_click_handler'] = None
                    badge_lbl.props('disable')

                # Filename label next to badge
                if proxy_file:
                    import os
                    state['resp_badge_file'].set_text(os.path.basename(proxy_file))
                    state['resp_badge_file'].set_visibility(True)
                else:
                    state['resp_badge_file'].set_visibility(False)

                state['resp_badge'].set_visibility(True)

            if state['resp_meta']:
                state['resp_meta'].set_text(f'{elapsed} ms  ·  {len(resp.content)} B')

            # M3 — Response body: RAW <pre> + JSON editor sub-tabs
            if state['resp_body']:
                state['resp_body'].clear()
                with state['resp_body']:
                    resp_body_sub = ui.tabs(value='JSON' if is_json else 'RAW') \
                        .classes('bg-gray-900/60 border-b border-gray-700') \
                        .style('flex-shrink:0') \
                        .props('dense align=left dark')
                    with resp_body_sub:
                        ui.tab('RAW',  icon='code').classes('text-xs text-gray-400')
                        ui.tab('JSON', icon='data_object').classes('text-xs text-gray-400')

                    with ui.tab_panels(resp_body_sub, value='JSON' if is_json else 'RAW') \
                            .classes('bg-gray-950 sub-panels').props('dark') \
                            .style('flex:1; min-height:0; overflow:hidden;'):

                        with ui.tab_panel('RAW').classes('p-0 panel-scrollable'):
                            escaped = _html.escape(body_pretty)
                            ui.html(
                                f'<pre style="margin:0;padding:12px;font-size:12px;'
                                f'font-family:monospace;color:#e5e7eb;background:#030712;'
                                f'white-space:pre-wrap;word-break:break-all;">{escaped}</pre>'
                            )

                        with ui.tab_panel('JSON').classes('p-0').style(
                            'display:flex; flex-direction:column; height:100%; overflow:hidden;'
                        ):
                            if is_json:
                                ui.json_editor(
                                    {'content': {'json': resp_json_obj}, 'readOnly': True}
                                ).style('flex:1; width:100%; height:100%; overflow:hidden;')
                            else:
                                with ui.column().classes('w-full h-full items-center justify-center gap-3 p-4'):
                                    ui.icon('warning_amber', size='32px').classes('text-yellow-600')
                                    ui.label('Response is not valid JSON') \
                                        .classes('text-gray-400 text-sm')
                                    ui.label('Use the RAW tab to view content') \
                                        .classes('text-gray-600 text-xs')

            if state['resp_hdrs']:
                state['resp_hdrs'].clear()
                with state['resp_hdrs']:
                    with ui.row().classes('w-full px-3 py-1 bg-gray-800/60 border-b border-gray-700 items-center'):
                        ui.label('Header').classes('w-48 shrink-0 text-xs font-bold text-gray-500')
                        ui.label('Value').classes('flex-1 text-xs font-bold text-gray-500')
                    for k, v in resp_headers:
                        with ui.row().classes('w-full px-3 py-1 border-b border-gray-700/50 items-start hover:bg-gray-800/40'):
                            ui.label(k).classes('w-48 shrink-0 text-xs text-blue-400 font-mono')
                            ui.label(v).classes('flex-1 text-xs text-gray-300 font-mono break-all')

            if state.get('resp_raw'):
                state['resp_raw'].clear()
                with state['resp_raw']:
                    # Build raw HTTP response preview
                    raw_lines = [f"HTTP/1.1 {resp.status_code} {resp.reason}"]
                    for k, v in resp_headers:
                        raw_lines.append(f"{k}: {v}")
                    raw_lines.append('')
                    raw_lines.append(body_pretty)
                    ui.html(
                        '<pre style="margin:0;padding:12px;font-size:12px;'
                        'font-family:monospace;color:#6b7280;background:#030712;'
                        'white-space:pre-wrap;word-break:break-all;">'
                        + _html.escape('\n'.join(raw_lines)) + '</pre>'
                    )

        except Exception as exc:
            status_lbl = state['resp_status']
            if status_lbl:
                status_lbl.set_text('Error')
                status_lbl.classes('text-red-400', remove='text-gray-500')
            if state['resp_body']:
                state['resp_body'].clear()
                with state['resp_body']:
                    with ui.column().classes('w-full p-6 gap-3 items-center'):
                        ui.icon('error_outline', size='36px').classes('text-red-500')
                        ui.label('Request failed') \
                            .classes('text-red-400 text-sm font-semibold')
                        ui.label(str(exc)).classes('text-red-300 text-xs font-mono break-all text-center')

        finally:
            state['send_btn'].props(remove='loading')
