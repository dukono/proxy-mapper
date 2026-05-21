"""Mappings view — coordinator for rule management."""

from nicegui import ui
from dialogs import MappingEditorDialog, ProfileManagerDialog
from .components import FileTreeBuilder, MappingActions


def _render_empty_state(on_create):
    with ui.column().classes('w-full h-64 items-center justify-center'):
        ui.icon('folder_open', size='48px').classes('text-gray-600 mb-4')
        ui.label("No mappings configured").classes('text-gray-500 text-lg')
        ui.label("Create rules in the Monitor tab or click 'New Mapping'").classes('text-gray-600 text-sm')
        ui.button('Create First Mapping', on_click=on_create, icon='add').classes('bg-blue-600 text-white mt-4')


class MappingsView:
    """Coordinator: toolbar + flat/table renderers + mapping actions."""

    def __init__(self, ui_instance):
        self.ui = ui_instance
        self.view_mode = 'table'
        self.tree_container = None
        self._path_label = None
        self._search_text = ''
        self._search_input = None
        self._search_bar = None
        self._search_visible = False
        self._actions = MappingActions(ui_instance, on_refresh=self._render_current_view)
        self._builder = FileTreeBuilder(
            mapping_loader=ui_instance.mapping_loader,
            rules_engine_fn=lambda: ui_instance.proxy.get_rules_engine(),
        )

    # ── setup ─────────────────────────────────────────────────────────────────

    def setup(self):
        ui.keyboard(on_key=self._on_key, ignore=[])
        with ui.row().classes('w-full h-full'):
            with ui.column().classes('w-full h-full p-4 gap-0'):
                self._render_toolbar()
                self._render_search_bar()
                self.tree_container = ui.column().classes('w-full flex-1 overflow-auto')
                self._render_current_view()

    def refresh(self):
        if self._path_label:
            profile = self.ui.config.get_current_profile()
            profile_name = profile.name if profile else self.ui.config.current_profile
            base_path = self.ui.config.get_mappings_dir()
            self._path_label.set_text(f"{profile_name}: {base_path}")
        self._render_current_view()

    # ── keyboard ──────────────────────────────────────────────────────────────

    def _on_key(self, e):
        if not e.action.keydown:
            return
        if e.modifiers.ctrl and str(e.key) == 'f':
            # Always open/focus, never close with Ctrl+F
            self._open_search()
        elif str(e.key) == 'Escape' and self._search_visible:
            self._close_search()

    def _open_search(self):
        self._search_visible = True
        self._search_bar.style('display:flex;')
        if self._search_input:
            self._search_input.run_method('focus')

    def _toggle_search(self):
        if self._search_visible:
            self._close_search()
        else:
            self._open_search()

    def _close_search(self):
        self._search_visible = False
        self._search_bar.style('display:none;')
        self._search_text = ''
        if self._search_input:
            self._search_input.set_value('')
        self._render_current_view()

    # ── toolbar ───────────────────────────────────────────────────────────────

    def _render_toolbar(self):
        with ui.row().classes('w-full items-center gap-2 mb-2'):
            ui.toggle(
                options={'flat': 'Flat', 'table': 'Table'},
                value=self.view_mode,
                on_change=lambda e: self._on_view_change(e.value)
            ).props('dense').classes('text-sm')

            ui.button('New Mapping', on_click=self._show_new_mapping_dialog, icon='add').classes('bg-blue-600 text-white')
            ui.element('q-separator').classes('mx-2')
            ui.button('Enable All',  on_click=self._actions.enable_all,  icon='power_settings_new').props('flat dense color=green').classes('text-xs')
            ui.button('Disable All', on_click=self._actions.disable_all, icon='power_off').props('flat dense color=grey').classes('text-xs')
            ui.element('q-separator').classes('mx-2')

            profile = self.ui.config.get_current_profile()
            profile_name = profile.name if profile else self.ui.config.current_profile
            base_path = self.ui.config.get_mappings_dir()
            with ui.row().classes('items-center gap-1 flex-1'):
                ui.icon('folder', size='18px').classes('text-yellow-500')
                self._path_label = ui.label(f"{profile_name}: {base_path}").classes('text-xs text-gray-400 font-mono truncate')

            ui.button(icon='search', on_click=self._toggle_search) \
                .props('flat round dense').classes('text-gray-400').tooltip('Search (Ctrl+F)')

    # ── search bar ────────────────────────────────────────────────────────────

    def _render_search_bar(self):
        self._search_bar = ui.row().classes('w-full items-center gap-2 px-1 py-1 bg-gray-900 border border-gray-600 rounded mb-2') \
            .style('display:none;')
        with self._search_bar:
            ui.icon('search', size='18px').classes('text-gray-400 shrink-0')
            self._search_input = ui.input(
                placeholder='Search mappings... (Ctrl+F)',
                on_change=lambda e: self._on_search(e.value)
            ).props('dense outlined dark clearable').classes('flex-1').style('min-width:0;')
            self._match_label = ui.label('').classes('text-xs text-gray-400 shrink-0')
            ui.button(icon='close', on_click=self._close_search) \
                .props('flat round dense size=xs').classes('text-gray-400 shrink-0')

    def _on_search(self, value: str):
        self._search_text = value or ''
        self._render_current_view()

    # ── view dispatch ─────────────────────────────────────────────────────────

    def _on_view_change(self, mode: str):
        self.view_mode = mode
        self._render_current_view()

    def _render_current_view(self):
        if self.view_mode == 'flat':
            self._render_flat()
        else:
            self._render_table()

    # ── highlight helper ──────────────────────────────────────────────────────

    def _highlight(self, text: str) -> str:
        """Return HTML with search term highlighted in yellow."""
        if not self._search_text or not text:
            return f'<span>{text}</span>'
        import html as _html
        import re
        escaped_text = _html.escape(str(text))
        escaped_term = _html.escape(self._search_text)
        pattern = re.compile(re.escape(self._search_text), re.IGNORECASE)
        highlighted = pattern.sub(
            lambda m: f'<mark style="background:#facc15;color:#111;border-radius:2px;padding:0 1px;">{_html.escape(m.group())}</mark>',
            escaped_text
        )
        return f'<span>{highlighted}</span>'

    def _matches(self, *fields) -> bool:
        if not self._search_text:
            return True
        term = self._search_text.lower()
        return any(term in str(f).lower() for f in fields if f)

    # ── flat view ─────────────────────────────────────────────────────────────

    def _render_flat(self):
        if not self.tree_container:
            return
        self.tree_container.clear()
        with self.tree_container:
            base_path = self.ui.config.get_mappings_dir()
            tree_data = self._builder.build_tree(base_path)
            if not tree_data:
                _render_empty_state(self._show_new_mapping_dialog)
                return
            count = self._render_flat_nodes(tree_data)
            self._update_match_count(count)

    def _has_matches(self, items: list) -> bool:
        """Return True if any descendant matches the current search text."""
        for item in items:
            if item['type'] == 'directory':
                if self._has_matches(item.get('children', [])):
                    return True
            elif item['type'] == 'mapping':
                if self._matches(item.get('label'), item.get('url'), item.get('mapping_id')):
                    return True
            else:
                if self._matches(item.get('label')):
                    return True
        return False

    def _render_flat_nodes(self, items: list, level: int = 0, parent_lines: list = None) -> int:
        if parent_lines is None:
            parent_lines = []
        count = 0
        for i, item in enumerate(items):
            is_last = (i == len(items) - 1)
            prefix = ''.join('    ' if pl else '│   ' for pl in parent_lines)
            if level > 0:
                prefix += '└── ' if is_last else '├── '

            if item['type'] == 'directory':
                if self._search_text and not self._has_matches(item.get('children', [])):
                    continue
                with ui.row().classes('w-full py-1.5 px-2 bg-gray-800/40 border-b border-gray-700/30 items-center'):
                    ui.label(prefix).classes('text-xs text-gray-600 font-mono whitespace-pre')
                    ui.icon('folder', size='16px').classes('text-yellow-500 mr-1')
                    ui.html(self._highlight(item['label'])).classes('text-sm text-blue-300 font-mono flex-1')
                if item.get('children'):
                    count += self._render_flat_nodes(item['children'], level + 1, parent_lines + [is_last])

            elif item['type'] == 'mapping':
                if self._matches(item.get('label'), item.get('url'), item.get('mapping_id')):
                    self._render_flat_mapping_row(item, prefix)
                    count += 1

            else:
                if self._matches(item.get('label')):
                    with ui.row().classes('w-full py-1.5 px-2 bg-gray-800/30 border-b border-gray-700/30 items-center'):
                        ui.label(prefix).classes('text-xs text-gray-600 font-mono whitespace-pre')
                        ui.icon('insert_drive_file', size='16px').classes('text-gray-500 mr-1')
                        ui.html(self._highlight(item['label'])).classes('text-sm text-gray-400 font-mono')
                    count += 1
        return count

    def _render_flat_mapping_row(self, item: dict, prefix: str):
        is_enabled = item['is_enabled']
        is_wire = item['is_wire']
        mid = item['mapping_id']
        bg = 'bg-gray-800' if is_enabled else 'bg-gray-900 opacity-60'

        with ui.row().classes(f'w-full py-1.5 px-2 border-b border-gray-700/30 items-center hover:bg-gray-700/30 {bg}'):
            with ui.row().classes('items-center flex-1'):
                ui.label(prefix).classes('text-xs text-gray-600 font-mono whitespace-pre')
                if is_wire:
                    ui.icon('cloud', size='18px').classes('text-blue-400').tooltip('External WireMock')
                else:
                    ui.icon('description', size='18px').classes(f"text-{'green' if is_enabled else 'grey'}-400")
                ui.html(self._highlight(item['label'])).classes('text-sm text-white font-mono ml-2')
            ui.html(self._highlight(item['url'])).classes('flex-1 text-xs text-gray-400 font-mono truncate hidden md:block')
            self._render_action_buttons(mid, is_enabled, is_wire)

    # ── table view ────────────────────────────────────────────────────────────

    def _render_table(self):
        if not self.tree_container:
            return
        self.tree_container.clear()
        with self.tree_container:
            base_path = self.ui.config.get_mappings_dir()
            rows = self._builder.build_table(base_path)
            if not rows:
                _render_empty_state(self._show_new_mapping_dialog)
                return
            # Filter rows by search
            if self._search_text:
                term = self._search_text.lower()
                rows = [r for r in rows if any(
                    term in str(r.get(f, '')).lower()
                    for f in ('name', 'url', 'folder', 'mapping_id')
                )]
            self._update_match_count(len(rows))
            self._render_table_widget(rows)

    def _update_match_count(self, count: int):
        if hasattr(self, '_match_label') and self._match_label:
            if self._search_text:
                self._match_label.set_text(f'{count} match{"es" if count != 1 else ""}')
            else:
                self._match_label.set_text('')

    def _render_table_widget(self, rows: list):
        # Inject highlighted html into name/url/folder for display
        if self._search_text:
            import html as _html, re
            pattern = re.compile(re.escape(self._search_text), re.IGNORECASE)
            def hl(text):
                escaped = _html.escape(str(text or ''))
                return pattern.sub(
                    lambda m: f'<mark style="background:#facc15;color:#111;border-radius:2px;padding:0 1px;">{_html.escape(m.group())}</mark>',
                    escaped
                )
            display_rows = [{**r, '_hl_name': hl(r.get('name','')), '_hl_url': hl(r.get('url','')), '_hl_folder': hl(r.get('folder',''))} for r in rows]
        else:
            display_rows = rows

        table = ui.table(
            columns=[
                {'name': 'actions', 'label': 'Actions',     'field': 'actions', 'sortable': False, 'align': 'center'},
                {'name': 'folder',  'label': 'Path',        'field': 'folder',  'sortable': True,  'align': 'left'},
                {'name': 'name',    'label': 'File',        'field': 'name',    'sortable': True,  'align': 'left'},
                {'name': 'url',     'label': 'URL Pattern', 'field': 'url',     'sortable': True,  'align': 'left'},
            ],
            rows=display_rows,
            row_key='mapping_id',
            pagination={'rowsPerPage': 1000}
        ).classes('w-full').props('dense dark flat bordered')

        table.add_slot('body-cell-folder', '''
            <q-td :props="props">
                <span v-html="props.row._hl_folder || props.row.folder"></span>
            </q-td>
        ''')

        table.add_slot('body-cell-name', '''
            <q-td :props="props">
                <div class="row items-center no-wrap cursor-pointer"
                     @click="$parent.$emit('edit_file', { mapping_id: props.row.mapping_id, path: props.row.path })">
                    <q-icon v-if="props.row.is_wire" name="cloud" color="blue" size="18px" class="q-mr-sm" />
                    <q-icon v-else name="description" :color="props.row.status === 'Enabled' ? 'green' : 'grey'" size="18px" class="q-mr-sm" />
                    <span v-html="props.row._hl_name || props.row.name" class="text-grey-1"></span>
                    <q-badge v-if="props.row.mapping_id && props.row.status === 'Disabled'"
                             color="grey" text-color="white" dense class="q-ml-sm">OFF</q-badge>
                </div>
            </q-td>
        ''')

        table.add_slot('body-cell-url', '''
            <q-td :props="props">
                <span v-html="props.row._hl_url || props.row.url" class="text-grey-3 text-caption font-mono"></span>
            </q-td>
        ''')

        table.add_slot('body-cell-actions', '''
            <q-td :props="props">
                <div class="row items-center justify-center no-wrap q-gutter-xs">
                    <q-btn v-if="props.row.mapping_id"
                           :icon="props.row.status === 'Enabled' ? 'power_settings_new' : 'power_off'"
                           :color="props.row.status === 'Enabled' ? 'green' : 'grey'"
                           flat round dense size="sm"
                           @click="$parent.$emit('toggle', props.row.mapping_id)" />
                    <q-btn v-if="props.row.mapping_id" icon="edit"   color="blue" flat round dense size="sm" @click="$parent.$emit('edit',   props.row.mapping_id)" />
                    <q-btn v-if="props.row.mapping_id" icon="delete" color="red"  flat round dense size="sm" @click="$parent.$emit('delete', props.row.mapping_id)" />
                    <q-badge v-if="!props.row.mapping_id" color="grey" text-color="white" dense>Not loaded</q-badge>
                </div>
            </q-td>
        ''')

        table.on('toggle', lambda e: self._actions.toggle(e.args))
        table.on('edit',   lambda e: self._actions.edit(e.args))
        table.on('delete', lambda e: self._actions.delete(e.args))
        table.on('edit_file', lambda e: (
            self._actions.edit(e.args['mapping_id']) if e.args.get('mapping_id')
            else self._actions.edit_by_path(e.args.get('path', ''))
        ))

    # ── shared action buttons ─────────────────────────────────────────────────

    def _render_action_buttons(self, mid: str, is_enabled: bool, is_wire: bool):
        with ui.row().classes('gap-1'):
            ui.button(
                icon='power_settings_new' if is_enabled else 'power_off',
                on_click=lambda rid=mid: self._actions.toggle(rid)
            ).props(f"flat round color={'green' if is_enabled else 'grey'} dense").classes('w-7 h-7')
            ui.button(icon='edit',   on_click=lambda m=mid: self._actions.edit(m)).props('flat round color=blue dense').classes('w-7 h-7')
            ui.button(icon='delete', on_click=lambda m=mid: self._actions.delete(m)).props('flat round color=red dense').classes('w-7 h-7')

    # ── dialog helpers ────────────────────────────────────────────────────────

    def _show_new_mapping_dialog(self):
        MappingEditorDialog(self.ui).show_create()

    def _show_profile_manager(self):
        ProfileManagerDialog(self.ui).show()
