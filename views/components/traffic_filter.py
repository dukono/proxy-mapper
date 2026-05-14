"""TrafficFilter component — filter bar + match logic."""

import re
from nicegui import ui


FILTER_FIELDS = ['ALL', 'URL', 'Query', 'Hdr', 'Body', 'Meth', 'Code']
MATCH_TYPES = ['Contains', 'Not Contains', 'Starts', 'Ends', 'Equals', 'Not Equals', 'Regex']


def apply_match(text: str, pattern: str, match_type: str) -> bool:
    if not text:
        return False
    tl, pl = text.lower(), pattern.lower()
    if match_type in ('Contains', 'Has'):        return pl in tl
    if match_type in ('Not Contains', 'No'):     return pl not in tl
    if match_type in ('Starts With', 'Starts', '^'): return tl.startswith(pl)
    if match_type in ('Ends With', 'Ends', '$'): return tl.endswith(pl)
    if match_type in ('Equals', 'Equal', 'Eq', '='): return tl == pl
    if match_type in ('Not Equals', 'Not Equal', 'Not Eq', '!='): return tl != pl
    if match_type in ('Regex', 'Reg'):
        try:    return bool(re.search(pattern, text, re.IGNORECASE))
        except re.error: return False
    return pl in tl


def matches_entry(entry, filter_text: str, field: str, match_type: str) -> bool:
    if not filter_text:
        return True

    if field == 'ALL':
        url = entry.original_url or entry.request.url
        parts = [url, entry.request.method]
        parts += [h.name for h in entry.request.headers] + [h.value for h in entry.request.headers]
        if entry.request.content:
            parts.append(entry.request.content)
        if entry.response:
            parts += [h.name for h in entry.response.headers] + [h.value for h in entry.response.headers]
            if entry.response.content:
                parts.append(entry.response.content)
        return apply_match(' '.join(parts), filter_text, 'Contains')

    if field == 'URL':
        return apply_match(entry.original_url or entry.request.url, filter_text, match_type)

    if field == 'Query':
        return any(
            apply_match(f"{k}={v}", filter_text, match_type)
            for k, v in (entry.request.query_params or {}).items()
        )

    if field in ('Hdr', 'Header'):
        headers = list(entry.request.headers)
        if entry.response:
            headers += list(entry.response.headers)
        return any(apply_match(f"{h.name}: {h.value}", filter_text, match_type) for h in headers)

    if field in ('Body', 'Req Body', 'Resp Body'):
        if apply_match(entry.request.content or '', filter_text, match_type):
            return True
        return bool(entry.response and apply_match(entry.response.content or '', filter_text, match_type))

    if field in ('Meth', 'Method'):
        return apply_match(entry.request.method, filter_text, match_type)

    if field in ('Code', 'Status'):
        return bool(entry.response and apply_match(str(entry.response.status_code), filter_text, match_type))

    return True


class TrafficFilter:
    """Compact filter bar rendered inside .filter-bar container."""

    def __init__(self, on_change):
        """
        Args:
            on_change: callable() called whenever any filter param changes.
        """
        self._on_change = on_change
        self.field = 'URL'
        self.match_type = 'Contains'
        self.text = ''

    def render(self):
        """Render the filter bar widgets. Must be called inside a row/container."""
        self._input_ref = ui.input(placeholder='Filter...', value=self.text,
                 on_change=lambda e: self._set_text(e.value)
                 ).props('dense outlined dark clearable').style('flex:1; min-width:60px;')

        ui.select(FILTER_FIELDS, value=self.field,
                  on_change=lambda e: self._set_field(e.value)
                  ).props('dense outlined dark').style('width:80px; min-width:0; flex-shrink:0;')

        ui.select(MATCH_TYPES, value=self.match_type,
                  on_change=lambda e: self._set_match(e.value)
                  ).props('dense outlined dark').style('width:110px; min-width:0; flex-shrink:0;')

    def filter(self, traffic: list) -> list:
        """Return filtered subset of traffic entries."""
        return [e for e in traffic if matches_entry(e, self.text, self.field, self.match_type)]

    # ── private ──────────────────────────────────────────────────────────────

    def _set_field(self, v):
        self.field = v
        self._on_change()

    def _set_match(self, v):
        self.match_type = v
        self._on_change()

    def _set_text(self, v):
        self.text = v
        self._on_change()
