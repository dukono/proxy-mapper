"""MappingActions — business logic for toggle/edit/delete mappings."""

import os
from nicegui import ui
from dialogs import MappingEditorDialog


class MappingActions:
    """Handles all mutation actions on mappings (toggle, edit, delete)."""

    def __init__(self, ui_instance, on_refresh):
        """
        Args:
            ui_instance: the main UI object with .proxy, .config, .mapping_loader
            on_refresh:  callable() to trigger view refresh after mutation
        """
        self._ui = ui_instance
        self._refresh = on_refresh

    def toggle(self, rule_id: str):
        self._ui.proxy.get_rules_engine().toggle_rule(rule_id)
        self._refresh()

    def enable_all(self):
        engine = self._ui.proxy.get_rules_engine()
        for rule in engine.rules:
            rule.enabled = True
        ui.notify(f"Enabled {len(engine.rules)} rules", type='positive')
        self._refresh()

    def disable_all(self):
        engine = self._ui.proxy.get_rules_engine()
        count = sum(1 for r in engine.rules if not getattr(r, 'is_default', False))
        for rule in engine.rules:
            if not getattr(rule, 'is_default', False):
                rule.enabled = False
        ui.notify(f"Disabled {count} rules", type='warning')
        self._refresh()

    def edit(self, mapping_id: str):
        file_info = self._ui.mapping_loader.get_info(mapping_id)
        if not file_info:
            ui.notify(f"Mapping not found: {mapping_id}", type='negative')
            return
        mapping_data = {
            'request_file':  file_info.get('request_file', ''),
            'response_file': file_info.get('response_file', ''),
            'full_json':     file_info.get('full_json', '{}'),
            'mapping_type':  file_info.get('mapping_type', 'default'),
        }
        MappingEditorDialog(self._ui).show_edit(mapping_id, mapping_data)

    def edit_by_path(self, rel_path: str):
        """Edit a JSON file that is not yet registered as a mapping."""
        import json
        from pathlib import Path
        base_path = self._ui.config.get_mappings_dir()
        full_path = Path(base_path) / rel_path
        try:
            content = json.loads(full_path.read_text())
            mapping_data = {
                'request_file':  rel_path,
                'response_file': '',
                'full_json':     json.dumps(content, indent=2),
                'mapping_type':  'default',
            }
            MappingEditorDialog(self._ui).show_edit('', mapping_data)
        except Exception as exc:
            ui.notify(f"Error reading file: {exc}", type='negative')

    def delete(self, mapping_id: str):
        file_info = self._ui.mapping_loader.get_info(mapping_id)
        if not file_info:
            ui.notify(f"Mapping not found: {mapping_id}", type='negative')
            return
        request_file = file_info.get('request_file', 'Unknown')

        with ui.dialog() as dlg:
            with ui.card().classes('bg-gray-800').style(
                'width:400px; min-width:300px; min-height:150px; resize:both; overflow:auto; padding:1rem;'
            ):
                ui.label("Delete Mapping").classes('text-lg font-bold text-white mb-2')
                ui.label(f"Are you sure you want to delete '{request_file}'?").classes('text-gray-300 mb-4')
                with ui.row().classes('w-full justify-end gap-2'):
                    ui.button('Cancel', on_click=dlg.close).props('flat color=white')
                    ui.button('Delete',
                              on_click=lambda: self._confirm_delete(mapping_id, dlg)
                              ).props('flat color=red').classes('bg-red-600 text-white')
        dlg.open()

    # ── private ──────────────────────────────────────────────────────────────

    def _confirm_delete(self, mapping_id: str, dialog):
        file_info = self._ui.mapping_loader.get_info(mapping_id)
        if file_info:
            self._ui.mapping_loader.unregister(mapping_id)
            mappings_dir = self._ui.config.get_mappings_dir()
            for key in ('request_file', 'response_file'):
                rel = file_info.get(key)
                if rel:
                    full = os.path.join(mappings_dir, rel)
                    if os.path.exists(full):
                        os.remove(full)
            ui.notify("Mapping deleted successfully", type='positive')
        dialog.close()
        self._refresh()
