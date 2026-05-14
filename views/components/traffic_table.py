"""TrafficTable component — sortable table with rich visual rows + keyboard navigation."""

from nicegui import ui
from utils import format_size, format_duration


COLUMNS = [
    {'name': 'status',   'label': '',        'field': 'status',   'sortable': False, 'align': 'center', 'style': 'width:32px; padding:0 4px;'},
    {'name': 'method',   'label': 'Method',  'field': 'method',   'sortable': True,  'align': 'center', 'style': 'width:64px;'},
    {'name': 'code',     'label': 'Code',    'field': 'code',     'sortable': True,  'align': 'center', 'style': 'width:52px;'},
    {'name': 'host',     'label': 'Host',    'field': 'host',     'sortable': True,  'align': 'left',   'style': 'width:160px; max-width:160px;'},
    {'name': 'path',     'label': 'Path',    'field': 'path',     'sortable': True,  'align': 'left',   'style': 'min-width:200px;'},
    {'name': 'duration', 'label': 'Time',    'field': 'duration', 'sortable': True,  'align': 'right',  'style': 'width:72px;'},
    {'name': 'req_size', 'label': 'Req',     'field': 'req_size', 'sortable': True,  'align': 'right',  'style': 'width:56px;'},
    {'name': 'resp_size','label': 'Resp',    'field': 'resp_size','sortable': True,  'align': 'right',  'style': 'width:56px;'},
    {'name': 'time',     'label': 'At',      'field': 'time',     'sortable': True,  'align': 'center', 'style': 'width:84px;'},
]

# Rich row slot — all visual logic in Vue template to avoid full Python re-render
ROW_SLOT = r'''
<q-tr :props="props"
      :class="props.selected ? 'bg-blue-900/40' : 'hover:bg-gray-800/60'"
      style="cursor:pointer; transition: background 0.1s;"
      @click="$parent.$emit('rowClick', [null, props.row])"
      @contextmenu.prevent="$parent.$emit('rowContextmenu', [$event.clientX, $event.clientY, props.row])">

  <!-- Hide selection checkbox cell -->
  <q-td style="display:none"></q-td>

  <!-- Status icon -->
  <q-td key="status" :props="props" style="padding:0 4px; text-align:center;">
    <span v-if="props.row.status_class === 'pending'"
          style="display:inline-block;width:10px;height:10px;border-radius:50%;border:2px solid #60a5fa;border-top-color:transparent;animation:spin .8s linear infinite;"></span>
    <q-icon v-else-if="props.row.status_class === 'mocked'" name="auto_fix_high" size="14px" color="purple-4" />
    <q-icon v-else-if="props.row.status_class === 'redirect'" name="alt_route" size="14px" color="blue-4" />
    <span v-else style="color:#4ade80;font-size:8px;">●</span>
  </q-td>

  <!-- Method badge -->
  <q-td key="method" :props="props" style="padding:0 4px; text-align:center;">
    <span :style="{
      display:'inline-block', padding:'1px 5px', borderRadius:'3px',
      fontSize:'10px', fontWeight:'700', fontFamily:'monospace', letterSpacing:'0.05em',
      color: props.row.method === 'GET'    ? '#93c5fd' :
             props.row.method === 'POST'   ? '#86efac' :
             props.row.method === 'PUT'    ? '#fde047' :
             props.row.method === 'DELETE' ? '#fca5a5' :
             props.row.method === 'PATCH'  ? '#d8b4fe' : '#9ca3af',
      background: props.row.method === 'GET'    ? 'rgba(59,130,246,0.15)' :
                  props.row.method === 'POST'   ? 'rgba(34,197,94,0.15)'  :
                  props.row.method === 'PUT'    ? 'rgba(234,179,8,0.15)'  :
                  props.row.method === 'DELETE' ? 'rgba(239,68,68,0.15)'  :
                  props.row.method === 'PATCH'  ? 'rgba(168,85,247,0.15)' : 'rgba(156,163,175,0.1)'
    }">{{ props.row.method }}</span>
  </q-td>

  <!-- Status code badge -->
  <q-td key="code" :props="props" style="padding:0 4px; text-align:center;">
    <span v-if="props.row.code !== '-'" :style="{
      display:'inline-block', padding:'1px 5px', borderRadius:'3px',
      fontSize:'11px', fontWeight:'600', fontFamily:'monospace',
      color: props.row.code_num < 300 ? '#4ade80' :
             props.row.code_num < 400 ? '#facc15' :
             props.row.code_num < 500 ? '#fb923c' : '#f87171',
      background: props.row.code_num < 300 ? 'rgba(74,222,128,0.1)'  :
                  props.row.code_num < 400 ? 'rgba(250,204,21,0.1)'  :
                  props.row.code_num < 500 ? 'rgba(251,146,60,0.1)'  : 'rgba(248,113,113,0.1)'
    }">{{ props.row.code }}</span>
    <span v-else style="color:#6b7280; font-size:11px;">—</span>
  </q-td>

  <!-- Host -->
  <q-td key="host" :props="props" style="max-width:160px; overflow:hidden;">
    <span style="color:#94a3b8; font-size:11px; font-family:monospace; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; display:block;">
      {{ props.row.host }}
    </span>
  </q-td>

  <!-- Path (+ query preview) -->
  <q-td key="path" :props="props">
    <div style="display:flex; align-items:baseline; gap:4px; overflow:hidden;">
      <span style="color:#e2e8f0; font-size:11px; font-family:monospace; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; flex:1;">
        {{ props.row.path }}
      </span>
      <span v-if="props.row.type_class === 'mocked'"
            style="font-size:9px; color:#c084fc; background:rgba(168,85,247,0.15); padding:0 3px; border-radius:2px; flex-shrink:0; cursor:default;">
        {{ props.row.mock_label }}
        <q-tooltip v-if="props.row.mapping_file" anchor="top middle" self="bottom middle"
                   style="font-size:10px; font-family:monospace; background:#1e1b4b; color:#c4b5fd; padding:4px 8px; border-radius:4px; max-width:600px; word-break:break-all;">
          {{ props.row.mapping_file }}
        </q-tooltip>
      </span>
    </div>
  </q-td>

  <!-- Duration with colour coding -->
  <q-td key="duration" :props="props" style="text-align:right; padding-right:8px;">
    <span :style="{
      fontSize:'11px', fontFamily:'monospace',
      color: props.row.duration_ms < 0    ? '#6b7280' :
             props.row.duration_ms < 200  ? '#4ade80' :
             props.row.duration_ms < 1000 ? '#facc15' : '#f87171'
    }">{{ props.row.duration }}</span>
  </q-td>

  <!-- Req size -->
  <q-td key="req_size" :props="props" style="text-align:right; padding-right:8px;">
    <span style="font-size:11px; font-family:monospace; color:#64748b;">{{ props.row.req_size }}</span>
  </q-td>

  <!-- Resp size -->
  <q-td key="resp_size" :props="props" style="text-align:right; padding-right:8px;">
    <span style="font-size:11px; font-family:monospace; color:#64748b;">{{ props.row.resp_size }}</span>
  </q-td>

  <!-- Time / At -->
  <q-td key="time" :props="props" style="text-align:center; max-width:84px; overflow:hidden;">
    <span style="font-size:10px; font-family:monospace; color:#475569;">{{ props.row.time }}</span>
  </q-td>

</q-tr>
'''


def _parse_url(url: str) -> tuple[str, str]:
    """Split a URL into (host, path_with_query)."""
    try:
        from urllib.parse import urlparse
        p = urlparse(url)
        host = p.netloc or p.hostname or url
        path = p.path or '/'
        if p.query:
            path += '?' + p.query[:80]
        return host, path
    except Exception:
        return url, '/'


def _duration_ms(entry) -> float:
    if entry.response and entry.response.duration_ms is not None:
        return entry.response.duration_ms
    return -1


def _build_row(idx: int, entry) -> dict:
    is_pending = entry.response is None
    is_mocked  = entry.operation_type in ('redirect', 'mock')
    url        = entry.original_url or entry.request.url
    host, path = _parse_url(url)
    dur_ms     = _duration_ms(entry)

    if is_pending:
        status_class = 'pending'
    elif entry.operation_type == 'redirect':
        status_class = 'redirect'
    elif is_mocked:
        status_class = 'mocked'
    else:
        status_class = 'normal'

    # Build the mock label: profile name if set, else operation type abbreviation
    if is_mocked:
        if entry.operation_type == 'redirect':
            mock_label = (entry.profile_name or 'REDIRECT').upper()
        else:
            mock_label = (entry.profile_name or 'MOCK').upper()
    else:
        mock_label = ''

    code_raw = str(entry.response.status_code) if entry.response else '-'
    try:
        code_num = int(code_raw)
    except ValueError:
        code_num = 0

    return {
        'entry_id':   entry.id,
        'idx':        idx,
        'full_url':   url,
        'host':       host,
        'path':       path,
        'method':     entry.request.method,
        'type_class': 'mocked' if is_mocked else 'normal',
        'code':       code_raw,
        'code_num':   code_num,
        'time':       entry.request.timestamp.strftime('%H:%M:%S.%f')[:-3],
        'duration':   format_duration(dur_ms) if dur_ms >= 0 else '—',
        'duration_ms': dur_ms,
        'req_size':   format_size(entry.request.size),
        'resp_size':  format_size(entry.response.size) if entry.response else '—',
        'status':     '',           # kept for compat
        'status_class': status_class,
        'mock_label':   mock_label,
        'mapping_file': getattr(entry, 'mapping_file', None) or '',
    }


class TrafficTable:
    """Renders the traffic table with rich visual rows."""

    def __init__(self, on_select, on_contextmenu, on_delete=None):
        self._on_select      = on_select
        self._on_contextmenu = on_contextmenu
        self._on_delete      = on_delete
        self._entries: list  = []
        self._rows_cache: list = []
        self._selected_entry_id: str | None = None
        self._selection_ids: set = set()      # multi-selection
        self._current_idx: int   = -1         # keyboard cursor
        self._table      = None
        self._ctx_anchor = None
        self._ctx_menu   = None
        self._keyboard   = None

    # ── public API ───────────────────────────────────────────────────────────

    def setup_keyboard(self):
        """Create the keyboard handler — call once from MonitorView.setup()."""
        self._keyboard = ui.keyboard(on_key=self._handle_key, ignore=[])

    def render(self, container, entries: list):
        self._entries    = entries
        self._rows_cache = [_build_row(i, e) for i, e in enumerate(entries[:500])]

        # Restore pre-selection
        pre_selected = [r for r in self._rows_cache if r['entry_id'] in self._selection_ids] \
                       if self._selection_ids else \
                       [r for r in self._rows_cache if r['entry_id'] == self._selected_entry_id]

        container.clear()
        with container:
            table = ui.table(
                columns=COLUMNS,
                rows=self._rows_cache,
                row_key='entry_id',
                selection='single',
            ).classes('w-full h-full bg-gray-900 text-gray-300').props(
                'dense flat bordered hide-selected-banner'
            ).style('font-size:12px;')
            table.props('table-class="bg-gray-900"')
            table.props('color="grey-9"')
            table.on('rowClick',       self._handle_click)
            table.on('rowContextmenu', self._handle_contextmenu)
            table.add_slot('body', ROW_SLOT)

            if pre_selected:
                table.selected = pre_selected

            self._table = table

            self._ctx_anchor = ui.element('div').style('position:fixed;width:0;height:0;z-index:9999')
            with self._ctx_anchor:
                self._ctx_menu = ui.menu()

    def show_context_menu(self, entry, x: float, y: float, items: list[tuple]):
        if not self._ctx_menu:
            return
        self._ctx_anchor.style(f'position:fixed;left:{x}px;top:{y}px;width:0;height:0')
        self._ctx_menu.clear()
        with self._ctx_menu:
            for label, cb in items:
                ui.menu_item(label, on_click=cb).classes('text-sm')
        self._ctx_menu.open()

    # ── keyboard ─────────────────────────────────────────────────────────────

    def _handle_key(self, e):
        if not e.action.keydown:
            return
        name = e.key.name
        if name == 'ArrowDown' and e.modifiers.shift:
            self._extend_selection(+1)
        elif name == 'ArrowUp' and e.modifiers.shift:
            self._extend_selection(-1)
        elif name == 'Delete':
            self._delete_selected()

    def _extend_selection(self, direction: int):
        if not self._entries:
            return
        # Anchor at current_idx; if not set yet, start from selected row
        if self._current_idx < 0:
            # find current selected in rows
            for i, r in enumerate(self._rows_cache):
                if r['entry_id'] == self._selected_entry_id:
                    self._current_idx = i
                    self._selection_ids.add(self._selected_entry_id)
                    break
            if self._current_idx < 0:
                return

        new_idx = max(0, min(len(self._entries) - 1, self._current_idx + direction))
        if new_idx == self._current_idx:
            return

        self._current_idx = new_idx
        entry = self._entries[new_idx]
        self._selection_ids.add(entry.id)
        self._selected_entry_id = entry.id

        # Update visual selection
        if self._table:
            self._table.selected = [r for r in self._rows_cache if r['entry_id'] in self._selection_ids]

        self._on_select(entry)

    def _delete_selected(self):
        ids = self._selection_ids or ({self._selected_entry_id} if self._selected_entry_id else set())
        if ids and self._on_delete:
            self._on_delete(list(ids))
            self._selection_ids.clear()
            self._current_idx    = -1
            self._selected_entry_id = None

    # ── row events ────────────────────────────────────────────────────────────

    def _handle_click(self, e):
        try:
            if isinstance(e.args, list) and len(e.args) >= 2:
                row = e.args[1]
                idx = row.get('idx')
                if idx is not None and 0 <= idx < len(self._entries):
                    entry = self._entries[idx]
                    # Normal click resets multi-selection
                    self._selection_ids.clear()
                    self._current_idx       = idx
                    self._selected_entry_id = entry.id
                    self._selection_ids.add(entry.id)
                    self._on_select(entry)
                    if self._table:
                        self._table.selected = [row]
        except Exception:
            pass

    def _handle_contextmenu(self, e):
        try:
            if isinstance(e.args, list) and len(e.args) >= 3:
                x, y, row = e.args[0], e.args[1], e.args[2]
                idx = row.get('idx')
                if idx is not None and 0 <= idx < len(self._entries):
                    entry = self._entries[idx]
                    # If right-clicked row not in selection, reset to it
                    if entry.id not in self._selection_ids:
                        self._selection_ids.clear()
                        self._current_idx       = idx
                        self._selected_entry_id = entry.id
                        self._selection_ids.add(entry.id)
                        self._on_select(entry)
                        if self._table:
                            self._table.selected = [row]
                    self._on_contextmenu(entry, x, y)
        except Exception:
            pass
