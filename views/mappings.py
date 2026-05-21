"""Mappings view — coordinator for rule management."""

import json as _json
import re as _re
from nicegui import ui
from dialogs import MappingEditorDialog, ProfileManagerDialog
from .components import FileTreeBuilder, MappingActions


def _render_empty_state(on_create):
    with ui.column().classes('w-full h-64 items-center justify-center'):
        ui.icon('folder_open', size='48px').classes('text-gray-600 mb-4')
        ui.label("No mappings configured").classes('text-gray-500 text-lg')
        ui.label("Create rules in the Monitor tab or click 'New Mapping'").classes('text-gray-600 text-sm')
        ui.button('Create First Mapping', on_click=on_create, icon='add').classes('bg-blue-600 text-white mt-4')


# ── Conflict detection ────────────────────────────────────────────────────────
#
# Two-phase approach:
#   1. Check if URL patterns overlap (could match the same path).
#   2. If URLs overlap, check whether method / queryParameters / headers /
#      bodyPatterns make the pair mutually exclusive. If we can PROVE they can
#      never match the same request → no conflict.
#
# Conservative rule: when in doubt, flag as conflict.

def _literal_prefix(s: str) -> str:
    """Longest literal (non-wildcard/regex) prefix of a URL-like string."""
    s = s.split('?')[0]
    s = _re.split(r'[*.()\[\]{}\\+|^$]', s)[0]
    return s.lower().rstrip('/')


def _wildcard_to_regex(pattern: str) -> str:
    escaped = _re.escape(pattern).replace(r'\*', '.*').replace(r'\?', '.')
    return f'^{escaped}$'


# ── Phase 1: URL overlap ──────────────────────────────────────────────────────

def _url_pattern_matches(match_type: str, match_value: str, candidate: str) -> bool:
    """Does the pattern (match_type, match_value) match the candidate string?"""
    c, v = candidate.lower(), match_value.lower()
    mt = match_type.upper()
    if mt in ('EQUALS', 'EQUAL'):
        return v == c
    if mt in ('CONTAINS', 'CONTAIN'):
        return v in c
    if mt == 'STARTS_WITH':
        return c.startswith(v)
    if mt == 'ENDS_WITH':
        return c.endswith(v)
    if mt == 'WILDCARD':
        try:
            return bool(_re.match(_wildcard_to_regex(match_value), candidate, _re.IGNORECASE))
        except Exception:
            return False
    if mt in ('REGEX', 'REGEXP'):
        try:
            return bool(_re.search(match_value, candidate, _re.IGNORECASE))
        except Exception:
            return False
    return False


def _default_urls_overlap(req_a: dict, req_b: dict) -> bool:
    """Return True if the two default-style URL patterns could match the same URL."""
    mt_a = req_a.get('matchType', 'EQUALS').upper()
    mv_a = req_a.get('matchValue', '')
    mt_b = req_b.get('matchType', 'EQUALS').upper()
    mv_b = req_b.get('matchValue', '')
    if not mv_a or not mv_b:
        return False
    # If B is exact, check if A's pattern matches it (and vice-versa)
    if mt_b in ('EQUALS', 'EQUAL') and _url_pattern_matches(mt_a, mv_a, mv_b):
        return True
    if mt_a in ('EQUALS', 'EQUAL') and _url_pattern_matches(mt_b, mv_b, mv_a):
        return True
    # Both non-exact: overlap when literal prefixes share a common root
    la, lb = _literal_prefix(mv_a), _literal_prefix(mv_b)
    return bool(la and lb and (la.startswith(lb) or lb.startswith(la)))


def _wire_urls_overlap(req_a: dict, req_b: dict) -> bool:
    """
    Return True if the two Wire-style URL patterns could match the same request.

    WireMock URL field semantics:
      urlPath        — exact path match, query string ignored
      url            — exact full URL match (path + query string)
      urlPathPattern — regex on path only, query string ignored
      urlPattern     — regex on full URL (path + query); \\? is a literal '?'

    All 10 combinations are handled explicitly to avoid false positives.
    """
    def field_of(r: dict):
        for k in ('urlPath', 'url', 'urlPathPattern', 'urlPattern'):
            v = r.get(k)
            if v:
                return k, v.lower()
        return None, ''

    def strip_query_exact(s: str) -> str:
        """Strip query string from an exact URL (bare '?' is the separator)."""
        return s.split('?')[0].rstrip('/')

    def strip_query_pattern(s: str) -> str:
        """Strip query from a WireMock regex URL (\\? is a literal '?' separator)."""
        return s.split('\\?')[0].rstrip('/')

    def literal_prefix(s: str) -> str:
        return _re.split(r'[.*+?()\[\]{}\\|^$]', s)[0]

    def try_match(pattern: str, target: str) -> bool:
        try:
            return bool(_re.search(pattern, target, _re.IGNORECASE))
        except Exception:
            return False

    def simplify_pattern(s: str) -> str:
        """Minimal concrete string: remove optional groups and wildcards.
        Used to cross-test two regex patterns without full regex intersection."""
        r = _re.sub(r'\(\?:[^)]*\)\?', '', s)   # (?:...)?  → ''
        r = _re.sub(r'\([^)]*\)\?',    '', r)    # (...)?    → ''
        r = r.replace('.*', '').replace('.+', 'x')
        return r

    fa, va = field_of(req_a)
    fb, vb = field_of(req_b)
    if not va or not vb:
        return False

    pair = frozenset({fa, fb})

    # ── urlPath vs urlPath ────────────────────────────────────────────────────
    # Both match exact path, query ignored. Conflict iff paths equal.
    if fa == 'urlPath' and fb == 'urlPath':
        return va.rstrip('/') == vb.rstrip('/')

    # ── url vs url ────────────────────────────────────────────────────────────
    # Both match full URL including query. Conflict iff entire URL identical.
    if fa == 'url' and fb == 'url':
        return va.rstrip('/') == vb.rstrip('/')

    # ── urlPath vs url ────────────────────────────────────────────────────────
    # urlPath ignores query; url includes it. A request to `url` also satisfies
    # urlPath if their path portions are equal.
    if pair == {'urlPath', 'url'}:
        path_val = va if fa == 'urlPath' else vb
        url_val  = va if fa == 'url'     else vb
        return strip_query_exact(url_val) == path_val.rstrip('/')

    # ── urlPathPattern vs urlPath ─────────────────────────────────────────────
    # Regex matches path; exact path is a valid candidate to test directly.
    if pair == {'urlPathPattern', 'urlPath'}:
        pat   = va if fa == 'urlPathPattern' else vb
        exact = va if fa == 'urlPath'        else vb
        return try_match(pat, exact.rstrip('/'))

    # ── urlPathPattern vs url ─────────────────────────────────────────────────
    # Regex matches path; strip query from url before testing.
    if pair == {'urlPathPattern', 'url'}:
        pat = va if fa == 'urlPathPattern' else vb
        url = va if fa == 'url'           else vb
        return try_match(pat, strip_query_exact(url))

    # ── urlPattern vs urlPath ─────────────────────────────────────────────────
    # urlPattern can match any URL that starts with the exact path (no query).
    if pair == {'urlPattern', 'urlPath'}:
        pat   = va if fa == 'urlPattern' else vb
        exact = va if fa == 'urlPath'    else vb
        return try_match(pat, exact.rstrip('/'))

    # ── urlPattern vs url ─────────────────────────────────────────────────────
    # Test the full URL regex against the exact URL value.
    if pair == {'urlPattern', 'url'}:
        pat = va if fa == 'urlPattern' else vb
        url = va if fa == 'url'        else vb
        return try_match(pat, url.rstrip('/'))

    # ── urlPathPattern vs urlPathPattern ─────────────────────────────────────
    if fa == 'urlPathPattern' and fb == 'urlPathPattern':
        la, lb = literal_prefix(va), literal_prefix(vb)
        if not (la and lb and (la.startswith(lb) or lb.startswith(la))):
            return False
        if la == va:
            return try_match(vb, va)
        if lb == vb:
            return try_match(va, vb)
        # Both have regex chars: cross-test with minimal concrete strings
        sa, sb = simplify_pattern(va), simplify_pattern(vb)
        if sa and sb and not try_match(va, sb) and not try_match(vb, sa):
            return False
        return True

    # ── urlPattern vs urlPattern ──────────────────────────────────────────────
    if fa == 'urlPattern' and fb == 'urlPattern':
        pa_path = strip_query_pattern(va)
        pb_path = strip_query_pattern(vb)
        la, lb = literal_prefix(pa_path), literal_prefix(pb_path)
        if not (la and lb and (la.startswith(lb) or lb.startswith(la))):
            return False
        if la == pa_path:
            return try_match(vb, va)
        if lb == pb_path:
            return try_match(va, vb)
        # Both have regex chars: cross-test with minimal concrete strings (path only)
        sa, sb = simplify_pattern(pa_path), simplify_pattern(pb_path)
        if sa and sb and not try_match(pa_path, sb) and not try_match(pb_path, sa):
            return False
        return True

    # ── urlPathPattern vs urlPattern ──────────────────────────────────────────
    if pair == {'urlPathPattern', 'urlPattern'}:
        path_pat = va if fa == 'urlPathPattern' else vb
        url_pat  = va if fa == 'urlPattern'     else vb
        url_path = strip_query_pattern(url_pat)
        la = literal_prefix(path_pat)
        lb = literal_prefix(url_path)
        if not (la and lb and (la.startswith(lb) or lb.startswith(la))):
            return False
        if la == path_pat:
            return try_match(url_path, path_pat)
        if lb == url_path:
            return try_match(path_pat, url_path)
        # Both have regex chars: cross-test with minimal concrete strings
        sa, sb = simplify_pattern(path_pat), simplify_pattern(url_path)
        if sa and sb and not try_match(path_pat, sb) and not try_match(url_path, sa):
            return False
        return True

    return False


# ── Phase 2: mutual exclusion across other dimensions ────────────────────────

def _methods_exclusive(req_a: dict, req_b: dict) -> bool:
    """True if both specify different concrete HTTP methods (neither is ANY/*)."""
    ma = req_a.get('method', 'ANY').upper().strip()
    mb = req_b.get('method', 'ANY').upper().strip()
    return ma not in ('ANY', '', '*') and mb not in ('ANY', '', '*') and ma != mb


def _json_has_conflict(obj_a, obj_b) -> bool:
    """
    True if two JSON objects share at least one key whose values are incompatible
    (i.e. no single request body could satisfy both patterns simultaneously).
    Handles scalars, nested objects, and arrays (WireMock ignoreArrayOrder → set compare).
    """
    if not isinstance(obj_a, dict) or not isinstance(obj_b, dict):
        return False
    for key in set(obj_a) & set(obj_b):
        va, vb = obj_a[key], obj_b[key]
        if isinstance(va, (str, int, float, bool)) and isinstance(vb, (str, int, float, bool)):
            if va != vb:
                return True
        elif isinstance(va, list) and isinstance(vb, list):
            # WireMock compares array elements exactly (ignoreExtraElements doesn't
            # apply to array items), ignoreArrayOrder only relaxes ordering.
            # If the sets of elements differ, no single request can satisfy both.
            try:
                if {str(x) for x in va} != {str(x) for x in vb}:
                    return True
            except Exception:
                pass
        elif isinstance(va, dict) and isinstance(vb, dict):
            if _json_has_conflict(va, vb):
                return True
    return False


def _wire_body_exclusive(req_a: dict, req_b: dict) -> bool:
    """
    True if Wire bodyPatterns make the pair mutually exclusive.
    Handles both `equalTo` (plain string) and `equalToJson` (JSON object/string).
    """
    bp_a = req_a.get('bodyPatterns', [])
    bp_b = req_b.get('bodyPatterns', [])
    if not bp_a or not bp_b:
        return False

    # ── equalTo (plain string comparison) ────────────────────────────────────
    eq_a = {p['equalTo'] for p in bp_a if 'equalTo' in p}
    eq_b = {p['equalTo'] for p in bp_b if 'equalTo' in p}
    if eq_a and eq_b and eq_a.isdisjoint(eq_b):
        return True

    # ── equalToJson (structural comparison) ──────────────────────────────────
    def _parse_etj(raw):
        if isinstance(raw, dict):
            return raw
        try:
            return _json.loads(raw)
        except Exception:
            return None

    etj_a = [_parse_etj(p['equalToJson']) for p in bp_a if 'equalToJson' in p]
    etj_b = [_parse_etj(p['equalToJson']) for p in bp_b if 'equalToJson' in p]
    etj_a = [o for o in etj_a if o is not None]
    etj_b = [o for o in etj_b if o is not None]

    if etj_a and etj_b:
        for obj_a in etj_a:
            for obj_b in etj_b:
                if _json_has_conflict(obj_a, obj_b):
                    return True

    return False


def _wire_query_exclusive(req_a: dict, req_b: dict) -> bool:
    """
    True if both specify the same query parameter with incompatible equalTo values.
    """
    qp_a = req_a.get('queryParameters', {})
    qp_b = req_b.get('queryParameters', {})
    for param in set(qp_a) & set(qp_b):
        va = qp_a[param].get('equalTo')
        vb = qp_b[param].get('equalTo')
        if va is not None and vb is not None and str(va) != str(vb):
            return True
    return False


def _wire_headers_exclusive(req_a: dict, req_b: dict) -> bool:
    """
    True if both require the same header with incompatible equalTo values.
    """
    ha = req_a.get('headers', {})
    hb = req_b.get('headers', {})
    for header in set(ha) & set(hb):
        va = ha[header].get('equalTo')
        vb = hb[header].get('equalTo')
        if va is not None and vb is not None and str(va) != str(vb):
            return True
    return False


def _wire_mutually_exclusive(req_a: dict, req_b: dict) -> bool:
    return (
        _methods_exclusive(req_a, req_b)
        or _wire_body_exclusive(req_a, req_b)
        or _wire_query_exclusive(req_a, req_b)
        or _wire_headers_exclusive(req_a, req_b)
    )


def _default_body_exclusive(req_a: dict, req_b: dict) -> bool:
    """True if default-style body matchers are mutually exclusive (both 'equal' with different values)."""
    if not req_a.get('bodyMatch') or not req_b.get('bodyMatch'):
        return False
    bmt_a = req_a.get('bodyMatchType', 'contains').lower()
    bmt_b = req_b.get('bodyMatchType', 'contains').lower()
    if bmt_a not in ('equal', 'equals') or bmt_b not in ('equal', 'equals'):
        return False
    bmv_a = req_a.get('bodyMatchValue', '')
    bmv_b = req_b.get('bodyMatchValue', '')
    return bool(bmv_a and bmv_b and bmv_a != bmv_b)


def _default_mutually_exclusive(req_a: dict, req_b: dict) -> bool:
    return (
        _methods_exclusive(req_a, req_b)
        or _default_body_exclusive(req_a, req_b)
    )


# ── Combined entry-level check ────────────────────────────────────────────────

def _entries_could_conflict(a: dict, b: dict) -> bool:
    mt_a = a['mapping_type'].lower()
    mt_b = b['mapping_type'].lower()

    # Phase 1: do URL patterns overlap?
    if mt_a == mt_b:
        if mt_a == 'wire':
            url_ok = _wire_urls_overlap(a['request'], b['request'])
        else:
            url_ok = _default_urls_overlap(a['request'], b['request'])
    else:
        la = _literal_prefix(a['url'])
        lb = _literal_prefix(b['url'])
        url_ok = bool(la and lb and (la.startswith(lb) or lb.startswith(la)))

    if not url_ok:
        return False

    # Phase 2: can we prove another dimension is mutually exclusive?
    if mt_a == mt_b:
        if mt_a == 'wire':
            return not _wire_mutually_exclusive(a['request'], b['request'])
        return not _default_mutually_exclusive(a['request'], b['request'])

    # Mixed mapping types — assume conflict when URLs overlap
    return True


def detect_conflicts(file_info: dict) -> list:
    """Return list of direct conflict pairs; each element is [rule_id_a, rule_id_b]."""
    entries = [
        {
            'rule_id': rid,
            'url': info.get('url', ''),
            'request': info.get('request', {}),
            'mapping_type': info.get('mapping_type', ''),
            'request_file': info.get('request_file', ''),
        }
        for rid, info in file_info.items()
    ]
    if len(entries) < 2:
        return []

    pairs = []
    n = len(entries)
    for i in range(n):
        for j in range(i + 1, n):
            if _entries_could_conflict(entries[i], entries[j]):
                pairs.append([entries[i]['rule_id'], entries[j]['rule_id']])
    return pairs


def group_conflicts_by_anchor(pairs: list, file_info: dict) -> list:
    """
    Group conflict pairs by anchor (the more permissive mapping).
    Anchor priority: regex field > exact field; then higher conflict degree.
    Returns list of (anchor_rid, [dependent_rid, ...]).
    """
    degree: dict = {}
    for a, b in pairs:
        degree[a] = degree.get(a, 0) + 1
        degree[b] = degree.get(b, 0) + 1

    anchor_to_deps: dict = {}
    for rid_a, rid_b in pairs:
        req_a = file_info.get(rid_a, {}).get('request', {})
        req_b = file_info.get(rid_b, {}).get('request', {})
        a_regex = bool(req_a.get('urlPattern') or req_a.get('urlPathPattern'))
        b_regex = bool(req_b.get('urlPattern') or req_b.get('urlPathPattern'))

        if a_regex and not b_regex:
            anchor, dep = rid_a, rid_b
        elif b_regex and not a_regex:
            anchor, dep = rid_b, rid_a
        elif degree.get(rid_a, 0) >= degree.get(rid_b, 0):
            anchor, dep = rid_a, rid_b
        else:
            anchor, dep = rid_b, rid_a

        anchor_to_deps.setdefault(anchor, [])
        if dep not in anchor_to_deps[anchor]:
            anchor_to_deps[anchor].append(dep)

    return list(anchor_to_deps.items())


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
        self._active_subtab = 'all'
        self._panel_all = None
        self._panel_conflicts = None
        self._btn_subtab_all = None
        self._btn_subtab_conflicts = None
        self._conflicts_container = None
        self._conflict_cache: dict | None = None   # {pairs, groups} — invalidated on refresh
        self._conflicts_page = 0                   # current page index (pagination)
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
                # Primary navigation: tabs at top
                self._render_subtab_bar()

                # Panel: All Mappings
                self._panel_all = ui.column().classes('w-full flex-1 overflow-hidden gap-0')
                with self._panel_all:
                    self._render_toolbar()
                    self._render_search_bar()
                    self.tree_container = ui.column().classes('w-full flex-1 overflow-auto')
                    self._render_current_view()

                # Panel: Conflicts
                self._panel_conflicts = ui.column().classes('w-full flex-1 overflow-auto').style('display:none;')
                with self._panel_conflicts:
                    self._conflicts_container = ui.column().classes('w-full gap-3')
                    self._render_conflicts()

    def refresh(self):
        self._conflict_cache = None          # invalidate on any data change
        self._conflicts_page = 0
        if self._path_label:
            profile = self.ui.config.get_current_profile()
            profile_name = profile.name if profile else self.ui.config.current_profile
            base_path = self.ui.config.get_mappings_dir()
            self._path_label.set_text(f"{profile_name}: {base_path}")
        self._render_current_view()
        self._refresh_subtab_label()
        if self._active_subtab == 'conflicts':
            self._render_conflicts()

    def _get_conflicts(self) -> tuple:
        """Cached (pairs, groups) — recomputed only when cache is invalidated."""
        if self._conflict_cache is None:
            pairs = detect_conflicts(self.ui.mapping_loader.file_info)
            groups = group_conflicts_by_anchor(pairs, self.ui.mapping_loader.file_info)
            self._conflict_cache = {'pairs': pairs, 'groups': groups}
        return self._conflict_cache['pairs'], self._conflict_cache['groups']

    # ── sub-tabs ──────────────────────────────────────────────────────────────

    def _render_subtab_bar(self):
        _, groups = self._get_conflicts()
        total = len(groups)
        conflicts_label = f'Conflictos ({total})' if total else 'Conflictos'

        with ui.row().classes('w-full items-center gap-1 mb-2 border-b border-gray-700 pb-1'):
            self._btn_subtab_all = (
                ui.button('Todos los Mappings', on_click=lambda: self._switch_subtab('all'))
                .props('flat dense').classes('text-sm text-white font-semibold')
            )
            with ui.row().classes('items-center gap-1'):
                self._btn_subtab_conflicts = (
                    ui.button(conflicts_label, on_click=lambda: self._switch_subtab('conflicts'))
                    .props('flat dense').classes('text-sm text-gray-400')
                )
                if total:
                    ui.icon('warning_amber', size='16px').classes('text-yellow-400')
        self._update_subtab_styles()

    def _refresh_subtab_label(self):
        if not self._btn_subtab_conflicts:
            return
        _, groups = self._get_conflicts()
        total = len(groups)
        label = f'Conflictos ({total})' if total else 'Conflictos'
        self._btn_subtab_conflicts.set_text(label)

    def _switch_subtab(self, tab: str):
        self._active_subtab = tab
        self._update_subtab_styles()
        if tab == 'all':
            if self._panel_all:
                self._panel_all.style('display:flex;')
            if self._panel_conflicts:
                self._panel_conflicts.style('display:none;')
        else:
            if self._panel_all:
                self._panel_all.style('display:none;')
            if self._panel_conflicts:
                self._panel_conflicts.style('display:flex;')
            self._render_conflicts()

    def _update_subtab_styles(self):
        if not self._btn_subtab_all:
            return
        if self._active_subtab == 'all':
            self._btn_subtab_all.classes('text-white font-semibold', remove='text-gray-400')
            self._btn_subtab_conflicts.classes('text-gray-400', remove='text-white font-semibold')
        else:
            self._btn_subtab_conflicts.classes('text-white font-semibold', remove='text-gray-400')
            self._btn_subtab_all.classes('text-gray-400', remove='text-white font-semibold')

    # ── conflicts view ────────────────────────────────────────────────────────

    _PAGE_SIZE = 20

    def _render_conflicts(self):
        if not self._conflicts_container:
            return
        self._conflicts_container.clear()
        with self._conflicts_container:
            file_info = self.ui.mapping_loader.file_info
            engine = self.ui.proxy.get_rules_engine()
            pairs, groups = self._get_conflicts()

            if not groups:
                with ui.column().classes('w-full h-64 items-center justify-center'):
                    ui.icon('check_circle', size='48px').classes('text-green-500 mb-4')
                    ui.label('No se detectaron conflictos').classes('text-gray-400 text-lg')
                    ui.label('Todos los mappings tienen patrones de URL únicos').classes('text-gray-600 text-sm')
                return

            unique = len({rid for pair in pairs for rid in pair})

            def _pattern_detail(rid: str) -> str:
                info = file_info.get(rid, {})
                req = info.get('request', {})
                is_wire = info.get('mapping_type', '').lower() == 'wire'
                if is_wire:
                    parts = []
                    for key in ('urlPath', 'url', 'urlPattern', 'urlPathPattern'):
                        if req.get(key):
                            parts.append(f'{key}={req[key]}')
                    if req.get('queryParameters'):
                        qp = ', '.join(
                            f'{k}={list(v.values())[0] if v else v}'
                            for k, v in req['queryParameters'].items()
                        )
                        parts.append(f'query: {qp}')
                    if req.get('method') and req['method'] != 'ANY':
                        parts.append(req['method'])
                    return ' · '.join(parts)
                else:
                    mt = req.get('matchType', '')
                    mv = req.get('matchValue', info.get('url', ''))
                    return f'{mt}: {mv}' if mt else mv

            def _mapping_row(rid: str, indent: bool = False):
                info = file_info.get(rid)
                if not info:
                    return
                rule = next((r for r in engine.rules if r.id == rid), None)
                is_enabled = rule.enabled if rule else True
                is_wire = info.get('mapping_type', '').lower() == 'wire'
                filename = info.get('request_file', rid)
                detail = _pattern_detail(rid)
                opacity = '' if is_enabled else 'opacity-50'
                indent_cls = 'pl-6' if indent else 'pl-2'

                priority = None
                try:
                    priority = _json.loads(info.get('full_json', '{}')).get('priority')
                except Exception:
                    pass

                with ui.row().classes(f'w-full items-start gap-2 py-1.5 pr-2 {indent_cls} {opacity} hover:bg-gray-700/20') \
                        .style('min-width:0;'):
                    if indent:
                        ui.icon('subdirectory_arrow_right', size='14px').classes('text-gray-500 shrink-0')
                    if is_wire:
                        ui.icon('cloud', size='16px').classes('text-blue-400 shrink-0')
                    else:
                        color = 'green' if is_enabled else 'grey'
                        ui.icon('description', size='16px').classes(f'text-{color}-400 shrink-0')

                    with ui.column().classes('flex-1 gap-0 min-w-0 cursor-pointer') \
                            .on('click', lambda r=rid: self._actions.edit(r)):
                        ui.label(filename).classes('text-xs text-gray-300 font-mono break-all w-full')
                        ui.label(detail).classes('text-xs text-yellow-300/80 font-mono break-all w-full')
                        if priority is not None:
                            ui.label(f'priority: {priority}').classes('text-xs text-purple-300/80 font-mono')

                    with ui.row().classes('gap-1 shrink-0'):
                        ui.button(
                            icon='power_settings_new' if is_enabled else 'power_off',
                            on_click=lambda r=rid: self._actions.toggle(r),
                        ).props(f"flat round dense color={'green' if is_enabled else 'grey'} size=xs")
                        ui.button(icon='edit', on_click=lambda r=rid: self._actions.edit(r)) \
                            .props('flat round dense color=blue size=xs')
                        ui.button(icon='delete', on_click=lambda r=rid: self._actions.delete(r)) \
                            .props('flat round dense color=red size=xs')

            n_groups = len(groups)
            page = self._conflicts_page
            page_size = self._PAGE_SIZE
            start = page * page_size
            end = min(start + page_size, n_groups)
            visible = groups[start:end]

            ui.label(
                f'{n_groups} grupo{"s" if n_groups != 1 else ""} de conflicto'
                f' · {unique} mappings afectados'
                + (f' · mostrando {start + 1}–{end}' if n_groups > page_size else '')
            ).classes('text-yellow-400 text-sm font-semibold px-1 mb-1')

            for anchor_rid, dep_rids in visible:
                if anchor_rid not in file_info:
                    continue
                with ui.card().classes('w-full bg-gray-800/60 border border-yellow-700/40 rounded mb-2 p-0 gap-0'):
                    _mapping_row(anchor_rid, indent=False)
                    with ui.row().classes('w-full items-center px-3 py-0.5 gap-1 bg-yellow-900/20 border-t border-yellow-700/20'):
                        ui.icon('warning_amber', size='13px').classes('text-yellow-500')
                        n_deps = len(dep_rids)
                        ui.label(
                            f'solapa con {n_deps} mapping{"s" if n_deps != 1 else ""}'
                        ).classes('text-xs text-yellow-600/80')
                    for dep_rid in dep_rids:
                        if dep_rid in file_info:
                            _mapping_row(dep_rid, indent=True)

            # Pagination controls
            if n_groups > page_size:
                with ui.row().classes('w-full justify-center items-center gap-2 mt-2'):
                    ui.button(
                        icon='chevron_left',
                        on_click=lambda: self._conflicts_go(page - 1),
                    ).props('flat round dense color=white').props(
                        'disabled' if page == 0 else ''
                    )
                    last_page = (n_groups - 1) // page_size
                    ui.label(f'{page + 1} / {last_page + 1}').classes('text-xs text-gray-400')
                    ui.button(
                        icon='chevron_right',
                        on_click=lambda: self._conflicts_go(page + 1),
                    ).props('flat round dense color=white').props(
                        'disabled' if page >= last_page else ''
                    )

    def _conflicts_go(self, page: int):
        pairs, groups = self._get_conflicts()
        last = max(0, (len(groups) - 1) // self._PAGE_SIZE)
        self._conflicts_page = max(0, min(page, last))
        self._render_conflicts()

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
