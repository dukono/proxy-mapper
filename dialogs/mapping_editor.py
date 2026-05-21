"""Mapping Editor Dialog for creating and editing WireMock mappings."""

import json
import os
from typing import Optional

from nicegui import ui

from config import get_global_config
from strategies import MappingStrategyFactory
from utils import get_logger
from views.components.edit_repeat_dialog import _JSON_EDITOR_CSS

log = get_logger("MAPPING_EDITOR")


class MappingEditorDialog:
    """Dialog for creating and editing WireMock mappings."""

    WIRE_TEMPLATE = '''{
  "request": {
    "method": "GET",
    "urlPath": "/api/example"
  },
  "response": {
    "status": 200,
    "headers": {
      "Content-Type": "application/json"
    },
    "bodyFileName": "responses/example.json"
  }
}'''

    DEFAULT_TEMPLATE = '''{
  "request": {
    "method": "GET",
    "matchType": "contains",
    "matchValue": "/api/example"
  },
  "response": {
    "status": 200,
    "headers": {
      "Content-Type": "application/json"
    },
    "body": "{\\"message\\": \\"Hello World\\"}"
  }
}'''

    BODY_TEMPLATE = '''{
  "message": "Hello from body file"
}'''

    def __init__(self, ui_instance):
        self.ui = ui_instance
        self.dialog = None
        self._request_filename_input: Optional[ui.input] = None
        self._response_filename_input: Optional[ui.input] = None
        self._request_editor = None
        self._response_editor = None
        self._save_btn = None
        self._edit_mode = False
        self._edit_rule_id: Optional[str] = None
        self._original_mapping_filename: Optional[str] = None
        self._original_body_filename: Optional[str] = None
        self._request_json_data = {}
        self._response_json_data = {}

    def show_create(self, mapping_data: Optional[dict] = None):
        """Show dialog for creating a new mapping."""
        self._edit_mode = False
        self._edit_rule_id = None
        self._show_dialog("Create New Mapping", mapping_data)

    def show_edit(self, rule_id: str, mapping_data: dict):
        """Show dialog for editing an existing mapping."""
        self._edit_mode = True
        self._edit_rule_id = rule_id
        self._show_dialog("Edit Mapping", mapping_data)

    def _show_dialog(self, title: str, mapping_data: Optional[dict] = None):
        """Internal method to show the dialog."""
        ui.add_head_html(_JSON_EDITOR_CSS)

        config = get_global_config()
        profile = config.get_current_profile()
        mapping_type = profile.mapping_type if profile else 'Wire'
        is_wire = mapping_type == 'Wire'

        # ── Resolve initial values ─────────────────────────────────────────
        if mapping_data:
            full_json_str = mapping_data.get('full_json', '{}')
            try:
                full_json = json.loads(full_json_str)
                request_value = json.dumps(full_json, indent=2)
            except Exception:
                request_value = full_json_str
                full_json = {}

            request_filename = mapping_data.get('request_file', '')

            if is_wire:
                response_data = full_json.get('response', {})
                response_filename = response_data.get('bodyFileName', '') or mapping_data.get('response_file', '')
                explicit_body = mapping_data.get('_body_content', '')
                response_body = response_data.get('body', '')

                if explicit_body:
                    response_value = explicit_body
                elif response_body:
                    try:
                        response_value = json.dumps(json.loads(response_body), indent=2)
                    except Exception:
                        response_value = response_body
                elif response_filename:
                    files_dir = config.get_files_dir()
                    root_path = profile.root_path if profile else ''
                    candidate_paths = [
                        os.path.join(files_dir, response_filename),
                        os.path.join(os.path.dirname(config.get_mappings_dir()), '__files', response_filename),
                        os.path.join(root_path, '__files', response_filename),
                        os.path.join(root_path, response_filename),
                    ]
                    raw = None
                    for candidate in candidate_paths:
                        norm = os.path.normpath(candidate)
                        if os.path.exists(norm):
                            with open(norm, 'r') as f:
                                raw = f.read()
                            break
                    if raw is not None:
                        try:
                            response_value = json.dumps(json.loads(raw), indent=2)
                        except Exception:
                            response_value = raw
                    else:
                        log.warning("Body file not found: %s", response_filename)
                        response_value = self.BODY_TEMPLATE
                else:
                    response_value = self.BODY_TEMPLATE
            else:
                response_filename = ''
                response_value = ''
        else:
            request_filename = ''
            response_filename = ''
            request_value = self.WIRE_TEMPLATE if is_wire else self.DEFAULT_TEMPLATE
            response_value = self.BODY_TEMPLATE if is_wire else ''

        self._original_mapping_filename = request_filename
        self._original_body_filename = response_filename

        # ── Resolve paths ──────────────────────────────────────────────────
        _cfg = get_global_config()
        _mdir = _cfg.get_mappings_dir()
        _fdir = _cfg.get_files_dir()

        # ── Build dialog ───────────────────────────────────────────────────
        with ui.dialog() as self.dialog:
            self.dialog.props('resizable')
            ui.add_css(
                '.mapping-editor-dialog > .q-dialog__inner {'
                '    max-width: none !important;'
                '    max-height: none !important;'
                '    width: 100vw !important;'
                '    height: 100vh !important;'
                '    padding: 0 !important;'
                '    pointer-events: none;'
                '    display: flex !important;'
                '    align-items: center !important;'
                '    justify-content: center !important;'
                '}'
                '.mapping-editor-card {'
                '    pointer-events: all;'
                '    display: flex !important;'
                '    flex-direction: column !important;'
                '    resize: both;'
                '    overflow: hidden !important;'
                '    min-width: 600px;'
                '    min-height: 400px;'
                '    max-width: 98vw;'
                '    max-height: 96vh;'
                '    position: relative;'
                '    gap: 0 !important;'
                '}'
                '.mapping-editor-card .editor-body {'
                '    flex: 1 !important;'
                '    min-height: 0 !important;'
                '    overflow: hidden !important;'
                '    margin: 0 !important;'
                '    padding: 2px !important;'
                '    gap: 2px !important;'
                '}'
                '.mapping-editor-card > div {'
                '    margin: 0 !important;'
                '}'
                '.mapping-editor-inputs .q-field { padding-bottom: 0 !important; }'
                '.mapping-editor-inputs .q-field__control,'
                '.mapping-editor-inputs .q-field--dense .q-field__control,'
                '.mapping-editor-inputs .q-field--outlined.q-field--dense .q-field__control {'
                '    min-height: 24px !important; height: 24px !important;'
                '    padding-top: 0 !important; padding-bottom: 0 !important;'
                '}'
                '.mapping-editor-inputs .q-field__native,'
                '.mapping-editor-inputs .q-field__input {'
                '    min-height: 24px !important; height: 24px !important;'
                '    padding-top: 0 !important; padding-bottom: 0 !important;'
                '    line-height: 24px !important; font-size: 11px !important;'
                '}'
                '.mapping-editor-inputs .q-field__marginal,'
                '.mapping-editor-inputs .q-field__append,'
                '.mapping-editor-inputs .q-field__prepend {'
                '    min-height: 24px !important; height: 24px !important;'
                '}'
            )
            # Intercept Ctrl+C inside the dialog to avoid navigator.clipboard
            # permission request that crashes pywebview (PyQt6 enum mismatch).
            ui.add_head_html('''<script>
            document.addEventListener("keydown", function(e) {
                if ((e.ctrlKey || e.metaKey) && e.key === "c") {
                    var sel = window.getSelection();
                    if (sel && sel.toString().length > 0) {
                        e.preventDefault();
                        var text = sel.toString();
                        var el = document.createElement("textarea");
                        el.value = text;
                        el.style.cssText = "position:fixed;top:0;left:0;opacity:0;";
                        document.body.appendChild(el);
                        el.focus(); el.select();
                        document.execCommand("copy");
                        document.body.removeChild(el);
                    }
                }
            }, true);
            </script>''')

            self.dialog.classes('mapping-editor-dialog')
            card_style = 'width:92vw; height:90vh;' if is_wire else 'width:70vw; height:90vh;'

            with ui.card().classes('p-0 m-0 bg-gray-800 shadow-none mapping-editor-card').style(card_style):
                # Content
                with ui.row().classes('editor-body w-full gap-2 flex-nowrap items-stretch'):
                    # Left: Mapping JSON
                    with ui.card().classes('bg-gray-800 p-2 flex flex-col overflow-hidden shadow-none border border-gray-700 flex-1'):
                        with ui.row().classes('mapping-editor-inputs w-full items-center gap-2 shrink-0'):
                            ui.label("📄 Mapping JSON").classes('text-sm font-bold text-blue-400')
                            self._request_filename_input = ui.input(
                                placeholder='e.g., auth-login.json',
                                value=request_filename
                            ).classes('flex-1').props('dark outlined dense input-class=text-xs')
                        if is_wire:
                            ui.html(f'<div title="{_mdir}" style="font-size:10px;color:#6b7280;font-family:monospace;font-weight:300;line-height:1.2;margin:1px 0 2px 0;overflow-x:auto;white-space:nowrap;padding-bottom:1px;">{_mdir}</div>')
                        with ui.scroll_area().classes('flex-1 w-full min-h-0'):
                            try:
                                request_json = json.loads(request_value)
                            except Exception:
                                request_json = {}
                            self._request_editor = ui.json_editor(
                                {'content': {'json': request_json}},
                                on_change=self._on_request_change
                            ).classes('w-full h-full')

                    # Right: Body File (Wire only)
                    if is_wire:
                        with ui.card().classes('bg-gray-800 p-2 flex flex-col overflow-hidden shadow-none border border-gray-700 flex-1'):
                            with ui.row().classes('mapping-editor-inputs w-full items-center gap-2 shrink-0'):
                                ui.label("📄 Body File").classes('text-sm font-bold text-green-400')
                                self._response_filename_input = ui.input(
                                    placeholder='e.g., responses/auth-success.json',
                                    value=response_filename
                                ).classes('flex-1').props('dark outlined dense input-class=text-xs')
                            ui.html(f'<div title="{_fdir}" style="font-size:10px;color:#6b7280;font-family:monospace;font-weight:300;line-height:1.2;margin:1px 0 2px 0;overflow-x:auto;white-space:nowrap;padding-bottom:1px;">{_fdir}</div>')
                            with ui.scroll_area().classes('flex-1 w-full min-h-0'):
                                try:
                                    response_json = json.loads(response_value)
                                except Exception:
                                    response_json = {}
                                self._response_editor = ui.json_editor(
                                    {'content': {'json': response_json}},
                                    on_change=self._on_response_change
                                ).classes('w-full h-full')

                # Footer
                with ui.row().classes('w-full px-3 py-2 border-t border-gray-700 items-center shrink-0 bg-gray-800'):
                    with ui.row().classes('items-center gap-2 flex-1'):
                        ui.label(title).classes('text-sm font-bold text-white')
                        ui.label(f"({mapping_type} format)").classes('text-xs text-gray-500')
                        ui.button(icon='help', on_click=lambda: self._show_help_dialog(mapping_type)).props('flat round dense color=cyan size=xs').tooltip('Show JSON structure help')
                    with ui.row().classes('items-center gap-2'):
                        ui.button('Cancel', on_click=lambda: [self.dialog.close(), self._clear_state()]).props('flat color=white size=sm')
                        ui.button('Validate', on_click=self._validate, icon='check_circle').props('flat color=blue size=sm').classes('text-white')
                        self._save_btn = ui.button('Save', on_click=self._save, icon='save').props('flat color=green size=sm').classes('text-white')

        self.dialog.open()

    # ── Editor change handlers ─────────────────────────────────────────────

    def _on_request_change(self, e):
        try:
            content = e.content if hasattr(e, 'content') else e.get('content', {})
            if 'json' in content:
                self._request_json_data = content['json']
            elif 'text' in content:
                try:
                    self._request_json_data = json.loads(content['text'])
                except Exception:
                    pass  # keep last valid JSON
        except Exception:
            pass

    def _on_response_change(self, e):
        try:
            content = e.content if hasattr(e, 'content') else e.get('content', {})
            if 'json' in content:
                self._response_json_data = content['json']
            elif 'text' in content:
                try:
                    self._response_json_data = json.loads(content['text'])
                except Exception:
                    pass  # keep last valid JSON
        except Exception:
            pass

    def _get_request_json(self) -> dict:
        if self._request_json_data:
            return self._request_json_data
        if self._request_editor is None:
            return {}
        return self._request_editor.properties.get('content', {}).get('json', {})

    def _get_response_json(self) -> dict:
        if self._response_json_data:
            return self._response_json_data
        return self._response_editor.properties.get('content', {}).get('json', {}) if self._response_editor else {}

    # ── Help dialog ────────────────────────────────────────────────────────

    def _show_help_dialog(self, mapping_type: str):
        if mapping_type == 'Wire':
            help_content = (
                "## WireMock Mapping Structure\n\n"
                "---\n\n"
                "### 📥 `request` — Matching Options\n\n"
                "| Field | Type | Description |\n"
                "|---|---|---|\n"
                "| `method` | string | HTTP method: `GET`, `POST`, `PUT`, `DELETE`, `PATCH`, `OPTIONS`, `ANY` |\n"
                "| `urlPath` | string | Exact URL path match, e.g. `/api/users` |\n"
                "| `urlPattern` | string | Regex URL match, e.g. `/api/users/[0-9]+` |\n"
                "| `url` | string | Exact full URL match including query string |\n"
                "| `urlPathPattern` | string | Regex match on path only (ignores query string) |\n\n"
                "#### `queryParameters` — Query String Matching\n"
                "```json\n"
                '"queryParameters": {\n'
                '  "page": { "equalTo": "1" },\n'
                '  "search": { "contains": "john" },\n'
                '  "id": { "matches": "[0-9]+" },\n'
                '  "token": { "absent": true }\n'
                '}\n'
                "```\n\n"
                "#### `headers` — Request Header Matching\n"
                "```json\n"
                '"headers": {\n'
                '  "Content-Type": { "equalTo": "application/json" },\n'
                '  "Authorization": { "contains": "Bearer" },\n'
                '  "X-Custom": { "absent": true }\n'
                '}\n'
                "```\n\n"
                "#### `bodyPatterns` — Request Body Matching\n"
                "```json\n"
                '"bodyPatterns": [\n'
                '  { "equalToJson": {"id": 1}, "ignoreArrayOrder": true },\n'
                '  { "matchesJsonPath": "$.user.name" },\n'
                '  { "contains": "someText" },\n'
                '  { "equalToXml": "<item>value</item>" }\n'
                ']\n'
                "```\n\n"
                "---\n\n"
                "### 📤 `response` — Response Options\n\n"
                "| Field | Type | Description |\n"
                "|---|---|---|\n"
                "| `status` | int | HTTP status code, e.g. `200`, `201`, `400`, `404`, `500` |\n"
                "| `body` | string | Inline response body (plain text or JSON string) |\n"
                "| `bodyFileName` | string | Path to body file relative to `__files/`, e.g. `responses/users.json` |\n"
                "| `headers` | object | Response headers map, e.g. `{\"Content-Type\": \"application/json\"}` |\n"
                "| `fixedDelayMilliseconds` | int | Fixed delay in ms before responding, e.g. `500` |\n"
                "| `fault` | string | Simulate faults: `CONNECTION_RESET_BY_PEER`, `EMPTY_RESPONSE`, `MALFORMED_RESPONSE_CHUNK`, `RANDOM_DATA_THEN_CLOSE` |\n\n"
                "#### `delayDistribution` — Random Delay\n"
                "```json\n"
                '"delayDistribution": {\n'
                '  "type": "uniform",\n'
                '  "lower": 100,\n'
                '  "upper": 500\n'
                '}\n'
                "```\n\n"
                "---\n\n"
                "### ✅ Full Example\n"
                "```json\n"
                '{\n'
                '  "request": {\n'
                '    "method": "POST",\n'
                '    "urlPath": "/api/login",\n'
                '    "headers": { "Content-Type": { "equalTo": "application/json" } },\n'
                '    "bodyPatterns": [{ "matchesJsonPath": "$.username" }]\n'
                '  },\n'
                '  "response": {\n'
                '    "status": 200,\n'
                '    "headers": { "Content-Type": "application/json" },\n'
                '    "bodyFileName": "responses/login-success.json",\n'
                '    "fixedDelayMilliseconds": 200\n'
                '  }\n'
                '}\n'
                "```\n"
            )
        else:
            help_content = (
                "## Custom (Default) Mapping Structure\n\n"
                "---\n\n"
                "### 📥 `request` — Matching Options\n\n"
                "| Field | Type | Description |\n"
                "|---|---|---|\n"
                "| `method` | string | HTTP method: `GET`, `POST`, `PUT`, `DELETE`, `PATCH`, `ANY` |\n"
                "| `matchType` | string | How to match the URL — see values below |\n"
                "| `matchValue` | string | The value to match against the request URL |\n\n"
                "#### `matchType` Values\n\n"
                "| Value | Description | Example |\n"
                "|---|---|---|\n"
                "| `contains` | URL contains the string | `/api` matches `/api/users` |\n"
                "| `equal` | Exact URL match | `/api/users` only matches `/api/users` |\n"
                "| `regexp` | Regex match on full URL | `/api/users/[0-9]+` |\n"
                "| `startswith` | URL starts with the string | `/api/v2` |\n\n"
                "---\n\n"
                "### 📤 `response` — Response Options\n\n"
                "| Field | Type | Description |\n"
                "|---|---|---|\n"
                "| `status` | int | HTTP status code, e.g. `200`, `201`, `400`, `404`, `500` |\n"
                "| `body` | string | Inline response body. Can be a plain string or a JSON-encoded string |\n"
                "| `headers` | object | Response headers, e.g. `{\"Content-Type\": \"application/json\"}` |\n\n"
                "#### `body` — Inline JSON Example\n"
                "```json\n"
                '"body": "{\\"id\\": 1, \\"name\\": \\"John\\"}"\n'
                "```\n\n"
                "---\n\n"
                "### ✅ Full Example\n"
                "```json\n"
                '{\n'
                '  "request": {\n'
                '    "method": "GET",\n'
                '    "matchType": "contains",\n'
                '    "matchValue": "/api/products"\n'
                '  },\n'
                '  "response": {\n'
                '    "status": 200,\n'
                '    "headers": { "Content-Type": "application/json" },\n'
                '    "body": "{\\"products\\": [], \\"total\\": 0}"\n'
                '  }\n'
                '}\n'
                "```\n"
            )

        with ui.dialog() as help_dialog:
            help_dialog.props('resizable')
            with ui.card().classes('w-[800px] max-w-[95vw] h-[85vh] bg-gray-800 p-0 flex flex-col'):
                with ui.row().classes('w-full p-3 border-b border-gray-700 items-center justify-between shrink-0'):
                    ui.label(f"📖 JSON Structure Help — {mapping_type}").classes('text-lg font-bold text-white')
                    ui.button(icon='close', on_click=help_dialog.close).props('flat round dense color=white').classes('w-8 h-8')
                with ui.scroll_area().classes('flex-1 w-full min-h-0 p-4'):
                    ui.markdown(help_content).classes('text-gray-300 text-sm prose prose-invert max-w-none')
                with ui.row().classes('w-full p-3 border-t border-gray-700 justify-end shrink-0'):
                    ui.button('Close', on_click=help_dialog.close).props('flat color=white')

        help_dialog.open()

    # ── Validate & Save ────────────────────────────────────────────────────

    def _validate(self) -> bool:
        try:
            mapping = self._get_request_json()
            config = get_global_config()
            profile = config.get_current_profile()
            mapping_type = profile.mapping_type if profile else 'Wire'
            strategy = MappingStrategyFactory.get_strategy(mapping_type, self.ui)
            is_valid, errors = strategy.validate_mapping(mapping)
            if is_valid:
                ui.notify(f"✅ JSON is valid ({mapping_type} format)", type='positive')
                return True
            else:
                error_text = "\n".join(f"• {e}" for e in errors)
                ui.notify(f"❌ Validation errors:\n{error_text}", type='negative', multi_line=True)
                return False
        except Exception as e:
            ui.notify(f"❌ Validation error: {e}", type='negative')
            return False

    def _save(self):
        save_btn = self._save_btn
        if save_btn:
            save_btn.props('loading')
        try:
            if not self._validate():
                return

            mapping_filename = self._request_filename_input.value.strip()
            body_filename = self._response_filename_input.value.strip() if self._response_filename_input else ''

            if not mapping_filename:
                ui.notify("⚠️ Mapping filename is required", type='negative')
                return
            if not mapping_filename.endswith('.json'):
                mapping_filename += '.json'

            mapping = self._get_request_json()
            mapping_content = json.dumps(mapping, indent=2)

            body_json = self._get_response_json()
            body_content = json.dumps(body_json, indent=2) if body_json is not None else ''

            response = mapping.get('response', {})
            actual_body_filename = body_filename or response.get('bodyFileName', '')

            config = get_global_config()
            mappings_dir = os.path.normpath(config.get_mappings_dir())
            files_dir = os.path.normpath(config.get_files_dir())

            log.info("Save — mappings_dir=%s  files_dir=%s", mappings_dir, files_dir)
            log.info("Save — mapping_filename=%s  body_filename=%s", mapping_filename, actual_body_filename)

            os.makedirs(mappings_dir, exist_ok=True)
            if actual_body_filename:
                os.makedirs(files_dir, exist_ok=True)

            saved_files = []

            old_mapping = self._original_mapping_filename
            mapping_path = os.path.normpath(os.path.join(mappings_dir, mapping_filename))
            if not mapping_path.startswith(os.path.normpath(mappings_dir) + os.sep):
                ui.notify("⚠️ Invalid filename: path traversal not allowed", type='negative')
                return
            os.makedirs(os.path.dirname(mapping_path), exist_ok=True)

            if self._edit_mode and old_mapping and old_mapping != mapping_filename:
                old_path = os.path.join(mappings_dir, old_mapping)
                if os.path.exists(old_path):
                    if os.path.exists(mapping_path):
                        ui.notify(f"⚠️ '{mapping_filename}' already exists and will be overwritten", type='warning')
                    os.rename(old_path, mapping_path)
                    saved_files.append(f"mappings/{mapping_filename} (renamed)")
                else:
                    saved_files.append(f"mappings/{mapping_filename} (new)")
            else:
                saved_files.append(f"mappings/{mapping_filename}")

            with open(mapping_path, 'w', encoding='utf-8') as f:
                f.write(mapping_content)
            log.info("Wrote mapping → %s", mapping_path)

            if actual_body_filename and body_content:
                body_path = os.path.join(files_dir, actual_body_filename)
                os.makedirs(os.path.dirname(body_path), exist_ok=True)

                old_body = self._original_body_filename
                if self._edit_mode and old_body and old_body != actual_body_filename:
                    old_body_path = os.path.join(files_dir, old_body)
                    if os.path.exists(old_body_path):
                        os.rename(old_body_path, body_path)
                        saved_files.append(f"__files/{actual_body_filename} (renamed)")
                    else:
                        saved_files.append(f"__files/{actual_body_filename} (new)")
                else:
                    saved_files.append(f"__files/{actual_body_filename}")

                with open(body_path, 'w', encoding='utf-8') as f:
                    f.write(body_content)
                log.info("Wrote body → %s", body_path)

            if self._edit_mode and self._edit_rule_id:
                self.ui.mapping_loader.unregister(self._edit_rule_id)
            self.ui.mapping_loader.register(mapping, mapping_filename, actual_body_filename)

            ui.notify(f"✅ Saved: {', '.join(saved_files)}", type='positive')
            self.dialog.close()
            self._clear_state()

            if hasattr(self.ui, 'mappings_view'):
                self.ui.mappings_view.refresh()

        except Exception as e:
            log.error("Save error: %s", e, exc_info=True)
            ui.notify(f"❌ Error saving: {e}", type='negative')
        finally:
            if save_btn:
                save_btn.props(remove='loading')

    def _clear_state(self):
        self._edit_mode = False
        self._edit_rule_id = None
        self.dialog = None
        self._request_filename_input = None
        self._response_filename_input = None
        self._request_editor = None
        self._response_editor = None
        self._save_btn = None
        self._original_mapping_filename = None
        self._original_body_filename = None
        self._request_json_data = {}
        self._response_json_data = {}

